#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/release/build-public-skill.sh <version> [output-dir]

Build the public using-forge skill bundle as a release tarball.
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

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
version_raw="$1"
version="${version_raw#v}"
output_dir="${2:-${repo_root}/dist/public}"
skill_root="${repo_root}/.agents/skills/using-forge"

if [[ ! -d "${skill_root}" ]]; then
  echo "missing skill root: ${skill_root}" >&2
  exit 1
fi

mkdir -p "${output_dir}"

archive_path="${output_dir}/forge_skill_using-forge_${version}.tar.gz"
stage_dir="$(mktemp -d)"
trap 'rm -rf "${stage_dir}"' EXIT

mkdir -p "${stage_dir}/using-forge"
cp -R "${skill_root}/." "${stage_dir}/using-forge/"

tar -C "${stage_dir}" -czf "${archive_path}" using-forge

cat <<EOF
Built Forge public skill bundle:
  version: ${version}
  output: ${archive_path}
EOF
