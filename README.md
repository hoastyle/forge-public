# Forge

Forge is a public CLI + service runtime for note ingestion, raw review, knowledge promotion, and
insight synthesis.

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/hoastyle/forge-public/main/scripts/release/install-public-cli.sh | bash
forge version
forge login --server https://forge.example.com --token "$FORGE_SERVER_TOKEN"
forge doctor
```

The public installer installs both:

- the `forge` CLI
- the public `using-forge` skill bundle for supported local agent skill directories

## Repository Scope

- This repository is public runtime and distribution code.
- It does not contain production `raw/`, `knowledge/`, or `insights`.
- Private data lives in a separate `forge-data` repository that consumes published images.

## Distribution

Forge is distributed from GitHub Releases and GHCR:

- CLI downloads: `https://github.com/hoastyle/forge-public/releases`
- Skill bundle downloads: `forge_skill_using-forge_<version>.tar.gz` from the same GitHub Releases page
- Runtime image: `ghcr.io/hoastyle/forge-public`
- Canonical user entrypoint: `forge ...`

## Docs

Use the public docs surface that matches your role:

- `docs/management/forge-operator-guide.md`: use the published CLI against a configured Forge service
- `docs/management/self-hosting.md`: run the published runtime image without the private data repo path
- `docs/management/forge-release-distribution.md`: release, GHCR, and install contract
- `.agents/skills/using-forge/SKILL.md`: AI-facing operator contract for tools that only have CLI + service access
