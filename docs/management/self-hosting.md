# Forge Self-Hosting

Run a self-hosted Forge service with the published runtime image.

## Runtime Model

Keep three concerns separate:

- image/app root: code and runtime shipped in `ghcr.io/hoastyle/forge:<tag>`
- content root: `raw/`, `knowledge/`, `insights/`, and optional `.env`
- state root: receipts, snapshots, traces, and jobs

The service reads content from `--repo-root` and operational state from `--state-root`.

## Quick Start

```bash
mkdir -p repo/raw repo/knowledge repo/insights state

docker run --rm -p 8000:8000 \
  -e FORGE_SERVER_TOKEN=change-me \
  -v "$PWD/repo:/var/lib/forge/repo" \
  -v "$PWD/state:/var/lib/forge/state" \
  ghcr.io/hoastyle/forge:v0.2.0
```

Then connect with the public CLI:

```bash
forge login --server http://127.0.0.1:8000 --token change-me
forge doctor
```

## Notes

- Pin a concrete image tag instead of relying on `latest`
- The self-hosted service does not require the private data repo path
- Instance-specific secrets should live outside git
