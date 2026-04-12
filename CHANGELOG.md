# Changelog

## [0.2.0](https://github.com/pleasedodisturb/kestrel/compare/v0.1.0...v0.2.0) (2026-04-12)


### Features

* add 10 brand illustrations - logos, heroes, art ([33b5f19](https://github.com/pleasedodisturb/kestrel/commit/33b5f19b1a9d7adba2f6d118bbdeed1499815b95))
* add 10 brand illustrations for docs, README, and marketing ([bcac7cf](https://github.com/pleasedodisturb/kestrel/commit/bcac7cf282469959a34273ea9034880729efadd2))
* add 31 curated illustrations to gallery for future use ([8ca7a80](https://github.com/pleasedodisturb/kestrel/commit/8ca7a801712cc1c7197b1ad1319b6e4bfd8c7ce8))
* add one-command installers (curl, npx, brew) — closes [#21](https://github.com/pleasedodisturb/kestrel/issues/21) ([83d9d10](https://github.com/pleasedodisturb/kestrel/commit/83d9d10a5846141a10804c5a6eeeb75bdc8bd73f))
* **scoring:** rule-based red flag detection + letter-grade scoring ([#83](https://github.com/pleasedodisturb/kestrel/issues/83)) ([9f6c437](https://github.com/pleasedodisturb/kestrel/commit/9f6c43775c65549fbdca9fdbe04d8b3043bc1c31))
* show new matches banner in Discovery page ([#29](https://github.com/pleasedodisturb/kestrel/issues/29)) ([06fbdc8](https://github.com/pleasedodisturb/kestrel/commit/06fbdc839289fa1d45de6190989e9a607fbb5d7c))
* wire illustrations into all docs + GitHub Pages ([f051b80](https://github.com/pleasedodisturb/kestrel/commit/f051b8014ae8f52c3f82576658133ac6914fdf8f))
* wire illustrations into docs + GitHub Pages setup ([8da7224](https://github.com/pleasedodisturb/kestrel/commit/8da7224c94a1df40e73f70eaa5e843437895e403))


### Bug Fixes

* add comments to empty except blocks (S108) ([81d6cf8](https://github.com/pleasedodisturb/kestrel/commit/81d6cf8d70789b427c86a62a24c8e5e5767b3470))
* add DB fixture to CLI tests that query profiles table ([#81](https://github.com/pleasedodisturb/kestrel/issues/81)) ([#82](https://github.com/pleasedodisturb/kestrel/issues/82)) ([eb8949a](https://github.com/pleasedodisturb/kestrel/commit/eb8949aa2290f649e15c373745d59934badf847f))
* add job_family to all test Profile fixtures + remove stale xfail markers ([0acee5d](https://github.com/pleasedodisturb/kestrel/commit/0acee5d704bc887d23b9871f3c036d02d3f135b9))
* address documentation review findings ([7476ada](https://github.com/pleasedodisturb/kestrel/commit/7476ada6c90116098049d8b2bc479c860452349c))
* address documentation review findings ([5dd52e9](https://github.com/pleasedodisturb/kestrel/commit/5dd52e927ad152774c8616d5a70b5ae61cdb3bb6))
* block scoring on incomplete profile and show banner ([#27](https://github.com/pleasedodisturb/kestrel/issues/27)) ([e16e6e8](https://github.com/pleasedodisturb/kestrel/commit/e16e6e8091d4ba6c7e931e344dd47f4f61320b81))
* convert FastAPI endpoints to Annotated pattern + remove redundant response_model ([#50](https://github.com/pleasedodisturb/kestrel/issues/50)) ([b32c36d](https://github.com/pleasedodisturb/kestrel/commit/b32c36dff0a93e645e79fe01aa9c94a447255c07))
* deduplicate Profile fixture data across 11 test files ([2bc624b](https://github.com/pleasedodisturb/kestrel/commit/2bc624b16ddea9eacdce808c386afc70690e250b))
* deduplicate remaining inline Profile constructors in 5 test files ([ea4f835](https://github.com/pleasedodisturb/kestrel/commit/ea4f835d8badc369179fa0c2e3961d805c231cb5))
* detect OpenRouter credit exhaustion and surface to user ([#28](https://github.com/pleasedodisturb/kestrel/issues/28)) ([7ea5c1a](https://github.com/pleasedodisturb/kestrel/commit/7ea5c1afa785070a0baeb928e53a5a9847c4f7de))
* document HTTPException status codes in FastAPI endpoint responses param ([cbb956a](https://github.com/pleasedodisturb/kestrel/commit/cbb956ab74262c5f7a6a9055765fcb2e264a4d3e)), closes [#53](https://github.com/pleasedodisturb/kestrel/issues/53)
* documentation and config cleanup (round 2) ([ccdb27e](https://github.com/pleasedodisturb/kestrel/commit/ccdb27ee394820ab861bea8b53d3ce134737376f))
* documentation and config cleanup (round 2) ([2021064](https://github.com/pleasedodisturb/kestrel/commit/20210649082811c790af0c6e29849b6aabb9505c))
* eliminate remaining RESP_NOT_FOUND duplication with **RESP_404 spread ([9ad6d2d](https://github.com/pleasedodisturb/kestrel/commit/9ad6d2dbe931af6e4466141be8b34590f4acb96e))
* extract "Not found" to RESP_NOT_FOUND constant (S1192) ([a3d87ca](https://github.com/pleasedodisturb/kestrel/commit/a3d87caf5fdab7d03061e6985aa1b06562ba704a))
* extract nested ternary color chains and improve semantic HTML (S3358, S6853) ([c25711b](https://github.com/pleasedodisturb/kestrel/commit/c25711bd4abebbaec6bdd5f4d3e70354c2b8d2b8))
* extract shared response dicts to reduce SonarCloud duplication ([890b122](https://github.com/pleasedodisturb/kestrel/commit/890b122217fce54f76d0a0d67fefdbeec3926d07))
* format merged test files and remove unused pytest import ([29a4334](https://github.com/pleasedodisturb/kestrel/commit/29a4334fbd7029f2a7aa839851e5d4111b5b34cb))
* format test_pages_links.py ([6965723](https://github.com/pleasedodisturb/kestrel/commit/6965723a1cfe2191a8ccf1fead4d92acc01c4302))
* GitHub Pages 404s + doc link tests + remove pricing doc ([5188dda](https://github.com/pleasedodisturb/kestrel/commit/5188dda7a8383fd06d086402ce45e2024e42f6e9))
* GitHub Pages rendering + doc link tests + remove pricing doc ([0683953](https://github.com/pleasedodisturb/kestrel/commit/0683953db26f7977e98df96d8c6b3570d9c19655))
* lint - use ternary for path resolution ([4d116e2](https://github.com/pleasedodisturb/kestrel/commit/4d116e2d8748d3954dc76704f5f303b283b61a25))
* properly remove try/finally blocks instead of just finally:pass ([5611d13](https://github.com/pleasedodisturb/kestrel/commit/5611d13407e08f9a264b14c8f6e593af04f8f26e))
* README now properly explains all 3 install paths ([6381ccf](https://github.com/pleasedodisturb/kestrel/commit/6381ccff958e224d6f36c228ed819698aa1a1781))
* README properly explains pip install, Docker, and Codespaces ([d7edade](https://github.com/pleasedodisturb/kestrel/commit/d7edade2edf96e00d99924e73315a46918835c4b))
* reduce test code duplication for SonarCloud quality gate ([2b95ad2](https://github.com/pleasedodisturb/kestrel/commit/2b95ad2a95a6024647c912a5904aacc9f3e18e4e))
* remove pricing doc, fix GitHub Pages doc rendering ([5bd2b52](https://github.com/pleasedodisturb/kestrel/commit/5bd2b52717a764e7f784aa90bc7c2849eb4959dc))
* remove pricing strategy from public repo, fix Jekyll config ([5ac81aa](https://github.com/pleasedodisturb/kestrel/commit/5ac81aa78e37503a0cfcc0326ce1ab086b824817))
* replace URL substring checks with hostname validation (18 CodeQL alerts) ([#35](https://github.com/pleasedodisturb/kestrel/issues/35)) ([e82e89b](https://github.com/pleasedodisturb/kestrel/commit/e82e89b327a9b54cf86f618df40eee375c140d49))
* resolve CI failures — ruff format + move scoreColor to utils ([9c2b857](https://github.com/pleasedodisturb/kestrel/commit/9c2b857484e85f8bd55c33e993484c809cddd4c5))
* resolve leftover SonarCloud issues (S8410, S8415, S1244, S117) ([8b69476](https://github.com/pleasedodisturb/kestrel/commit/8b69476100c3782354fb2ba47085d244e7259cc1))
* resolve SonarCloud issues across 6 batches (S8410, S8415, S1192, S108, S3776, S3358) ([a5b6897](https://github.com/pleasedodisturb/kestrel/commit/a5b6897a266fcfeaf716602b97e5c90b1d85b3c6))
* resolve TypeScript/React SonarCloud issues in frontend (S6759, S6853, S3358, etc.) ([052975d](https://github.com/pleasedodisturb/kestrel/commit/052975d1e39683206137bf255211659967794aec)), closes [#60](https://github.com/pleasedodisturb/kestrel/issues/60)
* **security:** batch backend fixes for [#24](https://github.com/pleasedodisturb/kestrel/issues/24), [#25](https://github.com/pleasedodisturb/kestrel/issues/25), [#18](https://github.com/pleasedodisturb/kestrel/issues/18) ([#102](https://github.com/pleasedodisturb/kestrel/issues/102)) ([8f67baf](https://github.com/pleasedodisturb/kestrel/commit/8f67baf1f05776ec9b16d6511ca5c2b1cfee4ec8))
* SonarCloud - 61 float comparisons + 19 empty blocks (80 issues) ([9633491](https://github.com/pleasedodisturb/kestrel/commit/9633491c9be35dc75877c267358d728ccb96e72d))
* SonarCloud - 80 issues (float comparisons + empty blocks) ([df5056f](https://github.com/pleasedodisturb/kestrel/commit/df5056f79b8f4b647f33a57e51e46265be484f98))
* SonarCloud - remove 119 redundant response_model + 33 unused vars ([b36b345](https://github.com/pleasedodisturb/kestrel/commit/b36b345f31c18e33183d9a94dbda514e9193b5e0))
* SonarCloud - remove 119 redundant response_model, fix unused vars ([eac47d5](https://github.com/pleasedodisturb/kestrel/commit/eac47d54a45975137e7ff65e5d85cd3fbdb00bb9))
* SonarCloud React - readonly props, keyboard a11y, form labels ([752aa96](https://github.com/pleasedodisturb/kestrel/commit/752aa966b52c50739caa6bc65df16efc2ef9c404))
* SonarCloud React - readonly props, keyboard a11y, form labels (107 issues) ([1db84d1](https://github.com/pleasedodisturb/kestrel/commit/1db84d179f46352051b899d159fffee49408f96a))
* SonarCloud S117 - rename MockClient to mock_client (22 issues) ([5421b10](https://github.com/pleasedodisturb/kestrel/commit/5421b10526b15b9e999b6b66ea2cb64195f237c1))
* SonarCloud S117 - rename MockClient to snake_case (22 issues) ([98ac01e](https://github.com/pleasedodisturb/kestrel/commit/98ac01e94e37a0a4d3afcbd0345c1abc4206659e))
* SonarCloud security - log injection, DoS, path traversal ([7837f80](https://github.com/pleasedodisturb/kestrel/commit/7837f8053803f3e8ac7f336612f7e5e7dc109bf8))
* SonarCloud security - sanitize logs, bound loops, validate paths ([b3ebb72](https://github.com/pleasedodisturb/kestrel/commit/b3ebb72a3a74bef892a6f718555864c27585bc27))
* unused variables, float equality, naming conventions (S1481+S1244+S117) ([92e7077](https://github.com/pleasedodisturb/kestrel/commit/92e70776f17fb229f877dbd26a9b34dc34101365)), closes [#54](https://github.com/pleasedodisturb/kestrel/issues/54)


### Documentation

* add illustration credits (Maginary AI) and usage guide ([93d1ccd](https://github.com/pleasedodisturb/kestrel/commit/93d1ccd62abeee466d1d51aa2d2d9e68a6336527))
* add Perplexity Computer to job search tool comparison ([#94](https://github.com/pleasedodisturb/kestrel/issues/94)) ([fdc2b76](https://github.com/pleasedodisturb/kestrel/commit/fdc2b7668fd0b331b8482d43224dd9eb06764943))
* extract mobile UX findings for web responsive design ([#122](https://github.com/pleasedodisturb/kestrel/issues/122)) ([8d4f98c](https://github.com/pleasedodisturb/kestrel/commit/8d4f98ce5bf3756405134155899a0c98c75de85f))
