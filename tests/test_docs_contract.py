import unittest
from pathlib import Path


class PublicDocsContractTests(unittest.TestCase):
    def test_public_contract_lists_only_supported_operator_commands(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "management"
            / "forge-command-contract.md"
        ).read_text(encoding="utf-8")
        public_section = text.split("## Contract Rules", 1)[0]
        self.assertIn("forge promote-ready --confirm-receipt <receipt_ref>", public_section)
        self.assertIn("forge knowledge get <knowledge_ref>", public_section)
        self.assertIn("forge explain insight <receipt_ref>", public_section)
        self.assertIn("forge synthesize-insights --dry-run", public_section)
        self.assertIn("forge synthesize-insights --confirm-receipt <receipt_ref>", public_section)
        self.assertNotIn("forge review-sensitive", public_section)
        self.assertNotIn("forge redact-raw", public_section)

    def test_public_readme_advertises_cli_install(self):
        text = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        self.assertIn("install-public-cli.sh", text)
        self.assertIn("forge login", text)
        self.assertIn("using-forge", text)
        self.assertIn("forge doctor", text)

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
        self.assertIn("forge knowledge get <knowledge_ref>", text)
        self.assertIn("forge explain insight <receipt_ref>", text)
        self.assertIn("trigger semantics remain explicit", text)

    def test_public_skill_does_not_advertise_unsupported_commands(self):
        text = (
            Path(__file__).resolve().parents[1]
            / ".agents"
            / "skills"
            / "using-forge"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("forge synthesize-insights --dry-run", text)
        self.assertIn("forge synthesize-insights --confirm-receipt <receipt_ref>", text)
        for unsupported in (
            "forge review-sensitive",
            "forge redact-raw",
        ):
            self.assertNotIn(unsupported, text)

    def test_public_command_recipes_do_not_advertise_unsupported_commands(self):
        text = (
            Path(__file__).resolve().parents[1]
            / ".agents"
            / "skills"
            / "using-forge"
            / "references"
            / "forge-command-recipes.md"
        ).read_text(encoding="utf-8")
        self.assertIn("forge synthesize-insights --dry-run", text)
        self.assertIn("forge synthesize-insights --confirm-receipt <receipt_ref>", text)
        for unsupported in (
            "forge review-sensitive",
            "forge redact-raw",
        ):
            self.assertNotIn(unsupported, text)

    def test_release_doc_mentions_skill_bundle(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "management"
            / "forge-release-distribution.md"
        ).read_text(encoding="utf-8")
        self.assertIn("skill bundle", text)
        self.assertIn("forge_skill_using-forge_", text)


if __name__ == "__main__":
    unittest.main()
