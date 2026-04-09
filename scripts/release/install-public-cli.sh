#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/release/install-public-cli.sh [--version <tag>] [--install-dir <dir>] [--repo <owner/name>] [--base-url <url>] [--no-skill] [--skill-only] [--skill-home <dir>] [--include-repo-skill-dir <path>]

Install the standalone Forge public CLI and the public `using-forge` skill from GitHub release archives.

Defaults:
  repo:        hoastyle/forge-public
  install-dir: ~/.local/bin
  version:     latest GitHub release tag
  skill-home:  ${XDG_DATA_HOME:-$HOME/.local/share}/forge/skills

Notes:
  - The installer defaults to CLI + skill together.
  - User-level skill targets are auto-discovered and updated when they already exist.
  - repo-local .agents/skills is never modified unless --include-repo-skill-dir is passed explicitly.
EOF
}

download_to() {
  local url="$1"
  local output_path="$2"
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
  local repo="$1"
  local api_url="https://api.github.com/repos/${repo}/releases/latest"
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

dedupe_existing_skill_dirs() {
  declare -A seen=()
  local path=""
  for path in "$@"; do
    if [[ -z "${path}" ]]; then
      continue
    fi
    if [[ ! -d "${path}" ]]; then
      continue
    fi
    if [[ -n "${seen["${path}"]+x}" ]]; then
      continue
    fi
    seen["${path}"]=1
    printf '%s\n' "${path}"
  done
}

install_skill_target() {
  local source_dir="$1"
  local target_dir="$2"
  local target_path="${target_dir}/using-forge"

  mkdir -p "${target_dir}"

  if [[ -L "${target_path}" ]] && [[ "$(readlink "${target_path}")" == "${source_dir}" ]]; then
    printf '  linked (existing): %s\n' "${target_path}"
    return
  fi

  rm -rf "${target_path}"
  if ln -s "${source_dir}" "${target_path}" 2>/dev/null; then
    printf '  linked: %s -> %s\n' "${target_path}" "${source_dir}"
    return
  fi

  mkdir -p "${target_path}"
  cp -R "${source_dir}/." "${target_path}/"
  printf '  copied: %s\n' "${target_path}"
}

repo="${FORGE_RELEASE_REPO:-hoastyle/forge-public}"
base_url="${FORGE_RELEASE_BASE_URL:-}"
install_dir="${FORGE_INSTALL_DIR:-$HOME/.local/bin}"
skill_home="${FORGE_SKILL_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/forge/skills}"
version="${FORGE_VERSION:-}"
install_cli=1
install_skill=1
explicit_skill_dirs=()

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
    --no-skill)
      install_skill=0
      shift
      ;;
    --skill-only)
      install_cli=0
      install_skill=1
      shift
      ;;
    --skill-home)
      skill_home="${2:-}"
      shift 2
      ;;
    --include-repo-skill-dir)
      explicit_skill_dirs+=("${2:-}")
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

if [[ "${install_cli}" -eq 0 && "${install_skill}" -eq 0 ]]; then
  echo "nothing to install: --skill-only and --no-skill cannot disable both outputs" >&2
  exit 1
fi

if [[ -z "${version}" ]]; then
  version="$(latest_release_tag "${repo}")"
fi

if [[ -z "${version}" ]]; then
  echo "could not determine latest Forge release; pass --version explicitly" >&2
  exit 1
fi

if [[ -z "${base_url}" ]]; then
  base_url="https://github.com/${repo}/releases/download"
fi

os_name="$(normalize_os)"
arch_name="$(normalize_arch)"
file_version="${version#v}"

temp_dir="$(mktemp -d)"
trap 'rm -rf "${temp_dir}"' EXIT

if [[ "${install_cli}" -eq 1 ]]; then
  archive_name="forge_${file_version}_${os_name}_${arch_name}.tar.gz"
  archive_url="${base_url}/${version}/${archive_name}"
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
fi

if [[ "${install_skill}" -eq 1 ]]; then
  skill_archive_name="forge_skill_using-forge_${file_version}.tar.gz"
  skill_archive_url="${base_url}/${version}/${skill_archive_name}"
  skill_archive_path="${temp_dir}/${skill_archive_name}"
  skill_stage_root="${temp_dir}/skill-bundle"
  skill_install_root="${skill_home%/}/using-forge"

  download_to "${skill_archive_url}" "${skill_archive_path}"
  mkdir -p "${skill_stage_root}"
  tar -C "${skill_stage_root}" -xzf "${skill_archive_path}"

  if [[ ! -d "${skill_stage_root}/using-forge" ]]; then
    echo "skill bundle missing using-forge/ root: ${skill_archive_url}" >&2
    exit 1
  fi

  mkdir -p "${skill_home}"
  rm -rf "${skill_install_root}"
  cp -R "${skill_stage_root}/using-forge" "${skill_install_root}"

  echo "Installed Forge public skill:"
  echo "  version: ${version}"
  echo "  skill_home: ${skill_install_root}"
  echo "  source: ${skill_archive_url}"

  discovered_skill_dirs=(
    "${CODEX_HOME:-}/skills"
    "${HOME}/.codex/skills"
    "${HOME}/.claude/skills"
    "${HOME}/.continue/skills"
    "${HOME}/.factory/skills"
  )

  while IFS= read -r dir; do
    discovered_skill_dirs+=("${dir}")
  done < <(printf '%s\n' "${explicit_skill_dirs[@]:-}" | sed '/^$/d')

  echo "Skill directory updates:"
  while IFS= read -r target_dir; do
    install_skill_target "${skill_install_root}" "${target_dir}"
  done < <(dedupe_existing_skill_dirs "${discovered_skill_dirs[@]}")
fi
