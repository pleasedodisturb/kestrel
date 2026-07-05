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

Kestrel's geo gate (`tools/batch_probe.py`) is built to defeat both.

## The rule

A role is **eligible** only if:

- it is onsite / hybrid in your **home region** (any home city — intra-home
  relocation is assumed OK), **or**
- it is remote and genuinely open to a home-based person: remote-home,
  remote-EU-wide, remote-EMEA, remote-Europe, or global / unspecified remote.

A role is **dropped** if:

- it is onsite / hybrid in a foreign location — *even when a home city is also
  listed* on the unreliable list string, if the real office is foreign; **or**
- it is country-locked remote to a foreign country ("Remote - Sweden",
  "All France (remote)", …).

## The two invariants

**Authoritative offices override the list string.** When you can fetch the
per-job payload, use it. The list string is only a fallback:

- Greenhouse: `offices[].name` from the single-job endpoint.
- Ashby: `address` + `location` + every `secondaryLocations[].location`.

`geo_classify(location_text, offices=…, is_remote=…)` uses `offices` when present
and ignores the list string — that is the whole point.

**`is_remote` never makes a role eligible on its own.** The remote flag only
distinguishes a remote posting from an onsite one. *Where* the role is open is
decided exclusively by the location text and the authoritative offices. A remote
role anchored to a foreign country is still dropped.

## Configuring your home region

The home region is **parameterized** — there is no hardcoded country in the code.
Copy the example config and set your own home cities / country names:

```bash
cp config/geo.example.yaml config/geo.yaml
```

```yaml
home_tokens:
  - <your-country>
  - <your-city>
  - <another-home-city>
allow_pan_region_remote: true   # count EMEA / EU-wide / global remote as eligible
extra_foreign_tokens: []        # optional extra places to always drop
```

A home token **always wins** classification, so you can list a place that also
appears in the built-in public foreign-geography list and it will be treated as
home. The pan-region tokens (EMEA / EU-wide / Europe / global / bare-remote) and
the foreign-place list are public geography defined in `tools/batch_probe.py`;
you normally only need to set `home_tokens`.

## Verdicts

`geo_classify(...)` returns:

| Verdict            | Meaning                                                       |
| ------------------ | ------------------------------------------------------------- |
| `"home"`           | onsite / hybrid / remote anchored in your home region         |
| `"eligible_remote"`| remote open to a home-based person (EU-wide / EMEA / global)  |
| `None`             | drop — foreign onsite, or country-locked foreign remote       |

`geo_eligibility(...)` (in `tools/job_scorer.py`) exposes the finer four-way
classification — `"home"`, `"eligible_remote"`, `"foreign"`, `"unknown"` — for
downstream tier routing.
