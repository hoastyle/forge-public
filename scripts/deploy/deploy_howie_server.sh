#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/deploy/deploy_howie_server.sh [options]

Options:
  --host <ssh-host>          SSH host alias or target. Default: howie_server
  --remote-dir <path>        Remote deploy root. Default: /home/howie/apps/forge
  --public-port <port>       Public host port for compose.deploy.yaml. Default: 18080
  --token <token>            Forge service bearer token. Falls back to env/.env/remote .env.
  --build-local              Build the image locally, then transfer it via docker save/load.
  --proxy <url|host:port>    Optional proxy for remote docker compose pull/build.
  --skip-build               Sync files but skip docker compose up --build.
  --no-verify                Skip remote healthz/doctor verification.
  --help                     Show this message.
EOF
}

log() {
  printf '==> %s\n' "$*" >&2
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

read_env_value() {
  local file="$1"
  local key="$2"

  if [ ! -f "$file" ]; then
    return 0
  fi

  sed -n "s/^${key}=//p" "$file" | tail -n 1
}

normalize_proxy() {
  local value="$1"

  if [ -z "$value" ]; then
    return 0
  fi
  if [[ "$value" == *"://"* ]]; then
    printf '%s' "$value"
    return 0
  fi
  printf 'http://%s' "$value"
}

HOST="howie_server"
REMOTE_DIR="/home/howie/apps/forge"
PUBLIC_PORT=""
SERVICE_TOKEN=""
PROXY=""
BUILD_LOCAL=0
SKIP_BUILD=0
VERIFY=1

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host)
      [ "$#" -ge 2 ] || die "--host requires a value"
      HOST="$2"
      shift 2
      ;;
    --remote-dir)
      [ "$#" -ge 2 ] || die "--remote-dir requires a value"
      REMOTE_DIR="$2"
      shift 2
      ;;
    --public-port)
      [ "$#" -ge 2 ] || die "--public-port requires a value"
      PUBLIC_PORT="$2"
      shift 2
      ;;
    --token)
      [ "$#" -ge 2 ] || die "--token requires a value"
      SERVICE_TOKEN="$2"
      shift 2
      ;;
    --build-local)
      BUILD_LOCAL=1
      shift
      ;;
    --proxy)
      [ "$#" -ge 2 ] || die "--proxy requires a value"
      PROXY="$2"
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    --no-verify)
      VERIFY=0
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

require_command git
require_command rsync
require_command ssh
require_command docker

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOCAL_ENV_PATH="${REPO_ROOT}/.env"
LOCAL_COMPOSE_DEPLOY_PATH="${REPO_ROOT}/compose.deploy.yaml"
LOCAL_CONTENT_ENV_TMP="$(mktemp)"
trap 'rm -f "${LOCAL_CONTENT_ENV_TMP}"' EXIT

[ -f "${LOCAL_ENV_PATH}" ] || die "repo-local .env is required at ${LOCAL_ENV_PATH}"
[ -f "${LOCAL_COMPOSE_DEPLOY_PATH}" ] || die "compose.deploy.yaml is required at ${LOCAL_COMPOSE_DEPLOY_PATH}"

if [ -z "${PUBLIC_PORT}" ]; then
  PUBLIC_PORT="${FORGE_PUBLIC_PORT:-}"
fi
if [ -z "${PUBLIC_PORT}" ]; then
  PUBLIC_PORT="$(read_env_value "${LOCAL_ENV_PATH}" "FORGE_PUBLIC_PORT")"
fi
if [ -z "${PUBLIC_PORT}" ]; then
  PUBLIC_PORT="18080"
fi

if [ -z "${SERVICE_TOKEN}" ]; then
  SERVICE_TOKEN="${FORGE_SERVER_TOKEN:-}"
fi
if [ -z "${SERVICE_TOKEN}" ]; then
  SERVICE_TOKEN="$(read_env_value "${LOCAL_ENV_PATH}" "FORGE_SERVER_TOKEN")"
fi
if [ -z "${SERVICE_TOKEN}" ]; then
  SERVICE_TOKEN="$(
    ssh "${HOST}" "if [ -f '${REMOTE_DIR}/.env' ]; then sed -n 's/^FORGE_SERVER_TOKEN=//p' '${REMOTE_DIR}/.env' | tail -n 1; fi" 2>/dev/null || true
  )"
fi
[ -n "${SERVICE_TOKEN}" ] || die "set FORGE_SERVER_TOKEN in the environment, local .env, remote .env, or pass --token"

PROXY="$(normalize_proxy "${PROXY}")"

grep -Ev '^(FORGE_SERVER_TOKEN|FORGE_PUBLIC_PORT)=' "${LOCAL_ENV_PATH}" > "${LOCAL_CONTENT_ENV_TMP}" || true

log "preparing remote directories on ${HOST}:${REMOTE_DIR}"
ssh "${HOST}" "mkdir -p '${REMOTE_DIR}/data/repo/raw' '${REMOTE_DIR}/data/repo/knowledge' '${REMOTE_DIR}/data/repo/insights' '${REMOTE_DIR}/data/state'"

log "syncing application tree"
rsync -az --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '.pytest_cache/' \
  --exclude '.mypy_cache/' \
  --exclude '.ruff_cache/' \
  --exclude '__pycache__/' \
  --exclude '.env' \
  --exclude 'data/' \
  --exclude 'state/' \
  --exclude 'raw/' \
  --exclude 'knowledge/' \
  --exclude 'insights/' \
  "${REPO_ROOT}/" "${HOST}:${REMOTE_DIR}/"

log "syncing repository content roots"
rsync -az --delete "${REPO_ROOT}/raw/" "${HOST}:${REMOTE_DIR}/data/repo/raw/"
rsync -az --delete "${REPO_ROOT}/knowledge/" "${HOST}:${REMOTE_DIR}/data/repo/knowledge/"
rsync -az --delete "${REPO_ROOT}/insights/" "${HOST}:${REMOTE_DIR}/data/repo/insights/"
rsync -az "${LOCAL_CONTENT_ENV_TMP}" "${HOST}:${REMOTE_DIR}/data/repo/.env"

log "writing remote service env"
{
  ssh "${HOST}" "if [ -f '${REMOTE_DIR}/.env' ]; then grep -Ev '^(FORGE_SERVER_TOKEN|FORGE_PUBLIC_PORT)=' '${REMOTE_DIR}/.env'; fi" 2>/dev/null || true
  printf 'FORGE_SERVER_TOKEN=%s\n' "${SERVICE_TOKEN}"
  printf 'FORGE_PUBLIC_PORT=%s\n' "${PUBLIC_PORT}"
} | ssh "${HOST}" "umask 077 && cat > '${REMOTE_DIR}/.env'"

if [ "${BUILD_LOCAL}" = "1" ] && [ "${SKIP_BUILD}" != "1" ]; then
  log "building image locally"
  docker_build_args=(-t forge-forge:latest)
  if [ -n "${PROXY}" ]; then
    docker_build_args+=(--build-arg "HTTP_PROXY=${PROXY}")
    docker_build_args+=(--build-arg "HTTPS_PROXY=${PROXY}")
    docker_build_args+=(--build-arg "ALL_PROXY=${PROXY}")
  fi
  docker build "${docker_build_args[@]}" "${REPO_ROOT}"

  log "transferring image to remote host"
  docker save forge-forge:latest | ssh "${HOST}" docker load
fi

log "deploying compose stack"
ssh "${HOST}" bash -s -- "${REMOTE_DIR}" "${PROXY:-__FORGE_NO_PROXY__}" "${SKIP_BUILD}" "${VERIFY}" "${PUBLIC_PORT}" "${BUILD_LOCAL}" <<'EOF'
set -euo pipefail

remote_dir="$1"
proxy_url="$2"
skip_build="$3"
verify="$4"
public_port="$5"
build_local="$6"

if [ "${proxy_url}" = "__FORGE_NO_PROXY__" ]; then
  proxy_url=""
fi

cd "${remote_dir}"

if [ -n "${proxy_url}" ]; then
  export HTTP_PROXY="${proxy_url}"
  export HTTPS_PROXY="${proxy_url}"
  export ALL_PROXY="${proxy_url}"
fi

if [ "${skip_build}" = "1" ] || [ "${build_local}" = "1" ]; then
  docker compose -f compose.deploy.yaml up -d --no-build
else
  docker compose -f compose.deploy.yaml up -d --build
fi

docker compose -f compose.deploy.yaml ps

if [ "${verify}" = "1" ]; then
  ready=0
  for attempt in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${public_port}/healthz" >/dev/null; then
      token="$(sed -n 's/^FORGE_SERVER_TOKEN=//p' .env | tail -n 1)"
      if [ -n "${token}" ] && curl -fsS -H "Authorization: Bearer ${token}" "http://127.0.0.1:${public_port}/v1/doctor" >/dev/null; then
        ready=1
        break
      fi
    fi
    sleep 2
  done
  if [ "${ready}" != "1" ]; then
    echo "service failed readiness checks after 30 attempts" >&2
    exit 1
  fi
fi
EOF

log "deployment finished"
printf 'host=%s\n' "${HOST}"
printf 'remote_dir=%s\n' "${REMOTE_DIR}"
printf 'public_url=http://%s:%s\n' "${HOST}" "${PUBLIC_PORT}"
