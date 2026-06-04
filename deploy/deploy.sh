#!/usr/bin/env bash
# Universal project deployer for the homelab platform.
# Lives at /srv/_platform/deploy.sh on the server.
#
# Usage:  ./deploy.sh <project_name>
#         ./deploy.sh prooflayer
#         ./deploy.sh hello             # generic Django test app
#
# Project metadata: /srv/<project>/shared/deploy.toml (see deploy.toml.example)

set -euo pipefail
PROJECT="${1:?usage: deploy.sh <project>}"
TS=$(date +%Y%m%d-%H%M%S)
PROJ_ROOT="/srv/${PROJECT}"
SHARED="${PROJ_ROOT}/shared"
RELEASES="${PROJ_ROOT}/releases"
RELEASE="${RELEASES}/${TS}"

log()  { printf "\e[1;36m[deploy:%s]\e[0m %s\n" "$PROJECT" "$*"; }
fail() { printf "\e[1;31m[fail]\e[0m %s\n" "$*" >&2; exit 1; }

[[ -d "$SHARED" ]] || fail "$SHARED missing. First-time deploy needs manual setup."
[[ -f "$SHARED/deploy.toml" ]] || fail "$SHARED/deploy.toml missing"

# Parse deploy.toml (simple key=value, no nested tables)
TYPE=$(grep '^type'             "$SHARED/deploy.toml" | head -1 | cut -d'"' -f2 || echo "")
REPO=$(grep '^repo'             "$SHARED/deploy.toml" | head -1 | cut -d'"' -f2 || echo "")
BRANCH=$(grep '^branch'         "$SHARED/deploy.toml" | head -1 | cut -d'"' -f2 || echo "main")
SETTINGS=$(grep '^settings'     "$SHARED/deploy.toml" | head -1 | cut -d'"' -f2 || echo "")
HEALTHCHECK=$(grep '^healthcheck' "$SHARED/deploy.toml" | head -1 | cut -d'"' -f2 || echo "")

log "type=$TYPE repo=$REPO branch=$BRANCH"

mkdir -p "$RELEASES"

# ===== Clone or fetch =====
log "fetch source -> $RELEASE"
git clone --depth 50 --branch "$BRANCH" "$REPO" "$RELEASE"
COMMIT=$(git -C "$RELEASE" rev-parse --short HEAD)
log "deploying commit $COMMIT"

case "$TYPE" in

    django)
        # -- Python venv (shared, only rebuild if requirements changed) --
        REQ_HASH=$(sha256sum "$RELEASE/requirements.txt" 2>/dev/null | awk '{print $1}')
        STAMP="$SHARED/venv/.req-${REQ_HASH:-none}"
        if [[ ! -f "$STAMP" ]]; then
            log "building venv (requirements changed)"
            rm -rf "$SHARED/venv"
            python3 -m venv "$SHARED/venv"
            "$SHARED/venv/bin/pip" install --upgrade pip wheel
            "$SHARED/venv/bin/pip" install -r "$RELEASE/requirements.txt"
            touch "$STAMP"
        fi

        # Symlink venv + shared dirs into release
        ln -sfn "$SHARED/venv" "$RELEASE/venv"
        ln -sfn "$SHARED/media" "$RELEASE/media"

        # Ensure caddy can read media files written by gunicorn (different uid)
        mkdir -p "$SHARED/media"
        chmod -R o+rX "$SHARED/media" 2>/dev/null || true

        # Source env for management commands
        set -a; . "$SHARED/.env"; set +a

        # -- Migrations + collectstatic --
        log "migrate + collectstatic"
        cd "$RELEASE"
        "$SHARED/venv/bin/python" manage.py migrate --noinput
        "$SHARED/venv/bin/python" manage.py collectstatic --noinput

        # -- systemd unit --
        SOCK="/run/${PROJECT}.sock"
        UNIT="/etc/systemd/system/${PROJECT}.service"
        log "rendering $UNIT"
        sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=${PROJECT} gunicorn
After=network.target

[Service]
User=seb0107
Group=www-data
WorkingDirectory=/srv/${PROJECT}/current
EnvironmentFile=/srv/${PROJECT}/shared/.env
ExecStart=/srv/${PROJECT}/shared/venv/bin/gunicorn \\
    --bind unix:${SOCK} \\
    --workers 3 \\
--worker-class gthread --threads 2 \\
    --timeout 120 \\
    --access-logfile - --error-logfile - \\
    ${SETTINGS%.*}.wsgi:application
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
        sudo systemctl daemon-reload

        # -- Caddy snippet --
        CADDY_SITE="/etc/caddy/sites/${PROJECT}.caddy"
        if [[ ! -f "$CADDY_SITE" ]]; then
            sudo tee "$CADDY_SITE" >/dev/null <<EOF
${PROJECT}.prooflayer.cloud {
    reverse_proxy unix/${SOCK}
    tls internal
}
EOF
            sudo systemctl reload caddy
        fi

        # -- Atomic swap --
        ln -sfn "$RELEASE" "${PROJ_ROOT}/current"
        sudo systemctl enable --now "${PROJECT}.service"
        sudo systemctl restart "${PROJECT}.service"
        ;;

    compose)
        # Symlink env into release
        ln -sfn "$SHARED/.env" "$RELEASE/deploy/.env"
        cd "$RELEASE/deploy"

        log "docker compose build"
        docker compose -f compose.prod.yml --env-file "$SHARED/.env" build

        log "docker compose up (rolling)"
        docker compose -f compose.prod.yml --env-file "$SHARED/.env" up -d --remove-orphans

        # Atomic swap (compose is already pointing at $RELEASE)
        ln -sfn "$RELEASE" "${PROJ_ROOT}/current"

        # Caddy snippet (one-time setup expected, idempotent restart)
        if [[ -f "$RELEASE/deploy/caddy.snippet" ]]; then
            sudo cp "$RELEASE/deploy/caddy.snippet" "/etc/caddy/sites/${PROJECT}.caddy"
            sudo systemctl restart caddy
        fi
        ;;

    *)
        fail "unknown type: $TYPE (expected django|compose)"
        ;;
esac

# ===== Healthcheck =====
if [[ -n "$HEALTHCHECK" ]]; then
    sleep 3
    log "healthcheck: $HEALTHCHECK"
    for i in 1 2 3 4 5; do
        if curl -fsS --max-time 10 "$HEALTHCHECK" >/dev/null; then
            log "healthcheck OK"
            break
        fi
        sleep 3
    done
fi

# ===== Cleanup old releases (keep last 5) =====
log "pruning releases"
ls -1dt "${RELEASES}"/*/ 2>/dev/null | tail -n +6 | xargs -r rm -rf

log "deployed ${PROJECT} @ ${COMMIT} (release ${TS})"
