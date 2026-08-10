# The Frankfurt-preset reference set

A 277-posting sample of real scraped job postings, labelled GO/SKIP against one
contributor's search, whose home base is the `FRANKFURT_PROFILE` preset.

> **What produced these labels.** `judgements.json` holds an **automated
> (LLM) judge's** verdicts, gated at 90% agreement on a control stratum — NOT
> hand labels. That distinction was blurred in earlier versions of this file and
> is worth stating plainly, because it changes what the numbers below mean. Its single
purpose is to prove the geo engine did **not** change behaviour during the port
from the source project: the committed reference freezes the source engine's
class assignment for every item, and CI asserts the generic engine +
`FRANKFURT_PROFILE` reproduces all 277 verdicts exactly, then holds the set's
measured precision/recall floor.

**These labels are NOT canonical ground truth for anyone else's job search.**
GO/SKIP encodes one person's eligibility, commute tolerance and role taste.
Likewise the thresholds in `reference_assignments.json` (`recall >= 0.93`,
`precision >= 0.74`) are that set's measured numbers against the automated
judge — not universal quality bars, and **not the engine's accuracy against
human labels**.

That second caveat is not theoretical. In August 2026 the same contributor
hand-labelled all 277 items himself. Scored against **his** labels rather than
the judge's, the same engine on the same data measures **81.4% recall / 59.3%
precision** — and **79.1% / 53.1%** on the full-description, authoritative-
offices path that runs in production. The judge had been flattering the engine.

The thresholds here are therefore a **regression floor against the judge**:
useful for proving the port did not change behaviour, which is what this fixture
exists for. They are not a quality claim, and should not be quoted as one.

## Files

| File | What it is |
|------|------------|
| `blind_items.json` | 277 scrubbed postings: `{id, company, title, location, remote, desc}` |
| `judgements.json` | **Automated-judge** GO/SKIP verdict + score + reason per item id (90% control-stratum agreement gate) |
| `reference_assignments.json` | Frozen source-engine class (`eyas_class`), its generic rename (`generic_class`), and the frozen `role_keep` flag per item, plus the class map and thresholds |
| `GENERATION_LOG.md` | The provenance record: scrub proof, behaviour-neutrality result, environment fingerprint |
| `generate_reference.py` | One-shot regeneration script — requires a local Eyas checkout; **not run by CI** |

`answer_key.json` from the source benchmark is deliberately absent: it carries
per-item application URLs and nothing here needs it (verdicts live in
`judgements.json`). The fixture was scrubbed before ever entering this repo —
URL query strings/fragments stripped, PII patterns asserted at zero — and the
fixture-integrity test in `../test_blindset_regression.py` re-runs that scan on
every CI eval run. See `GENERATION_LOG.md` for the full audit trail.

`role_keep` is frozen on purpose: Kestrel ports the GEO engine only, not the
source project's role filter, so freezing the role flag keeps the joint
precision/recall figures comparable without importing that role vocabulary.

## Build your own reference set

Your search is not this search. To gate the engine on your own data:

1. **Export** your scraped postings to the same shape as `blind_items.json`:
   `{id, company, title, location, remote, desc}` (one JSON list).
2. **Label** each posting as GO or SKIP in a `judgements.json`-shaped file:
   `{"<id>": {"id", "verdict": "GO"|"SKIP", "score", "reason"}}`. If you use an
   LLM to label, record that — and hand-label a sample to check it. The gap
   between the two is itself a finding; here it was 14 points of precision.
3. **Point** `../replay.py`'s loaders at your files (or drop your files in
   place of these) and classify with your own `GeoProfile` — see
   `career_os.services.geo.profile.GeoProfile.from_home_tokens`.
4. **Set your own thresholds** from your first measured run, then gate on them
   the way `../test_blindset_regression.py` does.
