# Changelog

## [0.25.0](https://github.com/pleasedodisturb/kestrel/compare/v0.24.0...v0.25.0) (2026-08-04)


### Features

* add 10 brand illustrations - logos, heroes, art ([238ce18](https://github.com/pleasedodisturb/kestrel/commit/238ce18846b7806ecdb98f6154b1058e3bef9cb2))
* add 10 brand illustrations for docs, README, and marketing ([fb0867f](https://github.com/pleasedodisturb/kestrel/commit/fb0867f66bed6150248fb1d34799384c404f36c3))
* add 31 curated illustrations to gallery for future use ([af2f78f](https://github.com/pleasedodisturb/kestrel/commit/af2f78fd511d30c923450b7b351a8df775f847de))
* add one-command installers (curl, npx, brew) — closes [#21](https://github.com/pleasedodisturb/kestrel/issues/21) ([6273247](https://github.com/pleasedodisturb/kestrel/commit/6273247de67748b2bf59d8e96a465b96fedec731))
* add OpenRouter OAuth PKCE backend endpoints ([85fc560](https://github.com/pleasedodisturb/kestrel/commit/85fc560c6766b7bc86540c984394f8c2ee14383e))
* **G-1200:** declare Railway volume via requiredMountPath ([#400](https://github.com/pleasedodisturb/kestrel/issues/400)) ([16251c9](https://github.com/pleasedodisturb/kestrel/commit/16251c9389ffeff4467367a94cd86f2809786ea2))
* **G-1217:** upstream Eyas discovery-pipeline improvements (PII-free) ([#404](https://github.com/pleasedodisturb/kestrel/issues/404)) ([8651718](https://github.com/pleasedodisturb/kestrel/commit/8651718b08fa63204231e9da352ef2dfa01b4204))
* **G-1275:** switch npm publish to OIDC Trusted Publishing — no token needed ([#428](https://github.com/pleasedodisturb/kestrel/issues/428)) ([8ffb023](https://github.com/pleasedodisturb/kestrel/commit/8ffb023fbd03399ddb06967c49bfd86d2dce6179))
* **G-1277:** automate security-fix inclusion — Dependabot automerge, docker ecosystem, weekly rebuild ([#417](https://github.com/pleasedodisturb/kestrel/issues/417)) ([a0d3c2f](https://github.com/pleasedodisturb/kestrel/commit/a0d3c2fc138e90c3f8d79d4fd6574b0d43bdc77e))
* **G-1282:** port blocklist + parameterized geo gate from private fork (PII-stripped) ([#436](https://github.com/pleasedodisturb/kestrel/issues/436)) ([02f06db](https://github.com/pleasedodisturb/kestrel/commit/02f06db5653294aff49df576b4bf0c89c91ed96e))
* **G-1282:** port tiered application model + SmartRecruiters/Personio scrapers (PII-stripped) ([#439](https://github.com/pleasedodisturb/kestrel/issues/439)) ([3804900](https://github.com/pleasedodisturb/kestrel/commit/38049007a7e48c358ab6d5c30600c55149b21b59))
* **G-1315:** default Mistral provider to Small (benchmark-driven scoring) ([#448](https://github.com/pleasedodisturb/kestrel/issues/448)) ([0489a9d](https://github.com/pleasedodisturb/kestrel/commit/0489a9d7af8e421a9d3fdcacade53f3bd58c600f))
* **G-1335:** role-fit hard gate + company-prestige cap (halo fix) ([#452](https://github.com/pleasedodisturb/kestrel/issues/452)) ([bdd664a](https://github.com/pleasedodisturb/kestrel/commit/bdd664a099484736de2d2475c682ec86e7e62fba))
* **G-1336:** scoring eval infrastructure — golden-set κ/NDCG + shadow-mode + drift canary ([#454](https://github.com/pleasedodisturb/kestrel/issues/454)) ([a23bd80](https://github.com/pleasedodisturb/kestrel/commit/a23bd80993ca6b17821f84c72013961e627da0b4))
* **G-1337:** calibration hygiene — 0–5 judge scale + spread metrics + per-provider calibration ([#455](https://github.com/pleasedodisturb/kestrel/issues/455)) ([2367944](https://github.com/pleasedodisturb/kestrel/commit/23679444eab063b059f7491961599635c44e5729))
* **G-1338:** confidence-routed cascade (conservative, shadow-first) — part 2 ([#458](https://github.com/pleasedodisturb/kestrel/issues/458)) ([9fd700d](https://github.com/pleasedodisturb/kestrel/commit/9fd700dcba8437de25a55a4da3552af61b92c82c))
* **G-1338:** scoring features — distillation logging + ESCO overlap + relative scoring ([#457](https://github.com/pleasedodisturb/kestrel/issues/457)) ([c99709f](https://github.com/pleasedodisturb/kestrel/commit/c99709f7b923887aaea3239137e70328dad5dacd))
* **G-1351:** ESCO occupations taxonomy cache + loader + bundled fixture (Phase A) ([#467](https://github.com/pleasedodisturb/kestrel/issues/467)) ([337dbc3](https://github.com/pleasedodisturb/kestrel/commit/337dbc33e4e0fb939ab7034512bdf5a578a0df0c))
* **G-1351:** occupation matcher — family/title→tier classifier + in-package taxonomy consumer (Phase B) ([#468](https://github.com/pleasedodisturb/kestrel/issues/468)) ([aab8a97](https://github.com/pleasedodisturb/kestrel/commit/aab8a97d9279f0035a10926d53bc5a241b551a07))
* **G-1351:** shadow-first occupation signal — cascade 4th signal + distillation logging + startup populate (Phase C) ([#473](https://github.com/pleasedodisturb/kestrel/issues/473)) ([cfa9832](https://github.com/pleasedodisturb/kestrel/commit/cfa9832d1665fb480e8b478a0bc239d0e21ffcd8))
* **G-1391:** browser extension Phase 1 — THE EYE (capture + inline score + gap + auto-log) ([#478](https://github.com/pleasedodisturb/kestrel/issues/478)) ([ae4f316](https://github.com/pleasedodisturb/kestrel/commit/ae4f31667a5800e5892e277ff1af285353c93a3a))
* G-236 add client-side PII masking layer for AI prompts ([bf6885c](https://github.com/pleasedodisturb/kestrel/commit/bf6885c5bf97d7342f1611caa7aa53b202b1d02a))
* **G-269:** add scoring rubric with few-shot calibration examples ([#177](https://github.com/pleasedodisturb/kestrel/issues/177)) ([8263949](https://github.com/pleasedodisturb/kestrel/commit/8263949d697ea6dfebd1a0e5931a8795c2a2767a))
* **G-270:** add ghost job detection as red flag rule [#8](https://github.com/pleasedodisturb/kestrel/issues/8) ([#178](https://github.com/pleasedodisturb/kestrel/issues/178)) ([7e4d93c](https://github.com/pleasedodisturb/kestrel/commit/7e4d93cc2031db35c7bba9444b2bc2bd4f445522))
* **G-271:** add score context & percentiles to scoring API ([#179](https://github.com/pleasedodisturb/kestrel/issues/179)) ([8ba8be5](https://github.com/pleasedodisturb/kestrel/commit/8ba8be5071707e2fedd424b1cf08fd0d8c3a9f85))
* **G-273:** borderline 2-pass scoring ([#187](https://github.com/pleasedodisturb/kestrel/issues/187)) ([8f9c8f9](https://github.com/pleasedodisturb/kestrel/commit/8f9c8f980d7f414c5590ec7f7e80770a84c8315c))
* **G-274:** user feedback loop for score correction ([#181](https://github.com/pleasedodisturb/kestrel/issues/181)) ([6c104ed](https://github.com/pleasedodisturb/kestrel/commit/6c104edb3c5eafe10f606320ae63047c53367bc8))
* **G-275:** dual-score architecture (fit vs desire) ([#180](https://github.com/pleasedodisturb/kestrel/issues/180)) ([5d6dd4a](https://github.com/pleasedodisturb/kestrel/commit/5d6dd4a61aa13ce9dd8e78938b1a5939f3bcd45c))
* **G-276:** add ESCO skill taxonomy normalization service ([#182](https://github.com/pleasedodisturb/kestrel/issues/182)) ([316c9ab](https://github.com/pleasedodisturb/kestrel/commit/316c9abb8a91b7812a51a5357f8548531fc11564))
* **G-277:** WARN Act layoff integration ([#183](https://github.com/pleasedodisturb/kestrel/issues/183)) ([ea50f6d](https://github.com/pleasedodisturb/kestrel/commit/ea50f6d2f49b4f1564ef2ec6fb23516e44bdc26d))
* **G-278:** add uncertainty ranges for sparse profiles ([#184](https://github.com/pleasedodisturb/kestrel/issues/184)) ([22a7914](https://github.com/pleasedodisturb/kestrel/commit/22a791463fb46a70bebeee954aa4a317fc66f680))
* **G-279:** add Bayesian preference learning service ([#185](https://github.com/pleasedodisturb/kestrel/issues/185)) ([c84e9aa](https://github.com/pleasedodisturb/kestrel/commit/c84e9aa333adae0abff174c3f39995f9787c4f09))
* **G-291:** add post-scoring hard caps and keyword exemption system ([#231](https://github.com/pleasedodisturb/kestrel/issues/231)) ([82e1ac0](https://github.com/pleasedodisturb/kestrel/commit/82e1ac0a874b78dcd6c089b617d02c5f09e105f2))
* **G-291:** port robust JSON scoring parser from CareerOS ([#230](https://github.com/pleasedodisturb/kestrel/issues/230)) ([5ec37b3](https://github.com/pleasedodisturb/kestrel/commit/5ec37b3a1f74b08debffa3436bbb80455ae52bf3))
* **G-293:** add daily scan watchdog and external trigger script ([#228](https://github.com/pleasedodisturb/kestrel/issues/228)) ([0b38342](https://github.com/pleasedodisturb/kestrel/commit/0b383425a96369eb5859bf9d61a7bb50c21275dd))
* **G-295:** expand golden set — fix miscategorizations, add finance & design sets ([#194](https://github.com/pleasedodisturb/kestrel/issues/194)) ([b38d693](https://github.com/pleasedodisturb/kestrel/commit/b38d6937ec0c939a7f16d1fe768b644f3283a6d1))
* **G-296:** rubric v1.1 — sharpen dream boundary, add 7.5 example ([#189](https://github.com/pleasedodisturb/kestrel/issues/189)) ([e64e2e7](https://github.com/pleasedodisturb/kestrel/commit/e64e2e73963d59288a93f78fe88af1f31bb908b9))
* **G-301:** add 288 job family weight presets across 16 sectors ([#204](https://github.com/pleasedodisturb/kestrel/issues/204)) ([9d999d4](https://github.com/pleasedodisturb/kestrel/commit/9d999d4fd657bc3ab6948e147a7c21c9586eeae7))
* **G-305:** CI optimization — markers, path filtering, testmon, PR comments ([#234](https://github.com/pleasedodisturb/kestrel/issues/234)) ([9fe31c4](https://github.com/pleasedodisturb/kestrel/commit/9fe31c4a441eb8b297a0b75dc7ea64d3886242d7))
* **G-345:** add scoring prompt calibration with distribution enforcement ([#223](https://github.com/pleasedodisturb/kestrel/issues/223)) ([d92ec3e](https://github.com/pleasedodisturb/kestrel/commit/d92ec3e13707479fbc42056040e3a670756b76c9))
* **G-349:** enable token-efficient tool use header ([#206](https://github.com/pleasedodisturb/kestrel/issues/206)) ([8ebb55a](https://github.com/pleasedodisturb/kestrel/commit/8ebb55a3fc06d59e68d55dde6f0cb76ed160ed26))
* **G-350:** add token usage tracking to AIResponse ([#211](https://github.com/pleasedodisturb/kestrel/issues/211)) ([4e1f042](https://github.com/pleasedodisturb/kestrel/commit/4e1f0427fbe32f0b0cd5e831f0c436dde726124c))
* **G-351:** add Batch API support for discovery scoring sweeps ([#213](https://github.com/pleasedodisturb/kestrel/issues/213)) ([aedb211](https://github.com/pleasedodisturb/kestrel/commit/aedb2116d67b6c06884c57da235685c83f01412e))
* **G-352:** add task-based model routing with complexity tiers ([#212](https://github.com/pleasedodisturb/kestrel/issues/212)) ([b0a8f31](https://github.com/pleasedodisturb/kestrel/commit/b0a8f312379fd047a62625dca9d4f3b8163e4953))
* **G-354:** add Together.ai provider for open-source model routing ([#210](https://github.com/pleasedodisturb/kestrel/issues/210)) ([44ef52b](https://github.com/pleasedodisturb/kestrel/commit/44ef52b7f825cd22e5c45cce0f8e7d6ad72d41d2))
* **G-392:** Onboarding Epic — 6 phases, 361 tests ([13771fd](https://github.com/pleasedodisturb/kestrel/commit/13771fd9211dc54d2ac9b97ebb83658f88c020a7))
* **G-394, G-305:** rename CLI to kestrel + CI optimization phase 1 ([#233](https://github.com/pleasedodisturb/kestrel/issues/233)) ([937af5d](https://github.com/pleasedodisturb/kestrel/commit/937af5dd77ef98a19593844ac604da8a92d6df44))
* **G-394:** make kestrel the primary CLI entry point, keep career as alias ([#316](https://github.com/pleasedodisturb/kestrel/issues/316)) ([ab8b710](https://github.com/pleasedodisturb/kestrel/commit/ab8b7108d9f3619ba226568f7b062a23242218d2))
* **G-394:** rename CLI entry point from career to kestrel ([#232](https://github.com/pleasedodisturb/kestrel/issues/232)) ([9932e88](https://github.com/pleasedodisturb/kestrel/commit/9932e88822b6a51c3dbe260c68014e7559cbf10c))
* **G-397:** AI cost visibility — token usage logging and OpenRouter attribution ([#244](https://github.com/pleasedodisturb/kestrel/issues/244)) ([9f7d8e1](https://github.com/pleasedodisturb/kestrel/commit/9f7d8e1ce530da8713e0b0af7fc11c6cf23fcd06))
* **G-405:** provider fallback chain — automatic retry on quota/timeout ([#249](https://github.com/pleasedodisturb/kestrel/issues/249)) ([2997bcf](https://github.com/pleasedodisturb/kestrel/commit/2997bcf1148eb79dced4e73174f4b9771e187d9f))
* **G-407:** enforce PII safety boundary — block personal data from non-ZDR providers ([#311](https://github.com/pleasedodisturb/kestrel/issues/311)) ([300b394](https://github.com/pleasedodisturb/kestrel/commit/300b394137d6aac94546cfa7fa1c2e2b7ea072d1))
* **G-408:** Langfuse observability blueprint ([#236](https://github.com/pleasedodisturb/kestrel/issues/236)) ([19ff7ff](https://github.com/pleasedodisturb/kestrel/commit/19ff7ffae7cf621f0febdd3e3bc0b3574ef206e3))
* **G-427:** cache break detection — alert on prompt cache invalidation ([#246](https://github.com/pleasedodisturb/kestrel/issues/246)) ([0afbf4f](https://github.com/pleasedodisturb/kestrel/commit/0afbf4f3e75d308729a003240d7766d2134e926e))
* **G-430:** input validation hardening — INT64 bounds on all API integers ([#251](https://github.com/pleasedodisturb/kestrel/issues/251)) ([2664dc1](https://github.com/pleasedodisturb/kestrel/commit/2664dc173cdc24db83af963bca85fb753cba4208))
* **G-436:** recover Phase 2 agent-aware enforcement from orphaned G-394 ([#255](https://github.com/pleasedodisturb/kestrel/issues/255)) ([2a71f6c](https://github.com/pleasedodisturb/kestrel/commit/2a71f6cf1bbef89bfb144977c3e0135353e5aafb))
* **G-436:** recover Phase 3 advanced testing from orphaned G-394 ([#256](https://github.com/pleasedodisturb/kestrel/issues/256)) ([03575aa](https://github.com/pleasedodisturb/kestrel/commit/03575aa9057350fae782ab81b92a1f3a18e94b47))
* **G-437:** spike — regex pre-filter vs AI scoring accuracy on 10K jobs ([#254](https://github.com/pleasedodisturb/kestrel/issues/254)) ([09c4e53](https://github.com/pleasedodisturb/kestrel/commit/09c4e533a6f5bd0538399940651c223ff0529593))
* **G-439:** integrate pre-filter into discovery pipeline ([#272](https://github.com/pleasedodisturb/kestrel/issues/272)) ([fe286c6](https://github.com/pleasedodisturb/kestrel/commit/fe286c6234ba5a20cc430744d9e20add9eb6c7d3))
* **G-440:** batch scoring — multiple jobs per prompt ([#273](https://github.com/pleasedodisturb/kestrel/issues/273)) ([cd29b72](https://github.com/pleasedodisturb/kestrel/commit/cd29b72323654adb027226a4186c5dac7e38ee08))
* **G-441:** prompt caching for scoring calls — profile in system prefix ([#274](https://github.com/pleasedodisturb/kestrel/issues/274)) ([7cab632](https://github.com/pleasedodisturb/kestrel/commit/7cab632493c9b5d0c7b6824a14e4929f6a36569f))
* **G-442:** add cost presets system (Free/Budget/Quality/Private/Custom) ([#283](https://github.com/pleasedodisturb/kestrel/issues/283)) ([2624255](https://github.com/pleasedodisturb/kestrel/commit/26242554549da3411df4664eadb8c69e0bbcefcc))
* **G-443:** integrate Anthropic + OpenAI async Batch APIs for 50% off scoring ([#286](https://github.com/pleasedodisturb/kestrel/issues/286)) ([d480ca1](https://github.com/pleasedodisturb/kestrel/commit/d480ca166f898a8617ba3ac3b3f3f3f7b5d5d26b))
* **G-445:** add Groq provider (OpenAI-compatible) ([#280](https://github.com/pleasedodisturb/kestrel/issues/280)) ([3b69ac1](https://github.com/pleasedodisturb/kestrel/commit/3b69ac19dc6acd10548c827ba2cc0407c4993d77))
* **G-446:** add OpenAI direct provider ([#261](https://github.com/pleasedodisturb/kestrel/issues/261)) ([a65ccc5](https://github.com/pleasedodisturb/kestrel/commit/a65ccc57953725a5f125a52173ca39c4bdc3a319))
* **G-447:** add xAI/Grok provider with red privacy tier ([#284](https://github.com/pleasedodisturb/kestrel/issues/284)) ([949068e](https://github.com/pleasedodisturb/kestrel/commit/949068e6a3c54331f8b7c27ca638aae4c88db67d))
* **G-448:** add Google Gemini AI provider ([#287](https://github.com/pleasedodisturb/kestrel/issues/287)) ([62e674d](https://github.com/pleasedodisturb/kestrel/commit/62e674d81955d766966a05c91b780c23109b2b50))
* **G-449:** add provider privacy disclosures to AI Providers integration panel ([#270](https://github.com/pleasedodisturb/kestrel/issues/270)) ([54f311b](https://github.com/pleasedodisturb/kestrel/commit/54f311b40e23e018b9834e415130007046399d96))
* **G-450:** add Kestrel MCP server for Claude Code ([#262](https://github.com/pleasedodisturb/kestrel/issues/262)) ([f0cc834](https://github.com/pleasedodisturb/kestrel/commit/f0cc834f4f2d595950075c57cb8c2086219a4a98))
* **G-451:** OpenRouter OAuth PKCE onboarding flow ([#263](https://github.com/pleasedodisturb/kestrel/issues/263)) ([25c6683](https://github.com/pleasedodisturb/kestrel/commit/25c66830a176d52ab4ad7662d9de76cb41da61a3))
* **G-453:** batch scoring quality A/B test spike ([#278](https://github.com/pleasedodisturb/kestrel/issues/278)) ([701d640](https://github.com/pleasedodisturb/kestrel/commit/701d6408455054df5f273fe5345287e5c9810727))
* **G-540, G-541:** add Mistral + Hugging Face AI providers ([#331](https://github.com/pleasedodisturb/kestrel/issues/331)) ([c90c004](https://github.com/pleasedodisturb/kestrel/commit/c90c004ce6aab6dd8e66238de60ceb3359ca3401))
* **G-626:** dispatch React-combobox dropdowns in batch_apply_browser ([#370](https://github.com/pleasedodisturb/kestrel/issues/370)) ([68fd8b8](https://github.com/pleasedodisturb/kestrel/commit/68fd8b801ffb48e708f95ec18c095193b76cbd34))
* **G-627:** per-role qualifying-question overlay in batch_apply_browser ([#369](https://github.com/pleasedodisturb/kestrel/issues/369)) ([357e388](https://github.com/pleasedodisturb/kestrel/commit/357e388dd9abd6b5b0369150ac724cc164e2d5a8)), closes [#347](https://github.com/pleasedodisturb/kestrel/issues/347)
* **G-630:** add remotely.de + arbeitnow EU-tech sources to daily_pipeline ([#372](https://github.com/pleasedodisturb/kestrel/issues/372)) ([d36afdf](https://github.com/pleasedodisturb/kestrel/commit/d36afdf8bb94c59d2b5a4a0ce5e21f1e3fa25f03))
* **G-636:** tier-0 ATS poller (Greenhouse/Lever/Ashby) for dream companies ([#371](https://github.com/pleasedodisturb/kestrel/issues/371)) ([887c186](https://github.com/pleasedodisturb/kestrel/commit/887c1860a189fc6e82bbb3ab685ee0a5f7a05ddb))
* initial public roadmap with deep dives and one-click dev environment ([#350](https://github.com/pleasedodisturb/kestrel/issues/350)) ([75980e9](https://github.com/pleasedodisturb/kestrel/commit/75980e975d2cb56d1d4d6fb1e3133556cba6a421))
* multi-provider AI architecture — Wave 1 ([#132](https://github.com/pleasedodisturb/kestrel/issues/132)) ([0046ab3](https://github.com/pleasedodisturb/kestrel/commit/0046ab371c0c13095c1f0c880e3fa02d28d54b86))
* pip install + Codespaces - Docker-free install paths ([6d2a4af](https://github.com/pleasedodisturb/kestrel/commit/6d2a4aff1eedfeb740612fb51285b59e0b19141d))
* pip install support - no Docker required ([7483174](https://github.com/pleasedodisturb/kestrel/commit/7483174e83bade1dce743d50a3dfe8b2fbd541dc))
* **scoring:** rule-based red flag detection + letter-grade scoring ([#83](https://github.com/pleasedodisturb/kestrel/issues/83)) ([0ad94a6](https://github.com/pleasedodisturb/kestrel/commit/0ad94a6404a644d9a7a433c4611ca9bb091a9788))
* show new matches banner in Discovery page ([#29](https://github.com/pleasedodisturb/kestrel/issues/29)) ([2901a2f](https://github.com/pleasedodisturb/kestrel/commit/2901a2f6fe86fe621767f057a375804e36793f08))
* update README with three install paths (pip, Docker, Codespaces) ([ed46342](https://github.com/pleasedodisturb/kestrel/commit/ed46342a0316b09ac4abacd8331ec41b379caa60))
* wire illustrations into all docs + GitHub Pages ([8c99d84](https://github.com/pleasedodisturb/kestrel/commit/8c99d841f636f87d68aadff8f02de8a207c79336))
* wire illustrations into docs + GitHub Pages setup ([598bc49](https://github.com/pleasedodisturb/kestrel/commit/598bc49e1f0700b1e0933f5cbf9a315ae3554b06))


### Bug Fixes

* **03.3-01:** add _ensure_utc validators to 7 schema files for RFC 3339 compliance ([#258](https://github.com/pleasedodisturb/kestrel/issues/258)) ([19d59e6](https://github.com/pleasedodisturb/kestrel/commit/19d59e684b65047e3887880ef392e999a81636f9))
* add comments to empty except blocks (S108) ([2c6f82b](https://github.com/pleasedodisturb/kestrel/commit/2c6f82b7c7e7ad0120a3ba399099ac87cad061cb))
* add DB fixture to CLI tests that query profiles table ([#81](https://github.com/pleasedodisturb/kestrel/issues/81)) ([#82](https://github.com/pleasedodisturb/kestrel/issues/82)) ([af98479](https://github.com/pleasedodisturb/kestrel/commit/af984796016f12a98e75ee1bb0d1c8afc1b82a2b))
* add job_family to all test Profile fixtures + remove stale xfail markers ([1b609ef](https://github.com/pleasedodisturb/kestrel/commit/1b609ef9ee9ca0ae58e987e733964707cface116))
* add missing pytest import in test_cli.py ([14c78e5](https://github.com/pleasedodisturb/kestrel/commit/14c78e50c4d90cbfe325b0cf82149b520766f9d6))
* add tests/ to gitleaks allowlist for placeholder API keys ([d6e038b](https://github.com/pleasedodisturb/kestrel/commit/d6e038bd196fae8ab91b49d5f721e0b5a5ed4278))
* address documentation review findings ([78d5830](https://github.com/pleasedodisturb/kestrel/commit/78d5830edd29f92ecd9ba19ad8c03572b32fa35c))
* address documentation review findings ([322cb18](https://github.com/pleasedodisturb/kestrel/commit/322cb18a2880971a2922fde3476020a67aa20887))
* block scoring on incomplete profile and show banner ([#27](https://github.com/pleasedodisturb/kestrel/issues/27)) ([4bd6943](https://github.com/pleasedodisturb/kestrel/commit/4bd6943d34e53dbdcf69d1643d009f63ac3a3c64))
* **ci:** harden CI reliability — SonarCloud, commitlint, pytest-timeout ([#167](https://github.com/pleasedodisturb/kestrel/issues/167)) ([9fd67c4](https://github.com/pleasedodisturb/kestrel/commit/9fd67c4c9dfe276de398f9a9fec5d8abfa1c7cdc))
* **ci:** merge SonarCloud into CI workflow with coverage integration ([#163](https://github.com/pleasedodisturb/kestrel/issues/163)) ([709929d](https://github.com/pleasedodisturb/kestrel/commit/709929de07de1568be58df59751b7c20ee141dea))
* clean PII stragglers, fix lint, update tool docs ([49d9250](https://github.com/pleasedodisturb/kestrel/commit/49d925011e77249e640f0b6217c5ab237ad1190b))
* convert FastAPI endpoints to Annotated pattern + remove redundant response_model ([#50](https://github.com/pleasedodisturb/kestrel/issues/50)) ([a18babf](https://github.com/pleasedodisturb/kestrel/commit/a18babfafea0b86a2300f64f0d13fb047e048235))
* deduplicate Profile fixture data across 11 test files ([c631486](https://github.com/pleasedodisturb/kestrel/commit/c6314865ae8b54f55431b1a8269eccb396a3d137))
* deduplicate remaining inline Profile constructors in 5 test files ([6bca6fa](https://github.com/pleasedodisturb/kestrel/commit/6bca6fa7dd6fca12b426169be5261027db1df6cf))
* **deploy:** make Railway one-click deploy actually work ([#398](https://github.com/pleasedodisturb/kestrel/issues/398)) ([6af8c3e](https://github.com/pleasedodisturb/kestrel/commit/6af8c3e6df4e2044d5d24b2cfa8cc443c8367c50))
* detect OpenRouter credit exhaustion and surface to user ([#28](https://github.com/pleasedodisturb/kestrel/issues/28)) ([f29d1a9](https://github.com/pleasedodisturb/kestrel/commit/f29d1a9b14425e1847e8d9c9e5a2f21e71e92735))
* document HTTPException status codes in FastAPI endpoint responses param ([3d5cede](https://github.com/pleasedodisturb/kestrel/commit/3d5cede21a6a0a001671190637f969ecd5ab6309)), closes [#53](https://github.com/pleasedodisturb/kestrel/issues/53)
* documentation and config cleanup (round 2) ([7794636](https://github.com/pleasedodisturb/kestrel/commit/77946366e8c5851633f9d2192c24810219b430e1))
* documentation and config cleanup (round 2) ([a32b6ef](https://github.com/pleasedodisturb/kestrel/commit/a32b6efe674124c46b5c592ba5e9c500cbd50852))
* eliminate remaining RESP_NOT_FOUND duplication with **RESP_404 spread ([6055c56](https://github.com/pleasedodisturb/kestrel/commit/6055c56b9717a7d9a4601914024ad86de23f5dd6))
* exclude Claude skill docs from gitleaks scanning ([21ee8f3](https://github.com/pleasedodisturb/kestrel/commit/21ee8f3210a0eeb245b4f616237540372042feed))
* explain how to edit .env for non-technical users in README ([40092a8](https://github.com/pleasedodisturb/kestrel/commit/40092a8d360af6878363cb9413258bfd7bbf3368))
* extract "Not found" to RESP_NOT_FOUND constant (S1192) ([b0c947e](https://github.com/pleasedodisturb/kestrel/commit/b0c947e8565f783d782442bfdbcb89f2a144a467))
* extract nested ternary color chains and improve semantic HTML (S3358, S6853) ([676dba6](https://github.com/pleasedodisturb/kestrel/commit/676dba66810e26ddf4bc3d73bd545ec73452686b))
* extract shared response dicts to reduce SonarCloud duplication ([8dd4c89](https://github.com/pleasedodisturb/kestrel/commit/8dd4c89a155a47f2409e15dd46720881f692cbd1))
* format merged test files and remove unused pytest import ([73b071b](https://github.com/pleasedodisturb/kestrel/commit/73b071bb754aacad6f386349000513d722220848))
* format test_cli.py imports ([6493312](https://github.com/pleasedodisturb/kestrel/commit/6493312f5bb2175a0aa27ec09cecd2e22ccab2b8))
* format test_pages_links.py ([479b6ba](https://github.com/pleasedodisturb/kestrel/commit/479b6ba185a68004980ba68f8f160b3d577e2fff))
* **frontend:** resolve react-hooks/set-state-in-effect lint error ([#361](https://github.com/pleasedodisturb/kestrel/issues/361)) ([b47ca95](https://github.com/pleasedodisturb/kestrel/commit/b47ca95bad075ba3e6c9d093ddc159f7ec8f7604))
* **G-1274:** repair disabled workflows — scorecard pin, daily-scan guard, release-checks ([#415](https://github.com/pleasedodisturb/kestrel/issues/415)) ([ffef164](https://github.com/pleasedodisturb/kestrel/commit/ffef16470bd9dd35fe53e2584fbc18ff50c71916))
* **G-1288:** revert runtime to python:3.11-slim, guard runtime images from auto-bumps ([#427](https://github.com/pleasedodisturb/kestrel/issues/427)) ([174bee2](https://github.com/pleasedodisturb/kestrel/commit/174bee2cd4382e217003926d271b8261957db708))
* **G-1295:** correct npm-package README license from MIT to AGPL-3.0-or-later ([#440](https://github.com/pleasedodisturb/kestrel/issues/440)) ([b5f746b](https://github.com/pleasedodisturb/kestrel/commit/b5f746b54243fe0984d9e042e5ffb143ddc79262))
* **G-1348:** repair the dead OpenAI provider + cross-provider contract tests ([#464](https://github.com/pleasedodisturb/kestrel/issues/464)) ([5548482](https://github.com/pleasedodisturb/kestrel/commit/5548482f049a9199f9ba396de47400677cfc8233))
* **G-1349:** bump setuptools to &gt;=83.0.0 (PYSEC-2026-3447) ([#453](https://github.com/pleasedodisturb/kestrel/issues/453)) ([07c9640](https://github.com/pleasedodisturb/kestrel/commit/07c96400af21f08acc600f89dde91d24f3859083))
* **G-1350:** make in-package migrations the single source of truth ([#465](https://github.com/pleasedodisturb/kestrel/issues/465)) ([2bb1bae](https://github.com/pleasedodisturb/kestrel/commit/2bb1bae7f33d91d72c33d348bd442dbcef696a12))
* **G-1352:** scoring-v2 cross-phase cleanup (shadow gate, distillation desire, batch parity) ([#459](https://github.com/pleasedodisturb/kestrel/issues/459)) ([80a0561](https://github.com/pleasedodisturb/kestrel/commit/80a0561d79aff2b579d9f5306aba0fa353dee4e3))
* **G-1378:** guard openrouter premium-model routing in fallback chains ([#461](https://github.com/pleasedodisturb/kestrel/issues/461)) ([d83d2ed](https://github.com/pleasedodisturb/kestrel/commit/d83d2edb5526c827d94758f9569e6f920a0debce))
* **G-1391:** single-pass HTML-entity decode in stripHtml (js/double-escaping) ([#479](https://github.com/pleasedodisturb/kestrel/issues/479)) ([d58be8b](https://github.com/pleasedodisturb/kestrel/commit/d58be8baa3a2b1e4f9f8b874efa115ade0ce6df2))
* **G-1412:** code-scanning backlog — CodeQL highs, workflow token permissions, SHA/digest pinning ([#474](https://github.com/pleasedodisturb/kestrel/issues/474)) ([a57f544](https://github.com/pleasedodisturb/kestrel/commit/a57f5442b78ffd6cdc092b5125d2cba9d4968e19))
* **G-1427:** Web Storage shim covers Node 26's undefined localStorage global ([#491](https://github.com/pleasedodisturb/kestrel/issues/491)) ([3dce5ae](https://github.com/pleasedodisturb/kestrel/commit/3dce5aefd637ad4f45d8d9551b949a79a62afdc8))
* G-265 re-add BMAD/GSD gitignore entries dropped during merge ([#165](https://github.com/pleasedodisturb/kestrel/issues/165)) ([eca53fa](https://github.com/pleasedodisturb/kestrel/commit/eca53facef6f991925f529bfe661c8fbd66ccaa7))
* **G-266:** resolve 28 new-code SonarCloud blocker/critical issues ([#170](https://github.com/pleasedodisturb/kestrel/issues/170)) ([b6ee3aa](https://github.com/pleasedodisturb/kestrel/commit/b6ee3aac49068a1c047fc53096a35fd7aa2db142))
* **G-294:** add JSON parse retry and robust extraction in AI providers ([#188](https://github.com/pleasedodisturb/kestrel/issues/188)) ([02b3635](https://github.com/pleasedodisturb/kestrel/commit/02b3635f796d947042d531609ea4dabab9c5d5df))
* **G-297:** raise vague_responsibilities threshold from 200 to 400 chars ([#190](https://github.com/pleasedodisturb/kestrel/issues/190)) ([8f04f48](https://github.com/pleasedodisturb/kestrel/commit/8f04f4822dc94b1d8e54af4c8056abede991d1f1))
* **G-379:** sync all version artifacts with release-please ([#218](https://github.com/pleasedodisturb/kestrel/issues/218)) ([5b17a72](https://github.com/pleasedodisturb/kestrel/commit/5b17a72b276aaee7dece35758d0c6b72e46cb51d))
* **G-382:** resolve frontend TS build errors blocking PyPI publish ([#219](https://github.com/pleasedodisturb/kestrel/issues/219)) ([15f04fd](https://github.com/pleasedodisturb/kestrel/commit/15f04fd0f2dd993d118c3ded912b1ad9e75db9cd))
* **G-385:** add load_dotenv for reliable .env file reading ([#225](https://github.com/pleasedodisturb/kestrel/issues/225)) ([850d880](https://github.com/pleasedodisturb/kestrel/commit/850d88056915551f891e28bde2ed02196a53047b))
* **G-385:** scrub personal data from public repo (29 files) ([#220](https://github.com/pleasedodisturb/kestrel/issues/220)) ([ab2bf97](https://github.com/pleasedodisturb/kestrel/commit/ab2bf97153b56e7fef4252a6413e71e7cda39eb4))
* **G-401, G-456:** fix flaky CLI test + test_md_to_pdf failures ([#305](https://github.com/pleasedodisturb/kestrel/issues/305)) ([56d6087](https://github.com/pleasedodisturb/kestrel/commit/56d6087deff75596b6fed0fb724f252029781381))
* **G-412:** add test isolation guard — block real AI provider HTTP calls ([#310](https://github.com/pleasedodisturb/kestrel/issues/310)) ([bd375eb](https://github.com/pleasedodisturb/kestrel/commit/bd375eb16d105af40d97728029a804b423ffc5f3))
* **G-412:** add test isolation guard — prevent tests from hitting real AI providers ([#237](https://github.com/pleasedodisturb/kestrel/issues/237)) ([00c5720](https://github.com/pleasedodisturb/kestrel/commit/00c57208c0c78060606f5d218bf83545ddb455aa))
* **G-412:** format test_ai_isolation_guard.py for ruff ([#322](https://github.com/pleasedodisturb/kestrel/issues/322)) ([7ac487e](https://github.com/pleasedodisturb/kestrel/commit/7ac487e1600fa148a56e978dd634f959d4d640b3))
* **G-419:** fix SonarCloud coverage report path configuration ([#303](https://github.com/pleasedodisturb/kestrel/issues/303)) ([56af6a7](https://github.com/pleasedodisturb/kestrel/commit/56af6a75a17c543510f5767e659883a55228702c))
* **G-457:** recalibrate golden set fixtures after scoring evolution ([#260](https://github.com/pleasedodisturb/kestrel/issues/260)) ([885c670](https://github.com/pleasedodisturb/kestrel/commit/885c670184c66f305ce76cd70704a60ca984ab3c))
* **G-457:** recalibrate golden set fixtures for scoring evolution ([a7f6faf](https://github.com/pleasedodisturb/kestrel/commit/a7f6faf7d711c71b1e51c16f7627d96d4652ecae))
* **G-458:** fix ContactCreate enum validation for Schemathesis stateful mode ([#306](https://github.com/pleasedodisturb/kestrel/issues/306)) ([037ee2a](https://github.com/pleasedodisturb/kestrel/commit/037ee2aa6aeb0df29b026676d7769bc154ad09c7))
* **G-464:** restore version to 0.10.0 after G-392 regression ([#276](https://github.com/pleasedodisturb/kestrel/issues/276)) ([c9146b9](https://github.com/pleasedodisturb/kestrel/commit/c9146b9a54466a77f2bce7fd9d163b8ece28a26a))
* **G-464:** simplify Mermaid diagrams for GitHub rendering ([#267](https://github.com/pleasedodisturb/kestrel/issues/267)) ([e102257](https://github.com/pleasedodisturb/kestrel/commit/e10225790f6d5360c111cf7a746d81b467f18104))
* **G-488:** unblock all Docker install paths for new users ([#293](https://github.com/pleasedodisturb/kestrel/issues/293)) ([c31629b](https://github.com/pleasedodisturb/kestrel/commit/c31629bb7e88de519d55f84f26363c39f1a27350))
* **G-491:** fix release gate date parsing and qualifying commit detection ([#308](https://github.com/pleasedodisturb/kestrel/issues/308)) ([8300dbf](https://github.com/pleasedodisturb/kestrel/commit/8300dbfd5c4ac865b6a7782016c44085e13dae02))
* **G-491:** fix release gate heredoc syntax errors ([#315](https://github.com/pleasedodisturb/kestrel/issues/315)) ([872103c](https://github.com/pleasedodisturb/kestrel/commit/872103c57fff7798915eb1f6128234323071241d))
* **G-491:** safely handle failed_checks variable with special characters ([#312](https://github.com/pleasedodisturb/kestrel/issues/312)) ([97e4bd0](https://github.com/pleasedodisturb/kestrel/commit/97e4bd0ad0521cf5f256b7029cde5a15f1fd6921))
* **G-495:** fix discovery test mock/schema breakage (22 CI failures) ([#317](https://github.com/pleasedodisturb/kestrel/issues/317)) ([501b45e](https://github.com/pleasedodisturb/kestrel/commit/501b45eae3d3af6bf86f5e2c38befce1af40adf7))
* **G-496:** wire observability spans into cache and PII masking layers ([#318](https://github.com/pleasedodisturb/kestrel/issues/318)) ([e3aeb92](https://github.com/pleasedodisturb/kestrel/commit/e3aeb9207c60cbd5bf1ec39adb4d220849cb2bbe))
* **G-497:** add _build_fallback_chain to factory and wire into get_ai_provider ([#319](https://github.com/pleasedodisturb/kestrel/issues/319)) ([14870ac](https://github.com/pleasedodisturb/kestrel/commit/14870acf4def153c324a6a8d27f46d1f9cb615e5))
* **G-498:** fix stale test assertions for X-Title header and batch payload ([#320](https://github.com/pleasedodisturb/kestrel/issues/320)) ([f8d3387](https://github.com/pleasedodisturb/kestrel/commit/f8d33870bfc013c11c2c55edf1f79ac58335b024))
* **G-499:** fix doc link tests for reorganized docs directory ([#321](https://github.com/pleasedodisturb/kestrel/issues/321)) ([e9c2103](https://github.com/pleasedodisturb/kestrel/commit/e9c210359d7cfa3ade0cc0c698dc6ba8637acf72))
* **G-625:** type-aware setter for textarea fill in batch_apply_browser ([#373](https://github.com/pleasedodisturb/kestrel/issues/373)) ([55d0780](https://github.com/pleasedodisturb/kestrel/commit/55d0780824fe50aa6dd681d504f6d618e374a5c8))
* **G-roadmap:** fix md_to_pdf test failures — undefined variable and empty file crash ([#327](https://github.com/pleasedodisturb/kestrel/issues/327)) ([8272f81](https://github.com/pleasedodisturb/kestrel/commit/8272f813bab291630d21c34f4d4919d2fb27f091))
* GitHub Pages 404s + doc link tests + remove pricing doc ([a64bba1](https://github.com/pleasedodisturb/kestrel/commit/a64bba1d3a7243e4707c35896ac791b634e609f5))
* GitHub Pages rendering + doc link tests + remove pricing doc ([954245f](https://github.com/pleasedodisturb/kestrel/commit/954245fad3be14b8412aba4460de3a99dd45b48e))
* harden AI isolation guard against substring spoofing ([#353](https://github.com/pleasedodisturb/kestrel/issues/353)) ([f8e6b0b](https://github.com/pleasedodisturb/kestrel/commit/f8e6b0bb84d2e9ed3f137b31890d74279f2a047c))
* harden OAuth, PII masking, cache, and gitleaks config ([c9ed034](https://github.com/pleasedodisturb/kestrel/commit/c9ed034927308259853ca0ab2bbc3fb62aaaa43b))
* import ordering in test_cli.py ([71a53db](https://github.com/pleasedodisturb/kestrel/commit/71a53dbcd8cc1eeb9f4f7aadc3d8608ed6416e58))
* lint - use ternary for path resolution ([0fbd6e5](https://github.com/pleasedodisturb/kestrel/commit/0fbd6e5df0164eb89c9ac542f94c10076c7ccc01))
* pin GitHub Actions to full commit SHAs in SonarCloud workflow ([058aefd](https://github.com/pleasedodisturb/kestrel/commit/058aefd6faf5d7dc77fe7fdf10410f119c02253b))
* **profiles:** refuse DELETE if profile owns child rows; add rotating snapshot script ([#367](https://github.com/pleasedodisturb/kestrel/issues/367)) ([3f1a7b9](https://github.com/pleasedodisturb/kestrel/commit/3f1a7b9b6034e120d4b35d2a426d292d481a2033))
* properly remove try/finally blocks instead of just finally:pass ([e4d31ff](https://github.com/pleasedodisturb/kestrel/commit/e4d31ff9b620e3030b101e72d3b8bc48ead7ccd3))
* README now properly explains all 3 install paths ([b5f51dc](https://github.com/pleasedodisturb/kestrel/commit/b5f51dcd6b0b34425aa12a298abbbfd3adc3e0eb))
* README properly explains pip install, Docker, and Codespaces ([72a80ec](https://github.com/pleasedodisturb/kestrel/commit/72a80ecc519e1ab24a64e887f39a345f55eabb65))
* reduce test code duplication for SonarCloud quality gate ([81c458b](https://github.com/pleasedodisturb/kestrel/commit/81c458bb1bc54fd0d24f38bf46b15cb3c3ec30ae))
* remove hardcoded PII from SonarCloud MCP server defaults ([5efd115](https://github.com/pleasedodisturb/kestrel/commit/5efd115703b140cf406c160ad0a5bea1ace6f2e4))
* remove leaked personal assets and profile data ([2993390](https://github.com/pleasedodisturb/kestrel/commit/2993390e79636e85e5b8992444ccf37931e1e0bc))
* remove pricing doc, fix GitHub Pages doc rendering ([d0ef870](https://github.com/pleasedodisturb/kestrel/commit/d0ef870523e4ccf7d0614c2ae771c77fb94924f7))
* remove pricing strategy from public repo, fix Jekyll config ([b0618f5](https://github.com/pleasedodisturb/kestrel/commit/b0618f5d77b55ecb459d6ead6d3ee5567512eb14))
* remove unused imports in test_kestrel_start.py ([badd3a3](https://github.com/pleasedodisturb/kestrel/commit/badd3a3b1bf2590b5716a5b080b8f33904b7bedd))
* replace regex HTML filter with stdlib HTMLParser (CodeQL [#34](https://github.com/pleasedodisturb/kestrel/issues/34)) ([#34](https://github.com/pleasedodisturb/kestrel/issues/34)) ([9cb8908](https://github.com/pleasedodisturb/kestrel/commit/9cb8908becc201e5f788759845ef09fcec2fb472))
* replace URL substring checks with hostname validation (18 CodeQL alerts) ([#35](https://github.com/pleasedodisturb/kestrel/issues/35)) ([aed7983](https://github.com/pleasedodisturb/kestrel/commit/aed7983b909aea3c2531802479da0f5fad83c677))
* resolve 118 ruff lint errors in alembic migration files ([79bf49a](https://github.com/pleasedodisturb/kestrel/commit/79bf49a76e8dd55e5b2ce23fbbf1ad857928d499))
* resolve CI failures — ruff format + move scoreColor to utils ([fb2c999](https://github.com/pleasedodisturb/kestrel/commit/fb2c999b604a52535526d5b493b8cde75643374e))
* resolve leftover SonarCloud issues (S8410, S8415, S1244, S117) ([a4b7865](https://github.com/pleasedodisturb/kestrel/commit/a4b7865aaf94891208d114f9894396bf16311ba5))
* resolve PR [#132](https://github.com/pleasedodisturb/kestrel/issues/132) conflicts — combine security features from both branches ([#160](https://github.com/pleasedodisturb/kestrel/issues/160)) ([311bf69](https://github.com/pleasedodisturb/kestrel/commit/311bf692e8e0efb14c4c8e67a6ca0605686f9bdd))
* resolve SonarCloud issues across 6 batches (S8410, S8415, S1192, S108, S3776, S3358) ([c7ecfe4](https://github.com/pleasedodisturb/kestrel/commit/c7ecfe4bece6c26ec0079c80a0ad1a14aca474ed))
* resolve TypeScript/React SonarCloud issues in frontend (S6759, S6853, S3358, etc.) ([66a2275](https://github.com/pleasedodisturb/kestrel/commit/66a22758a61332da56eb6830134080ad93c3f562)), closes [#60](https://github.com/pleasedodisturb/kestrel/issues/60)
* route daily_pipeline through provider stack + loud failure alarm ([#332](https://github.com/pleasedodisturb/kestrel/issues/332)) ([b94bac5](https://github.com/pleasedodisturb/kestrel/commit/b94bac5114021eb97d285d923d32c1adce23178c))
* **security:** batch backend fixes for [#24](https://github.com/pleasedodisturb/kestrel/issues/24), [#25](https://github.com/pleasedodisturb/kestrel/issues/25), [#18](https://github.com/pleasedodisturb/kestrel/issues/18) ([#102](https://github.com/pleasedodisturb/kestrel/issues/102)) ([aaf62cb](https://github.com/pleasedodisturb/kestrel/commit/aaf62cb294645b3f53f95644c1d2ed3e226c2117))
* **security:** harden OAuth, cache, PII masking, and privacy registry ([5fa20cd](https://github.com/pleasedodisturb/kestrel/commit/5fa20cd844db83ee6785b47dd8053de37ac79c3b))
* setup SonarCloud CI properly and resolve ~420 issues ([#166](https://github.com/pleasedodisturb/kestrel/issues/166)) ([19458f3](https://github.com/pleasedodisturb/kestrel/commit/19458f3a4038fec1fbbe294632f8ee1bc0d29ac1))
* SonarCloud - 61 float comparisons + 19 empty blocks (80 issues) ([a1655b3](https://github.com/pleasedodisturb/kestrel/commit/a1655b32d1460b6be63a919c7a53ae2a435f98c3))
* SonarCloud - 80 issues (float comparisons + empty blocks) ([f598bff](https://github.com/pleasedodisturb/kestrel/commit/f598bff9f36b7b5cdd9b41b5c874528715e30ae9))
* SonarCloud - remove 119 redundant response_model + 33 unused vars ([2027ef4](https://github.com/pleasedodisturb/kestrel/commit/2027ef44fad087d69d01b904cc2be18ef8eaeeda))
* SonarCloud - remove 119 redundant response_model, fix unused vars ([2d2a469](https://github.com/pleasedodisturb/kestrel/commit/2d2a4690229876294069e3ee421abcbe6063f2f5))
* SonarCloud React - readonly props, keyboard a11y, form labels ([e669c83](https://github.com/pleasedodisturb/kestrel/commit/e669c83493885431c58e94cd29c6d8bc78a28b61))
* SonarCloud React - readonly props, keyboard a11y, form labels (107 issues) ([f3346df](https://github.com/pleasedodisturb/kestrel/commit/f3346dfad1f394b1b1b2f7558dead50d6da2750a))
* SonarCloud S117 - rename MockClient to mock_client (22 issues) ([7bae4ba](https://github.com/pleasedodisturb/kestrel/commit/7bae4ba0f5196d7e7a8641f4b19f9e98962014b1))
* SonarCloud S117 - rename MockClient to snake_case (22 issues) ([2f16462](https://github.com/pleasedodisturb/kestrel/commit/2f164628cb60b98a1c5fbf8d4d4a3e9909b03aa2))
* SonarCloud security - log injection, DoS, path traversal ([ba0fb58](https://github.com/pleasedodisturb/kestrel/commit/ba0fb5896afdcb44625acf582dc62f9bc3b79867))
* SonarCloud security - sanitize logs, bound loops, validate paths ([17a9e0f](https://github.com/pleasedodisturb/kestrel/commit/17a9e0f8d13730d7e69c3efc34115233c7d1d284))
* strip ANSI codes in CLI tests for CI compatibility ([0952860](https://github.com/pleasedodisturb/kestrel/commit/09528601e3925f275dfbefc272a6917372f99d51))
* unused variables, float equality, naming conventions (S1481+S1244+S117) ([783580e](https://github.com/pleasedodisturb/kestrel/commit/783580eac1e10e9637a352924809648a932cedca)), closes [#54](https://github.com/pleasedodisturb/kestrel/issues/54)
* update markdownify to &gt;=1.2.2 to resolve CVE-2025-46656 ([#133](https://github.com/pleasedodisturb/kestrel/issues/133)) ([dcb9a8c](https://github.com/pleasedodisturb/kestrel/commit/dcb9a8cb8e83a4ebb21ba971525c91a1e557799e))
* update vulnerable npm dependencies across all packages ([#32](https://github.com/pleasedodisturb/kestrel/issues/32)) ([31612ca](https://github.com/pleasedodisturb/kestrel/commit/31612ca65126e34f66cc46b0876e9eb7360cf62c))


### Performance

* **G-261:** compress system prompts — 67% token reduction ([#243](https://github.com/pleasedodisturb/kestrel/issues/243)) ([93bf719](https://github.com/pleasedodisturb/kestrel/commit/93bf7198aa85cffa6a97bd402245eaff93ac3a7c))
* **G-428:** use compact JSON serialization in AI provider score() calls ([#239](https://github.com/pleasedodisturb/kestrel/issues/239)) ([b41522d](https://github.com/pleasedodisturb/kestrel/commit/b41522d9e391e855059baf210db4e53da6050c10))
* **G-429:** system prompt deduplication — profile in cached system block ([#242](https://github.com/pleasedodisturb/kestrel/issues/242)) ([b54ed37](https://github.com/pleasedodisturb/kestrel/commit/b54ed3711d3b28a6316f4668c1e153a14ca5c508))


### Documentation

* add honest tool status - mark auto-apply as experimental ([32aea26](https://github.com/pleasedodisturb/kestrel/commit/32aea26d210d66f05b327112a2a0fb7e9836e650))
* add illustration credits (Maginary AI) and usage guide ([f018b51](https://github.com/pleasedodisturb/kestrel/commit/f018b512f860691a97970a3a02f97a411515dbfe))
* add nav index + restructure install by effort level ([#330](https://github.com/pleasedodisturb/kestrel/issues/330)) ([606bef4](https://github.com/pleasedodisturb/kestrel/commit/606bef4e49e5eb18d24b89630342499216548a0b))
* add Perplexity Computer to job search tool comparison ([#94](https://github.com/pleasedodisturb/kestrel/issues/94)) ([0986be3](https://github.com/pleasedodisturb/kestrel/commit/0986be3ccdb916b61c0ccf3068fcdf4167a0769c))
* add session summary for 2026-04-13 (BMAD installation) ([#169](https://github.com/pleasedodisturb/kestrel/issues/169)) ([50e52ae](https://github.com/pleasedodisturb/kestrel/commit/50e52ae2275d7d36c54930e41793d361ff44a7bf))
* add session summary for 2026-04-14 (Supabase research) ([#172](https://github.com/pleasedodisturb/kestrel/issues/172)) ([1fe3eb5](https://github.com/pleasedodisturb/kestrel/commit/1fe3eb54dc20adf3ff510b9dfdfd27c4b65bfda3))
* add session summary for 2026-04-16 ([#209](https://github.com/pleasedodisturb/kestrel/issues/209)) ([4c12580](https://github.com/pleasedodisturb/kestrel/commit/4c12580c87163ad7627681a1dd284f74725fb578))
* add session summary for 2026-04-23 ([#325](https://github.com/pleasedodisturb/kestrel/issues/325)) ([a2f0851](https://github.com/pleasedodisturb/kestrel/commit/a2f08511cf5b30d5435eec6122d5bba2052ba2ee))
* extract mobile UX findings for web responsive design ([#122](https://github.com/pleasedodisturb/kestrel/issues/122)) ([25f7c4d](https://github.com/pleasedodisturb/kestrel/commit/25f7c4d4e73e02d694027bb6fa6efc085b640b30))
* free tier pricing, real cost table, PII safety boundary ([#235](https://github.com/pleasedodisturb/kestrel/issues/235)) ([03a7ae2](https://github.com/pleasedodisturb/kestrel/commit/03a7ae2b818d086cdade69ed86997e9089225d28))
* **G-1281:** distill writing system — anti-slop, voice corpus, cover letters, LinkedIn ([#433](https://github.com/pleasedodisturb/kestrel/issues/433)) ([052bf9b](https://github.com/pleasedodisturb/kestrel/commit/052bf9ba65b1b087dde0304248ab3c6fd6a69dda))
* **G-1305:** add COE for the initial-commit PII exposure ([#445](https://github.com/pleasedodisturb/kestrel/issues/445)) ([e766c04](https://github.com/pleasedodisturb/kestrel/commit/e766c0413510fd028008667cf1648f6370a06349))
* **G-1315:** explain cost-optimal fallback-chain ordering ([#446](https://github.com/pleasedodisturb/kestrel/issues/446)) ([dea0d6a](https://github.com/pleasedodisturb/kestrel/commit/dea0d6ac60b4098bc7163dd53ff19c90b3a9cbcb))
* **G-1335:** add 2026-07 scoring-technique audit (7-agent research sweep) ([#450](https://github.com/pleasedodisturb/kestrel/issues/450)) ([e24e05a](https://github.com/pleasedodisturb/kestrel/commit/e24e05a1e3e2d09a933b0ccb938479a293c79900))
* **G-268:** add Jekyll front matter to scoring-evolution-epics ([#216](https://github.com/pleasedodisturb/kestrel/issues/216)) ([1b36d36](https://github.com/pleasedodisturb/kestrel/commit/1b36d365faf9d74c11778a5bd6ef34ae9b878474))
* **G-298:** add user-facing scoring explainer (how-scoring-works.md) ([#191](https://github.com/pleasedodisturb/kestrel/issues/191)) ([0357573](https://github.com/pleasedodisturb/kestrel/commit/03575732b4b8df7aedf37415f3a60ca0f8350ef0))
* **G-299:** add PII-scrubbed benchmark artifacts from G-286 validation ([#192](https://github.com/pleasedodisturb/kestrel/issues/192)) ([a1d1d5c](https://github.com/pleasedodisturb/kestrel/commit/a1d1d5c90807906ecba7659ea16af463dffc6086))
* **G-300:** create Kestrel feature audit for CareerOS sync matrix ([#202](https://github.com/pleasedodisturb/kestrel/issues/202)) ([7b1ea82](https://github.com/pleasedodisturb/kestrel/commit/7b1ea82a5024df03e0e53e55676a17186df480c5))
* **G-302:** validation report v2.0 — post-fix benchmark results ([#197](https://github.com/pleasedodisturb/kestrel/issues/197)) ([ea3ab6a](https://github.com/pleasedodisturb/kestrel/commit/ea3ab6a248d106d5d5d6f6acb7a696c5339f1254))
* **G-305:** add testing strategy research docs in 3 formats ([#195](https://github.com/pleasedodisturb/kestrel/issues/195)) ([c13f42a](https://github.com/pleasedodisturb/kestrel/commit/c13f42a225a791cee08ffbda78712d468664476d))
* **G-305:** research docs integration — license fix, scoring docs, README matrix ([#198](https://github.com/pleasedodisturb/kestrel/issues/198)) ([4417c8c](https://github.com/pleasedodisturb/kestrel/commit/4417c8c6ff241ac7552b8d16c401ceb3f3ba0626))
* **G-305:** testing strategy — what shipped, what was trimmed, and why ([#259](https://github.com/pleasedodisturb/kestrel/issues/259)) ([80e918f](https://github.com/pleasedodisturb/kestrel/commit/80e918f421c691ec370a40b22d47e1e74c2416ca))
* **G-306:** add CI/CD research docs in 4 formats ([#196](https://github.com/pleasedodisturb/kestrel/issues/196)) ([80591d2](https://github.com/pleasedodisturb/kestrel/commit/80591d2701650216f218bb5210960a657f094b83))
* **G-348:** add 3-layer token optimization documentation ([#247](https://github.com/pleasedodisturb/kestrel/issues/247)) ([b1281f3](https://github.com/pleasedodisturb/kestrel/commit/b1281f308ce471adc6ef6f4470770bb85b236464))
* **G-348:** add benchmark results to token optimization docs and README ([#252](https://github.com/pleasedodisturb/kestrel/issues/252)) ([e90fcbb](https://github.com/pleasedodisturb/kestrel/commit/e90fcbb9725f0f9525babacaa4ddc8f2277a20f5))
* **G-437:** cost control research — 4 research documents ([#257](https://github.com/pleasedodisturb/kestrel/issues/257)) ([1b31d01](https://github.com/pleasedodisturb/kestrel/commit/1b31d012881af246b1194e4566aa366c177f61f4))
* **G-438:** comprehensive documentation for cost control epic ([#288](https://github.com/pleasedodisturb/kestrel/issues/288)) ([76d06f0](https://github.com/pleasedodisturb/kestrel/commit/76d06f0f4386478bb99ea64a8cd7244db396723e))
* **G-444:** add edutainment guide for AI costs, tiers, and privacy ([#268](https://github.com/pleasedodisturb/kestrel/issues/268)) ([7197151](https://github.com/pleasedodisturb/kestrel/commit/719715148eb22fbcf0e65918c2b5344e4504afc0))
* **G-452:** add automation paths guide ([#269](https://github.com/pleasedodisturb/kestrel/issues/269)) ([8ea809f](https://github.com/pleasedodisturb/kestrel/commit/8ea809fcb228368df2bd8153d5b74c08b38fd4c0))
* **G-454:** research OpenRouter rate limit tiers at $0/$10/$50 balance ([#271](https://github.com/pleasedodisturb/kestrel/issues/271)) ([dc359c2](https://github.com/pleasedodisturb/kestrel/commit/dc359c20b1bade03d719aab7980394aa21f0fbb2))
* **G-455:** research preset tier validation with real model benchmarks ([#279](https://github.com/pleasedodisturb/kestrel/issues/279)) ([eba4a09](https://github.com/pleasedodisturb/kestrel/commit/eba4a0973d1bdb7af483a5fc63ddbc99b4374c91))
* **G-464:** documentation audit, reorg & rewrite ([#266](https://github.com/pleasedodisturb/kestrel/issues/266)) ([6a79cd2](https://github.com/pleasedodisturb/kestrel/commit/6a79cd22509acca496cdaa8f337a3eeb128cd8db))
* **G-464:** move "How we build" section to CONTRIBUTING.md ([#326](https://github.com/pleasedodisturb/kestrel/issues/326)) ([52cbf00](https://github.com/pleasedodisturb/kestrel/commit/52cbf00ebd2f49831738c32493d05d9561a9d455))
* **G-464:** rewrite README for first-time users — cut 55%, sharpen hook ([#323](https://github.com/pleasedodisturb/kestrel/issues/323)) ([e13c7b1](https://github.com/pleasedodisturb/kestrel/commit/e13c7b1613f6f07eb8a22cd3ff024bdbaca7c8c2))
* **G-465:** mark mobile app as planned future release in CLAUDE.md ([#290](https://github.com/pleasedodisturb/kestrel/issues/290)) ([7a31662](https://github.com/pleasedodisturb/kestrel/commit/7a316621e549bbad80bceb6aae559968f55c00aa))
* **G-489:** document release pipeline, smoke tests, and bug sync workflows ([#307](https://github.com/pleasedodisturb/kestrel/issues/307)) ([b4aabf6](https://github.com/pleasedodisturb/kestrel/commit/b4aabf6165024ca22528a16dd99b7fdb2a7b4d52))
* **G-677:** land repo-coaching playbook (research + masterlist + QUICK-APPLY + 19 snippets) ([#374](https://github.com/pleasedodisturb/kestrel/issues/374)) ([55180c5](https://github.com/pleasedodisturb/kestrel/commit/55180c5cc0b382303269bb8530fb397d7c4d5dec))
* **G-842:** CLAUDE.md cleanup — fix stale refs + strip GSD boilerplate ([#389](https://github.com/pleasedodisturb/kestrel/issues/389)) ([c79ce71](https://github.com/pleasedodisturb/kestrel/commit/c79ce71e899385b04373bb030c737b5a0372457e))
* **G-851:** fix stale test-count badge in REFERENCE.md ([#390](https://github.com/pleasedodisturb/kestrel/issues/390)) ([caf2e52](https://github.com/pleasedodisturb/kestrel/commit/caf2e52a08317c80fc7068c638546f61fd7acd27))
* public roadmap — real screenshots, user story, deploy buttons ([#328](https://github.com/pleasedodisturb/kestrel/issues/328)) ([1ed5db5](https://github.com/pleasedodisturb/kestrel/commit/1ed5db5c8b66f3a5f799bc9c54898d42177bee24))
* rewrite CLAUDE.md with dev commands and mobile coverage ([#123](https://github.com/pleasedodisturb/kestrel/issues/123)) ([7a33745](https://github.com/pleasedodisturb/kestrel/commit/7a33745413e6dbf0809a503a29816718891e839c))


### Dependencies

* bump @size-limit/file from 11.2.0 to 12.1.0 in /frontend ([#425](https://github.com/pleasedodisturb/kestrel/issues/425)) ([02621ef](https://github.com/pleasedodisturb/kestrel/commit/02621ef929eab66957dca0399d3105ca2300e442))
* bump @tanstack/react-query from 5.100.9 to 5.101.0 in /frontend ([#386](https://github.com/pleasedodisturb/kestrel/issues/386)) ([c282c9a](https://github.com/pleasedodisturb/kestrel/commit/c282c9a24c5b13fe7694463f5a6f8753b0507ddb))
* bump @tanstack/react-query in /frontend in the tanstack group ([#357](https://github.com/pleasedodisturb/kestrel/issues/357)) ([85e8c8b](https://github.com/pleasedodisturb/kestrel/commit/85e8c8b805dce74d00fb57d1fd5551a57f3a6ff2))
* bump @tanstack/react-query in /frontend in the tanstack group ([#411](https://github.com/pleasedodisturb/kestrel/issues/411)) ([707bc94](https://github.com/pleasedodisturb/kestrel/commit/707bc9402e3340e6cfae6a11c6bb5317f0a3eca3))
* bump @tanstack/react-query in /frontend in the tanstack group ([#487](https://github.com/pleasedodisturb/kestrel/issues/487)) ([c1e7458](https://github.com/pleasedodisturb/kestrel/commit/c1e74585128bcb28ff98a2a48244345386bb6fc4))
* bump @types/node from 24.12.0 to 25.6.0 in /frontend ([#344](https://github.com/pleasedodisturb/kestrel/issues/344)) ([ac7928d](https://github.com/pleasedodisturb/kestrel/commit/ac7928d8382ec8890384ccfdebf6577c78076b78))
* bump globals from 17.4.0 to 17.5.0 in /frontend ([#343](https://github.com/pleasedodisturb/kestrel/issues/343)) ([e0b4ba8](https://github.com/pleasedodisturb/kestrel/commit/e0b4ba838807b930045905ebc320323ef661e23c))
* bump globals from 17.5.0 to 17.7.0 in /frontend ([#414](https://github.com/pleasedodisturb/kestrel/issues/414)) ([6d50b07](https://github.com/pleasedodisturb/kestrel/commit/6d50b07461bd0cdd34944dab6a8894a18410ed62))
* bump jsdom from 29.0.2 to 29.1.1 in /frontend ([#431](https://github.com/pleasedodisturb/kestrel/issues/431)) ([69a060f](https://github.com/pleasedodisturb/kestrel/commit/69a060f7fdbe8f187ed294c481fe196ad942029c))
* bump python from 3.11-slim to 3.14-slim ([#418](https://github.com/pleasedodisturb/kestrel/issues/418)) ([5f195bf](https://github.com/pleasedodisturb/kestrel/commit/5f195bf5f4a3b7710e70059fe02e458b4877a2a7))
* bump react-router and react-router-dom in /frontend ([#392](https://github.com/pleasedodisturb/kestrel/issues/392)) ([bea6383](https://github.com/pleasedodisturb/kestrel/commit/bea63839d1aae0c146d7c05f9f23f6edec15b818))
* bump react-router-dom from 7.13.1 to 7.14.2 in /frontend ([#336](https://github.com/pleasedodisturb/kestrel/issues/336)) ([f7d2ae2](https://github.com/pleasedodisturb/kestrel/commit/f7d2ae2f9d5f01886e7ad9cd6f63ffbbe89f9802))
* bump recharts from 3.8.0 to 3.9.2 in /frontend ([#430](https://github.com/pleasedodisturb/kestrel/issues/430)) ([1ba877b](https://github.com/pleasedodisturb/kestrel/commit/1ba877b325d26e967ec2fead75776dc537b7f624))
* bump size-limit from 11.2.0 to 12.1.0 in /frontend ([#426](https://github.com/pleasedodisturb/kestrel/issues/426)) ([2e14ff1](https://github.com/pleasedodisturb/kestrel/commit/2e14ff130f60603f0926574fc4a99b1cb194349a))
* bump the eslint group across 1 directory with 3 updates ([#409](https://github.com/pleasedodisturb/kestrel/issues/409)) ([9fdac8d](https://github.com/pleasedodisturb/kestrel/commit/9fdac8d97d480395eeaf4631eeaafb18ad84791a))
* bump the eslint group in /frontend with 2 updates ([#385](https://github.com/pleasedodisturb/kestrel/issues/385)) ([b3a2474](https://github.com/pleasedodisturb/kestrel/commit/b3a24744f3a7f11c7daab1b7dd320227f7845709))
* bump the eslint group in /frontend with 2 updates ([#486](https://github.com/pleasedodisturb/kestrel/issues/486)) ([812b890](https://github.com/pleasedodisturb/kestrel/commit/812b89083acb50c26ddd24e51270068cb39c5bb4))
* bump the react group across 1 directory with 2 updates ([#354](https://github.com/pleasedodisturb/kestrel/issues/354)) ([0125f16](https://github.com/pleasedodisturb/kestrel/commit/0125f16a9f23c3a5edbc030128b28d0a2a9cde8d))
* bump the react group in /frontend with 2 updates ([#484](https://github.com/pleasedodisturb/kestrel/issues/484)) ([01cef5f](https://github.com/pleasedodisturb/kestrel/commit/01cef5f13bbeeeebd5f7c4e3fcd9259bfcd92a26))
* bump the react group in /frontend with 3 updates ([#384](https://github.com/pleasedodisturb/kestrel/issues/384)) ([e6444ff](https://github.com/pleasedodisturb/kestrel/commit/e6444ff07f558fdd79416f7fd74844ab951d0ba4))
* bump the tailwind group across 1 directory with 2 updates ([#358](https://github.com/pleasedodisturb/kestrel/issues/358)) ([736c87e](https://github.com/pleasedodisturb/kestrel/commit/736c87e2a590ebd0405abe7839ddf70250feb778))
* bump the tailwind group across 1 directory with 2 updates ([#412](https://github.com/pleasedodisturb/kestrel/issues/412)) ([0b7cb11](https://github.com/pleasedodisturb/kestrel/commit/0b7cb11974ba974eddafa3a3496a9b562f677db0))
* bump the tailwind group across 1 directory with 2 updates ([#488](https://github.com/pleasedodisturb/kestrel/issues/488)) ([ded357f](https://github.com/pleasedodisturb/kestrel/commit/ded357f6c457e6837668896fc50a2c6a42ea9375))
* bump the tailwind group in /frontend with 2 updates ([#387](https://github.com/pleasedodisturb/kestrel/issues/387)) ([c17b177](https://github.com/pleasedodisturb/kestrel/commit/c17b1775e0b84522a099fd06ecdfea38398d1055))
* bump the vitest group across 1 directory with 2 updates ([#413](https://github.com/pleasedodisturb/kestrel/issues/413)) ([a26cbe8](https://github.com/pleasedodisturb/kestrel/commit/a26cbe8a03c74610c647e7702f9f009809d3ef5d))
* bump the vitest group across 1 directory with 3 updates ([#489](https://github.com/pleasedodisturb/kestrel/issues/489)) ([d68dafc](https://github.com/pleasedodisturb/kestrel/commit/d68dafcfd5fcb7ef6f536e7010ddd62c8da9aaf2))
* bump the vitest group in /frontend with 2 updates ([#388](https://github.com/pleasedodisturb/kestrel/issues/388)) ([9136e5c](https://github.com/pleasedodisturb/kestrel/commit/9136e5c6bff802416d3723d8b7a1fffffa491ef7))
* bump typescript from 6.0.2 to 6.0.3 in /frontend ([#424](https://github.com/pleasedodisturb/kestrel/issues/424)) ([10c3938](https://github.com/pleasedodisturb/kestrel/commit/10c39383c8054cbde85c947fe3991e5341fe609f))
* bump typescript-eslint from 8.57.0 to 8.59.1 in /frontend ([#341](https://github.com/pleasedodisturb/kestrel/issues/341)) ([5bc5677](https://github.com/pleasedodisturb/kestrel/commit/5bc567773e31032df0c8bdfa01e5be23c3a37cbe))
* bump vite from 8.0.7 to 8.0.11 in /frontend ([#359](https://github.com/pleasedodisturb/kestrel/issues/359)) ([9ba38e3](https://github.com/pleasedodisturb/kestrel/commit/9ba38e33dc1669a2bfa41466bb6dff985c8e1fea))
* bump vite from 8.1.0 to 8.1.3 in /frontend ([#432](https://github.com/pleasedodisturb/kestrel/issues/432)) ([cba3807](https://github.com/pleasedodisturb/kestrel/commit/cba3807de3769d90291185dd2e68a3a7a80ea51c))
* **frontend:** bump eslint group manually (replaces stuck [#355](https://github.com/pleasedodisturb/kestrel/issues/355)) ([#363](https://github.com/pleasedodisturb/kestrel/issues/363)) ([ad3a1df](https://github.com/pleasedodisturb/kestrel/commit/ad3a1dfe2a1a6b760a0bb0fbcb453258cb37c42e))
* **G-1384:** bump brace-expansion to 5.0.7 in frontend + dashboard ([#466](https://github.com/pleasedodisturb/kestrel/issues/466)) ([3838e13](https://github.com/pleasedodisturb/kestrel/commit/3838e13033cfc2c86f94a56176f6b98d5c02ae36))
* **G-1408:** fix all 9 open Dependabot alerts (1 critical) — extension, dashboard, worker ([#472](https://github.com/pleasedodisturb/kestrel/issues/472)) ([5cf50ea](https://github.com/pleasedodisturb/kestrel/commit/5cf50eae1057a98251838510b4972aecf095918c))
* **G-1412:** react-router 7.18.1 + brace-expansion/postcss advisory bumps (frontend) ([#476](https://github.com/pleasedodisturb/kestrel/issues/476)) ([3eeb600](https://github.com/pleasedodisturb/kestrel/commit/3eeb6001e9b7e9701ebe3d817e89f81bf1d3381a))
* Update dependency lucide-react to v1 ([#149](https://github.com/pleasedodisturb/kestrel/issues/149)) ([20440d0](https://github.com/pleasedodisturb/kestrel/commit/20440d0d789e7d4a63734b00dd40856ccd8f6a09))
* Update docker/build-push-action action to v7 ([#145](https://github.com/pleasedodisturb/kestrel/issues/145)) ([e03e971](https://github.com/pleasedodisturb/kestrel/commit/e03e9710a806b79901753903f7878f60cb0dc97f))
* Update docker/setup-buildx-action action to v4 ([35028ce](https://github.com/pleasedodisturb/kestrel/commit/35028cea13d4a9054c5c5e05a76e05004e65f9ff))
* Update GitHub Artifact Actions ([#147](https://github.com/pleasedodisturb/kestrel/issues/147)) ([5b203e6](https://github.com/pleasedodisturb/kestrel/commit/5b203e60954098fdf84953c5654c4ccf74f9a1cb))
* update GitHub artifact actions to latest majors ([24c4c7f](https://github.com/pleasedodisturb/kestrel/commit/24c4c7f0c245766ad7f149ad8dce52bb25370638))
* update openai requirement from &gt;=1.0.0 to &gt;=2.35.1 ([#342](https://github.com/pleasedodisturb/kestrel/issues/342)) ([361927b](https://github.com/pleasedodisturb/kestrel/commit/361927bfc02d72370e196fa4b37baa5cb96fd823))
* update openai requirement from &gt;=2.35.1 to &gt;=2.40.0 ([#380](https://github.com/pleasedodisturb/kestrel/issues/380)) ([2035358](https://github.com/pleasedodisturb/kestrel/commit/20353580648563f8823b6b4aecdf761422965e2e))
* update openai requirement from &gt;=2.41.0 to &gt;=2.44.0 ([#410](https://github.com/pleasedodisturb/kestrel/issues/410)) ([6eed7a6](https://github.com/pleasedodisturb/kestrel/commit/6eed7a65e9dd8149b3e92d58608bd8c2425070e7))
* update openai requirement from &gt;=2.44.0 to &gt;=2.50.0 ([#485](https://github.com/pleasedodisturb/kestrel/issues/485)) ([80becab](https://github.com/pleasedodisturb/kestrel/commit/80becab47eb80788c50c58db4698cc1c20cb3a1e))
* update pandas requirement from &lt;3,&gt;=2.2.0 to &gt;=2.2.0,&lt;4 ([#335](https://github.com/pleasedodisturb/kestrel/issues/335)) ([7fb9a6e](https://github.com/pleasedodisturb/kestrel/commit/7fb9a6e7db0f7ef68dc648de26947184bf5261ee))
* update pyyaml requirement from &gt;=6.0 to &gt;=6.0.3 ([#340](https://github.com/pleasedodisturb/kestrel/issues/340)) ([0c2429d](https://github.com/pleasedodisturb/kestrel/commit/0c2429db942dc4cda12fab1e836b4342ee4de0fd))

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
