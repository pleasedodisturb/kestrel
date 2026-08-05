# Geo blind-set fixture — generation log (G-1474)

Produced by `generate_reference.py` (one-shot, never run by CI). This log is
the auditable proof that the committed fixture was scrubbed, that the scrub
changed no verdict of the then-current Eyas engine, and which environment the
frozen reference came from.

## Scrub result

SCRUB-PROOF: PASS

| Metric | Value |
|--------|-------|
| Source items | 277 |
| Scrubbed items written | 277 |
| Judgements written | 277 |
| Items whose text changed | 16 |
| URLs stripped of query/fragment | 16 |
| `answer_key.json` copied | no (deliberately excluded — carries application URLs) |

### Per-pattern PII match counts (all must be 0)

| Pattern (redacted label) | Matches |
|--------------------------|---------|
| `generic:email` | 0 |
| `personal:home-city-country` | 0 |
| `personal:mail-domain` | 0 |
| `personal:name-stem` | 0 |
| `personal:surname` | 0 |
| `tracking:url-query` | 0 |

## Behaviour-neutrality proof (Step B)

The CURRENT Eyas engine was run over the original AND the scrubbed items with
the exact benchmark argument shape (`geofix_v2.py::geo_v2`).

| Metric | Value |
|--------|-------|
| Items compared | 277 |
| Items differing | 0 |

(On any difference this log is never written and the script exits non-zero.)

## Environment fingerprint

| Field | Value |
|-------|-------|
| Eyas repo commit | `6de611d` |
| Kestrel repo commit | `dfa0dfa` |
| Python | `3.14.6` (macOS-26.6-arm64-arm-64bit-Mach-O) |
| Generated at | 2026-08-05T15:22:19Z |

### Resolved third-party packages imported during generation

- `click==8.4.2`
- `httpx==0.28.1`
- `idna==3.18`
- `kestrel-app==0.25.0`
- `numpy==1.26.3`
- `pandas==2.3.3`
- `Pygments==2.20.0`
- `python-dateutil==2.9.0.post0`
- `pytz==2026.3.post1`
- `PyYAML==6.0.3`
- `rich==15.0.0`
- `setuptools==83.0.0`
- `six==1.17.0`
