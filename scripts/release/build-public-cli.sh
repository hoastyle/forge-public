#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/release/build-public-cli.sh <version> [output-dir]

Build standalone Forge public CLI archives.

Examples:
  scripts/release/build-public-cli.sh v0.1.0
  FORGE_BUILD_TARGETS="linux/amd64 darwin/arm64" scripts/release/build-public-cli.sh 0.1.0 dist/public
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "${1:-}" ]]; then
  usage
  exit 1
fi

if ! command -v go >/dev/null 2>&1; then
  echo "go is required" >&2
  exit 1
fi

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

default_target() {
  local detected_os
  local detected_arch

  detected_os="$(go env GOOS 2>/dev/null || true)"
  detected_arch="$(go env GOARCH 2>/dev/null || true)"
  if [[ -z "${detected_os}" ]]; then
    detected_os="$(normalize_os)"
  fi
  if [[ -z "${detected_arch}" ]]; then
    detected_arch="$(normalize_arch)"
  fi
  printf "%s/%s\n" "${detected_os}" "${detected_arch}"
}

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
    return
  fi
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
    return
  fi
  if command -v openssl >/dev/null 2>&1; then
    openssl dgst -sha256 "$1" | awk '{print $NF}'
    return
  fi
  echo "sha256 tool not found" >&2
  exit 1
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
version_raw="$1"
output_dir="${2:-${repo_root}/dist/public}"
version="${version_raw#v}"
commit="$(git -C "${repo_root}" rev-parse --short HEAD)"
build_date="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
targets="${FORGE_BUILD_TARGETS:-$(default_target)}"

mkdir -p "${output_dir}"
checksums_path="${output_dir}/checksums.txt"
: > "${checksums_path}"

for target in ${targets}; do
  goos="${target%/*}"
  goarch="${target#*/}"
  package_name="forge_${version}_${goos}_${goarch}"
  stage_dir="$(mktemp -d)"
  archive_path="${output_dir}/${package_name}.tar.gz"

  if ! (
    cd "${repo_root}"
    GOOS="${goos}" GOARCH="${goarch}" CGO_ENABLED=0 \
      go build \
        -trimpath \
        -ldflags="-s -w -X main.version=${version} -X main.commit=${commit} -X main.buildDate=${build_date}" \
        -o "${stage_dir}/forge" \
        ./cmd/forge
  ); then
    rm -rf "${stage_dir}"
    cat <<EOF >&2
failed to build target ${target}

By default this script builds only the current host target. For multi-target release matrices, set
FORGE_BUILD_TARGETS explicitly and run on builders whose Go toolchain supports those targets.
EOF
    exit 1
  fi

  tar -C "${stage_dir}" -czf "${archive_path}" forge
  checksum="$(sha256_file "${archive_path}")"
  printf "%s  %s\n" "${checksum}" "$(basename "${archive_path}")" >> "${checksums_path}"
  rm -rf "${stage_dir}"
done

cat <<EOF
Built Forge public CLI artifacts:
  version: ${version}
  output: ${output_dir}
  checksums: ${checksums_path}
EOF
