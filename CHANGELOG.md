# Changelog

## [0.24.1](https://github.com/pleasedodisturb/kestrel/compare/v0.24.0...v0.24.1) (2026-08-02)


### Bug Fixes

* **G-1427:** Web Storage shim covers Node 26's undefined localStorage global ([#491](https://github.com/pleasedodisturb/kestrel/issues/491)) ([3dce5ae](https://github.com/pleasedodisturb/kestrel/commit/3dce5aefd637ad4f45d8d9551b949a79a62afdc8))

## [0.24.0](https://github.com/pleasedodisturb/kestrel/compare/v0.23.1...v0.24.0) (2026-08-02)


### Features

* **G-1391:** browser extension Phase 1 — THE EYE (capture + inline score + gap + auto-log) ([#478](https://github.com/pleasedodisturb/kestrel/issues/478)) ([ae4f316](https://github.com/pleasedodisturb/kestrel/commit/ae4f31667a5800e5892e277ff1af285353c93a3a))


### Bug Fixes

* **G-1391:** single-pass HTML-entity decode in stripHtml (js/double-escaping) ([#479](https://github.com/pleasedodisturb/kestrel/issues/479)) ([d58be8b](https://github.com/pleasedodisturb/kestrel/commit/d58be8baa3a2b1e4f9f8b874efa115ade0ce6df2))


### Dependencies

* bump @tanstack/react-query in /frontend in the tanstack group ([#487](https://github.com/pleasedodisturb/kestrel/issues/487)) ([c1e7458](https://github.com/pleasedodisturb/kestrel/commit/c1e74585128bcb28ff98a2a48244345386bb6fc4))
* bump the eslint group in /frontend with 2 updates ([#486](https://github.com/pleasedodisturb/kestrel/issues/486)) ([812b890](https://github.com/pleasedodisturb/kestrel/commit/812b89083acb50c26ddd24e51270068cb39c5bb4))
* bump the react group in /frontend with 2 updates ([#484](https://github.com/pleasedodisturb/kestrel/issues/484)) ([01cef5f](https://github.com/pleasedodisturb/kestrel/commit/01cef5f13bbeeeebd5f7c4e3fcd9259bfcd92a26))
* bump the tailwind group across 1 directory with 2 updates ([#488](https://github.com/pleasedodisturb/kestrel/issues/488)) ([ded357f](https://github.com/pleasedodisturb/kestrel/commit/ded357f6c457e6837668896fc50a2c6a42ea9375))
* bump the vitest group across 1 directory with 3 updates ([#489](https://github.com/pleasedodisturb/kestrel/issues/489)) ([d68dafc](https://github.com/pleasedodisturb/kestrel/commit/d68dafcfd5fcb7ef6f536e7010ddd62c8da9aaf2))
* **G-1412:** react-router 7.18.1 + brace-expansion/postcss advisory bumps (frontend) ([#476](https://github.com/pleasedodisturb/kestrel/issues/476)) ([3eeb600](https://github.com/pleasedodisturb/kestrel/commit/3eeb6001e9b7e9701ebe3d817e89f81bf1d3381a))
* update openai requirement from &gt;=2.44.0 to &gt;=2.50.0 ([#485](https://github.com/pleasedodisturb/kestrel/issues/485)) ([80becab](https://github.com/pleasedodisturb/kestrel/commit/80becab47eb80788c50c58db4698cc1c20cb3a1e))

## [0.23.1](https://github.com/pleasedodisturb/kestrel/compare/v0.23.0...v0.23.1) (2026-07-23)


### Bug Fixes

* **G-1412:** code-scanning backlog — CodeQL highs, workflow token permissions, SHA/digest pinning ([#474](https://github.com/pleasedodisturb/kestrel/issues/474)) ([a57f544](https://github.com/pleasedodisturb/kestrel/commit/a57f5442b78ffd6cdc092b5125d2cba9d4968e19))

## [0.23.0](https://github.com/pleasedodisturb/kestrel/compare/v0.22.0...v0.23.0) (2026-07-22)


### Features

* **G-1351:** ESCO occupations taxonomy cache + loader + bundled fixture (Phase A) ([#467](https://github.com/pleasedodisturb/kestrel/issues/467)) ([337dbc3](https://github.com/pleasedodisturb/kestrel/commit/337dbc33e4e0fb939ab7034512bdf5a578a0df0c))
* **G-1351:** occupation matcher — family/title→tier classifier + in-package taxonomy consumer (Phase B) ([#468](https://github.com/pleasedodisturb/kestrel/issues/468)) ([aab8a97](https://github.com/pleasedodisturb/kestrel/commit/aab8a97d9279f0035a10926d53bc5a241b551a07))
* **G-1351:** shadow-first occupation signal — cascade 4th signal + distillation logging + startup populate (Phase C) ([#473](https://github.com/pleasedodisturb/kestrel/issues/473)) ([cfa9832](https://github.com/pleasedodisturb/kestrel/commit/cfa9832d1665fb480e8b478a0bc239d0e21ffcd8))


### Bug Fixes

* **G-1348:** repair the dead OpenAI provider + cross-provider contract tests ([#464](https://github.com/pleasedodisturb/kestrel/issues/464)) ([5548482](https://github.com/pleasedodisturb/kestrel/commit/5548482f049a9199f9ba396de47400677cfc8233))
* **G-1350:** make in-package migrations the single source of truth ([#465](https://github.com/pleasedodisturb/kestrel/issues/465)) ([2bb1bae](https://github.com/pleasedodisturb/kestrel/commit/2bb1bae7f33d91d72c33d348bd442dbcef696a12))
* **G-1378:** guard openrouter premium-model routing in fallback chains ([#461](https://github.com/pleasedodisturb/kestrel/issues/461)) ([d83d2ed](https://github.com/pleasedodisturb/kestrel/commit/d83d2edb5526c827d94758f9569e6f920a0debce))


### Dependencies

* **G-1384:** bump brace-expansion to 5.0.7 in frontend + dashboard ([#466](https://github.com/pleasedodisturb/kestrel/issues/466)) ([3838e13](https://github.com/pleasedodisturb/kestrel/commit/3838e13033cfc2c86f94a56176f6b98d5c02ae36))
* **G-1408:** fix all 9 open Dependabot alerts (1 critical) — extension, dashboard, worker ([#472](https://github.com/pleasedodisturb/kestrel/issues/472)) ([5cf50ea](https://github.com/pleasedodisturb/kestrel/commit/5cf50eae1057a98251838510b4972aecf095918c))

## [0.22.0](https://github.com/pleasedodisturb/kestrel/compare/v0.21.0...v0.22.0) (2026-07-17)


### Features

* **G-1337:** calibration hygiene — 0–5 judge scale + spread metrics + per-provider calibration ([#455](https://github.com/pleasedodisturb/kestrel/issues/455)) ([2367944](https://github.com/pleasedodisturb/kestrel/commit/23679444eab063b059f7491961599635c44e5729))
* **G-1338:** confidence-routed cascade (conservative, shadow-first) — part 2 ([#458](https://github.com/pleasedodisturb/kestrel/issues/458)) ([9fd700d](https://github.com/pleasedodisturb/kestrel/commit/9fd700dcba8437de25a55a4da3552af61b92c82c))
* **G-1338:** scoring features — distillation logging + ESCO overlap + relative scoring ([#457](https://github.com/pleasedodisturb/kestrel/issues/457)) ([c99709f](https://github.com/pleasedodisturb/kestrel/commit/c99709f7b923887aaea3239137e70328dad5dacd))


### Bug Fixes

* **G-1352:** scoring-v2 cross-phase cleanup (shadow gate, distillation desire, batch parity) ([#459](https://github.com/pleasedodisturb/kestrel/issues/459)) ([80a0561](https://github.com/pleasedodisturb/kestrel/commit/80a0561d79aff2b579d9f5306aba0fa353dee4e3))

## [0.21.0](https://github.com/pleasedodisturb/kestrel/compare/v0.20.0...v0.21.0) (2026-07-15)


### Features

* **G-1335:** role-fit hard gate + company-prestige cap (halo fix) ([#452](https://github.com/pleasedodisturb/kestrel/issues/452)) ([bdd664a](https://github.com/pleasedodisturb/kestrel/commit/bdd664a099484736de2d2475c682ec86e7e62fba))
* **G-1336:** scoring eval infrastructure — golden-set κ/NDCG + shadow-mode + drift canary ([#454](https://github.com/pleasedodisturb/kestrel/issues/454)) ([a23bd80](https://github.com/pleasedodisturb/kestrel/commit/a23bd80993ca6b17821f84c72013961e627da0b4))


### Bug Fixes

* **G-1349:** bump setuptools to &gt;=83.0.0 (PYSEC-2026-3447) ([#453](https://github.com/pleasedodisturb/kestrel/issues/453)) ([07c9640](https://github.com/pleasedodisturb/kestrel/commit/07c96400af21f08acc600f89dde91d24f3859083))


### Documentation

* **G-1335:** add 2026-07 scoring-technique audit (7-agent research sweep) ([#450](https://github.com/pleasedodisturb/kestrel/issues/450)) ([e24e05a](https://github.com/pleasedodisturb/kestrel/commit/e24e05a1e3e2d09a933b0ccb938479a293c79900))

## [0.20.0](https://github.com/pleasedodisturb/kestrel/compare/v0.19.0...v0.20.0) (2026-07-09)


### Features

* **G-1315:** default Mistral provider to Small (benchmark-driven scoring) ([#448](https://github.com/pleasedodisturb/kestrel/issues/448)) ([0489a9d](https://github.com/pleasedodisturb/kestrel/commit/0489a9d7af8e421a9d3fdcacade53f3bd58c600f))

## [0.19.0](https://github.com/pleasedodisturb/kestrel/compare/v0.18.0...v0.19.0) (2026-07-09)


### Features

* **G-1282:** port tiered application model + SmartRecruiters/Personio scrapers (PII-stripped) ([#439](https://github.com/pleasedodisturb/kestrel/issues/439)) ([3804900](https://github.com/pleasedodisturb/kestrel/commit/38049007a7e48c358ab6d5c30600c55149b21b59))


### Bug Fixes

* **G-1295:** correct npm-package README license from MIT to AGPL-3.0-or-later ([#440](https://github.com/pleasedodisturb/kestrel/issues/440)) ([b5f746b](https://github.com/pleasedodisturb/kestrel/commit/b5f746b54243fe0984d9e042e5ffb143ddc79262))


### Documentation

* **G-1305:** add COE for the initial-commit PII exposure ([#445](https://github.com/pleasedodisturb/kestrel/issues/445)) ([e766c04](https://github.com/pleasedodisturb/kestrel/commit/e766c0413510fd028008667cf1648f6370a06349))
* **G-1315:** explain cost-optimal fallback-chain ordering ([#446](https://github.com/pleasedodisturb/kestrel/issues/446)) ([dea0d6a](https://github.com/pleasedodisturb/kestrel/commit/dea0d6ac60b4098bc7163dd53ff19c90b3a9cbcb))

## [0.18.0](https://github.com/pleasedodisturb/kestrel/compare/v0.17.1...v0.18.0) (2026-07-05)


### Features

* **G-1282:** port blocklist + parameterized geo gate from private fork (PII-stripped) ([#436](https://github.com/pleasedodisturb/kestrel/issues/436)) ([d02ca5a](https://github.com/pleasedodisturb/kestrel/commit/d02ca5a1dc814b416efceab5ce26e898e1ca3e64))


### Dependencies

* bump @size-limit/file from 11.2.0 to 12.1.0 in /frontend ([#425](https://github.com/pleasedodisturb/kestrel/issues/425)) ([c11603c](https://github.com/pleasedodisturb/kestrel/commit/c11603c4f4d793d008d0241e7fe75dc24fb8468f))
* bump size-limit from 11.2.0 to 12.1.0 in /frontend ([#426](https://github.com/pleasedodisturb/kestrel/issues/426)) ([9e0ad53](https://github.com/pleasedodisturb/kestrel/commit/9e0ad5322736389bd47710b107f36437134766ac))

## [0.17.1](https://github.com/pleasedodisturb/kestrel/compare/v0.17.0...v0.17.1) (2026-07-05)


### Documentation

* **G-1281:** distill writing system — anti-slop, voice corpus, cover letters, LinkedIn ([#433](https://github.com/pleasedodisturb/kestrel/issues/433)) ([8057e9d](https://github.com/pleasedodisturb/kestrel/commit/8057e9d4d5da2f2d6ce177d5b18a50a11dadc4a3))

## [0.17.0](https://github.com/pleasedodisturb/kestrel/compare/v0.16.0...v0.17.0) (2026-07-05)


### Features

* **G-1275:** switch npm publish to OIDC Trusted Publishing — no token needed ([#428](https://github.com/pleasedodisturb/kestrel/issues/428)) ([e5d2c21](https://github.com/pleasedodisturb/kestrel/commit/e5d2c21a20478e2f1ae187a61cbddf1d14ce8d78))
* **G-1277:** automate security-fix inclusion — Dependabot automerge, docker ecosystem, weekly rebuild ([#417](https://github.com/pleasedodisturb/kestrel/issues/417)) ([eef5deb](https://github.com/pleasedodisturb/kestrel/commit/eef5debc108ef4d9204ebcc796012126306d2902))


### Bug Fixes

* **G-1274:** repair disabled workflows — scorecard pin, daily-scan guard, release-checks ([#415](https://github.com/pleasedodisturb/kestrel/issues/415)) ([f7b1a5e](https://github.com/pleasedodisturb/kestrel/commit/f7b1a5eea078d9b5ff23149cc7c757de4a576970))
* **G-1288:** revert runtime to python:3.11-slim, guard runtime images from auto-bumps ([#427](https://github.com/pleasedodisturb/kestrel/issues/427)) ([16f0ce4](https://github.com/pleasedodisturb/kestrel/commit/16f0ce4358763856f7606bdcc42f214994604774))


### Dependencies

* bump @tanstack/react-query in /frontend in the tanstack group ([#411](https://github.com/pleasedodisturb/kestrel/issues/411)) ([e17d7f8](https://github.com/pleasedodisturb/kestrel/commit/e17d7f8c531893185e32bb28294b66edf222222e))
* bump globals from 17.5.0 to 17.7.0 in /frontend ([#414](https://github.com/pleasedodisturb/kestrel/issues/414)) ([2341a70](https://github.com/pleasedodisturb/kestrel/commit/2341a707423a983bad78cf10930cfc0cc96172c6))
* bump python from 3.11-slim to 3.14-slim ([#418](https://github.com/pleasedodisturb/kestrel/issues/418)) ([1c84cab](https://github.com/pleasedodisturb/kestrel/commit/1c84cab7877130aeb59a255247a8a8d4123e79e1))
* bump the eslint group across 1 directory with 3 updates ([#409](https://github.com/pleasedodisturb/kestrel/issues/409)) ([8f613b9](https://github.com/pleasedodisturb/kestrel/commit/8f613b90c2552c0b3eb67a35ed7549fe2b0e4973))
* bump the tailwind group across 1 directory with 2 updates ([#412](https://github.com/pleasedodisturb/kestrel/issues/412)) ([c7bce76](https://github.com/pleasedodisturb/kestrel/commit/c7bce7625a7b3877cd5c7a6b556f7d631ebcee32))
* bump the vitest group across 1 directory with 2 updates ([#413](https://github.com/pleasedodisturb/kestrel/issues/413)) ([ec3171b](https://github.com/pleasedodisturb/kestrel/commit/ec3171be6f1fb28b79a36e6b23890e7a247a10eb))
* bump typescript from 6.0.2 to 6.0.3 in /frontend ([#424](https://github.com/pleasedodisturb/kestrel/issues/424)) ([bc17c50](https://github.com/pleasedodisturb/kestrel/commit/bc17c5000796ee8ffdf47a0834ca19fcc52e7897))
* update openai requirement from &gt;=2.41.0 to &gt;=2.44.0 ([#410](https://github.com/pleasedodisturb/kestrel/issues/410)) ([190b9d5](https://github.com/pleasedodisturb/kestrel/commit/190b9d5987d40f259577ccc2c4ec9113d8a76834))

## [0.16.0](https://github.com/pleasedodisturb/kestrel/compare/v0.15.2...v0.16.0) (2026-06-28)


### Features

* **G-1200:** declare Railway volume via requiredMountPath ([#400](https://github.com/pleasedodisturb/kestrel/issues/400)) ([bcc4a55](https://github.com/pleasedodisturb/kestrel/commit/bcc4a5536cbfd20a0b68d5e5feb5f22b9558364d))
* **G-1217:** upstream Eyas discovery-pipeline improvements (PII-free) ([#404](https://github.com/pleasedodisturb/kestrel/issues/404)) ([2e8d94f](https://github.com/pleasedodisturb/kestrel/commit/2e8d94ff5866e663f7aa4868620bc701105be809))


### Bug Fixes

* **deploy:** make Railway one-click deploy actually work ([#398](https://github.com/pleasedodisturb/kestrel/issues/398)) ([8c3c65b](https://github.com/pleasedodisturb/kestrel/commit/8c3c65b99dd52aee49620989618ab591bfe2b25e))

## [0.15.2](https://github.com/pleasedodisturb/kestrel/compare/v0.15.1...v0.15.2) (2026-06-08)


### Documentation

* **G-842:** CLAUDE.md cleanup — fix stale refs + strip GSD boilerplate ([#389](https://github.com/pleasedodisturb/kestrel/issues/389)) ([9140093](https://github.com/pleasedodisturb/kestrel/commit/9140093216b33cb2c7a41df61d602a1307681439))
* **G-851:** fix stale test-count badge in REFERENCE.md ([#390](https://github.com/pleasedodisturb/kestrel/issues/390)) ([cece6ac](https://github.com/pleasedodisturb/kestrel/commit/cece6ac8f020993240e09e56fd03fadecc62f079))


### Dependencies

* bump @tanstack/react-query from 5.100.9 to 5.101.0 in /frontend ([#386](https://github.com/pleasedodisturb/kestrel/issues/386)) ([71dbbf1](https://github.com/pleasedodisturb/kestrel/commit/71dbbf1cfb5a12c82e4dde009087be5604a492a4))
* bump react-router and react-router-dom in /frontend ([#392](https://github.com/pleasedodisturb/kestrel/issues/392)) ([232bf32](https://github.com/pleasedodisturb/kestrel/commit/232bf32a13584b56551720d0e8fe190906310916))
* bump the eslint group in /frontend with 2 updates ([#385](https://github.com/pleasedodisturb/kestrel/issues/385)) ([36df76b](https://github.com/pleasedodisturb/kestrel/commit/36df76b99608b4b831f13696ef3aa26da076a5fc))
* bump the react group in /frontend with 3 updates ([#384](https://github.com/pleasedodisturb/kestrel/issues/384)) ([d567c4e](https://github.com/pleasedodisturb/kestrel/commit/d567c4ed4ec9cb28a59175eb27212d2b325795c1))
* bump the tailwind group in /frontend with 2 updates ([#387](https://github.com/pleasedodisturb/kestrel/issues/387)) ([ecf71d6](https://github.com/pleasedodisturb/kestrel/commit/ecf71d6b02ce04120e6db88731054aee5f9a0f98))
* bump the vitest group in /frontend with 2 updates ([#388](https://github.com/pleasedodisturb/kestrel/issues/388)) ([5f4ec68](https://github.com/pleasedodisturb/kestrel/commit/5f4ec6818ee56760e0b1e44ab66485e3e163d635))
* update openai requirement from &gt;=2.35.1 to &gt;=2.40.0 ([#380](https://github.com/pleasedodisturb/kestrel/issues/380)) ([bfaa9f7](https://github.com/pleasedodisturb/kestrel/commit/bfaa9f75f8c3147e04e8f1380dcc185a6722bda4))

## [0.15.1](https://github.com/pleasedodisturb/kestrel/compare/v0.15.0...v0.15.1) (2026-05-17)


### Documentation

* **G-677:** land repo-coaching playbook (research + masterlist + QUICK-APPLY + 19 snippets) ([#374](https://github.com/pleasedodisturb/kestrel/issues/374)) ([25b55f6](https://github.com/pleasedodisturb/kestrel/commit/25b55f6cb185bcfae453e011cd415e14ee9a12c0))

## [0.15.0](https://github.com/pleasedodisturb/kestrel/compare/v0.14.3...v0.15.0) (2026-05-12)


### Features

* **G-626:** dispatch React-combobox dropdowns in batch_apply_browser ([#370](https://github.com/pleasedodisturb/kestrel/issues/370)) ([7935768](https://github.com/pleasedodisturb/kestrel/commit/7935768d71667a0ef9cdfd10bec4a7832652e67e))
* **G-627:** per-role qualifying-question overlay in batch_apply_browser ([#369](https://github.com/pleasedodisturb/kestrel/issues/369)) ([6047148](https://github.com/pleasedodisturb/kestrel/commit/6047148c9785987be6ba846a208f7148a66f9d19)), closes [#347](https://github.com/pleasedodisturb/kestrel/issues/347)
* **G-630:** add remotely.de + arbeitnow EU-tech sources to daily_pipeline ([#372](https://github.com/pleasedodisturb/kestrel/issues/372)) ([c6e9c51](https://github.com/pleasedodisturb/kestrel/commit/c6e9c518741aad55323a9e9b6a650ae41d51c9d4))
* **G-636:** tier-0 ATS poller (Greenhouse/Lever/Ashby) for dream companies ([#371](https://github.com/pleasedodisturb/kestrel/issues/371)) ([42538b5](https://github.com/pleasedodisturb/kestrel/commit/42538b5a7d332368b5f5cdb1947737485c49bda1))


### Bug Fixes

* **G-625:** type-aware setter for textarea fill in batch_apply_browser ([#373](https://github.com/pleasedodisturb/kestrel/issues/373)) ([e334b49](https://github.com/pleasedodisturb/kestrel/commit/e334b492daa360da1e761ad0f62797ffd510b458))
* **profiles:** refuse DELETE if profile owns child rows; add rotating snapshot script ([#367](https://github.com/pleasedodisturb/kestrel/issues/367)) ([75d837e](https://github.com/pleasedodisturb/kestrel/commit/75d837eafa6bc8cd106f288b4adcc4cd98b1673a))

## [0.14.3](https://github.com/pleasedodisturb/kestrel/compare/v0.14.2...v0.14.3) (2026-05-11)


### Dependencies

* **frontend:** bump eslint group manually (replaces stuck [#355](https://github.com/pleasedodisturb/kestrel/issues/355)) ([#363](https://github.com/pleasedodisturb/kestrel/issues/363)) ([b4bbf53](https://github.com/pleasedodisturb/kestrel/commit/b4bbf5306a1dcdbba02e72ae4faca1fd569cda19))

## [0.14.2](https://github.com/pleasedodisturb/kestrel/compare/v0.14.1...v0.14.2) (2026-05-07)


### Bug Fixes

* **frontend:** resolve react-hooks/set-state-in-effect lint error ([#361](https://github.com/pleasedodisturb/kestrel/issues/361)) ([6ca83b5](https://github.com/pleasedodisturb/kestrel/commit/6ca83b589e1aa5155685e421a7683145231b7b50))

## [0.14.1](https://github.com/pleasedodisturb/kestrel/compare/v0.14.0...v0.14.1) (2026-05-07)


### Dependencies

* bump the tailwind group across 1 directory with 2 updates ([#358](https://github.com/pleasedodisturb/kestrel/issues/358)) ([87a8114](https://github.com/pleasedodisturb/kestrel/commit/87a81142b28bfb49c1806d29f9f9645befeb883d))

## [0.14.0](https://github.com/pleasedodisturb/kestrel/compare/v0.13.0...v0.14.0) (2026-05-07)


### Features

* initial public roadmap with deep dives and one-click dev environment ([#350](https://github.com/pleasedodisturb/kestrel/issues/350)) ([b7b6e03](https://github.com/pleasedodisturb/kestrel/commit/b7b6e03f3bfd728c098327979bd4189bdc73c17c))


### Bug Fixes

* harden AI isolation guard against substring spoofing ([#353](https://github.com/pleasedodisturb/kestrel/issues/353)) ([229cf6f](https://github.com/pleasedodisturb/kestrel/commit/229cf6f6864fc38545a82a810f7e4c3a5a1d6f3a))


### Dependencies

* bump @tanstack/react-query in /frontend in the tanstack group ([#357](https://github.com/pleasedodisturb/kestrel/issues/357)) ([a6b717c](https://github.com/pleasedodisturb/kestrel/commit/a6b717ce543501d8a4b7a6b6ad6edb082e22ef54))
* bump @types/node from 24.12.0 to 25.6.0 in /frontend ([#344](https://github.com/pleasedodisturb/kestrel/issues/344)) ([6b7ba13](https://github.com/pleasedodisturb/kestrel/commit/6b7ba13515df6cd5211ea740cf0e4042a83b6ad2))
* bump globals from 17.4.0 to 17.5.0 in /frontend ([#343](https://github.com/pleasedodisturb/kestrel/issues/343)) ([4b6ed73](https://github.com/pleasedodisturb/kestrel/commit/4b6ed73f457fa05717859ac11c664877b32d23d5))
* bump react-router-dom from 7.13.1 to 7.14.2 in /frontend ([#336](https://github.com/pleasedodisturb/kestrel/issues/336)) ([3ebe316](https://github.com/pleasedodisturb/kestrel/commit/3ebe31644f5d29716304a079bf80c0d07875b292))
* bump the react group across 1 directory with 2 updates ([#354](https://github.com/pleasedodisturb/kestrel/issues/354)) ([b986940](https://github.com/pleasedodisturb/kestrel/commit/b98694020a14137fe151f0f74f6eb6d7c7b8452f))
* bump typescript-eslint from 8.57.0 to 8.59.1 in /frontend ([#341](https://github.com/pleasedodisturb/kestrel/issues/341)) ([2d4f8ff](https://github.com/pleasedodisturb/kestrel/commit/2d4f8ff0a6fbaf9a2bbd724f9a1833ea313ac84f))
* bump vite from 8.0.7 to 8.0.11 in /frontend ([#359](https://github.com/pleasedodisturb/kestrel/issues/359)) ([5235469](https://github.com/pleasedodisturb/kestrel/commit/52354691c9789626af9ce0eb405757c1c9b73b23))
* update openai requirement from &gt;=1.0.0 to &gt;=2.35.1 ([#342](https://github.com/pleasedodisturb/kestrel/issues/342)) ([768ae7d](https://github.com/pleasedodisturb/kestrel/commit/768ae7d7378fd8aabe3ce7927dc8977238771190))
* update pandas requirement from &lt;3,&gt;=2.2.0 to &gt;=2.2.0,&lt;4 ([#335](https://github.com/pleasedodisturb/kestrel/issues/335)) ([25b42e0](https://github.com/pleasedodisturb/kestrel/commit/25b42e0db5a12fdae2f603a8c0b8ab366bd42108))
* update pyyaml requirement from &gt;=6.0 to &gt;=6.0.3 ([#340](https://github.com/pleasedodisturb/kestrel/issues/340)) ([caa49c9](https://github.com/pleasedodisturb/kestrel/commit/caa49c97a83096d1b4447c8a54183a2f4d01072b))

## [0.13.0](https://github.com/pleasedodisturb/kestrel/compare/v0.12.0...v0.13.0) (2026-04-27)


### Features

* **G-540, G-541:** add Mistral + Hugging Face AI providers ([#331](https://github.com/pleasedodisturb/kestrel/issues/331)) ([55ac65f](https://github.com/pleasedodisturb/kestrel/commit/55ac65fb75b20afcf28b4c536c2d7dfac7af6d75))


### Bug Fixes

* route daily_pipeline through provider stack + loud failure alarm ([#332](https://github.com/pleasedodisturb/kestrel/issues/332)) ([2ec1e46](https://github.com/pleasedodisturb/kestrel/commit/2ec1e46be4bb7df7793f53867f8955d73fdca7ea))


### Documentation

* add nav index + restructure install by effort level ([#330](https://github.com/pleasedodisturb/kestrel/issues/330)) ([3e24999](https://github.com/pleasedodisturb/kestrel/commit/3e24999e534d141275c387e167a8d80cadc24dd4))
* public roadmap — real screenshots, user story, deploy buttons ([#328](https://github.com/pleasedodisturb/kestrel/issues/328)) ([5c2368e](https://github.com/pleasedodisturb/kestrel/commit/5c2368e15272835c4e6d0cb7c36095a16f63389c))

## [0.12.0](https://github.com/pleasedodisturb/kestrel/compare/v0.11.0...v0.12.0) (2026-04-23)


### Features

* **G-394:** make kestrel the primary CLI entry point, keep career as alias ([#316](https://github.com/pleasedodisturb/kestrel/issues/316)) ([debc225](https://github.com/pleasedodisturb/kestrel/commit/debc225d751990234c98652b21120e6e4f410263))
* **G-407:** enforce PII safety boundary — block personal data from non-ZDR providers ([#311](https://github.com/pleasedodisturb/kestrel/issues/311)) ([268fd08](https://github.com/pleasedodisturb/kestrel/commit/268fd088d84ce0a18377991beabc7a2465b1b4c0))


### Bug Fixes

* **G-401, G-456:** fix flaky CLI test + test_md_to_pdf failures ([#305](https://github.com/pleasedodisturb/kestrel/issues/305)) ([8597990](https://github.com/pleasedodisturb/kestrel/commit/8597990384c5ab8c1e36dd6608495bb8633eba12))
* **G-412:** add test isolation guard — block real AI provider HTTP calls ([#310](https://github.com/pleasedodisturb/kestrel/issues/310)) ([890514c](https://github.com/pleasedodisturb/kestrel/commit/890514caeb7458e844c6c712174f5eb3f0d69b8d))
* **G-412:** format test_ai_isolation_guard.py for ruff ([#322](https://github.com/pleasedodisturb/kestrel/issues/322)) ([5125a53](https://github.com/pleasedodisturb/kestrel/commit/5125a5393724d8e32797d505f12aae55f85f6e92))
* **G-419:** fix SonarCloud coverage report path configuration ([#303](https://github.com/pleasedodisturb/kestrel/issues/303)) ([fe3ab24](https://github.com/pleasedodisturb/kestrel/commit/fe3ab244213b623788282d6bb8ced5a938d4928a))
* **G-457:** recalibrate golden set fixtures for scoring evolution ([6fe9374](https://github.com/pleasedodisturb/kestrel/commit/6fe9374816214ae83f437ac3dd3017b545d14ef0))
* **G-458:** fix ContactCreate enum validation for Schemathesis stateful mode ([#306](https://github.com/pleasedodisturb/kestrel/issues/306)) ([01e1e31](https://github.com/pleasedodisturb/kestrel/commit/01e1e319d9a551e8eae041bdd3fe8f99734f0d27))
* **G-488:** unblock all Docker install paths for new users ([#293](https://github.com/pleasedodisturb/kestrel/issues/293)) ([0a4ba32](https://github.com/pleasedodisturb/kestrel/commit/0a4ba3240e0e16177345602ef6d518d116eb1449))
* **G-491:** fix release gate date parsing and qualifying commit detection ([#308](https://github.com/pleasedodisturb/kestrel/issues/308)) ([7751f6b](https://github.com/pleasedodisturb/kestrel/commit/7751f6bdd414afbd4cae003baa38025f1f143f4e))
* **G-491:** fix release gate heredoc syntax errors ([#315](https://github.com/pleasedodisturb/kestrel/issues/315)) ([8a17d26](https://github.com/pleasedodisturb/kestrel/commit/8a17d268c6befc5cccd9b86232f26440713c1326))
* **G-491:** safely handle failed_checks variable with special characters ([#312](https://github.com/pleasedodisturb/kestrel/issues/312)) ([9376d87](https://github.com/pleasedodisturb/kestrel/commit/9376d879ffeab6b5b7bd08b3e24eb13b71b8ebc2))
* **G-495:** fix discovery test mock/schema breakage (22 CI failures) ([#317](https://github.com/pleasedodisturb/kestrel/issues/317)) ([159f496](https://github.com/pleasedodisturb/kestrel/commit/159f496fdb1afc316a00c470825b8728922f6f60))
* **G-496:** wire observability spans into cache and PII masking layers ([#318](https://github.com/pleasedodisturb/kestrel/issues/318)) ([0aff60f](https://github.com/pleasedodisturb/kestrel/commit/0aff60f77f7c22c3717b87345668a0a9159fc51f))
* **G-497:** add _build_fallback_chain to factory and wire into get_ai_provider ([#319](https://github.com/pleasedodisturb/kestrel/issues/319)) ([412101d](https://github.com/pleasedodisturb/kestrel/commit/412101dd410c359fae556d0679b7bf0321fe7642))
* **G-498:** fix stale test assertions for X-Title header and batch payload ([#320](https://github.com/pleasedodisturb/kestrel/issues/320)) ([6c82021](https://github.com/pleasedodisturb/kestrel/commit/6c820214f6057668804ad85c8c769d37e67d1b08))
* **G-499:** fix doc link tests for reorganized docs directory ([#321](https://github.com/pleasedodisturb/kestrel/issues/321)) ([9a8a647](https://github.com/pleasedodisturb/kestrel/commit/9a8a647748f1d2341329e1ebc4055cbe75667588))
* **G-roadmap:** fix md_to_pdf test failures — undefined variable and empty file crash ([#327](https://github.com/pleasedodisturb/kestrel/issues/327)) ([82a3d2f](https://github.com/pleasedodisturb/kestrel/commit/82a3d2f88c72ba004e8aa63375b7f578033bc920))


### Documentation

* add session summary for 2026-04-23 ([#325](https://github.com/pleasedodisturb/kestrel/issues/325)) ([54142b1](https://github.com/pleasedodisturb/kestrel/commit/54142b1b6a2382d22a03f73e74389185d57728d1))
* **G-464:** move "How we build" section to CONTRIBUTING.md ([#326](https://github.com/pleasedodisturb/kestrel/issues/326)) ([8cd3880](https://github.com/pleasedodisturb/kestrel/commit/8cd38805088639511c4f90517c4e926041b8e9a9))
* **G-464:** rewrite README for first-time users — cut 55%, sharpen hook ([#323](https://github.com/pleasedodisturb/kestrel/issues/323)) ([90a9ba7](https://github.com/pleasedodisturb/kestrel/commit/90a9ba75836772cd980055baba45118f46bece65))
* **G-489:** document release pipeline, smoke tests, and bug sync workflows ([#307](https://github.com/pleasedodisturb/kestrel/issues/307)) ([b3b75a4](https://github.com/pleasedodisturb/kestrel/commit/b3b75a44f765db6497ae6e53a0e55ef7b7537d09))

## [0.11.0](https://github.com/pleasedodisturb/kestrel/compare/v0.10.0...v0.11.0) (2026-04-21)


### Features

* **G-392:** Onboarding Epic — 6 phases, 361 tests ([4866cb4](https://github.com/pleasedodisturb/kestrel/commit/4866cb44c5ac4355a7a3089bf2b760ee413dfdb5))
* **G-439:** integrate pre-filter into discovery pipeline ([#272](https://github.com/pleasedodisturb/kestrel/issues/272)) ([9ec21de](https://github.com/pleasedodisturb/kestrel/commit/9ec21ded85f5a752d030f0c3ac7b7735a37fee05))
* **G-440:** batch scoring — multiple jobs per prompt ([#273](https://github.com/pleasedodisturb/kestrel/issues/273)) ([60212b1](https://github.com/pleasedodisturb/kestrel/commit/60212b13fb72db23aadbb19b9f7f481cf91f3054))
* **G-441:** prompt caching for scoring calls — profile in system prefix ([#274](https://github.com/pleasedodisturb/kestrel/issues/274)) ([13abe3a](https://github.com/pleasedodisturb/kestrel/commit/13abe3af94f50f24f38c939b390e189c25b0ab91))
* **G-442:** add cost presets system (Free/Budget/Quality/Private/Custom) ([#283](https://github.com/pleasedodisturb/kestrel/issues/283)) ([5a0acd3](https://github.com/pleasedodisturb/kestrel/commit/5a0acd340f3044548bd77150c47b498c921ea656))
* **G-443:** integrate Anthropic + OpenAI async Batch APIs for 50% off scoring ([#286](https://github.com/pleasedodisturb/kestrel/issues/286)) ([49940da](https://github.com/pleasedodisturb/kestrel/commit/49940da673ceba6f3a9e9aa7169fa5f03ec8e707))
* **G-445:** add Groq provider (OpenAI-compatible) ([#280](https://github.com/pleasedodisturb/kestrel/issues/280)) ([9eb47c3](https://github.com/pleasedodisturb/kestrel/commit/9eb47c33dc088cee3fd00af78499470ede5a1d58))
* **G-446:** add OpenAI direct provider ([#261](https://github.com/pleasedodisturb/kestrel/issues/261)) ([81ef3a8](https://github.com/pleasedodisturb/kestrel/commit/81ef3a826b6f9a7d50a1b17507ff20071121e075))
* **G-447:** add xAI/Grok provider with red privacy tier ([#284](https://github.com/pleasedodisturb/kestrel/issues/284)) ([d16aaaf](https://github.com/pleasedodisturb/kestrel/commit/d16aaaf60a70bc3b09c03ad0f0eaee1eacb1b023))
* **G-448:** add Google Gemini AI provider ([#287](https://github.com/pleasedodisturb/kestrel/issues/287)) ([787dff1](https://github.com/pleasedodisturb/kestrel/commit/787dff1e3e6896d860aceafc95dde247e5473d8d))
* **G-449:** add provider privacy disclosures to AI Providers integration panel ([#270](https://github.com/pleasedodisturb/kestrel/issues/270)) ([bf32fc8](https://github.com/pleasedodisturb/kestrel/commit/bf32fc8698e7c681c40ae1c5b79eabfc5fd0e2cb))
* **G-450:** add Kestrel MCP server for Claude Code ([#262](https://github.com/pleasedodisturb/kestrel/issues/262)) ([7bb8b5a](https://github.com/pleasedodisturb/kestrel/commit/7bb8b5aa36db68a360e200e417106fcd99dc5acb))
* **G-451:** OpenRouter OAuth PKCE onboarding flow ([#263](https://github.com/pleasedodisturb/kestrel/issues/263)) ([ac1a37c](https://github.com/pleasedodisturb/kestrel/commit/ac1a37ca22f88b38ec80a1c2cff5e00b1da458e0))
* **G-453:** batch scoring quality A/B test spike ([#278](https://github.com/pleasedodisturb/kestrel/issues/278)) ([28b8423](https://github.com/pleasedodisturb/kestrel/commit/28b8423de93deb63f8278b8be5114fb2c76e1fe3))


### Bug Fixes

* **G-464:** restore version to 0.10.0 after G-392 regression ([#276](https://github.com/pleasedodisturb/kestrel/issues/276)) ([8a73f78](https://github.com/pleasedodisturb/kestrel/commit/8a73f787218e0eb66c4743738ed4a3fdcccda108))
* **G-464:** simplify Mermaid diagrams for GitHub rendering ([#267](https://github.com/pleasedodisturb/kestrel/issues/267)) ([324cb8a](https://github.com/pleasedodisturb/kestrel/commit/324cb8a1cfa4d57b6a6a06ea8f3834d5d973e1a3))


### Documentation

* **G-438:** comprehensive documentation for cost control epic ([#288](https://github.com/pleasedodisturb/kestrel/issues/288)) ([4e5468d](https://github.com/pleasedodisturb/kestrel/commit/4e5468d91965ccd235dfbb15d6a68f3fb560f052))
* **G-444:** add edutainment guide for AI costs, tiers, and privacy ([#268](https://github.com/pleasedodisturb/kestrel/issues/268)) ([2fbbd8c](https://github.com/pleasedodisturb/kestrel/commit/2fbbd8c1f1e95717e37a448e073ade005e18f36f))
* **G-452:** add automation paths guide ([#269](https://github.com/pleasedodisturb/kestrel/issues/269)) ([df89353](https://github.com/pleasedodisturb/kestrel/commit/df8935307359f10e314d1963b20b3202579cdc4a))
* **G-454:** research OpenRouter rate limit tiers at $0/$10/$50 balance ([#271](https://github.com/pleasedodisturb/kestrel/issues/271)) ([961af7b](https://github.com/pleasedodisturb/kestrel/commit/961af7b955c8715f2e297aad52527f1bf6ea8099))
* **G-455:** research preset tier validation with real model benchmarks ([#279](https://github.com/pleasedodisturb/kestrel/issues/279)) ([41f9292](https://github.com/pleasedodisturb/kestrel/commit/41f92927e6d17bfc63bcfd8a15d5eb38521d12aa))
* **G-464:** documentation audit, reorg & rewrite ([#266](https://github.com/pleasedodisturb/kestrel/issues/266)) ([1b2c0b0](https://github.com/pleasedodisturb/kestrel/commit/1b2c0b044599238596035b6305bbf5407804846f))
* **G-465:** mark mobile app as planned future release in CLAUDE.md ([#290](https://github.com/pleasedodisturb/kestrel/issues/290)) ([1da0cdf](https://github.com/pleasedodisturb/kestrel/commit/1da0cdf91cbd682a279bcf3eef90b70b3acf6eec))

## [0.5.2](https://github.com/pleasedodisturb/kestrel/compare/v0.5.1...v0.5.2) (2026-04-19)


### Bug Fixes

* **G-385:** scrub personal data from public repo (29 files) ([#220](https://github.com/pleasedodisturb/kestrel/issues/220)) ([74c826d](https://github.com/pleasedodisturb/kestrel/commit/74c826d6f6937eab26d9fdde7d190efc4ce1f0e4))

## [0.5.1](https://github.com/pleasedodisturb/kestrel/compare/v0.5.0...v0.5.1) (2026-04-19)


### Bug Fixes

* **G-379:** sync all version artifacts with release-please ([#218](https://github.com/pleasedodisturb/kestrel/issues/218)) ([4471148](https://github.com/pleasedodisturb/kestrel/commit/4471148c15516aec78243971e2c95d8469b284b3))
* **G-382:** resolve frontend TS build errors blocking PyPI publish ([#219](https://github.com/pleasedodisturb/kestrel/issues/219)) ([ce2ebae](https://github.com/pleasedodisturb/kestrel/commit/ce2ebaea319e19e96f6e7034ae565aa06aa13cd4))


### Documentation

* **G-268:** add Jekyll front matter to scoring-evolution-epics ([#216](https://github.com/pleasedodisturb/kestrel/issues/216)) ([96f5a93](https://github.com/pleasedodisturb/kestrel/commit/96f5a93067b67128b4f238ee5b9dbb01600d6300))

## [0.5.0](https://github.com/pleasedodisturb/kestrel/compare/v0.4.0...v0.5.0) (2026-04-16)


### Features

* **G-350:** add token usage tracking to AIResponse ([#211](https://github.com/pleasedodisturb/kestrel/issues/211)) ([00f6bdf](https://github.com/pleasedodisturb/kestrel/commit/00f6bdfde0730d3f697a892c9a3d64027576de85))
* **G-351:** add Batch API support for discovery scoring sweeps ([#213](https://github.com/pleasedodisturb/kestrel/issues/213)) ([8b4ed96](https://github.com/pleasedodisturb/kestrel/commit/8b4ed965be73e25be57bc74a92658cdfdd5f791a))
* **G-352:** add task-based model routing with complexity tiers ([#212](https://github.com/pleasedodisturb/kestrel/issues/212)) ([ea99e03](https://github.com/pleasedodisturb/kestrel/commit/ea99e03e3b615b44febcbe8e464311d7e4cc4529))
* **G-354:** add Together.ai provider for open-source model routing ([#210](https://github.com/pleasedodisturb/kestrel/issues/210)) ([0c53060](https://github.com/pleasedodisturb/kestrel/commit/0c530601a00b3b12d86ef58b46136e1972d1a871))


### Documentation

* add session summary for 2026-04-16 ([#209](https://github.com/pleasedodisturb/kestrel/issues/209)) ([a6076b8](https://github.com/pleasedodisturb/kestrel/commit/a6076b89a60c58e909f473a5f7ce156fd1d2677b))

## [0.4.0](https://github.com/pleasedodisturb/kestrel/compare/v0.3.1...v0.4.0) (2026-04-16)


### Features

* **G-269:** add scoring rubric with few-shot calibration examples ([#177](https://github.com/pleasedodisturb/kestrel/issues/177)) ([4bc847a](https://github.com/pleasedodisturb/kestrel/commit/4bc847a4089cdc972d21d7bd31f55f0be2278f05))
* **G-270:** add ghost job detection as red flag rule [#8](https://github.com/pleasedodisturb/kestrel/issues/8) ([#178](https://github.com/pleasedodisturb/kestrel/issues/178)) ([0516680](https://github.com/pleasedodisturb/kestrel/commit/05166801c4dfe10236816dc3f769d6741e070ca2))
* **G-271:** add score context & percentiles to scoring API ([#179](https://github.com/pleasedodisturb/kestrel/issues/179)) ([746d4d7](https://github.com/pleasedodisturb/kestrel/commit/746d4d7a5f867077e9e15754ae0f5278835fae7e))
* **G-273:** borderline 2-pass scoring ([#187](https://github.com/pleasedodisturb/kestrel/issues/187)) ([0c1acf3](https://github.com/pleasedodisturb/kestrel/commit/0c1acf3cedbdb3104eb35b892935605b3a047a5c))
* **G-274:** user feedback loop for score correction ([#181](https://github.com/pleasedodisturb/kestrel/issues/181)) ([7ad2c65](https://github.com/pleasedodisturb/kestrel/commit/7ad2c6523b40dfe99492c072d2320e4573f5d6ab))
* **G-275:** dual-score architecture (fit vs desire) ([#180](https://github.com/pleasedodisturb/kestrel/issues/180)) ([505fc0a](https://github.com/pleasedodisturb/kestrel/commit/505fc0a928fefad30af2539f02c6b3e50bf4c695))
* **G-276:** add ESCO skill taxonomy normalization service ([#182](https://github.com/pleasedodisturb/kestrel/issues/182)) ([2e0e070](https://github.com/pleasedodisturb/kestrel/commit/2e0e07071b92ef1d765034858eb8298b4e32d200))
* **G-277:** WARN Act layoff integration ([#183](https://github.com/pleasedodisturb/kestrel/issues/183)) ([51d4eba](https://github.com/pleasedodisturb/kestrel/commit/51d4eba92de57c7610e1b0b9433a05ed6725dd0a))
* **G-278:** add uncertainty ranges for sparse profiles ([#184](https://github.com/pleasedodisturb/kestrel/issues/184)) ([51e31ad](https://github.com/pleasedodisturb/kestrel/commit/51e31adf7663c60ed8ea275989467b29ecfe0150))
* **G-279:** add Bayesian preference learning service ([#185](https://github.com/pleasedodisturb/kestrel/issues/185)) ([a3140d4](https://github.com/pleasedodisturb/kestrel/commit/a3140d4fe810e050797920f25354c5c270d7d5f5))
* **G-295:** expand golden set — fix miscategorizations, add finance & design sets ([#194](https://github.com/pleasedodisturb/kestrel/issues/194)) ([ca6cdc0](https://github.com/pleasedodisturb/kestrel/commit/ca6cdc008edc2a1118d4f3365cbbec592c0165c7))
* **G-296:** rubric v1.1 — sharpen dream boundary, add 7.5 example ([#189](https://github.com/pleasedodisturb/kestrel/issues/189)) ([f827fb5](https://github.com/pleasedodisturb/kestrel/commit/f827fb5608a52110dbe510b09dc7b2c0165ba063))
* **G-301:** add 288 job family weight presets across 16 sectors ([#204](https://github.com/pleasedodisturb/kestrel/issues/204)) ([63763a6](https://github.com/pleasedodisturb/kestrel/commit/63763a6753c1219cd7c98571b357ae7827ecbd6b))
* **G-349:** enable token-efficient tool use header ([#206](https://github.com/pleasedodisturb/kestrel/issues/206)) ([0136579](https://github.com/pleasedodisturb/kestrel/commit/01365798199890d02b4ae67987f5b01bdf3e1427))


### Bug Fixes

* **G-294:** add JSON parse retry and robust extraction in AI providers ([#188](https://github.com/pleasedodisturb/kestrel/issues/188)) ([659ef2d](https://github.com/pleasedodisturb/kestrel/commit/659ef2d01b0467992ff96a3c53d0578c77b38a88))
* **G-297:** raise vague_responsibilities threshold from 200 to 400 chars ([#190](https://github.com/pleasedodisturb/kestrel/issues/190)) ([8546901](https://github.com/pleasedodisturb/kestrel/commit/8546901debcf8616c61efa17a9649b1a5ca55652))


### Documentation

* add session summary for 2026-04-14 (Supabase research) ([#172](https://github.com/pleasedodisturb/kestrel/issues/172)) ([af0dacb](https://github.com/pleasedodisturb/kestrel/commit/af0dacbe9ff5141f134ceaad910d11a90774b67b))
* **G-298:** add user-facing scoring explainer (how-scoring-works.md) ([#191](https://github.com/pleasedodisturb/kestrel/issues/191)) ([80d0e00](https://github.com/pleasedodisturb/kestrel/commit/80d0e00b175de7226a8e3914cc0ed2ee31c4a971))
* **G-299:** add PII-scrubbed benchmark artifacts from G-286 validation ([#192](https://github.com/pleasedodisturb/kestrel/issues/192)) ([29c6f3a](https://github.com/pleasedodisturb/kestrel/commit/29c6f3a0ba9c352b95b673e539d24907f5cb4ee6))
* **G-300:** create Kestrel feature audit for CareerOS sync matrix ([#202](https://github.com/pleasedodisturb/kestrel/issues/202)) ([a0f60c1](https://github.com/pleasedodisturb/kestrel/commit/a0f60c16916bbe056698d44664672c6cf8ba1ad7))
* **G-302:** validation report v2.0 — post-fix benchmark results ([#197](https://github.com/pleasedodisturb/kestrel/issues/197)) ([c1444d0](https://github.com/pleasedodisturb/kestrel/commit/c1444d0617c795a1e2981544d6d4ada79289c8de))
* **G-305:** add testing strategy research docs in 3 formats ([#195](https://github.com/pleasedodisturb/kestrel/issues/195)) ([1bdb358](https://github.com/pleasedodisturb/kestrel/commit/1bdb358756922c03801664a919a2368a29c6b2b4))
* **G-305:** research docs integration — license fix, scoring docs, README matrix ([#198](https://github.com/pleasedodisturb/kestrel/issues/198)) ([209caf1](https://github.com/pleasedodisturb/kestrel/commit/209caf189797f2d7602f0d2315ae3bcbcaf82393))
* **G-306:** add CI/CD research docs in 4 formats ([#196](https://github.com/pleasedodisturb/kestrel/issues/196)) ([2d1a6be](https://github.com/pleasedodisturb/kestrel/commit/2d1a6bea905c140e8e7b384bc19c2f70e951c2e3))

## [0.3.1](https://github.com/pleasedodisturb/kestrel/compare/v0.3.0...v0.3.1) (2026-04-13)


### Bug Fixes

* **G-266:** resolve 28 new-code SonarCloud blocker/critical issues ([#170](https://github.com/pleasedodisturb/kestrel/issues/170)) ([83b2a7b](https://github.com/pleasedodisturb/kestrel/commit/83b2a7b1fcedc8122e38286cd18e1526a17eddfa))

## [0.3.0](https://github.com/pleasedodisturb/kestrel/compare/v0.2.0...v0.3.0) (2026-04-13)


### Features

* add OpenRouter OAuth PKCE backend endpoints ([7ec4446](https://github.com/pleasedodisturb/kestrel/commit/7ec4446e07a85209253ebe4a2c0a28cf3f2c58bb))
* G-236 add client-side PII masking layer for AI prompts ([9282f95](https://github.com/pleasedodisturb/kestrel/commit/9282f95190a2bddc7ea3721896d3d3f1a4d5c24a))
* multi-provider AI architecture — Wave 1 ([#132](https://github.com/pleasedodisturb/kestrel/issues/132)) ([3632eb7](https://github.com/pleasedodisturb/kestrel/commit/3632eb7aeac173b05386c2099a00f167c6b566c7))


### Bug Fixes

* add tests/ to gitleaks allowlist for placeholder API keys ([e2a6d81](https://github.com/pleasedodisturb/kestrel/commit/e2a6d818cc69e2b30735a3cd3b0dc2e22e6c4755))
* **ci:** harden CI reliability — SonarCloud, commitlint, pytest-timeout ([#167](https://github.com/pleasedodisturb/kestrel/issues/167)) ([7cb2e6a](https://github.com/pleasedodisturb/kestrel/commit/7cb2e6ad897305d44e3125f098785eaa29588bbe))
* **ci:** merge SonarCloud into CI workflow with coverage integration ([#163](https://github.com/pleasedodisturb/kestrel/issues/163)) ([156bf43](https://github.com/pleasedodisturb/kestrel/commit/156bf436c5d41ee19fa1eb6d88e774638b28f06c))
* exclude Claude skill docs from gitleaks scanning ([f75a3d3](https://github.com/pleasedodisturb/kestrel/commit/f75a3d3341efc4d5e1a12efd9dd18879fdc333c6))
* G-265 re-add BMAD/GSD gitignore entries dropped during merge ([#165](https://github.com/pleasedodisturb/kestrel/issues/165)) ([e984b47](https://github.com/pleasedodisturb/kestrel/commit/e984b4781ad6c2449128ba1f26d7860767713d72))
* harden OAuth, PII masking, cache, and gitleaks config ([2d95d65](https://github.com/pleasedodisturb/kestrel/commit/2d95d65e4d8b9b5945132164931b844d987d6eb5))
* pin GitHub Actions to full commit SHAs in SonarCloud workflow ([0224f97](https://github.com/pleasedodisturb/kestrel/commit/0224f9753b028e4d3a41afd61a3ded2b02d49bff))
* remove hardcoded PII from SonarCloud MCP server defaults ([29dc9c9](https://github.com/pleasedodisturb/kestrel/commit/29dc9c9c4510b23a43537a448987afdb04f9281d))
* resolve PR [#132](https://github.com/pleasedodisturb/kestrel/issues/132) conflicts — combine security features from both branches ([#160](https://github.com/pleasedodisturb/kestrel/issues/160)) ([9f9b31d](https://github.com/pleasedodisturb/kestrel/commit/9f9b31d3087f780500e1b0bcc646a03715faace2))
* **security:** harden OAuth, cache, PII masking, and privacy registry ([e8199f5](https://github.com/pleasedodisturb/kestrel/commit/e8199f5c69ad197c825dccd4111ee5630dbe69c7))
* setup SonarCloud CI properly and resolve ~420 issues ([#166](https://github.com/pleasedodisturb/kestrel/issues/166)) ([bb7355c](https://github.com/pleasedodisturb/kestrel/commit/bb7355c129bc535c225bf480daeb2f3aa0f9c5e4))
* update markdownify to &gt;=1.2.2 to resolve CVE-2025-46656 ([#133](https://github.com/pleasedodisturb/kestrel/issues/133)) ([643f755](https://github.com/pleasedodisturb/kestrel/commit/643f7558ad3dbff6e8ce9a7d2cc2901cd7d74c25))


### Documentation

* add session summary for 2026-04-13 (BMAD installation) ([#169](https://github.com/pleasedodisturb/kestrel/issues/169)) ([8060d58](https://github.com/pleasedodisturb/kestrel/commit/8060d582f55a7a7d6a5c23d0c426da772bf71d6c))
* rewrite CLAUDE.md with dev commands and mobile coverage ([#123](https://github.com/pleasedodisturb/kestrel/issues/123)) ([c16b62b](https://github.com/pleasedodisturb/kestrel/commit/c16b62b6565524786b65769e1a53d3bfe8c7c32a))


### Dependencies

* Update dependency lucide-react to v1 ([#149](https://github.com/pleasedodisturb/kestrel/issues/149)) ([5a62031](https://github.com/pleasedodisturb/kestrel/commit/5a620316f7933fa8b7f3ebdbe37e55b0a6ed51f4))
* Update docker/build-push-action action to v7 ([#145](https://github.com/pleasedodisturb/kestrel/issues/145)) ([79bf055](https://github.com/pleasedodisturb/kestrel/commit/79bf055061a526748c9abcd9d6e6f39b6d7ef272))
* Update docker/setup-buildx-action action to v4 ([b335352](https://github.com/pleasedodisturb/kestrel/commit/b335352aa6100bb13d26b8866a39a41ca6bb25c5))
* Update GitHub Artifact Actions ([#147](https://github.com/pleasedodisturb/kestrel/issues/147)) ([5a39618](https://github.com/pleasedodisturb/kestrel/commit/5a39618b5280517dff7ea37e91a0e81483ec49fc))
* update GitHub artifact actions to latest majors ([9b89464](https://github.com/pleasedodisturb/kestrel/commit/9b89464bac6a64a980d497dd057114ebfc2f8a6f))

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
