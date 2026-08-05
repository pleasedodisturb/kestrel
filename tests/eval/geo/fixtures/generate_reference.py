#!/usr/bin/env python3
"""One-shot developer script: scrub the Eyas blind set and freeze its verdicts.

NOT run by CI — CI consumes only the committed artifacts this script writes
(``blind_items.json``, ``judgements.json``, ``reference_assignments.json``,
``GENERATION_LOG.md``). Regenerating requires a local Eyas checkout::

    .venv/bin/python tests/eval/geo/fixtures/generate_reference.py \
        --eyas-path /path/to/eyas

Order is mandatory and enforced here: scrub, prove the scrub is
behaviour-neutral against the CURRENT Eyas engine, freeze the reference from
the SCRUBBED items, then (and only then) write everything to disk together
with an auditable GENERATION_LOG.md. On any PII hit or any verdict drift the
script writes NOTHING and exits non-zero.

``answer_key.json`` is deliberately never copied — it carries per-item
application URLs and is not needed (verdicts come from ``judgements.json``).
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent
REPO_ROOT = FIXTURES.parents[3]
sys.path.insert(0, str(REPO_ROOT))

from tests.eval.geo.replay import scrub_patterns  # noqa: E402

# Eyas class -> generic (Kestrel) class. A KeyError here means the Eyas engine
# grew a class this port does not know about — fail loud, never guess.
CLASS_MAP = {
    "de_local": "home_local",
    "de_relocate": "home_relocate",
    "eu_relocate": "visa_free_relocate",
    "uk_relocate": "visa_required_relocate",
    "eligible_remote": "eligible_remote",
    "foreign": "foreign",
    "unknown": "unknown",
}

THRESHOLDS = {"recall": 0.93, "precision": 0.74}

# Matches a URL up to (not including) whitespace/quotes/closing brackets; the
# scrub cuts it at the first "?" or "#" so no query string or fragment ships.
_URL_RE = re.compile(r"https?://[^\s\"'<>\\)\]]+")


def _strip_url_params(text: str) -> tuple[str, int]:
    """Strip query strings and fragments from every URL in *text*."""
    stripped = 0

    def _cut(m: re.Match[str]) -> str:
        nonlocal stripped
        url = m.group(0)
        bare = url.split("?", 1)[0].split("#", 1)[0]
        if bare != url:
            stripped += 1
        return bare

    return _URL_RE.sub(_cut, text), stripped


def _scrub_value(value, counters: dict[str, int]):
    """Recursively scrub every string in a JSON-shaped structure."""
    if isinstance(value, str):
        scrubbed, n = _strip_url_params(value)
        counters["urls_stripped"] += n
        return scrubbed
    if isinstance(value, list):
        return [_scrub_value(v, counters) for v in value]
    if isinstance(value, dict):
        return {k: _scrub_value(v, counters) for k, v in value.items()}
    return value


def _serialize(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _eyas_verdict(geo_eligibility, rec: dict) -> str:
    """The exact benchmark-record argument shape from geofix_v2.py::geo_v2."""
    return geo_eligibility(
        location=" ".join(str(rec.get(f, "") or "") for f in ("location", "offices", "country")),
        offices=None,
        remote=bool(rec.get("remote")),
        title=(rec.get("title") or "").lower(),
        description=rec.get("desc") or "",
    )


def _git_short_sha(repo: Path) -> str:
    out = subprocess.run(  # noqa: S603
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def _resolved_packages() -> list[str]:
    """``name==version`` for every third-party distribution the run imported."""
    from importlib import metadata

    dist_map = metadata.packages_distributions()
    dists: set[str] = set()
    for mod in list(sys.modules):
        top = mod.split(".", 1)[0]
        for dist in dist_map.get(top, []):
            dists.add(dist)
    lines = []
    for dist in sorted(dists, key=str.lower):
        try:
            lines.append(f"{dist}=={metadata.version(dist)}")
        except metadata.PackageNotFoundError:  # pragma: no cover
            lines.append(f"{dist}==(unresolvable)")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--eyas-path",
        required=True,
        type=Path,
        help="Local Eyas checkout (read-only; supplies the engine + source fixtures)",
    )
    args = parser.parse_args()

    eyas = args.eyas_path.resolve()
    bench = eyas / "tools" / "benchmarks" / "g1388"
    if not bench.is_dir():
        print(f"FATAL: {bench} not found — wrong --eyas-path?", file=sys.stderr)
        return 1

    # Import the CURRENT Eyas engine (geofix_v2 puts eyas/tools on sys.path).
    sys.path.insert(0, str(bench))
    # geofix_v2 must import first: it puts eyas/tools on sys.path for job_scorer.
    from geofix_v2 import role_ok_v2  # noqa: E402
    from job_scorer import geo_eligibility  # noqa: E402

    # ------------------------------------------------------------------
    # Step A — scrub. Copy ONLY blind_items.json + judgements.json.
    # ------------------------------------------------------------------
    original_items = json.loads((bench / "blind_items.json").read_text(encoding="utf-8"))
    original_judgements = json.loads((bench / "judgements.json").read_text(encoding="utf-8"))

    counters = {"urls_stripped": 0}
    scrubbed_items = _scrub_value(original_items, counters)
    scrubbed_judgements = _scrub_value(original_judgements, counters)
    items_changed = sum(
        1 for orig, scrub in zip(original_items, scrubbed_items, strict=True) if orig != scrub
    )

    items_text = _serialize(scrubbed_items)
    judgements_text = _serialize(scrubbed_judgements)
    blob = items_text + judgements_text

    pattern_counts = {
        label: len(pat.findall(blob)) for label, pat in scrub_patterns(REPO_ROOT).items()
    }
    if any(pattern_counts.values()):
        print("SCRUB-PROOF: FAIL — refusing to write anything.", file=sys.stderr)
        for label, count in sorted(pattern_counts.items()):
            if count:
                print(f"  {label}: {count} match(es)", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # Step B — prove the scrub is behaviour-neutral on the CURRENT engine.
    # (URL stripping shortens desc, which could in principle shift the
    # description[:2500] window.)
    # ------------------------------------------------------------------
    diffs = []
    for orig, scrub in zip(original_items, scrubbed_items, strict=True):
        before = _eyas_verdict(geo_eligibility, orig)
        after = _eyas_verdict(geo_eligibility, scrub)
        if before != after:
            diffs.append((orig["id"], before, after))
    if diffs:
        print("SCRUB-PROOF: FAIL — scrub changed Eyas verdicts; nothing written.", file=sys.stderr)
        print("| id | original verdict | scrubbed verdict |", file=sys.stderr)
        print("|----|------------------|------------------|", file=sys.stderr)
        for item_id, before, after in diffs:
            print(f"| {item_id} | {before} | {after} |", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # Step C — freeze the reference from the SCRUBBED items.
    # ------------------------------------------------------------------
    eyas_sha = _git_short_sha(eyas)
    kestrel_sha = _git_short_sha(REPO_ROOT)
    ref_items = {}
    for rec in scrubbed_items:
        eyas_class = _eyas_verdict(geo_eligibility, rec)
        ref_items[rec["id"]] = {
            "eyas_class": eyas_class,
            "generic_class": CLASS_MAP[eyas_class],
            # Frozen deliberately: Kestrel ports the GEO engine only, not the
            # role filter, so the joint P/R figures stay comparable without
            # importing Eyas's role vocabulary.
            "role_keep": bool(role_ok_v2(rec)),
        }
    reference = {
        "generated_from": f"eyas tools/job_scorer.py @ {eyas_sha}",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile": "FRANKFURT_PROFILE",
        "thresholds": THRESHOLDS,
        "class_map": CLASS_MAP,
        "items": ref_items,
    }

    # ------------------------------------------------------------------
    # Step D — write artifacts + the audit trail, atomically at the end.
    # ------------------------------------------------------------------
    counts_table = "\n".join(
        f"| `{label}` | {count} |" for label, count in sorted(pattern_counts.items())
    )
    packages = "\n".join(f"- `{line}`" for line in _resolved_packages())
    log = f"""# Geo blind-set fixture — generation log (G-1474)

Produced by `generate_reference.py` (one-shot, never run by CI). This log is
the auditable proof that the committed fixture was scrubbed, that the scrub
changed no verdict of the then-current Eyas engine, and which environment the
frozen reference came from.

## Scrub result

SCRUB-PROOF: PASS

| Metric | Value |
|--------|-------|
| Source items | {len(original_items)} |
| Scrubbed items written | {len(scrubbed_items)} |
| Judgements written | {len(scrubbed_judgements)} |
| Items whose text changed | {items_changed} |
| URLs stripped of query/fragment | {counters["urls_stripped"]} |
| `answer_key.json` copied | no (deliberately excluded — carries application URLs) |

### Per-pattern PII match counts (all must be 0)

| Pattern (redacted label) | Matches |
|--------------------------|---------|
{counts_table}

## Behaviour-neutrality proof (Step B)

The CURRENT Eyas engine was run over the original AND the scrubbed items with
the exact benchmark argument shape (`geofix_v2.py::geo_v2`).

| Metric | Value |
|--------|-------|
| Items compared | {len(original_items)} |
| Items differing | 0 |

(On any difference this log is never written and the script exits non-zero.)

## Environment fingerprint

| Field | Value |
|-------|-------|
| Eyas repo commit | `{eyas_sha}` |
| Kestrel repo commit | `{kestrel_sha}` |
| Python | `{platform.python_version()}` ({platform.platform()}) |
| Generated at | {reference["generated_at"]} |

### Resolved third-party packages imported during generation

{packages}
"""

    (FIXTURES / "blind_items.json").write_text(items_text, encoding="utf-8")
    (FIXTURES / "judgements.json").write_text(judgements_text, encoding="utf-8")
    (FIXTURES / "reference_assignments.json").write_text(_serialize(reference), encoding="utf-8")
    (FIXTURES / "GENERATION_LOG.md").write_text(log, encoding="utf-8")
    print(
        f"SCRUB-PROOF: PASS — wrote {len(scrubbed_items)} items, "
        f"{counters['urls_stripped']} URLs stripped, reference @ eyas {eyas_sha}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
