import unittest
from pathlib import Path


class PublicDocsContractTests(unittest.TestCase):
    def test_public_readme_advertises_cli_install(self):
        text = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        self.assertIn("install-public-cli.sh", text)
        self.assertIn("forge login", text)

    def test_skill_does_not_assume_private_repo_access(self):
        text = (
            Path(__file__).resolve().parents[1]
            / ".agents"
            / "skills"
            / "using-forge"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("configured Forge service", text)
        self.assertNotIn("working inside the Forge repository", text)


if __name__ == "__main__":
    unittest.main()
