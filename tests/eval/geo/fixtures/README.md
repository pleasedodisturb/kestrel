# The Frankfurt-preset reference set

A 277-posting sample of real scraped job postings, human-judged GO/SKIP by one
contributor whose home base is the `FRANKFURT_PROFILE` preset. Its single
purpose is to prove the geo engine did **not** change behaviour during the port
from the source project: the committed reference freezes the source engine's
class assignment for every item, and CI asserts the generic engine +
`FRANKFURT_PROFILE` reproduces all 277 verdicts exactly, then holds the set's
measured precision/recall floor.

**These labels are NOT canonical ground truth for anyone else's job search.**
GO/SKIP encodes one person's eligibility, commute tolerance and role taste.
Likewise the thresholds in `reference_assignments.json` (`recall >= 0.93`,
`precision >= 0.74`) are that set's measured numbers — not universal quality
bars.

## Files

| File | What it is |
|------|------------|
| `blind_items.json` | 277 scrubbed postings: `{id, company, title, location, remote, desc}` |
| `judgements.json` | Human GO/SKIP verdict + score + reason per item id |
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
2. **Label** each posting yourself as GO or SKIP in a `judgements.json`-shaped
   file: `{"<id>": {"id", "verdict": "GO"|"SKIP", "score", "reason"}}`.
3. **Point** `../replay.py`'s loaders at your files (or drop your files in
   place of these) and classify with your own `GeoProfile` — see
   `career_os.services.geo.profile.GeoProfile.from_home_tokens`.
4. **Set your own thresholds** from your first measured run, then gate on them
   the way `../test_blindset_regression.py` does.
