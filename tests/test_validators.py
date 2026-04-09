import unittest


class CandidateValidatorTests(unittest.TestCase):
    def test_normalize_candidate_derives_evidence_strength_fields(self):
        from automation.pipeline.validators import normalize_candidate

        candidate = normalize_candidate(
            {
                "context": "The gateway reboot was followed by fake DNS answers.",
                "root_cause": "The upstream resolver injected fake-ip ranges.",
                "fix_steps": ["Override resolv.conf to 1.1.1.1"],
                "verification": ["dig github.com returns public IPs"],
            },
            fallback_title="Gateway DNS repair",
            fallback_tags=["network", "dns"],
        )

        self.assertEqual(candidate["observation"], "The gateway reboot was followed by fake DNS answers.")
        self.assertEqual(
            candidate["evidence"],
            [
                "The gateway reboot was followed by fake DNS answers.",
                "The upstream resolver injected fake-ip ranges.",
            ],
        )
        self.assertEqual(candidate["verified_results"], ["dig github.com returns public IPs"])
        self.assertEqual(
            candidate["scope_limits"],
            ["Applies only to the systems, inputs, and environment described in the source material."],
        )
        self.assertIn("captured evidence", candidate["confidence_basis"])
        self.assertIn("recorded verification results", candidate["confidence_basis"])

    def test_deterministic_candidate_issues_require_evidence_strength_fields(self):
        from automation.pipeline.validators import deterministic_candidate_issues

        issues = deterministic_candidate_issues(
            {
                "context": "",
                "root_cause": "",
                "fix_steps": [],
                "verification": [],
                "observation": "",
                "evidence": [],
                "verified_results": [],
                "scope_limits": [],
                "confidence_basis": "",
            }
        )

        self.assertIn("Observation is incomplete.", issues)
        self.assertIn("Evidence is incomplete.", issues)
        self.assertIn("Verified results are incomplete.", issues)
        self.assertIn("Scope limits are incomplete.", issues)
        self.assertIn("Confidence basis is incomplete.", issues)


if __name__ == "__main__":
    unittest.main()
