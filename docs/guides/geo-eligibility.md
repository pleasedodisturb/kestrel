# Geo-Eligibility: Never Trust the List-Location String

When you filter jobs by location, the location string on an ATS **list endpoint**
is a free-text marketing field. It lies. Two failure modes recur, and both come
from trusting the wrong signal:

1. **The remote-rescue bug.** A posting's `isRemote` flag is used as a *fallback*
   that overrides an explicit foreign-location rejection — so a role that is
   really onsite (or country-locked) in a place you cannot work sneaks into your
   batch because it is labelled "remote".
2. **The list-string lie.** The list endpoint names a city in your home region
   while the *authoritative* per-job office is somewhere else entirely, or it
   advertises a broad region ("EMEA") while the role is actually country-locked
   remote to one foreign country.

Kestrel's geo engine is built to defeat both. The **single geo authority** lives
in `src/career_os/services/geo/`: a pure, config-driven classifier
(`classifier.py`) that consults a `GeoProfile` (`profile.py`) carrying every
region-specific pattern. The engine itself contains no geography — swapping the
profile swaps the geography. `tools/batch_probe.py` remains the **legacy
tools-side gate** that still backs `geo_classify` / `geo_ok`; everything else
(including `tools/job_scorer.py`'s `geo_eligibility`) delegates to the package
engine.

## The 7 classes

`geo_eligibility(location, offices, remote, title, description, profile=...)`
returns exactly one of seven classes:

| Class                    | Meaning                                                        | Eligibility treatment              |
| ------------------------ | -------------------------------------------------------------- | ---------------------------------- |
| `home_local`             | Home commute belt — no move needed                             | Eligible                           |
| `home_relocate`          | Elsewhere in the home country — a move, but no visa            | Eligible (ranking only)            |
| `eligible_remote`        | Remote within an eligible region, pan-region, or unspecified   | Eligible                           |
| `visa_free_relocate`     | Onsite in a visa-free region — a real move                     | Keep, but flag                     |
| `visa_required_relocate` | Onsite where a work visa is needed                             | Keep, but flag (burden visible)    |
| `foreign`                | Explicit ineligible place — onsite OR country-locked remote    | Capped + review queue              |
| `unknown`                | No geo signal at all                                           | Eligible — **deliberately** so     |

`unknown` is deliberately eligible: absence of geo data must never bury a good
role. Only the explicit `foreign` class is ever hard-blocked; the two relocate
classes are kept-but-flagged so the relocation/visa burden stays visible without
hiding the role.

The membership sets are exported as constants —
`ELIGIBLE_CLASSES` (`home_local`, `home_relocate`, `eligible_remote`,
`unknown`), `MAYBE_CLASSES` (`visa_free_relocate`, `visa_required_relocate`) —
from `career_os.services.geo.classifier`, so downstream code never string-matches
its own treatment table.

## The two invariants

**Authoritative offices override the list string.** When you can fetch the
per-job payload, use it. The list string is only a fallback:

- Greenhouse: `offices[].name` from the single-job endpoint.
- Ashby: `address` + `location` + every `secondaryLocations[].location`.

`geo_eligibility(location, offices=…, …)` uses `offices` when present and
ignores the list string — that is the whole point. A secondary office in an
eligible region *rescues* a role whose primary location is foreign (the
multi-office rescue).

**`remote` never makes a role eligible on its own.** The remote flag only
distinguishes a remote posting from an onsite one. *Where* the role is open is
decided exclusively by the location text, the authoritative offices, the title
and (for bare-remote postings) the description. A remote role anchored to a
foreign country is still `foreign`.

## The two contract rules

Both rules were measured on the 277-item blind set and survive verbatim:

1. **Title region-tokens bind first.** "(AMER)" or ", Korea" in the *title*
   names the served market regardless of which office is listed — but an
   eligible region token alongside ("EMEA/AMER") rescues the posting.
2. **A bare "Remote" location consults the description before defaulting
   eligible.** A "Remote" posting whose text names only foreign cities is a
   foreign-remote role. Skipping this consult cost 9 points of precision
   during the original port, so the ordering is contractual.

## GeoProfile and the shipped presets

A `GeoProfile` (in `src/career_os/services/geo/profile.py`) is a frozen bundle
of compiled patterns — home country, commute belt, visa-free region, pan-region
tokens, visa-required region, foreign places, multi-region rescue tokens, and
title market tokens. A field left unset simply never matches, so partial
profiles are valid.

Two presets ship in `src/career_os/services/geo/presets.py`:

- `FRANKFURT_PROFILE` — the reference preset; its pattern strings are the
  measured artifact from the source engine's blind-set benchmark.
- `US_REMOTE_PROFILE` — an illustrative contrast preset for a US-based remote
  worker, proving the engine is config-driven (same input, different profile,
  different verdict). Demonstration data, not immigration advice.

The reference posting set used to validate the engine (and its provenance) is
documented in `tests/eval/geo/fixtures/README.md`.

## Build your own profile

There are two routes, with different expressive power. Be aware of what each
can and cannot say.

### 1. Config route — `config/geo.yaml` (the tools pipeline)

Copy the example config and set your own home cities / country names:

```bash
cp config/geo.example.yaml config/geo.yaml
```

```yaml
home_tokens:            # place names that count as YOUR home region
  - ireland
  - dublin
  - cork
allow_pan_region_remote: true   # count multi-country + unspecified remote as eligible
extra_foreign_tokens: []        # optional extra places to always drop
```

These are the **only three keys** the config loader parses: `home_tokens`,
`allow_pan_region_remote`, `extra_foreign_tokens`. Anything else in the file is
silently ignored — do not invent keys.

`allow_pan_region_remote: true` admits two things: multi-country region tokens
(`EMEA`, `Europe`, `DACH`, `Benelux`, `Nordics`, `EU-wide`) and the
global/worldwide/anywhere family, **plus** an unspecified bare `Remote` posting
with no other geo signal. Set it to `false` and all of those become `unknown`
instead — that is what "require an explicit home-region anchor" means. Note
`unknown` is still an eligible class (absence of signal never buries a role);
the flag changes classification, not survival.

The config route builds a profile via `GeoProfile.from_home_tokens(...)`: your
home tokens become the home vocabulary, and the shared public geography list
(minus your home tokens) becomes the foreign vocabulary. **A home token always
wins** — list your country and its cities are safe even where the same name
appears in the built-in public geography list. **A flat token
vocabulary cannot express a commute-belt split or a visa-required region** — a
config-driven profile classifies every home hit as `home_local`, and an onsite
posting in, say, an EU country outside your home tokens lands in the shared
foreign vocabulary rather than `visa_free_relocate`. If you need those
distinctions, use the code route.

### 2. Code route — the full ten-field profile

`build_profile(name, **pattern_strings)` compiles explicit regex strings for
all ten pattern fields (this is how the shipped presets are defined), and
`GeoProfile.from_home_tokens(name, home_tokens, *, home_local_tokens=...,
visa_required_tokens=..., extra_foreign_tokens=..., allow_pan_region_remote=...)`
accepts the finer vocabularies as **function parameters**.

`build_profile` compiles its pattern strings **verbatim, without escaping** —
that is the point of the route, but it means you own their complexity. Keep
them to literal alternations with at most one non-nested quantifier (as the
shipped presets do): a catastrophic pattern like `(\S+)+` would hang the
scorer on scraped text. For anything derived from untrusted input use
`from_home_tokens`, which `re.escape`s every token.

`home_local_tokens` and `visa_required_tokens` are code-level parameters only —
they are **not** YAML keys, and putting them in `config/geo.yaml` does nothing.
With them you can express the commute belt (postings there rank as
`home_local`) and a visa-required region (postings there classify as
`visa_required_relocate` instead of disappearing into `foreign`).

```python
from career_os.services.geo.profile import GeoProfile

profile = GeoProfile.from_home_tokens(
    "my-region",
    home_tokens=("ireland", "dublin", "cork", "galway"),
    home_local_tokens=("dublin",),            # commute belt: ranking only
    visa_required_tokens=("united states",),  # visible burden, not a drop
)
```

## Where the engine is wired

- **`tools/job_scorer.py`** — `geo_eligibility(...)` delegates to the package
  engine, building a memoized profile from `config/geo.yaml` when no explicit
  profile is passed. The `foreign` class is preserved verbatim for the
  `tools/t3_lane.py` guardrail (`geo == "foreign"`).
- **Discovery pre-filter** (`src/career_os/discovery/prefilter.py`) — an
  **opt-in** geo gate: set `PrefilterConfig.geo_profile` to enable it. It
  annotates each job dict with `job["geo_class"]` and counts the `foreign`
  class as `geo_rejections`, but **keeps the job** — `foreign` is the engine's
  cap / review-queue class, and deleting it costs ~6.4% recall against human
  GO judgements. Deletion requires the separate `geo_drop_foreign` opt-in.
  `unknown` and the flagged classes are never rejected under either setting.
  With no profile configured, pre-filter behaviour is unchanged.
  The `geo_class` annotation currently reaches **direct callers of
  `run_prefilter` only**: the discovery service rebuilds its merged job dicts
  after pre-filtering, so the verdict is not yet persisted to `DiscoveredJob`.
- **`tools/batch_probe.py`** — the legacy tools-side gate; `geo_classify` /
  `geo_ok` still use its internal 3-way token classifier and public geography
  lists. New code should call the package engine instead.
