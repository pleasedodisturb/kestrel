"""Tests for tools/kit_builder.py (T2 rapid-fire kit).

Adds tools/ to sys.path so the module imports directly (tools-test convention).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kit_builder as kb


def test_archetype_mapping():
    assert kb.archetype_for("Senior Developer Advocate") == "devrel"
    assert kb.archetype_for("Forward Deployed Engineer") == "solutions-fde"
    assert kb.archetype_for("Founding Product Engineer") == "product-eng"
    assert kb.archetype_for("Senior Technical Program Manager") == "pm"
    assert kb.archetype_for("Mystery Role") == "pm"  # default


def _jobs():
    return [
        {
            "company": "Acme",
            "title": "Product Manager AI",
            "location": "Berlin",
            "url": "https://job-boards.greenhouse.io/acme/jobs/1",
            "tier": "T2",
            "geo_class": "home",
            "fit_score": 7,
            "source": "greenhouse",
        },
        {
            "company": "Globex",
            "title": "Developer Advocate EMEA",
            "location": "Remote, EU",
            "url": "https://job-boards.greenhouse.io/globex/jobs/2",
            "tier": "T2",
            "geo_class": "eligible_remote",
            "fit_score": 6,
            "source": "greenhouse",
        },
    ]


def test_build_kit_structure(tmp_path):
    res = kb.build_kit(_jobs(), tmp_path, batch_date="2026-06-30", tier="T2")
    kit = Path(res["kit_dir"])
    assert res["count"] == 2
    assert (kit / "INDEX.md").exists()
    assert (kit / "apps" / "01-acme" / "01-SUBMIT.txt").exists()
    assert (kit / "apps" / "02-globex" / "02-SUBMIT.txt").exists()
    submit = (kit / "apps" / "02-globex" / "02-SUBMIT.txt").read_text()
    assert "Developer Advocate EMEA" in submit
    assert "cover-devrel" in submit  # archetype mapped
    assert "https://job-boards.greenhouse.io/globex/jobs/2" in submit
    index = (kit / "INDEX.md").read_text()
    assert "Acme" in index and "Globex" in index


def test_build_kit_open_q_annotation(tmp_path):
    jobs = _jobs()
    oq = {
        jobs[0]["url"]: {"checked": True, "has_open_questions": True, "essay_labels": ["Why us?"]},
        jobs[1]["url"]: {"checked": True, "has_open_questions": False, "essay_labels": []},
    }
    res = kb.build_kit(jobs, tmp_path, batch_date="2026-06-30", open_q_results=oq)
    assert res["with_essays"] == 1
    s1 = (Path(res["kit_dir"]) / "apps" / "01-acme" / "01-SUBMIT.txt").read_text()
    assert "Why us?" in s1


def test_build_kit_default_form_cheats_has_no_personal_literal(tmp_path):
    # The default form-cheats string must carry NO personal data (work-auth/salary/
    # pronouns are <configure> placeholders); callers inject their own.
    res = kb.build_kit([_jobs()[0]], tmp_path, batch_date="2026-06-30")
    submit = (Path(res["kit_dir"]) / "apps" / "01-acme" / "01-SUBMIT.txt").read_text()
    assert "<configure>" in submit
    lowered = submit.lower()
    for personal in ("blue card", "he/him", "120-160", "120000"):
        assert personal not in lowered


def test_build_kit_copies_pdfs_when_present(tmp_path):
    cover_dir = tmp_path / "covers"
    cover_dir.mkdir()
    (cover_dir / "_pm.pdf").write_bytes(b"%PDF cover")
    cv = tmp_path / "cv.pdf"
    cv.write_bytes(b"%PDF cv")
    res = kb.build_kit(
        [_jobs()[0]], tmp_path / "out", batch_date="2026-06-30", cover_dir=cover_dir, cv_path=cv
    )
    folder = Path(res["kit_dir"]) / "apps" / "01-acme"
    assert (folder / "01-cover-pm.pdf").exists()
    assert (folder / "01-CV.pdf").exists()
