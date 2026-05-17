#!/usr/bin/env bash
# Cloudflare Tunnel setup - run AFTER server-bootstrap.sh AND after
# Namecheap nameservers point to Cloudflare for prooflayer.cloud.
#
# Usage:  bash cf-tunnel-setup.sh
#
# Interactive: opens browser link for `cloudflared tunnel login` once.

set -euo pipefail

log()  { printf "\e[1;36m==>\e[0m %s\n" "$*"; }
warn() { printf "\e[1;33m[warn]\e[0m %s\n" "$*"; }

DOMAIN="prooflayer.cloud"
TUNNEL_NAME="ubuntu-dev"

# Install cloudflared if missing
if ! command -v cloudflared >/dev/null; then
    log "installing cloudflared"
    ARCH=$(dpkg --print-architecture)
    URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}.deb"
    curl -fsSL -o /tmp/cloudflared.deb "$URL"
    sudo dpkg -i /tmp/cloudflared.deb
fi

# Login (one-time interactive). Skips if cert.pem already present.
if [[ ! -f "$HOME/.cloudflared/cert.pem" ]] && [[ ! -f "/etc/cloudflared/cert.pem" ]]; then
    log "opening browser link for Cloudflare auth (paste URL into your local browser)"
    cloudflared tunnel login
fi

# Create tunnel if missing
if ! cloudflared tunnel list 2>/dev/null | grep -q "$TUNNEL_NAME"; then
    log "creating tunnel '$TUNNEL_NAME'"
    cloudflared tunnel create "$TUNNEL_NAME"
fi

TUNNEL_UUID=$(cloudflared tunnel list -o json | jq -r ".[] | select(.name==\"$TUNNEL_NAME\") | .id")
if [[ -z "$TUNNEL_UUID" || "$TUNNEL_UUID" == "null" ]]; then
    echo "Could not determine tunnel UUID. Run 'cloudflared tunnel list' to debug." >&2
    exit 1
fi
log "tunnel UUID: $TUNNEL_UUID"

# Copy credentials to /etc/cloudflared
sudo mkdir -p /etc/cloudflared
sudo cp "$HOME/.cloudflared/cert.pem" /etc/cloudflared/
sudo cp "$HOME/.cloudflared/${TUNNEL_UUID}.json" /etc/cloudflared/

# Write config.yml
log "writing /etc/cloudflared/config.yml"
sudo tee /etc/cloudflared/config.yml >/dev/null <<EOF
tunnel: ${TUNNEL_UUID}
credentials-file: /etc/cloudflared/${TUNNEL_UUID}.json

ingress:
  - hostname: ${DOMAIN}
    service: http://localhost:80
  - hostname: api.${DOMAIN}
    service: http://localhost:80
  - hostname: flower.${DOMAIN}
    service: http://localhost:80
  - hostname: "*.${DOMAIN}"
    service: http://localhost:80
  - service: http_status:404
EOF

# Route DNS to tunnel
log "routing DNS"
cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN" || warn "DNS already routed"
cloudflared tunnel route dns "$TUNNEL_NAME" "*.${DOMAIN}" || warn "wildcard DNS already routed"

# systemd service
if ! systemctl list-unit-files | grep -q cloudflared.service; then
    log "installing cloudflared service"
    sudo cloudflared service install
fi
sudo systemctl enable --now cloudflared
sudo systemctl restart cloudflared

log "Cloudflare Tunnel up. Verify: curl -I https://${DOMAIN}"
echo ""
echo "Tunnel status:"
sudo systemctl status cloudflared --no-pager | head -12
