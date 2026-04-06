#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/release/render-homebrew-formula.sh --version <tag> --archive-sha256 <sha> [--archive-url <url>] [--repo <owner/name>] [--output <path>]

Render packaging/homebrew/forge.rb.tmpl with release metadata.
EOF
}

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[\/&|\\]/\\&/g'
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
template_path="${repo_root}/packaging/homebrew/forge.rb.tmpl"
repo="hoastyle/forge"
version=""
archive_sha256=""
archive_url=""
output_path=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      version="${2:-}"
      shift 2
      ;;
    --archive-sha256)
      archive_sha256="${2:-}"
      shift 2
      ;;
    --archive-url)
      archive_url="${2:-}"
      shift 2
      ;;
    --repo)
      repo="${2:-}"
      shift 2
      ;;
    --output)
      output_path="${2:-}"
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

if [[ -z "${version}" || -z "${archive_sha256}" ]]; then
  usage
  exit 1
fi

if [[ -z "${archive_url}" ]]; then
  archive_url="https://github.com/${repo}/archive/refs/tags/${version}.tar.gz"
fi

escaped_version="$(escape_sed_replacement "${version#v}")"
escaped_archive_url="$(escape_sed_replacement "${archive_url}")"
escaped_archive_sha256="$(escape_sed_replacement "${archive_sha256}")"

rendered="$(
  sed \
    -e "s|__VERSION__|${escaped_version}|g" \
    -e "s|__ARCHIVE_URL__|${escaped_archive_url}|g" \
    -e "s|__ARCHIVE_SHA256__|${escaped_archive_sha256}|g" \
    "${template_path}"
)"

if [[ -n "${output_path}" ]]; then
  printf "%s\n" "${rendered}" > "${output_path}"
  echo "Wrote ${output_path}"
  exit 0
fi

printf "%s\n" "${rendered}"
