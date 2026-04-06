import copy
import tempfile
import unittest
from pathlib import Path

from automation.pipeline.controller import (
    DEFAULT_RUNTIME_LOCK,
    apply_patches,
    compile_intent_to_patches,
    load_or_create_patch_schema,
    validate_patch_bundle,
)
from automation.pipeline.models import Patch


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.schema_path = Path(self.tempdir.name) / "automation" / "schemas" / "patch.schema.json"

    def tearDown(self):
        self.tempdir.cleanup()

    def test_load_or_create_patch_schema_bootstraps_default_schema_file(self):
        schema = load_or_create_patch_schema(self.schema_path)

        self.assertTrue(self.schema_path.exists())
        self.assertEqual(schema["version"], 1)
        self.assertIn("/runtime/insight/min_evidence", schema["paths"])

    def test_compile_intent_to_patches_emits_schema_valid_bundle(self):
        schema = load_or_create_patch_schema(self.schema_path)
        patches = compile_intent_to_patches(
            "把 insight 生成改得更保守：evidence 至少 3 篇 knowledge，judge 改用更强模型。"
        )

        bundle = validate_patch_bundle(patches, schema)
        updated = apply_patches(copy.deepcopy(DEFAULT_RUNTIME_LOCK), patches)

        self.assertEqual(bundle["version"], 1)
        self.assertEqual(len(bundle["patches"]), 2)
        self.assertEqual(updated["runtime"]["insight"]["min_evidence"], 3)
        self.assertEqual(updated["runtime"]["insight"]["judge_profile"], "judge_strong")

    def test_default_runtime_lock_uses_gpt_5_4_for_all_builtin_profiles(self):
        models = {name: profile["model"] for name, profile in DEFAULT_RUNTIME_LOCK["profiles"].items()}

        self.assertEqual(
            models,
            {
                "writer_cheap": "openai/gpt-5.4",
                "writer_mid": "openai/gpt-5.4",
                "judge_mid": "openai/gpt-5.4",
                "judge_strong": "openai/gpt-5.4",
            },
        )

    def test_validate_patch_bundle_rejects_invalid_op(self):
        schema = load_or_create_patch_schema(self.schema_path)

        with self.assertRaisesRegex(ValueError, "patch op is not allowed"):
            validate_patch_bundle(
                [
                    Patch(
                        op="remove",
                        path="/runtime/insight/min_evidence",
                        value=3,
                        reason="remove is outside the control plane DSL",
                    )
                ],
                schema,
            )

    def test_validate_patch_bundle_rejects_invalid_path(self):
        schema = load_or_create_patch_schema(self.schema_path)

        with self.assertRaisesRegex(ValueError, "patch path is not allowed"):
            validate_patch_bundle(
                [
                    Patch(
                        op="replace",
                        path="/runtime/knowledge/min_chars",
                        value=100,
                        reason="this path is intentionally outside the allow list",
                    )
                ],
                schema,
            )

    def test_validate_patch_bundle_rejects_invalid_value_type_and_blank_reason(self):
        schema = load_or_create_patch_schema(self.schema_path)

        with self.assertRaisesRegex(ValueError, "patch value type mismatch"):
            validate_patch_bundle(
                [
                    Patch(
                        op="replace",
                        path="/runtime/insight/min_evidence",
                        value="3",
                        reason="must stay an integer",
                    )
                ],
                schema,
            )

        with self.assertRaisesRegex(ValueError, "patch reason must be a non-empty string"):
            validate_patch_bundle(
                [
                    Patch(
                        op="replace",
                        path="/runtime/insight/judge_profile",
                        value="judge_strong",
                        reason="  ",
                    )
                ],
                schema,
            )


if __name__ == "__main__":
    unittest.main()
