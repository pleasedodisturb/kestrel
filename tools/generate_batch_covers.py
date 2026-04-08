#!/usr/bin/env python3
"""Generate cover letter markdown files from batch templates + hooks."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "cv" / "applications" / "_batch-templates"
APPS_DIR = ROOT / "cv" / "applications"

TEMPLATE_MAP = {
    "a": TEMPLATES_DIR / "batch-a-chaos-veteran.md",
    "b": TEMPLATES_DIR / "batch-b-builder-operator.md",
    "c": TEMPLATES_DIR / "batch-c-connector-builder.md",
}


def main():
    hooks_file = TEMPLATES_DIR / "hooks.yaml"
    data = yaml.safe_load(hooks_file.read_text())

    generated = 0
    for pos in data["positions"]:
        slug = pos["slug"]
        role = pos["role"]
        batch = pos["batch"]
        hook = pos["hook"]
        db_id = pos["id"]

        # Read template
        template = TEMPLATE_MAP[batch].read_text()

        # Fill placeholders
        letter = template.replace("[ROLE]", role).replace("[HOOK]", hook)

        # Create application directory
        app_dir = APPS_DIR / slug
        app_dir.mkdir(exist_ok=True)

        # Write cover letter
        out_path = app_dir / "cover-letter.md"
        out_path.write_text(letter)
        generated += 1
        print(f"  [{batch.upper()}] {slug}/cover-letter.md (DB #{db_id})")

    print(f"\nGenerated {generated} cover letters.")


if __name__ == "__main__":
    main()
