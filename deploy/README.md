# ProofLayer Deploy (homelab Ubuntu)

Migrating from Railway to a self-hosted Ubuntu server (`ubuntu-dev` @ `192.168.8.112`).

See full plan: `/Users/sevastyan0107/.claude/plans/flickering-stirring-swan.md`.

## Stack on the server

- **Tailscale** - remote SSH from anywhere
- **Caddy** (native) - reverse proxy + per-project Caddyfile snippets at `/etc/caddy/sites/`
- **Cloudflare Tunnel** (`cloudflared`) - public access via `prooflayer.cloud` without port forwarding
- **Native Postgres + Redis** - shared by simple Django apps (ProofLayer uses its own containerised Postgres/Redis to match Railway parity)
- **Docker + docker-compose** - ProofLayer's multi-service stack
- **Ollama on Vulkan** - GPU inference via AMD RX 6700S
- **GPU guard** - systemd unit that keeps the laptop GPU out of thermal shutdown

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

## Maintenance page (Cloudflare Worker)

`cloudflare/maintenance/` is a Worker in front of `prooflayer.cloud`, `classroom.prooflayer.cloud` and
`api.prooflayer.cloud`. It passes every request through untouched. When the origin is unreachable
(tunnel down 1033/530, 502, 504, 52x) it answers 503 with a branded "we are updating the system" page
in Russian or English (by `Accept-Language`) that reloads itself every 60 seconds. API hosts get JSON
`{"code": "maintenance", "detail": "...", "retry_after": 60}` instead of HTML.

```bash
make maintenance-worker   # first deploy; asks for a Cloudflare login once
make maintenance-on       # force the page for planned work
make maintenance-off      # back to automatic mode
```

Workers free plan: 100k requests a day.

## Files in this directory

| File | Purpose |
|------|---------|
| `compose.prod.yml` | Production docker-compose (no exposed ports, gunicorn, nginx frontend, Ollama on Vulkan) |
| `env.prod.example` | Template for `/srv/prooflayer/shared/.env` |
| `caddy.snippet` | `prooflayer.cloud`, `api.prooflayer.cloud`, `flower.prooflayer.cloud` reverse-proxy config |
| `cloudflared.ingress.snippet` | Ingress rules for `/etc/cloudflared/config.yml` |
| `server-bootstrap.sh` | One-time server prep (Phases 1-4 of plan) |
| `cf-tunnel-setup.sh` | Interactive Cloudflare Tunnel install (Phase 5) |
| `deploy.sh` | Universal deployer for `django` and `compose` project types |
| `deploy.toml.example` | Per-project metadata template |
| `gpu-guard/` | Fan curve + Ollama pause when the GPU runs hot (systemd unit) |

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
      redis | minio + minio_init | ollama (Vulkan) | ollama_init | frontend (nginx)
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
ssh ubuntu-dev "docker compose -f /srv/prooflayer/current/deploy/compose.prod.yml logs ollama | grep -i vulkan"  # GPU picked up
ssh ubuntu-dev "curl -s localhost:11434/api/ps"  # size_vram > 0 once a model is loaded (inside the ollama container)
ssh ubuntu-dev "systemctl is-active prooflayer-gpu-guard"
```

## Ollama on the GPU (Vulkan)

Ollama runs on the RX 6700S through Vulkan, not ROCm. Benchmark on 245 held-out images (qwen2.5vl:3b,
lid closed, 2026-10-15):

| Backend | Seconds per image | VRAM | Stability |
|---------|------------------|------|-----------|
| CPU (Ollama 0.24) | 22-34 | - | stable |
| ROCm (`ollama/ollama:rocm`, `HSA_OVERRIDE_GFX_VERSION=10.3.0`) | 4.6 | 2.7 GiB | broke after ~100 calls ("Unexpected empty grammar stack", "token repeat limit reached") |
| Vulkan (`ollama/ollama:0.40.3`, `OLLAMA_VULKAN=1`) | 3.8 | 2.6 GiB | 0 failures |

The image is pinned in `compose.prod.yml`; bump it only after re-running the benchmark. Only `/dev/dri`
is passed in. `GGML_VK_VISIBLE_DEVICES` (`OLLAMA_VK_DEVICES` in `.env`, default `0`) picks the RX 6700S
over the Radeon 680M iGPU.

## GPU guard

The server is a G14 laptop with the lid closed. Under sustained load the RX 6700S reaches 80C in about
100 s even with fans at full speed, and on 2026-10-15 it hit the firmware thermal shutdown (prod down
~2.5 h, needed an ASUS EC reset). `gpu-guard/` prevents a repeat:

- sets `asus_custom_fan_curve` to full speed from 80C,
- pauses `deploy-ollama-1` when the GPU reaches 88C and resumes it at 75C (requests wait, nothing fails
  unless the vision call times out).

Install once (sudo):

```bash
sudo install -m 755 deploy/gpu-guard/gpu-guard.sh /usr/local/bin/prooflayer-gpu-guard
sudo install -m 644 deploy/gpu-guard/prooflayer-gpu-guard.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now prooflayer-gpu-guard
journalctl -t gpu-guard -f
```

Thresholds via `GPU_GUARD_HOT`, `GPU_GUARD_COOL`, `GPU_GUARD_INTERVAL` in the unit's environment.

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
