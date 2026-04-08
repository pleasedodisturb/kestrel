"""Tests for tools/render_tailored_cvs.py."""

import copy
from unittest.mock import MagicMock, mock_open, patch

import pytest
import yaml
from render_tailored_cvs import ROLES, load_base_yaml, render_variant

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_data():
    """Minimal base CV data structure matching cv.yaml layout."""
    return {
        "cv": {
            "name": "Test User",
            "sections": {
                "summary": ["Original summary that should be replaced."],
                "experience": [],
            },
        },
        "settings": {
            "render_command": {
                "pdf_path": "original.pdf",
                "html_path": "original.html",
            },
        },
    }


# ---------------------------------------------------------------------------
# ROLES dict structure
# ---------------------------------------------------------------------------


class TestRolesDict:
    def test_roles_has_entries(self):
        assert len(ROLES) == 14

    def test_all_entries_have_required_keys(self):
        for key, cfg in ROLES.items():
            assert "filename" in cfg, f"{key} missing 'filename'"
            assert "summary" in cfg, f"{key} missing 'summary'"

    def test_filenames_are_unique(self):
        filenames = [cfg["filename"] for cfg in ROLES.values()]
        assert len(filenames) == len(set(filenames)), "Duplicate filenames found"

    def test_summaries_are_non_empty(self):
        for key, cfg in ROLES.items():
            assert len(cfg["summary"].strip()) > 0, f"{key} has empty summary"

    def test_filenames_are_non_empty_strings(self):
        for key, cfg in ROLES.items():
            assert isinstance(cfg["filename"], str) and cfg["filename"].strip(), (
                f"{key} has invalid filename"
            )

    def test_role_keys_are_kebab_case(self):
        for key in ROLES:
            assert " " not in key, f"Role key '{key}' contains spaces"
            assert key == key.lower(), f"Role key '{key}' is not lowercase"


# ---------------------------------------------------------------------------
# load_base_yaml
# ---------------------------------------------------------------------------


class TestLoadBaseYaml:
    @patch("builtins.open", mock_open(read_data="cv:\n  name: Test\n"))
    def test_returns_parsed_yaml(self):
        result = load_base_yaml()
        assert result == {"cv": {"name": "Test"}}

    @patch("builtins.open", side_effect=FileNotFoundError("cv.yaml not found"))
    def test_raises_on_missing_file(self, mock_file):
        with pytest.raises(FileNotFoundError):
            load_base_yaml()


# ---------------------------------------------------------------------------
# render_variant
# ---------------------------------------------------------------------------


class TestRenderVariant:
    """Test render_variant with mocked subprocess and filesystem."""

    ROLE_KEY = "test-role"
    ROLE_CONFIG = {"filename": "user-test-cv", "summary": "Tailored summary."}

    def _run_render(self, tmp_path, base_data, returncode=0, pdf_exists=True):
        """Helper: run render_variant with controlled mocks."""
        import render_tailored_cvs as mod

        orig_base = mod.BASE_DIR
        orig_app = mod.APP_DIR

        mod.BASE_DIR = tmp_path
        mod.APP_DIR = tmp_path / "applications"
        mod.APP_DIR.mkdir(exist_ok=True)

        fake_result = MagicMock()
        fake_result.returncode = returncode
        fake_result.stderr = "render failed" if returncode != 0 else ""

        try:
            with patch("render_tailored_cvs.subprocess.run", return_value=fake_result) as mock_run:
                # If render succeeds and pdf should exist, create the PDF
                if returncode == 0 and pdf_exists:
                    pdf_path = tmp_path / f"{self.ROLE_CONFIG['filename']}.pdf"
                    pdf_path.write_bytes(b"%PDF-fake")

                result = render_variant(self.ROLE_KEY, self.ROLE_CONFIG, base_data)
                return result, mock_run
        finally:
            mod.BASE_DIR = orig_base
            mod.APP_DIR = orig_app

    def test_creates_temp_yaml_with_tailored_summary(self, tmp_path, base_data):
        """Verify the temp YAML contains the replaced summary."""
        import render_tailored_cvs as mod

        orig_base = mod.BASE_DIR
        mod.BASE_DIR = tmp_path
        mod.APP_DIR = tmp_path / "applications"
        mod.APP_DIR.mkdir()

        written_yaml = {}

        def capture_run(*args, **kwargs):
            # Read the temp YAML before it gets cleaned up
            temp_file = tmp_path / f"cv_tailored_{self.ROLE_KEY}.yaml"
            if temp_file.exists():
                with open(temp_file) as f:
                    written_yaml.update(yaml.safe_load(f))
            result = MagicMock()
            result.returncode = 0
            # Create PDF so the rest of the function works
            pdf = tmp_path / f"{self.ROLE_CONFIG['filename']}.pdf"
            pdf.write_bytes(b"%PDF-fake")
            return result

        try:
            with patch("render_tailored_cvs.subprocess.run", side_effect=capture_run):
                render_variant(self.ROLE_KEY, self.ROLE_CONFIG, base_data)

            assert written_yaml["cv"]["sections"]["summary"] == [self.ROLE_CONFIG["summary"]]
        finally:
            mod.BASE_DIR = orig_base

    def test_calls_rendercv_with_correct_args(self, tmp_path, base_data):
        """Verify subprocess.run is called with correct rendercv command."""
        result, mock_run = self._run_render(tmp_path, base_data)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "rendercv" in cmd[0]
        assert cmd[1] == "render"
        assert self.ROLE_KEY in cmd[2]  # temp yaml path contains role key
        assert call_args[1]["cwd"] == str(tmp_path)
        assert call_args[1]["capture_output"] is True
        assert call_args[1]["text"] is True

    def test_copies_pdf_to_application_folder(self, tmp_path, base_data):
        result, _ = self._run_render(tmp_path, base_data)

        assert result is True
        dst = tmp_path / "applications" / self.ROLE_KEY / f"{self.ROLE_CONFIG['filename']}.pdf"
        assert dst.exists()
        assert dst.read_bytes() == b"%PDF-fake"

    def test_cleans_up_temp_yaml(self, tmp_path, base_data):
        self._run_render(tmp_path, base_data)

        temp_yaml = tmp_path / f"cv_tailored_{self.ROLE_KEY}.yaml"
        assert not temp_yaml.exists()

    def test_cleans_up_source_pdf(self, tmp_path, base_data):
        self._run_render(tmp_path, base_data)

        src_pdf = tmp_path / f"{self.ROLE_CONFIG['filename']}.pdf"
        assert not src_pdf.exists()

    def test_cleans_up_source_html(self, tmp_path, base_data):
        """If an HTML file was generated alongside the PDF, it should be removed."""
        import render_tailored_cvs as mod

        orig_base = mod.BASE_DIR
        mod.BASE_DIR = tmp_path
        mod.APP_DIR = tmp_path / "applications"
        mod.APP_DIR.mkdir()

        html_path = tmp_path / f"{self.ROLE_CONFIG['filename']}.html"

        def fake_run(*args, **kwargs):
            # Create both PDF and HTML
            (tmp_path / f"{self.ROLE_CONFIG['filename']}.pdf").write_bytes(b"%PDF")
            html_path.write_text("<html></html>")
            r = MagicMock()
            r.returncode = 0
            return r

        try:
            with patch("render_tailored_cvs.subprocess.run", side_effect=fake_run):
                render_variant(self.ROLE_KEY, self.ROLE_CONFIG, base_data)
            assert not html_path.exists()
        finally:
            mod.BASE_DIR = orig_base

    def test_returns_false_on_render_failure(self, tmp_path, base_data):
        result, _ = self._run_render(tmp_path, base_data, returncode=1)
        assert result is False

    def test_returns_false_when_pdf_not_found(self, tmp_path, base_data):
        result, _ = self._run_render(tmp_path, base_data, returncode=0, pdf_exists=False)
        assert result is False

    def test_does_not_mutate_base_data(self, tmp_path, base_data):
        original = copy.deepcopy(base_data)
        self._run_render(tmp_path, base_data)
        assert base_data == original

    def test_variant_output_paths_use_role_filename(self, tmp_path, base_data):
        """The variant YAML should set pdf_path and html_path from role config."""
        import render_tailored_cvs as mod

        orig_base = mod.BASE_DIR
        mod.BASE_DIR = tmp_path
        mod.APP_DIR = tmp_path / "applications"
        mod.APP_DIR.mkdir()

        written_yaml = {}

        def capture_run(*args, **kwargs):
            temp_file = tmp_path / f"cv_tailored_{self.ROLE_KEY}.yaml"
            if temp_file.exists():
                with open(temp_file) as f:
                    written_yaml.update(yaml.safe_load(f))
            r = MagicMock()
            r.returncode = 0
            (tmp_path / f"{self.ROLE_CONFIG['filename']}.pdf").write_bytes(b"%PDF")
            return r

        try:
            with patch("render_tailored_cvs.subprocess.run", side_effect=capture_run):
                render_variant(self.ROLE_KEY, self.ROLE_CONFIG, base_data)

            settings = written_yaml["settings"]["render_command"]
            assert settings["pdf_path"] == f"{self.ROLE_CONFIG['filename']}.pdf"
            assert settings["html_path"] == f"{self.ROLE_CONFIG['filename']}.html"
        finally:
            mod.BASE_DIR = orig_base

    def test_creates_destination_directory(self, tmp_path, base_data):
        """Application subfolder is created if it does not exist."""
        result, _ = self._run_render(tmp_path, base_data)
        dst_dir = tmp_path / "applications" / self.ROLE_KEY
        assert dst_dir.is_dir()
