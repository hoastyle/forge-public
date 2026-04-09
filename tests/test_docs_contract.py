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

    def test_public_skill_bundles_command_reference(self):
        reference = (
            Path(__file__).resolve().parents[1]
            / ".agents"
            / "skills"
            / "using-forge"
            / "references"
            / "forge-command-recipes.md"
        )
        self.assertTrue(reference.exists())
        self.assertIn("forge receipt get", reference.read_text(encoding="utf-8"))

    def test_skill_mentions_receipts_and_detached_jobs(self):
        text = (
            Path(__file__).resolve().parents[1]
            / ".agents"
            / "skills"
            / "using-forge"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("forge receipt get <selector>", text)
        self.assertIn("forge job get <job_id>", text)
        self.assertIn("trigger semantics remain explicit", text)


if __name__ == "__main__":
    unittest.main()
