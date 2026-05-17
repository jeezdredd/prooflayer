#!/usr/bin/env bash
# Run this ONCE on a fresh ubuntu-dev (192.168.8.112) as seb0107.
# Idempotent: re-running is safe; existing pieces are skipped.
#
# Usage:  scp deploy/server-bootstrap.sh seb0107@192.168.8.112:~ && \
#         ssh seb0107@192.168.8.112 'bash server-bootstrap.sh'
#
# Phases 1-4 of plan: base packages, UFW, Tailscale, native Postgres+Redis, Caddy.
# Phase 5 (Cloudflare Tunnel) is interactive - run cf-tunnel-setup.sh after this.

set -euo pipefail

log()  { printf "\e[1;36m==>\e[0m %s\n" "$*"; }
warn() { printf "\e[1;33m[warn]\e[0m %s\n" "$*"; }

require_user() {
    if [[ "$(id -un)" != "seb0107" ]]; then
        echo "Run as seb0107, not $(id -un)" >&2; exit 1
    fi
}
require_user

# ===== Phase 1: bootstrap =====
log "apt update + base packages"
sudo apt update
sudo DEBIAN_FRONTEND=noninteractive apt -y full-upgrade
sudo apt install -y git make curl wget ufw fail2ban htop tmux unzip jq \
                     build-essential ca-certificates gnupg lsb-release \
                     debian-keyring debian-archive-keyring apt-transport-https \
                     python3-pip python3-venv python3-dev

log "UFW firewall"
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
yes | sudo ufw enable || true
sudo systemctl enable --now fail2ban

# ===== Phase 2: Tailscale =====
if ! command -v tailscale >/dev/null; then
    log "installing Tailscale"
    curl -fsSL https://tailscale.com/install.sh | sh
else
    log "Tailscale already installed"
fi
if ! tailscale status >/dev/null 2>&1; then
    warn "Run interactively to finish:  sudo tailscale up --ssh --accept-routes --hostname=ubuntu-dev"
fi

# ===== Phase 3: native Postgres + Redis =====
if ! command -v psql >/dev/null; then
    log "installing Postgres (default version for distro)"
    sudo apt install -y postgresql postgresql-contrib
    sudo systemctl enable --now postgresql
fi
if ! systemctl is-active --quiet redis-server 2>/dev/null && ! command -v redis-server >/dev/null; then
    log "installing Redis"
    sudo apt install -y redis-server
    sudo sed -i 's/^bind .*/bind 127.0.0.1 ::1/' /etc/redis/redis.conf
    sudo systemctl enable --now redis-server
fi
# Create deploy postgres role (idempotent)
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='deploy'" | grep -q 1; then
    DEPLOY_PW=$(openssl rand -base64 24 | tr -d '=+/' | cut -c1-24)
    log "creating Postgres role 'deploy' (password saved to /home/seb0107/.deploy-pgpass)"
    sudo -u postgres psql -c "CREATE ROLE deploy WITH LOGIN PASSWORD '${DEPLOY_PW}';"
    sudo -u postgres psql -c "ALTER ROLE deploy CREATEDB;"
    echo "deploy:${DEPLOY_PW}" > "$HOME/.deploy-pgpass"
    chmod 600 "$HOME/.deploy-pgpass"
fi

# ===== Phase 4: Caddy =====
if ! command -v caddy >/dev/null; then
    log "installing Caddy"
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
    sudo apt update && sudo apt install -y caddy
fi

# Caddyfile skeleton
sudo mkdir -p /etc/caddy/sites /var/log/caddy
if ! grep -q "import sites/" /etc/caddy/Caddyfile 2>/dev/null; then
    log "writing /etc/caddy/Caddyfile"
    sudo tee /etc/caddy/Caddyfile >/dev/null <<'EOF'
{
    email seb0107@prooflayer.cloud
    admin off
    auto_https disable_redirects
}

import sites/*.caddy
EOF
fi
sudo systemctl enable --now caddy

# ===== Docker (needed for ProofLayer compose + Ollama) =====
if ! command -v docker >/dev/null; then
    log "installing Docker"
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker seb0107
    warn "Log out / back in (or 'newgrp docker') to use docker without sudo"
fi

# ROCm tools for AMD GPU passthrough (Phase 8)
if ! command -v rocm-smi >/dev/null; then
    log "installing rocm-smi"
    sudo apt install -y rocm-smi-lib || warn "rocm-smi install failed - continue without GPU passthrough for now"
fi
sudo usermod -aG video,render seb0107 || true

# /srv layout
log "creating /srv layout"
sudo mkdir -p /srv/_platform/{lib,templates} /srv/_backups
sudo chown -R seb0107:seb0107 /srv/_platform /srv/_backups

log "bootstrap complete."
echo ""
echo "Next steps:"
echo "  1) sudo tailscale up --ssh --accept-routes --hostname=ubuntu-dev"
echo "  2) Set Namecheap nameservers for prooflayer.cloud to Cloudflare's (one-time)"
echo "  3) Run cf-tunnel-setup.sh (interactive Cloudflare login)"
echo "  4) Drop deploy.sh into /srv/_platform/ and add projects"
