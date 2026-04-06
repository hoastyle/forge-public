import unittest
from pathlib import Path


class PublicRepoBoundaryTests(unittest.TestCase):
    def test_private_layers_are_absent(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("raw", "knowledge", "insights", "reports", "state", "data"):
            self.assertFalse((root / name).exists(), f"{name} must not exist in the public repo")

    def test_public_runtime_artifacts_are_present(self):
        root = Path(__file__).resolve().parents[1]
        required = [
            root / "cmd" / "forge" / "main.go",
            root / "automation" / "pipeline" / "service_api.py",
            root / "Dockerfile",
            root / "compose.yaml",
            root / "scripts" / "release" / "install-public-cli.sh",
            root / "packaging" / "homebrew" / "forge.rb.tmpl",
        ]
        for path in required:
            self.assertTrue(path.exists(), f"{path} should exist in the public repo")


if __name__ == "__main__":
    unittest.main()
