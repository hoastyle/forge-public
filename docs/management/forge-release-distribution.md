# Forge Release Distribution

## Release Contract

- Public repository: `github.com/hoastyle/forge`
- Runtime registry: `ghcr.io/hoastyle/forge`
- Release source of truth: Git tags and GitHub Releases in `hoastyle/forge`
- Public users install the standalone CLI and connect to a Forge service; they do not clone the data repo
- Operator usage lives in `docs/management/forge-operator-guide.md`
- Self-hosted runtime usage lives in `docs/management/self-hosting.md`

## Maintainer Release Flow

1. Push a semver tag such as `v0.2.0`.
2. Let GitHub Actions build CLI archives for the release matrix.
3. Let GitHub Actions push `ghcr.io/hoastyle/forge:v0.2.0`.
4. Verify the GitHub Release page contains archives and checksums.
5. Update the public `using-forge` skill in the same change set if the operator contract moved.
