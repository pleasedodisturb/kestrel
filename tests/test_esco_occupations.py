"""Tests for the ESCO occupations taxonomy cache (G-1351, scoring F5 Phase A).

Covers the model, the loader's parsers and DB insert path, and the bundled
fixture's integrity. The title→occupation *matching* feature is Phase B; these
tests only guarantee the taxonomy layer it will stand on.
"""

import gzip
import importlib.util
import json
import sys
from pathlib import Path

from career_os.models.esco import ESCOOccupation

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "src" / "career_os" / "fixtures" / "esco_occupations_en.json.gz"

# Import the loader script as a module (scripts/ is not a package)
_spec = importlib.util.spec_from_file_location(
    "load_esco_occupations", REPO_ROOT / "scripts" / "load_esco_occupations.py"
)
loader = importlib.util.module_from_spec(_spec)
sys.modules["load_esco_occupations"] = loader
_spec.loader.exec_module(loader)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class TestESCOOccupationModel:
    def test_alt_labels_list_splits_newlines(self):
        occ = ESCOOccupation(
            concept_uri="http://data.europa.eu/esco/occupation/test",
            preferred_label="software developer",
            alt_labels="software engineer\n  coder \n\nprogrammer",
        )
        assert occ.alt_labels_list == ["software engineer", "coder", "programmer"]

    def test_alt_labels_list_empty(self):
        occ = ESCOOccupation(
            concept_uri="http://data.europa.eu/esco/occupation/test2",
            preferred_label="florist",
            alt_labels=None,
        )
        assert occ.alt_labels_list == []


# ---------------------------------------------------------------------------
# Loader parsers
# ---------------------------------------------------------------------------


class TestParsers:
    def test_isco_from_code(self):
        assert loader._isco_from_code("2166.4") == "2166"
        assert loader._isco_from_code("2512") == "2512"
        assert loader._isco_from_code("") == ""

    def test_parse_occupations_csv(self):
        csv_content = (
            "conceptUri,preferredLabel,altLabels,description,code,iscoGroup\n"
            "http://data.europa.eu/esco/occupation/abc,software developer,"
            '"programmer\ncoder",Writes software.,2512.4,2512\n'
            ",missing uri is skipped,,,,\n"
        )
        rows = loader.parse_occupations_csv(csv_content)
        assert len(rows) == 1
        row = rows[0]
        assert row["concept_uri"].endswith("/abc")
        assert row["preferred_label"] == "software developer"
        assert row["alt_labels"] == "programmer\ncoder"
        assert row["occupation_code"] == "2512.4"
        assert row["isco_group"] == "2512"

    def test_parse_csv_derives_isco_from_code_when_column_missing(self):
        csv_content = (
            "conceptUri,preferredLabel,altLabels,description,code,iscoGroup\n"
            "http://data.europa.eu/esco/occupation/x,project manager,,Manages.,1219.1,\n"
        )
        rows = loader.parse_occupations_csv(csv_content)
        assert rows[0]["isco_group"] == "1219"

    def test_api_record_to_row(self):
        rec = {
            "uri": "http://data.europa.eu/esco/occupation/y",
            "title": "data engineer",
            "preferredLabel": {"en": "data engineer"},
            "alternativeLabel": {"en": ["big data engineer", "ETL developer"]},
            "description": {"en": {"literal": "Builds pipelines."}},
            "code": "2511.5",
        }
        row = loader._api_record_to_row(rec)
        assert row["preferred_label"] == "data engineer"
        assert row["alt_labels"] == "big data engineer\nETL developer"
        assert row["description"] == "Builds pipelines."
        assert row["isco_group"] == "2511"


# ---------------------------------------------------------------------------
# DB load
# ---------------------------------------------------------------------------


class TestLoadIntoDb:
    def _rows(self):
        return [
            {
                "concept_uri": "http://data.europa.eu/esco/occupation/a",
                "preferred_label": "software developer",
                "alt_labels": "programmer",
                "description": "d",
                "occupation_code": "2512.4",
                "isco_group": "2512",
            },
            {
                "concept_uri": "http://data.europa.eu/esco/occupation/b",
                "preferred_label": "florist",
                "alt_labels": "",
                "description": "",
                "occupation_code": "5249.2",
                "isco_group": "5249",
            },
            {"concept_uri": "", "preferred_label": "broken row"},
        ]

    def test_load_occupations_into_db_real_function(self, tmp_path):
        """Exercise the ACTUAL production loader end-to-end against a temp DB.

        The first version of this test re-implemented the loader's loop inline
        and asserted on its own copy — the review flagged it as the vacuous-pass
        pattern (the real function could break while tests stayed green). This
        also pins the ``db_url`` plumbing: an earlier implementation set
        DATABASE_URL via env, which is a silent no-op once career_os.config is
        imported (as it always is under pytest) and would have written to the
        app database instead.
        """
        import sqlite3

        db_path = tmp_path / "occ.db"
        db_url = f"sqlite:///{db_path}"

        counts = loader.load_occupations_into_db(self._rows(), db_url=db_url)
        # 2 valid rows insert, the broken row errors
        assert counts == {"inserted": 2, "skipped": 0, "errors": 1}

        # the rows went to THIS database, not the app-configured one
        with sqlite3.connect(db_path) as con:
            labels = {row[0] for row in con.execute("SELECT preferred_label FROM esco_occupations")}
        assert labels == {"software developer", "florist"}

        # idempotency: a second run skips everything it already inserted
        counts2 = loader.load_occupations_into_db(self._rows(), db_url=db_url)
        assert counts2 == {"inserted": 0, "skipped": 2, "errors": 1}


# ---------------------------------------------------------------------------
# Bundled fixture integrity (the Phase A deliverable)
# ---------------------------------------------------------------------------


class TestBundledFixture:
    def test_fixture_exists_and_is_attributed(self):
        assert FIXTURE.is_file(), (
            f"bundled occupations fixture missing: {FIXTURE} — Phase A ships the "
            f"full English occupations pillar (G-1351)."
        )
        with gzip.open(FIXTURE, "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
        # CC BY 4.0 requires attribution + indication of changes — carried in-file
        meta = {k: payload[k] for k in ("source", "license", "language") if k in payload}
        assert "ESCO" in payload.get("source", ""), meta
        assert "CC BY 4.0" in payload.get("license", ""), meta
        assert payload.get("language") == "en"

    def test_fixture_is_the_full_pillar_and_rows_are_sound(self):
        with gzip.open(FIXTURE, "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
        rows = payload["occupations"]
        # the pillar has ~2,942 concepts; a truncated fixture would quietly gut
        # Phase B's title matching, so pin a floor
        assert len(rows) >= 2900, len(rows)
        for row in rows:
            assert row["concept_uri"].startswith("http://data.europa.eu/esco/occupation/")
            assert row["preferred_label"].strip()
            assert "\n" not in row["preferred_label"]
            assert row["occupation_code"]
            assert row["isco_group"] == row["occupation_code"].split(".")[0]

    def test_fixture_parses_through_the_loader(self):
        rows = loader.parse_fixture()
        assert len(rows) >= 2900
        uris = [r["concept_uri"] for r in rows]
        assert len(uris) == len(set(uris)), "duplicate concept URIs in fixture"

    def test_fixture_covers_core_job_families(self):
        """Smoke-check Phase B viability: the families the scorer actually sees
        must have matchable occupation labels in the fixture."""
        with gzip.open(FIXTURE, "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
        haystack = "\n".join(
            (r["preferred_label"] + "\n" + (r.get("alt_labels") or "")).lower()
            for r in payload["occupations"]
        )
        for needle in (
            "software developer",
            "project manager",
            "product manager",
            "data engineer",
            "software tester",
        ):
            assert needle in haystack, f"no occupation label mentions {needle!r}"
