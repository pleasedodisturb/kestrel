#!/usr/bin/env python3
"""Generate applications-to-submit-batch.yaml from hooks.yaml + DB URLs."""

import os
import sqlite3
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
HOOKS = yaml.safe_load(
    (ROOT / "cv" / "applications" / "_batch-templates" / "hooks.yaml").read_text()
)

_cv_filename = os.getenv("CV_FILENAME", "cv.pdf")
CV_MAP = {
    "a": f"cv/{_cv_filename}",
    "b": f"cv/{_cv_filename}",
    "c": f"cv/{_cv_filename}",
}

conn = sqlite3.connect(ROOT / "data" / "career_os.db")
cur = conn.cursor()

apps = []
for p in HOOKS["positions"]:
    cur.execute("SELECT url FROM applications WHERE id = ?", (p["id"],))
    row = cur.fetchone()
    url = row[0] if row else ""

    apps.append(
        {
            "company": p["slug"].split("-")[0].title(),
            "role": p["role"],
            "url": url,
            "cv": CV_MAP[p["batch"]],
            "cover_letter": f"cv/applications/{p['slug']}/cover-letter.pdf",
            "status": "pending",
            "score": None,
            "db_id": p["id"],
            "batch": p["batch"].upper(),
        }
    )

conn.close()


def _load_personal_config():
    """Load personal details from config/personal.yaml."""
    config_path = ROOT / "config" / "personal.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Personal config not found at {config_path}. "
            "Copy config/personal.yaml.example to config/personal.yaml and fill in your details."
        )
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    return {
        "first_name": cfg["name"]["first"],
        "last_name": cfg["name"]["last"],
        "email": cfg["contact"]["email"],
        "phone": cfg["contact"]["phone"],
        "linkedin": cfg["contact"]["linkedin"],
        "github": cfg["contact"]["github"],
        "location": cfg["location"],
        "current_company": cfg.get("current_company", ""),
    }


output = {
    "personal": _load_personal_config(),
    "applications": apps,
}

out_path = ROOT / "batch-apply-2026-03-27.yaml"
out_path.write_text(
    yaml.dump(output, default_flow_style=False, allow_unicode=True, sort_keys=False)
)
print(f"Written {len(apps)} applications to {out_path}")
