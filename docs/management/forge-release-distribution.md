# Forge Release Distribution

## Release Contract

- Public repository: `github.com/hoastyle/forge-public`
- Runtime registry: `ghcr.io/hoastyle/forge-public`
- Release source of truth: Git tags and GitHub Releases in `hoastyle/forge-public`
- Public users install the standalone CLI plus the public `using-forge` skill bundle, then connect to a Forge service; they do not clone the data repo
- Operator usage lives in `docs/management/forge-operator-guide.md`
- Self-hosted runtime usage lives in `docs/management/self-hosting.md`

## Release Assets

Each public GitHub Release should contain:

- host-specific CLI archives such as `forge_<version>_<os>_<arch>.tar.gz`
- a combined `checksums.txt`
- the public skill bundle `forge_skill_using-forge_<version>.tar.gz`

## Maintainer Release Flow

1. Push a semver tag such as `v0.2.0`.
2. Let GitHub Actions build CLI archives for the release matrix.
3. Let GitHub Actions build the public skill bundle `forge_skill_using-forge_<version>.tar.gz`.
4. Let GitHub Actions push `ghcr.io/hoastyle/forge-public:v0.2.0`.
5. Verify the GitHub Release page contains CLI archives, the skill bundle, and checksums.
6. Update the public `using-forge` skill in the same change set if the operator contract moved.
