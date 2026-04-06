# Forge

Forge is a public CLI + service runtime for note ingestion, raw review, knowledge promotion, and
insight synthesis.

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/hoastyle/forge/main/scripts/release/install-public-cli.sh | bash
forge version
forge login --server https://forge.example.com --token "$FORGE_SERVER_TOKEN"
forge doctor
```

## Repository Scope

- This repository is public runtime and distribution code.
- It does not contain production `raw/`, `knowledge/`, or `insights`.
- Private data lives in a separate `forge-data` repository that consumes published images.
