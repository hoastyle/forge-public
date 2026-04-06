#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/release/install-public-cli.sh [--version <tag>] [--install-dir <dir>] [--repo <owner/name>] [--base-url <url>]

Install the standalone Forge public CLI from a GitHub release archive.

Defaults:
  repo:        hoastyle/forge-public
  install-dir: ~/.local/bin
  version:     latest GitHub release tag
EOF
}

download_to() {
  url="$1"
  output_path="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "${url}" -o "${output_path}"
    return
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -qO "${output_path}" "${url}"
    return
  fi
  echo "curl or wget is required" >&2
  exit 1
}

path_contains_dir() {
  case ":${PATH:-}:" in
    *":$1:"*) return 0 ;;
    *) return 1 ;;
  esac
}

latest_release_tag() {
  repo="$1"
  api_url="https://api.github.com/repos/${repo}/releases/latest"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "${api_url}" | sed -n 's/.*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1
    return
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -qO- "${api_url}" | sed -n 's/.*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1
    return
  fi
  echo ""
}

normalize_os() {
  case "$(uname -s)" in
    Linux) echo "linux" ;;
    Darwin) echo "darwin" ;;
    *)
      echo "unsupported operating system: $(uname -s)" >&2
      exit 1
      ;;
  esac
}

normalize_arch() {
  case "$(uname -m)" in
    x86_64|amd64) echo "amd64" ;;
    arm64|aarch64) echo "arm64" ;;
    *)
      echo "unsupported architecture: $(uname -m)" >&2
      exit 1
      ;;
  esac
}

repo="${FORGE_RELEASE_REPO:-hoastyle/forge-public}"
base_url="${FORGE_RELEASE_BASE_URL:-}"
install_dir="${FORGE_INSTALL_DIR:-$HOME/.local/bin}"
version="${FORGE_VERSION:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      version="${2:-}"
      shift 2
      ;;
    --install-dir)
      install_dir="${2:-}"
      shift 2
      ;;
    --repo)
      repo="${2:-}"
      shift 2
      ;;
    --base-url)
      base_url="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${version}" ]]; then
  version="$(latest_release_tag "${repo}")"
fi

if [[ -z "${version}" ]]; then
  echo "could not determine latest Forge release; pass --version explicitly" >&2
  exit 1
fi

os_name="$(normalize_os)"
arch_name="$(normalize_arch)"
file_version="${version#v}"
archive_name="forge_${file_version}_${os_name}_${arch_name}.tar.gz"

if [[ -z "${base_url}" ]]; then
  base_url="https://github.com/${repo}/releases/download"
fi

archive_url="${base_url}/${version}/${archive_name}"
temp_dir="$(mktemp -d)"
trap 'rm -rf "${temp_dir}"' EXIT
archive_path="${temp_dir}/${archive_name}"

download_to "${archive_url}" "${archive_path}"
tar -C "${temp_dir}" -xzf "${archive_path}"

mkdir -p "${install_dir}"
install -m 0755 "${temp_dir}/forge" "${install_dir}/forge"

cat <<EOF
Installed Forge public CLI:
  version: ${version}
  binary: ${install_dir}/forge
  source: ${archive_url}
EOF

if path_contains_dir "${install_dir}"; then
  cat <<EOF
Next step:
  forge version
EOF
else
  cat <<EOF
PATH update required for this shell:
  export PATH="${install_dir}:\$PATH"

Then verify:
  ${install_dir}/forge version
EOF
fi
