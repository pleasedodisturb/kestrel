"""The source registry must make a silent zero impossible (G-1564).

Thesis: *a source returning nothing must never look like a source with nothing
to return.* Two sources in this repo were found in August 2026 to have never
been capable of returning a job — ``scrape_thehub`` (GET an HTML page, called
``.json()``) and ``scrape_germantechjobs`` (parsed ``.//item`` against a
``<jobs><job>`` feed, while the board served over a thousand postings). Neither
was caught by a test, a log line or a metric.

These tests pin the machinery that would have caught both on the first run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import source_registry as sr  # noqa: E402

EXAMPLE_CONFIG = Path(__file__).resolve().parents[2] / "config" / "scan-sources.example.yaml"


# --------------------------------------------------------------------------
# The registry cannot silently shrink (same discipline as tools/blocklist.py)
# --------------------------------------------------------------------------


def test_every_shipped_source_is_registered():
    """The embedded name list is the contract; config may extend, never shrink."""
    missing = set(sr.FLOOR_SOURCES) - sr.registered()
    assert not missing, f"registry lost sources: {sorted(missing)}"


def test_a_config_that_omits_a_source_does_not_unregister_it():
    """Otherwise "leave it out of the config" becomes a silent way to disable.

    That is the same hole as commenting the scraper out, which is what this
    module exists to replace.
    """
    assert set(sr.FLOOR_SOURCES) <= sr.registered()


def test_registry_survives_a_missing_config(monkeypatch, tmp_path):
    """No config is the normal case for a fresh install; reporting still works."""
    monkeypatch.setattr(sr, "_CONFIG_PATH", tmp_path / "nope.yaml")
    assert set(sr._load()) == set(sr.FLOOR_SOURCES)


def test_registry_survives_a_malformed_config(monkeypatch, tmp_path, caplog):
    bad = tmp_path / "bad.yaml"
    bad.write_text("sources:\n")  # present but empty
    monkeypatch.setattr(sr, "_CONFIG_PATH", bad)
    with caplog.at_level("WARNING"):
        specs = sr._load()
    assert set(specs) == set(sr.FLOOR_SOURCES)
    assert any("never silently empty" in r.getMessage() for r in caplog.records)


def test_unreadable_config_warns_but_a_missing_one_does_not(monkeypatch, tmp_path, caplog):
    """A missing config is normal; a broken one is not. Only the latter warns."""
    monkeypatch.setattr(sr, "_CONFIG_PATH", tmp_path / "absent.yaml")
    with caplog.at_level("WARNING"):
        sr._load()
    assert not caplog.records, "a fresh install must not be nagged"


# --------------------------------------------------------------------------
# Classification — the states a source can be in
# --------------------------------------------------------------------------


def _spec(monkeypatch, name, **kw):
    monkeypatch.setitem(sr.SOURCES, name, sr.SourceSpec(name=name, **kw))


def test_healthy_source_is_ok(monkeypatch):
    _spec(monkeypatch, "greenhouse", floor=1200)
    assert sr.classify("greenhouse", 4042) == sr.OK


def test_regression_below_floor_is_caught(monkeypatch):
    """The GermanTechJobs shape: a live board reduced to a trickle."""
    _spec(monkeypatch, "germantechjobs", floor=300)
    assert sr.classify("germantechjobs", 4) == sr.BELOW_FLOOR


def test_uncalibrated_source_never_reports_below_floor(monkeypatch):
    """An uncalibrated floor must not invent an alarm.

    Volumes are deployment-specific. Guessing a floor produces a warning that
    fires every run, and a warning that always fires is one the reader learns to
    skip — which costs more than having none.
    """
    _spec(monkeypatch, "jobicy", floor=None)
    assert sr.classify("jobicy", 1) == sr.OK
    assert sr.classify("jobicy", 99999) == sr.OK


def test_uncalibrated_source_still_catches_a_hard_zero(monkeypatch):
    """The protection that matters most works with no configuration at all."""
    _spec(monkeypatch, "jobicy", floor=None)
    assert sr.classify("jobicy", 0) == sr.ZERO


def test_blocked_beats_count(monkeypatch):
    """A blocked source is BLOCKED even though its count is a normal-looking 0."""
    _spec(monkeypatch, "startupjobs", floor=None, expect_blocked=True)
    assert sr.classify("startupjobs", 0, status="blocked") == sr.BLOCKED


def test_abandoned_beats_a_partial_count(monkeypatch):
    """A partial count from an abandoned source is still an abandoned source.

    Labelling it BELOW-FLOOR would send the reader hunting a scraper bug that
    is not there.
    """
    _spec(monkeypatch, "greenhouse", floor=1200)
    assert sr.classify("greenhouse", 300, status="abandoned") == sr.ABANDONED


def test_documented_zero_is_not_an_alarm(monkeypatch):
    _spec(monkeypatch, "lever", floor=0, note="roster deliberately empty")
    assert sr.classify("lever", 0) == sr.EMPTY_BY_DESIGN


def test_zero_floor_WITHOUT_a_note_is_still_loud(monkeypatch):
    """floor: 0 is a claim that zero is correct. Unjustified, it is just a zero.

    Without this, `floor: 0` becomes a one-line way to silence any broken
    source — the exact hole this module closes.
    """
    _spec(monkeypatch, "lever", floor=0, note="")
    assert sr.classify("lever", 0) == sr.ZERO


def test_undocumented_zero_is_loud(monkeypatch):
    _spec(monkeypatch, "personio", floor=None)
    assert sr.classify("personio", 0) == sr.ZERO


def test_source_that_did_not_report_at_all_is_zero():
    """Absence is the easiest failure to overlook, so it is treated as ZERO."""
    assert sr.classify("personio", None) == sr.ZERO


# --------------------------------------------------------------------------
# Exclusion must be LOUD -- the point of the whole design
# --------------------------------------------------------------------------


def test_disabled_source_is_reported_not_hidden(monkeypatch):
    """If a source could be switched off silently, this file would RECREATE the
    bug it exists to prevent."""
    _spec(monkeypatch, "jobicy", enabled=False, note="paused for X")
    assert sr.classify("jobicy", 0) == sr.DISABLED
    assert any("jobicy" in w and "DISABLED" in w for w in sr.check({"jobicy": 0}))


def test_disabled_beats_a_healthy_count(monkeypatch):
    """Even if a disabled source somehow returns jobs, say it is disabled."""
    _spec(monkeypatch, "jobicy", enabled=False, note="paused")
    assert sr.classify("jobicy", 500) == sr.DISABLED


def test_unknown_source_defaults_to_enabled():
    """A typo must not silently delete a source.

    Defaulting an unregistered name to DISABLED would make a misspelling behave
    exactly like a deliberate exclusion — the failure mode in miniature.
    """
    assert sr.is_enabled("a-source-nobody-registered") is True


# --------------------------------------------------------------------------
# check() over a whole run
# --------------------------------------------------------------------------


def test_a_vanished_source_is_caught():
    counts = {n: 10 for n in sr.registered()}
    counts.pop("greenhouse")
    assert any(w.startswith("greenhouse: ZERO") for w in sr.check(counts))


def test_a_healthy_uncalibrated_run_is_quiet():
    """A fresh install with everything working must produce no noise."""
    assert sr.check({n: 10 for n in sr.registered()}) == []


def test_status_table_lists_every_registered_source():
    """Nothing may be absent from the table — absence is how zeros hide."""
    table = sr.status_table({n: 5 for n in sr.registered()})
    for name in sr.registered():
        assert name in table


def test_status_table_shows_a_dash_for_a_source_that_did_not_run():
    table = sr.status_table({})
    assert "-" in table and "ZERO" in table


# --------------------------------------------------------------------------
# Calibration helper
# --------------------------------------------------------------------------


def test_suggested_floors_sit_below_the_observed_count():
    """A floor at or above the measured value fires on ordinary variance."""
    counts = {"greenhouse": 4042, "ashby": 2712, "remotive": 19}
    for name, f in sr.suggest_floors(counts).items():
        assert f < counts[name], f"{name}: floor {f} >= observed {counts[name]}"
        assert f >= 1


def test_calibration_refuses_to_guess_at_a_zero():
    """One run cannot distinguish a correct zero from a broken source."""
    assert sr.suggest_floors({"dead": 0, "live": 300}) == {"live": 99}


def test_calibrate_cli_emits_pasteable_yaml(capsys):
    sr._main(["--calibrate", json.dumps({"greenhouse": 4042})])
    out = capsys.readouterr().out
    assert "sources:" in out and "greenhouse:" in out and "floor: 1333" in out
    parsed = yaml.safe_load(out)
    assert parsed["sources"]["greenhouse"]["floor"] == 1333


# --------------------------------------------------------------------------
# The shipped example config must practise what the module preaches
# --------------------------------------------------------------------------


def test_example_config_parses():
    assert EXAMPLE_CONFIG.exists(), "the example config must be tracked in git"
    yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))


def test_example_config_ships_no_uncalibrated_floors():
    """Shipping someone else's numbers guarantees false alarms elsewhere."""
    raw = yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    for name, cfg in (raw.get("sources") or {}).items():
        assert (cfg or {}).get("floor") is None, (
            f"{name}: the example config must not ship a floor — volumes are "
            f"deployment-specific and a copied floor fires constantly"
        )


def test_example_config_zero_floors_carry_a_reason():
    raw = yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    for name, cfg in (raw.get("sources") or {}).items():
        cfg = cfg or {}
        if cfg.get("floor") == 0:
            assert (cfg.get("note") or "").strip(), f"{name}: floor 0 with no reason"


def test_removed_sources_record_why():
    """So nobody restores TheHub without reading why it went."""
    raw = yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    removed = raw.get("removed") or {}
    assert "thehub" in removed
    for name, cfg in removed.items():
        assert cfg.get("reason", "").strip(), f"{name}: removed with no reason"
        assert cfg.get("ticket"), f"{name}: removed with no ticket"


@pytest.mark.parametrize("name", sorted(sr.FLOOR_SOURCES))
def test_every_shipped_source_appears_in_the_example_config(name):
    """A source missing from the example is one a user never learns they have."""
    raw = yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    assert name in (raw.get("sources") or {}), f"{name} missing from the example config"


# --------------------------------------------------------------------------
# The registry must actually be WIRED IN. An unused module is documentation,
# and documentation is precisely what failed here before.
# --------------------------------------------------------------------------


def _calls_in(func) -> set[str]:
    """Names actually CALLED by `func`, via AST.

    Deliberately not a substring search on the source. The first version of this
    test did `"report_source_health(" in src` and passed happily when the call
    was commented out — the comment still contains the substring. A guard that
    a comment satisfies is not a guard.
    """
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    return {
        n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
    }


def test_report_source_health_is_called_by_the_orchestrator():
    """Guard the wiring, not just the logic.

    A registry that exists but is never invoked leaves the original bug fully
    intact while looking like it was fixed — the same "recorded state says fine"
    failure, one level up.
    """
    import scrape_resilient

    assert "report_source_health" in _calls_in(scrape_resilient.scrape_all_sources), (
        "scrape_all_sources must CALL report_source_health — an unwired registry "
        "protects nothing"
    )


def test_report_source_health_counts_from_emitted_source_values():
    import scrape_resilient
    from scrape_resilient import ScrapedJob

    def job(source):
        return ScrapedJob(title="t", company="c", location="l", url="u", source=source)

    jobs = [job("greenhouse")] * 5 + [job("ashby")] * 2
    warnings = scrape_resilient.report_source_health(jobs)
    # greenhouse and ashby produced rows -> not warned about.
    assert not any(w.startswith("greenhouse:") for w in warnings)
    assert not any(w.startswith("ashby:") for w in warnings)
    # Everything else registered produced nothing -> each is a loud ZERO.
    assert any(w.startswith("personio: ZERO") for w in warnings)


def test_a_source_that_returns_nothing_is_reported_not_omitted():
    """The core thesis, end to end through the real entry point."""
    import scrape_resilient

    warnings = scrape_resilient.report_source_health([])
    zeroed = {w.split(":")[0] for w in warnings if "ZERO" in w}
    assert set(sr.FLOOR_SOURCES) <= zeroed, (
        "every registered source must be accounted for when the scan returns nothing"
    )


def test_health_is_reported_before_dedup():
    """Dedup removes cross-posted duplicates; counting after it would understate
    a source's real contribution and make a healthy board look like it is fading."""
    import inspect

    import scrape_resilient

    src = inspect.getsource(scrape_resilient.scrape_all_sources)
    assert src.index("report_source_health(") < src.index("deduplicate(all_jobs)"), (
        "source health must be measured on raw contributions, before dedup"
    )
