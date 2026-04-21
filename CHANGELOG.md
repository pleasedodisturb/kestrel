# Changelog

## [0.10.0](https://github.com/pleasedodisturb/kestrel/compare/v0.9.0...v0.10.0) (2026-04-21)


### Features

* **G-430:** input validation hardening — INT64 bounds on all API integers ([#251](https://github.com/pleasedodisturb/kestrel/issues/251)) ([35a1907](https://github.com/pleasedodisturb/kestrel/commit/35a190720601b70924cce5ab8711448222fdcf4c))
* **G-436:** recover Phase 2 agent-aware enforcement from orphaned G-394 ([#255](https://github.com/pleasedodisturb/kestrel/issues/255)) ([de25bb1](https://github.com/pleasedodisturb/kestrel/commit/de25bb1ba3f4bce21981fbc904cf37874c4e7178))
* **G-436:** recover Phase 3 advanced testing from orphaned G-394 ([#256](https://github.com/pleasedodisturb/kestrel/issues/256)) ([224957b](https://github.com/pleasedodisturb/kestrel/commit/224957b872df80f522373aa7d0cc3b567a892d28))
* **G-437:** spike — regex pre-filter vs AI scoring accuracy on 10K jobs ([#254](https://github.com/pleasedodisturb/kestrel/issues/254)) ([ff837b8](https://github.com/pleasedodisturb/kestrel/commit/ff837b8242efc2f1f7440d2b0bfb44c02e861756))


### Bug Fixes

* **03.3-01:** add _ensure_utc validators to 7 schema files for RFC 3339 compliance ([#258](https://github.com/pleasedodisturb/kestrel/issues/258)) ([a5c0607](https://github.com/pleasedodisturb/kestrel/commit/a5c0607584705ed508062025adf084fe178d2ad0))
* **G-457:** recalibrate golden set fixtures after scoring evolution ([#260](https://github.com/pleasedodisturb/kestrel/issues/260)) ([0b5cdd2](https://github.com/pleasedodisturb/kestrel/commit/0b5cdd2ce57cf883c33b68cd836dba53ecbe6794))


### Documentation

* **G-305:** testing strategy — what shipped, what was trimmed, and why ([#259](https://github.com/pleasedodisturb/kestrel/issues/259)) ([c463d54](https://github.com/pleasedodisturb/kestrel/commit/c463d54875a952fcc62133ef2423d682a1ca7ebc))
* **G-348:** add benchmark results to token optimization docs and README ([#252](https://github.com/pleasedodisturb/kestrel/issues/252)) ([374ac11](https://github.com/pleasedodisturb/kestrel/commit/374ac114d975d8da895a030d1f778b31f8c7fdc3))
* **G-437:** cost control research — 4 research documents ([#257](https://github.com/pleasedodisturb/kestrel/issues/257)) ([9a335f9](https://github.com/pleasedodisturb/kestrel/commit/9a335f91e98892577cd33859083abfb7c0d4e593))

## [0.9.0](https://github.com/pleasedodisturb/kestrel/compare/v0.8.0...v0.9.0) (2026-04-20)


### Features

* **G-405:** provider fallback chain — automatic retry on quota/timeout ([#249](https://github.com/pleasedodisturb/kestrel/issues/249)) ([e6c3adb](https://github.com/pleasedodisturb/kestrel/commit/e6c3adba692cee581d4d8c3511fe8bd5f391f92f))

## [0.8.0](https://github.com/pleasedodisturb/kestrel/compare/v0.7.1...v0.8.0) (2026-04-20)


### Features

* **G-397:** AI cost visibility — token usage logging and OpenRouter attribution ([#244](https://github.com/pleasedodisturb/kestrel/issues/244)) ([b41ac3a](https://github.com/pleasedodisturb/kestrel/commit/b41ac3a70d71c2c0ad7958dabe871a798e5dc284))
* **G-427:** cache break detection — alert on prompt cache invalidation ([#246](https://github.com/pleasedodisturb/kestrel/issues/246)) ([382fcc8](https://github.com/pleasedodisturb/kestrel/commit/382fcc894a37a4f86e36221ce49559e76d431afe))


### Performance

* **G-261:** compress system prompts — 67% token reduction ([#243](https://github.com/pleasedodisturb/kestrel/issues/243)) ([115d576](https://github.com/pleasedodisturb/kestrel/commit/115d576543ba662491d037e78d4cef6ec98316dd))


### Documentation

* **G-348:** add 3-layer token optimization documentation ([#247](https://github.com/pleasedodisturb/kestrel/issues/247)) ([9b597e5](https://github.com/pleasedodisturb/kestrel/commit/9b597e57631448fcc49334707d28073a20e8dad7))

## [0.7.1](https://github.com/pleasedodisturb/kestrel/compare/v0.7.0...v0.7.1) (2026-04-20)


### Performance

* **G-428:** use compact JSON serialization in AI provider score() calls ([#239](https://github.com/pleasedodisturb/kestrel/issues/239)) ([34b4995](https://github.com/pleasedodisturb/kestrel/commit/34b4995d13ce1e304f22d913fca881e644ccd973))
* **G-429:** system prompt deduplication — profile in cached system block ([#242](https://github.com/pleasedodisturb/kestrel/issues/242)) ([b759290](https://github.com/pleasedodisturb/kestrel/commit/b759290c7b324a64857581be95e76e19b906b709))

## [0.7.0](https://github.com/pleasedodisturb/kestrel/compare/v0.6.0...v0.7.0) (2026-04-20)


### Features

* **G-291:** port robust JSON scoring parser from CareerOS ([#230](https://github.com/pleasedodisturb/kestrel/issues/230)) ([c32c0eb](https://github.com/pleasedodisturb/kestrel/commit/c32c0ebc35e58ea4a22f26214d9bdcbd2643de85))
* **G-408:** Langfuse observability blueprint ([#236](https://github.com/pleasedodisturb/kestrel/issues/236)) ([0d2d579](https://github.com/pleasedodisturb/kestrel/commit/0d2d57992c98959e67527288c55e74b681f4a313))


### Bug Fixes

* **G-412:** add test isolation guard — prevent tests from hitting real AI providers ([#237](https://github.com/pleasedodisturb/kestrel/issues/237)) ([374b937](https://github.com/pleasedodisturb/kestrel/commit/374b937292d022f533a629cd8c2dc310a1fbddea))

## [0.6.0](https://github.com/pleasedodisturb/kestrel/compare/v0.5.2...v0.6.0) (2026-04-20)


### Features

* **G-291:** add post-scoring hard caps and keyword exemption system ([#231](https://github.com/pleasedodisturb/kestrel/issues/231)) ([454a187](https://github.com/pleasedodisturb/kestrel/commit/454a18737a2018f74230087a043a2fcd7dce3979))
* **G-293:** add daily scan watchdog and external trigger script ([#228](https://github.com/pleasedodisturb/kestrel/issues/228)) ([6329e67](https://github.com/pleasedodisturb/kestrel/commit/6329e6733ce80ebcb33247620eb2fececd479f97))
* **G-305:** CI optimization — markers, path filtering, testmon, PR comments ([#234](https://github.com/pleasedodisturb/kestrel/issues/234)) ([30396e9](https://github.com/pleasedodisturb/kestrel/commit/30396e93febb3f86ae97557cb0b13e571f2b6182))
* **G-345:** add scoring prompt calibration with distribution enforcement ([#223](https://github.com/pleasedodisturb/kestrel/issues/223)) ([5f13dd8](https://github.com/pleasedodisturb/kestrel/commit/5f13dd80ff41dc7d5012a18d3b1001686c9b7384))
* **G-394, G-305:** rename CLI to kestrel + CI optimization phase 1 ([#233](https://github.com/pleasedodisturb/kestrel/issues/233)) ([e8be92b](https://github.com/pleasedodisturb/kestrel/commit/e8be92b414270a1a851d02f90db2ce247eec6cb5))
* **G-394:** rename CLI entry point from career to kestrel ([#232](https://github.com/pleasedodisturb/kestrel/issues/232)) ([0deb120](https://github.com/pleasedodisturb/kestrel/commit/0deb120b5597a011e06d0b82335629acb96f6917))


### Bug Fixes

* **G-385:** add load_dotenv for reliable .env file reading ([#225](https://github.com/pleasedodisturb/kestrel/issues/225)) ([7be6be5](https://github.com/pleasedodisturb/kestrel/commit/7be6be52d53eed31c79e2e6e1b7eb29cb24b637f))


### Documentation

* free tier pricing, real cost table, PII safety boundary ([#235](https://github.com/pleasedodisturb/kestrel/issues/235)) ([9eacff4](https://github.com/pleasedodisturb/kestrel/commit/9eacff49e945abea7ce52363220b9f18fb16024d))

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
