"""Scan-source registry: every source reported, every run, with a reason.

WHY THIS EXISTS
---------------
A source that returns nothing must never look like a source with nothing to
return. Those two states are indistinguishable in a bare job count, so a broken
scraper contributes zero indefinitely while the run looks healthy.

This is not hypothetical. Two sources in this repo were found in August 2026 to
have *never* been capable of returning a job:

* ``scrape_thehub`` GET an HTML page and called ``.json()`` on it;
* ``scrape_germantechjobs`` parsed ``.//item`` against a feed serving
  ``<jobs><job>`` — the board was serving over a thousand postings the whole
  time.

Neither was caught by a test, a log line, or a metric. Both were found by hand,
months later. This module is the machinery that would have caught them on the
first run.

WHAT IT ADDS
------------
1. an **expected floor** — the count below which a run shouts;
2. an explicit **enabled** flag, so a source can be switched off deliberately
   rather than commented out or quietly left broken.

THE RULE THAT MAKES EXCLUSION SAFE
----------------------------------
A disabled source is reported as ``DISABLED`` — never as absent, never as zero.
If a source could be silently switched off in config, this file would recreate
the exact bug it was written to kill. **Every registered source appears in every
status table**, with one of:

    ok · DISABLED · BLOCKED · ABANDONED · EMPTY-BY-DESIGN · BELOW-FLOOR · ZERO

CALIBRATION, AND WHY ``floor`` IS OPTIONAL
------------------------------------------
Floors are deployment-specific: a board that yields 4,000 postings for one
search yields 12 for another, and a floor copied from someone else's install
fires constantly. A warning that fires every run trains the reader to ignore it,
which is worse than no warning at all.

So ``floor`` has three distinct states, and the difference matters:

* **absent / null — not calibrated.** No BELOW-FLOOR check. A hard ZERO is still
  loud, so the protection that matters most is on from the first run without any
  configuration at all.
* **``floor: 0`` + a ``note``** — a *documented* zero. You are asserting that
  empty is correct here and saying why. Reported as EMPTY-BY-DESIGN, quietly.
* **``floor: N``** — calibrated. Below N shouts.

Run ``python tools/source_registry.py --calibrate <counts.json>`` to turn an
observed run into suggested floors.

Source of truth is ``config/scan-sources.yaml`` (gitignored; copy
``config/scan-sources.example.yaml``). As with ``tools/blocklist.py``, an
embedded fallback means an unreadable YAML can never silently empty the
registry.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger("source_registry")

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "scan-sources.yaml"

# Embedded fallback: the source NAMES this repo ships scrapers for. Deliberately
# names only — no counts. Counts are deployment-specific (see CALIBRATION above),
# so shipping someone else's numbers as defaults would guarantee false alarms.
#
# This doubles as the non-shrink guard: tests assert every name here stays
# registered, so a source cannot be dropped from the registry without a decision.
# These are the values scrapers actually put in ``ScrapedJob.source`` — verified
# against the emitting code, not guessed from function names. That distinction
# matters: registering a name nothing emits creates a permanent ZERO warning,
# and an alarm that always fires is one the reader learns to skip. Two traps
# found while building this:
#
#   * ``scrape_remotely_de`` emits "remotely.de" (a dot), not "remotely_de";
#   * ``scrape_jobspy`` emits ``row["site"]`` — the UNDERLYING board — so a
#     "jobspy" entry would never match. Its boards are listed individually.
FLOOR_SOURCES: tuple[str, ...] = (
    "aijobs",
    "arbeitnow",
    "ashby",
    "germantechjobs",
    "greenhouse",
    "himalayas",
    "jobicy",
    "lever",
    "personio",
    "remoteok",
    "remotely.de",
    "remotive",
    "smartrecruiters",
    "startupjobs",
    "weworkremotely",
    "workable",
)

# JobSpy is a multiplexer: it reports each posting under the board it came from
# (``row["site"]``), so it has no single source name. Which boards run is a
# caller argument, so these are registered only when configured — otherwise a
# user who scrapes Indeed alone would get four permanent ZEROs for boards they
# never asked for.
JOBSPY_BOARDS: tuple[str, ...] = ("indeed", "linkedin", "glassdoor", "google", "zip_recruiter")

# Status vocabulary.
OK = "ok"
DISABLED = "DISABLED"
BLOCKED = "BLOCKED"
BELOW_FLOOR = "BELOW-FLOOR"
ZERO = "ZERO"
# The source blew its wall-clock budget and the run walked away from it. It gets
# its own label for the same reason BLOCKED does: an abandoned source reported as
# a plain ZERO looks like a source that had nothing to give. Ranked ahead of every
# count-based label — a partial count from an abandoned source is still abandoned,
# and BELOW-FLOOR would send the reader hunting a scraper bug that is not there.
ABANDONED = "ABANDONED"
# A documented zero: floor 0 WITH a recorded reason. Distinct from ZERO, which
# means "nothing came back and nobody knows why" — the state this module exists
# to make impossible to overlook.
EMPTY_BY_DESIGN = "EMPTY-BY-DESIGN"


@dataclass(frozen=True)
class SourceSpec:
    name: str
    enabled: bool = True
    # None means "not calibrated" — no BELOW-FLOOR check. NOT the same as 0.
    floor: int | None = None
    expect_blocked: bool = False
    note: str = ""


def _load() -> dict[str, SourceSpec]:
    """Load the registry, falling back to the embedded names on any problem."""
    fallback = {n: SourceSpec(name=n) for n in FLOOR_SOURCES}
    try:
        raw = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        entries = raw.get("sources") or {}
        if not entries:
            raise ValueError("no `sources:` block")
        specs: dict[str, SourceSpec] = {}
        for name, cfg in entries.items():
            cfg = cfg or {}
            floor = cfg.get("floor", None)
            specs[name] = SourceSpec(
                name=name,
                enabled=bool(cfg.get("enabled", True)),
                floor=None if floor is None else int(floor),
                expect_blocked=bool(cfg.get("expect_blocked", False)),
                note=str(cfg.get("note", "") or "").strip(),
            )
        # A config that drops a shipped source must not remove it from reporting;
        # otherwise "not in the table" becomes a silent way to disable a source.
        for name, spec in fallback.items():
            specs.setdefault(name, spec)
        return specs
    except FileNotFoundError:
        # No config is the normal case for a fresh install — stay silent. The
        # embedded names still give full reporting with ZERO detection on.
        return fallback
    except Exception as exc:  # unreadable / malformed
        logger.warning(
            "config/scan-sources.yaml unusable (%s) — falling back to the embedded "
            "source list. The registry must never silently empty.",
            exc,
        )
        return fallback


SOURCES: dict[str, SourceSpec] = _load()


def is_enabled(name: str) -> bool:
    """Unknown sources default to ENABLED.

    Deliberate: a source missing from the registry must still run and still be
    reported. Defaulting to disabled would let a typo silently delete a source —
    the precise failure this module exists to prevent.
    """
    spec = SOURCES.get(name)
    return True if spec is None else spec.enabled


def floor(name: str) -> int | None:
    spec = SOURCES.get(name)
    return None if spec is None else spec.floor


def classify(name: str, count: int | None, status: str | None = None) -> str:
    """Return the status label for one source's result.

    ``count`` of None means the source did not run at all.
    ``status`` is the source's own report, e.g. "blocked" or "abandoned".
    """
    spec = SOURCES.get(name)
    if spec is not None and not spec.enabled:
        return DISABLED
    normalized = (status or "").lower()
    if normalized == "blocked":
        return BLOCKED
    if normalized == "abandoned":
        return ABANDONED
    if count is None:
        return ZERO
    if count > 0:
        f = floor(name)
        # Uncalibrated (None) means any positive count is acceptable — we have no
        # basis to call it low, and inventing one would cry wolf.
        return OK if f is None or count >= f else BELOW_FLOOR
    # count == 0. floor 0 is a CLAIM that zero is correct here; it must be
    # justified in writing or it is indistinguishable from an unnoticed breakage.
    if spec is not None and spec.floor == 0 and spec.note:
        return EMPTY_BY_DESIGN
    return ZERO


def check(
    counts: dict[str, int],
    statuses: dict[str, str] | None = None,
) -> list[str]:
    """Return human-readable WARNING lines for everything that is not ``ok``.

    Every registered source is considered, including ones absent from ``counts``
    — a source that did not report at all is the loudest failure of the lot, and
    the one most likely to be overlooked.
    """
    statuses = statuses or {}
    warnings: list[str] = []
    for name, spec in SOURCES.items():
        label = classify(name, counts.get(name), statuses.get(name))
        if label in (OK, EMPTY_BY_DESIGN):
            continue
        if label == DISABLED:
            warnings.append(
                f"{name}: DISABLED in config/scan-sources.yaml — "
                f"{spec.note or 'no reason recorded'}"
            )
        elif label == BLOCKED:
            detail = statuses.get(f"{name}_detail") or spec.note
            # An expected block is still reported. It stops being news when it is
            # FIXED, not when it becomes familiar.
            warnings.append(f"{name}: BLOCKED — {detail or 'host refused the request'}")
        elif label == ABANDONED:
            detail = statuses.get(f"{name}_detail") or "no budget recorded"
            warnings.append(
                f"{name}: ABANDONED — exceeded its wall-clock budget ({detail}) and the "
                f"run continued without it. Anything it returned is missing from this "
                f"scan; this is not an empty source."
            )
        elif label == BELOW_FLOOR:
            warnings.append(
                f"{name}: BELOW FLOOR — {counts.get(name)} jobs, expected >= {spec.floor}"
            )
        else:  # ZERO
            warnings.append(
                f"{name}: ZERO jobs and no explanation — a blocked source and an empty "
                f"source must never look the same. Investigate before trusting this run."
            )
    return warnings


def status_table(
    counts: dict[str, int],
    statuses: dict[str, str] | None = None,
) -> str:
    """Every registered source, one line each. Used by the run summary."""
    statuses = statuses or {}
    rows = ["source                 jobs   state", "-" * 62]
    for name in sorted(SOURCES):
        c = counts.get(name)
        rows.append(
            f"{name:<20}{('-' if c is None else c):>7}   "
            f"{classify(name, c, statuses.get(name))}"
        )
    return "\n".join(rows)


def registered() -> set[str]:
    return set(SOURCES)


def suggest_floors(counts: dict[str, int], fraction: float = 0.33) -> dict[str, int]:
    """Turn an observed run into conservative floor suggestions.

    Floors sit well below the observed count on purpose. A floor at or near the
    measured value fires on ordinary day-to-day variance, and a warning that
    fires every run is one the reader learns to skip — which costs more than
    having no warning at all.

    A source observed at zero gets no suggestion: we cannot tell from one run
    whether that is correct, and guessing would either paper over a break or
    invent a false alarm.
    """
    out: dict[str, int] = {}
    for name, count in sorted(counts.items()):
        if count > 0:
            out[name] = max(1, int(count * fraction))
    return out


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--calibrate",
        metavar="COUNTS_JSON",
        help='JSON file or literal mapping source -> count, e.g. \'{"greenhouse": 4042}\'',
    )
    parser.add_argument(
        "--fraction",
        type=float,
        default=0.33,
        help="floor as a fraction of the observed count (default: 0.33)",
    )
    args = parser.parse_args(argv)

    if not args.calibrate:
        print(status_table({}))
        return 0

    path = Path(args.calibrate)
    raw = path.read_text(encoding="utf-8") if path.exists() else args.calibrate
    counts = json.loads(raw)
    print("# Suggested floors — paste into config/scan-sources.yaml")
    print("# Sources observed at 0 are omitted deliberately: one run cannot tell")
    print("# a correct zero from a broken one. Investigate, then set floor: 0")
    print("# WITH a note if the zero is real.")
    print("sources:")
    for name, f in suggest_floors(counts, args.fraction).items():
        print(f"  {name}:\n    enabled: true\n    floor: {f}    # observed {counts[name]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_main())
