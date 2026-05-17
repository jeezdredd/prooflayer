# ProofLayer Deploy (homelab Ubuntu)

Migrating from Railway to a self-hosted Ubuntu server (`ubuntu-dev` @ `192.168.8.112`).

See full plan: `/Users/sevastyan0107/.claude/plans/flickering-stirring-swan.md`.

## Stack on the server

- **Tailscale** - remote SSH from anywhere
- **Caddy** (native) - reverse proxy + per-project Caddyfile snippets at `/etc/caddy/sites/`
- **Cloudflare Tunnel** (`cloudflared`) - public access via `prooflayer.cloud` without port forwarding
- **Native Postgres + Redis** - shared by simple Django apps (ProofLayer uses its own containerised Postgres/Redis to match Railway parity)
- **Docker + docker-compose** - ProofLayer's multi-service stack
- **Ollama on ROCm** - GPU inference via AMD RX 6700S

## First-time server bootstrap

```bash
# 1. From your laptop:
scp deploy/server-bootstrap.sh deploy/cf-tunnel-setup.sh deploy/deploy.sh \
    seb0107@192.168.8.112:~

# 2. On the server (Phases 1-4 from plan):
ssh seb0107@192.168.8.112
bash ~/server-bootstrap.sh
# follow on-screen "Next steps" hints

# 3. Set Namecheap nameservers for prooflayer.cloud -> Cloudflare
#    (Cloudflare dashboard will show the two NS hostnames after you add the domain)
#    Wait for nameserver propagation (Cloudflare dashboard turns "Active")

# 4. Run Cloudflare Tunnel setup (Phase 5):
bash ~/cf-tunnel-setup.sh
```

## Deploying ProofLayer for the first time

```bash
# On the server, as seb0107:
sudo mkdir -p /srv/prooflayer/{shared,releases}
sudo chown -R seb0107:seb0107 /srv/prooflayer

# Copy env template (you fill in secrets)
scp deploy/env.prod.example seb0107@ubuntu-dev:/srv/prooflayer/shared/.env
ssh ubuntu-dev "chmod 600 /srv/prooflayer/shared/.env && vim /srv/prooflayer/shared/.env"

# Copy deploy.toml
cat > /tmp/deploy.toml <<EOF
type        = "compose"
repo        = "https://github.com/jeezdredd/prooflayer.git"
branch      = "main"
settings    = ""
healthcheck = "https://api.prooflayer.cloud/api/v1/auth/health/"
EOF
scp /tmp/deploy.toml seb0107@ubuntu-dev:/srv/prooflayer/shared/deploy.toml

# Install platform deploy.sh
ssh ubuntu-dev "sudo install -o seb0107 -m 0755 ~/deploy.sh /srv/_platform/deploy.sh"

# Generate Caddy basicauth hash for Flower
ssh ubuntu-dev "caddy hash-password"   # paste output into deploy/caddy.snippet

# First deploy
ssh ubuntu-dev "/srv/_platform/deploy.sh prooflayer"
```

## Subsequent deploys (from laptop)

```bash
# Top-level Makefile shortcut (see /Makefile):
make deploy-server
```

## Files in this directory

| File | Purpose |
|------|---------|
| `compose.prod.yml` | Production docker-compose (no exposed ports, gunicorn, nginx frontend, Ollama ROCm) |
| `env.prod.example` | Template for `/srv/prooflayer/shared/.env` |
| `caddy.snippet` | `prooflayer.cloud`, `api.prooflayer.cloud`, `flower.prooflayer.cloud` reverse-proxy config |
| `cloudflared.ingress.snippet` | Ingress rules for `/etc/cloudflared/config.yml` |
| `server-bootstrap.sh` | One-time server prep (Phases 1-4 of plan) |
| `cf-tunnel-setup.sh` | Interactive Cloudflare Tunnel install (Phase 5) |
| `deploy.sh` | Universal deployer for `django` and `compose` project types |
| `deploy.toml.example` | Per-project metadata template |

## Architecture diagram

```
                Internet
                    |
            Cloudflare Edge (TLS termination)
                    |
              Cloudflare Tunnel (cloudflared, outbound)
                    |
        ubuntu-dev :80 (Caddy host-routes)
            |        |               |
            |        |               +-- flower.prooflayer.cloud  -> 127.0.0.1:5555 (basicauth)
            |        +-- api.prooflayer.cloud  -> 127.0.0.1:8000 (gunicorn in compose)
            +-- prooflayer.cloud  -> 127.0.0.1:8080 (nginx serving Vite dist)

      docker compose -f compose.prod.yml:
      backend (gunicorn) | celery_worker | flower | db (Postgres 16)
      redis | minio + minio_init | ollama:rocm | ollama_init | frontend (nginx)
```

## Verification

After deploy:

```bash
curl -I https://prooflayer.cloud                 # 200 OK (Vite SPA)
curl -I https://api.prooflayer.cloud/api/v1/auth/health/   # 200 OK
curl -I https://flower.prooflayer.cloud          # 401 (basicauth gate)

# Server checks (via Tailscale or LAN ssh):
ssh ubuntu-dev "systemctl is-active caddy cloudflared docker tailscaled"
ssh ubuntu-dev "docker compose -f /srv/prooflayer/current/deploy/compose.prod.yml ps"
ssh ubuntu-dev "rocm-smi"                        # GPU visible
ssh ubuntu-dev "docker compose -f /srv/prooflayer/current/deploy/compose.prod.yml exec ollama rocm-smi"  # GPU inside container
```

## Adding a new Django project

```bash
# On server:
sudo mkdir -p /srv/myapp/shared
sudo chown -R seb0107:seb0107 /srv/myapp
cat > /srv/myapp/shared/deploy.toml <<EOF
type        = "django"
repo        = "https://github.com/<you>/<repo>.git"
branch      = "main"
settings    = "config.settings.prod"
healthcheck = "https://myapp.prooflayer.cloud/healthz"
EOF
vim /srv/myapp/shared/.env   # set SECRET_KEY, DATABASE_URL, etc.
chmod 600 /srv/myapp/shared/.env

# Create Postgres DB for the app:
sudo -u postgres createdb -O deploy myapp

/srv/_platform/deploy.sh myapp
```

Cloudflared wildcard `*.prooflayer.cloud` covers the new subdomain automatically.
Caddy snippet is auto-generated by deploy.sh.
