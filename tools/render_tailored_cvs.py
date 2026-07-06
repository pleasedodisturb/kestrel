#!/usr/bin/env python3
"""Generate tailored CV PDFs from cv.yaml using RenderCV.

Creates a temporary YAML variant per role with a tailored summary,
renders it, and copies the PDF to the application folder.

Persona summaries are NOT hardcoded: they load from config/personal.yaml
(gitignored) under a ``cv_personas:`` key. The embedded floor below is an
OBVIOUSLY-FICTIONAL example set that keeps the rendering mechanism testable in
CI without any real CV content. See config/personal.yaml.example for the schema.
"""

import copy
import logging
import shutil
import subprocess
from pathlib import Path

import yaml

logger = logging.getLogger("render_tailored_cvs")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = PROJECT_ROOT / "cv"
APP_DIR = BASE_DIR / "applications"
RENDERCV = str(PROJECT_ROOT / ".venv" / "bin" / "rendercv")
PERSONAL_CONFIG = PROJECT_ROOT / "config" / "personal.yaml"

# Fictional floor personas — an invented person ("Alex Example") with generic,
# obviously-made-up summaries. They (a) keep the render mechanism runnable and
# testable in CI without real CV content and (b) document the expected shape.
# Replace via config/personal.yaml `cv_personas:` (see personal.yaml.example).
_FLOOR_CV_PERSONAS: dict[str, dict] = {
    "example-platform-engineer": {
        "filename": "example-platform-engineer-cv",
        "summary": (
            "Fictional example — replace via config/personal.yaml `cv_personas:`. "
            "Platform engineer who enjoys turning flaky build pipelines into boring, "
            "reliable ones. Comfortable across infrastructure and application code."
        ),
    },
    "example-product-manager": {
        "filename": "example-product-manager-cv",
        "summary": (
            "Fictional example — replace via config/personal.yaml `cv_personas:`. "
            "Product manager who prototypes before writing specs and prefers small, "
            "shippable increments over big-bang launches."
        ),
    },
    "example-developer-advocate": {
        "filename": "example-developer-advocate-cv",
        "summary": (
            "Fictional example — replace via config/personal.yaml `cv_personas:`. "
            "Developer advocate who writes runnable tutorials and treats documentation "
            "as a first-class product surface."
        ),
    },
}


def _load_cv_personas() -> dict[str, dict]:
    """Load CV personas from config/personal.yaml, falling back to the floor.

    A valid, non-empty ``cv_personas:`` mapping fully REPLACES the fictional
    floor (rendering floor personas alongside real ones would only produce
    junk PDFs). Entries must be mappings with string ``filename`` and
    ``summary`` keys; invalid entries are skipped. Absent config is the normal
    case and stays silent; a present-but-malformed file logs a warning.
    """
    personas = {k: dict(v) for k, v in _FLOOR_CV_PERSONAS.items()}
    if not PERSONAL_CONFIG.exists():
        return personas
    try:
        data = yaml.safe_load(PERSONAL_CONFIG.read_text(encoding="utf-8")) or {}
        cfg = data.get("cv_personas")
        if isinstance(cfg, dict) and cfg:
            parsed: dict[str, dict] = {}
            for slug, spec in cfg.items():
                if (
                    isinstance(spec, dict)
                    and isinstance(spec.get("filename"), str)
                    and spec["filename"].strip()
                    and isinstance(spec.get("summary"), str)
                    and spec["summary"].strip()
                ):
                    parsed[str(slug)] = {
                        "filename": spec["filename"],
                        "summary": spec["summary"],
                    }
            if parsed:
                personas = parsed
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("config/personal.yaml cv_personas unreadable (%s); using floor", exc)
    return personas


ROLES: dict[str, dict] = _load_cv_personas()


def load_base_yaml():
    """Load and parse the base cv.yaml."""
    with open(BASE_DIR / "cv.yaml") as f:
        return yaml.safe_load(f)


def render_variant(role_key: str, role_config: dict, base_data: dict):
    """Create a tailored YAML, render it, copy PDF to application folder."""
    variant = copy.deepcopy(base_data)

    # Replace summary
    variant["cv"]["sections"]["summary"] = [role_config["summary"]]

    # Update output filename
    variant["settings"]["render_command"]["pdf_path"] = f"{role_config['filename']}.pdf"
    variant["settings"]["render_command"]["html_path"] = f"{role_config['filename']}.html"

    # Write temp YAML
    temp_yaml = BASE_DIR / f"cv_tailored_{role_key}.yaml"
    with open(temp_yaml, "w") as f:
        yaml.dump(variant, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Render
    print(f"\n  Rendering {role_key}...")
    result = subprocess.run(
        [RENDERCV, "render", str(temp_yaml)],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  ERROR: {result.stderr}")
        return False

    # Copy PDF to application folder
    src_pdf = BASE_DIR / f"{role_config['filename']}.pdf"
    dst_dir = APP_DIR / role_key
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_pdf = dst_dir / f"{role_config['filename']}.pdf"

    if src_pdf.exists():
        shutil.copy2(src_pdf, dst_pdf)
        print(f"  ✓ {dst_pdf}")
        # Clean up temp files from base dir
        src_pdf.unlink()
        src_html = BASE_DIR / f"{role_config['filename']}.html"
        if src_html.exists():
            src_html.unlink()
    else:
        print(f"  ERROR: PDF not found at {src_pdf}")
        return False

    # Clean up temp YAML
    temp_yaml.unlink()

    return True


def main():
    print("Loading base cv.yaml...")
    base_data = load_base_yaml()

    successes = 0
    for role_key, role_config in ROLES.items():
        if render_variant(role_key, role_config, base_data):
            successes += 1

    print(f"\n{'=' * 50}")
    print(f"Done: {successes}/{len(ROLES)} CVs generated successfully")


if __name__ == "__main__":
    main()
