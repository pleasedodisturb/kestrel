"""Rapid-fire T2 application-kit generator.

Codifies a manual per-batch apply flow (manifest -> per-app numbered folders ->
tabs) into a repeatable build. Given a list of scored+tiered job dicts, emits:

    <out>/_batch-<date>-t<tier>/
        INDEX.md                      # numbered table: company/role/loc/tier/archetype/open-Q/apply
        apps/NN-<slug>/
            NN-SUBMIT.txt             # metadata + apply link + form cheats + CV/cover refs
            NN-cover-<archetype>.pdf  # copied if a source archetype cover exists
            NN-<cv>.pdf               # copied if a source CV exists

Numbering uses the NN- prefix convention so a number alone identifies the item.
The kit STRUCTURE is the codified value; CV/cover PDFs are copied in when source
files are found, otherwise referenced in SUBMIT.txt with a "(missing)" note.

Pure file I/O + deterministic mapping -> unit-testable with a tmp dir; no network.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

# Title -> cover/CV archetype. First match wins; order matters (specific first).
_ARCHETYPE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("devrel", ("developer advocate", "devrel", "developer relations", "evangelist", "community")),
    (
        "solutions-fde",
        (
            "solutions",
            "forward deployed",
            "fde",
            "sales engineer",
            "solutions architect",
            "customer engineer",
        ),
    ),
    (
        "product-eng",
        (
            "product engineer",
            "founding engineer",
            "ai engineer",
            "full stack",
            "fullstack",
            "software engineer",
            "swe",
        ),
    ),
    (
        "pm",
        (
            "product manager",
            "program manager",
            "tpm",
            "product lead",
            "group pm",
            "bizops",
            "operations",
            "strategy",
        ),
    ),
)
_DEFAULT_ARCHETYPE = "pm"

# Neutral placeholder cheat-sheet. Callers pass their own ``form_cheats`` string with
# real values; the default carries no personal data (work-auth/salary/pronouns are
# left as <configure> tokens so nothing personal ships in the module).
_FORM_CHEATS_DEFAULT = (
    "work-auth = <configure> · salary = <configure> · "
    "remote = <configure> · pronouns = <configure> · notice = <configure>"
)


def archetype_for(title: str | None) -> str:
    t = (title or "").lower()
    for archetype, kws in _ARCHETYPE_RULES:
        if any(k in t for k in kws):
            return archetype
    return _DEFAULT_ARCHETYPE


def _slug(company: str | None) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (company or "company").lower()).strip("-")
    return s or "company"


def _submit_txt(
    n: int,
    job: dict,
    archetype: str,
    cv_ref: str,
    cover_ref: str,
    open_q: dict | None,
    form_cheats: str,
) -> str:
    score = job.get("fit_score", "?")
    tier = job.get("tier", "?")
    if open_q is None or not open_q.get("checked"):
        oq = "unknown (verify on the form)"
    elif open_q.get("has_open_questions"):
        oq = "YES -- write the hook: " + "; ".join(open_q.get("essay_labels", []))
    else:
        oq = "none (standard fields only)"
    return (
        f"#{n:02d}  {job.get('company', '?')} — {job.get('title', '?')}\n"
        f"Location: {job.get('location', '?')}\n"
        f"Geo: {job.get('geo_class', '?')}  Tier: {tier}  Score: {score}/10\n"
        f"Open questions: {oq}\n\n"
        f"APPLY: {job.get('url', '')}\n\n"
        f"CV to upload:  {cv_ref}\n"
        f"Cover ({archetype}):  {cover_ref}\n\n"
        f"Form cheats: {form_cheats}\n"
    )


def build_kit(
    jobs: list[dict],
    out_root: Path | str,
    *,
    batch_date: str,
    tier: str = "T2",
    cover_dir: Path | str | None = None,
    cv_path: Path | str | None = None,
    open_q_results: dict | None = None,
    form_cheats: str = _FORM_CHEATS_DEFAULT,
) -> dict:
    """Generate the kit folder tree. Returns a summary dict.

    ``open_q_results`` maps a job url -> probe dict (so the caller controls whether
    network probing happens; tests pass canned results or None).
    ``cover_dir`` holds archetype cover PDFs named ``_<archetype>.pdf``; ``cv_path``
    is the default CV PDF. Either may be None/missing -> referenced, not copied.
    ``form_cheats`` is a caller-supplied cheat-sheet string; it defaults to a neutral
    placeholder that contains no personal data.
    """
    out_root = Path(out_root)
    kit_dir = out_root / f"_batch-{batch_date}-{tier.lower()}"
    apps_dir = kit_dir / "apps"
    apps_dir.mkdir(parents=True, exist_ok=True)
    cover_dir = Path(cover_dir) if cover_dir else None
    cv_path = Path(cv_path) if cv_path else None
    open_q_results = open_q_results or {}

    index_rows: list[str] = []
    for i, job in enumerate(jobs, start=1):
        archetype = archetype_for(job.get("title"))
        folder = apps_dir / f"{i:02d}-{_slug(job.get('company'))}"
        folder.mkdir(parents=True, exist_ok=True)

        # Cover: copy the archetype cover if present, else reference by name.
        cover_ref = f"{i:02d}-cover-{archetype}.pdf"
        src_cover = cover_dir / f"_{archetype}.pdf" if cover_dir else None
        if src_cover and src_cover.exists():
            shutil.copy2(src_cover, folder / cover_ref)
        else:
            cover_ref += "  (missing -- generate/attach archetype cover)"

        # CV: copy the default CV if present, else reference.
        cv_ref = f"{i:02d}-CV.pdf"
        if cv_path and cv_path.exists():
            shutil.copy2(cv_path, folder / cv_ref)
        else:
            cv_ref += "  (missing -- attach the right CV variant)"

        oq = open_q_results.get(job.get("url"))
        (folder / f"{i:02d}-SUBMIT.txt").write_text(
            _submit_txt(i, job, archetype, cv_ref, cover_ref, oq, form_cheats),
            encoding="utf-8",
        )

        oq_cell = (
            "?"
            if (oq is None or not oq.get("checked"))
            else ("essay" if oq.get("has_open_questions") else "none")
        )
        url = job.get("url", "") or ""
        index_rows.append(
            f"| {i:02d} | {job.get('company', '?')} | {job.get('title', '?')} | "
            f"{job.get('location', '?')} | {job.get('tier', '?')} | {archetype} | "
            f"{oq_cell} | {f'[apply]({url})' if url else ''} |"
        )

    index = [
        f"# Tier-{tier} rapid-fire kit — {batch_date}",
        "",
        f"**{len(jobs)} roles** · geo-filtered + deduped vs DB. "
        f"Fire ~2 min each: open APPLY, upload CV, fold the hook into the archetype "
        f"cover, submit.",
        "",
        "| # | Company | Role | Location | Tier | Archetype | OpenQ | Apply |",
        "|---|---------|------|----------|------|-----------|-------|-------|",
        *index_rows,
        "",
        "OpenQ: none = standard fields only (fast); essay = write a hook first; "
        "? = verify on the form.",
    ]
    (kit_dir / "INDEX.md").write_text("\n".join(index), encoding="utf-8")

    return {
        "kit_dir": str(kit_dir),
        "count": len(jobs),
        "tier": tier,
        "with_essays": sum(
            1 for j in jobs if (open_q_results.get(j.get("url")) or {}).get("has_open_questions")
        ),
    }
