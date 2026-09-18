import hashlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_modules.core.perception.providers import ProviderUnavailableError
from auto_modules.adapters.perception.rapidocr_models import (
    RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL,
    RapidOcrModelSpec,
    get_rapidocr_model_spec,
    list_rapidocr_model_specs,
    resolve_rapidocr_engine_options,
)
from tools.probes.install_perception_ocr_model import install_rapidocr_model


class _BytesResponse(io.BytesIO):
    """A closeable in-memory HTTP response stand-in for installer tests."""


class RapidOcrModelRegistryTests(unittest.TestCase):
    def test_multilingual_small_is_a_named_traditional_chinese_capable_resource(self):
        spec = get_rapidocr_model_spec(RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL)

        self.assertEqual(RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL, spec.model_id)
        self.assertEqual("PP-OCRv6_rec_small.onnx", spec.file_name)
        self.assertEqual(
            "6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884",
            spec.sha256,
        )
        self.assertIn("Traditional Chinese", spec.description)
        self.assertIn(spec, list_rapidocr_model_specs())

    def test_unknown_model_is_rejected_explicitly(self):
        with self.assertRaisesRegex(ValueError, "unknown RapidOCR model"):
            get_rapidocr_model_spec("rapidocr.not-installed")

    def test_missing_or_corrupt_asset_cannot_become_engine_options(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(ProviderUnavailableError, "install_perception_ocr_model.py"):
                resolve_rapidocr_engine_options(
                    RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL,
                    temporary_directory,
                )

            bad_file = Path(temporary_directory) / "PP-OCRv6_rec_small.onnx"
            bad_file.write_bytes(b"not the expected model")
            with self.assertRaisesRegex(ProviderUnavailableError, "checksum"):
                resolve_rapidocr_engine_options(
                    RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL,
                    temporary_directory,
                )

    def test_resolution_returns_a_fresh_verified_path_and_safe_overrides(self):
        content = b"model bytes for resolver test"
        spec = _fake_spec(content)
        with tempfile.TemporaryDirectory() as temporary_directory:
            model_path = Path(temporary_directory) / spec.file_name
            model_path.write_bytes(content)
            supplied_overrides = {"intra_op_num_threads": 7, "det_limit_side_len": 1280}

            with patch("auto_modules.adapters.perception.rapidocr_models.get_rapidocr_model_spec", return_value=spec):
                options = resolve_rapidocr_engine_options(spec.model_id, temporary_directory, overrides=supplied_overrides)

            supplied_overrides["intra_op_num_threads"] = 99
            self.assertEqual(str(model_path.resolve()), options["rec_model_path"])
            self.assertEqual(7, options["intra_op_num_threads"])
            self.assertEqual(1, options["inter_op_num_threads"])
            self.assertEqual(1280, options["det_limit_side_len"])

            with patch("auto_modules.adapters.perception.rapidocr_models.get_rapidocr_model_spec", return_value=spec):
                with self.assertRaisesRegex(ValueError, "rec_model_path"):
                    resolve_rapidocr_engine_options(
                        spec.model_id,
                        temporary_directory,
                        overrides={"rec_model_path": "another-model.onnx"},
                    )


class RapidOcrModelInstallerTests(unittest.TestCase):
    def test_installer_script_can_run_directly_from_the_project_root(self):
        project_root = Path(__file__).resolve().parents[1]

        completed = subprocess.run(
            [sys.executable, "tools/probes/install_perception_ocr_model.py", "--help"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("Install a checksum-verified RapidOCR perception model", completed.stdout)

    def test_installer_validates_download_before_atomically_replacing_a_bad_existing_asset(self):
        expected_content = b"verified multilingual model bytes"
        spec = _fake_spec(expected_content)

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory)
            final_path = destination / spec.file_name
            final_path.write_bytes(b"old invalid model")

            with patch("tools.probes.install_perception_ocr_model.get_rapidocr_model_spec", return_value=spec):
                installed = install_rapidocr_model(
                    spec.model_id,
                    destination,
                    opener=lambda _url, timeout: _BytesResponse(expected_content),
                )

            self.assertEqual(final_path, installed)
            self.assertEqual(expected_content, final_path.read_bytes())
            self.assertFalse(list(destination.glob("*.part")))

    def test_installer_leaves_an_existing_asset_untouched_when_download_checksum_fails(self):
        expected_content = b"verified multilingual model bytes"
        spec = _fake_spec(expected_content)

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory)
            final_path = destination / spec.file_name
            original_content = b"keep this old file until a verified replacement exists"
            final_path.write_bytes(original_content)

            with patch("tools.probes.install_perception_ocr_model.get_rapidocr_model_spec", return_value=spec):
                with self.assertRaisesRegex(ProviderUnavailableError, "checksum"):
                    install_rapidocr_model(
                        spec.model_id,
                        destination,
                        opener=lambda _url, timeout: _BytesResponse(b"damaged download"),
                    )

            self.assertEqual(original_content, final_path.read_bytes())
            self.assertFalse(list(destination.glob("*.part")))


def _fake_spec(content: bytes) -> RapidOcrModelSpec:
    return RapidOcrModelSpec(
        model_id="rapidocr.test-model",
        display_name="Test model",
        description="Offline installer test model",
        file_name="test-model.onnx",
        download_url="https://example.invalid/test-model.onnx",
        sha256=hashlib.sha256(content).hexdigest(),
    )


if __name__ == "__main__":
    unittest.main()
