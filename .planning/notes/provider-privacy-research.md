---
title: Provider Privacy Research — Factual Findings
date: 2026-04-21
context: 4 parallel research agents, evidence-based with source links
---

# Provider Privacy Research

## Google / Gemini

- **Free tier = training data.** Prompts and responses used to improve models. Human reviewers may see them.
- **EU users cannot use free tier** per Google's own Additional Terms.
- **Paid tier:** Not used for training by default. 55-day log retention.
- **Track record:** €575M+ CNIL fines, $5B Incognito Mode settlement, unilateral 2023 privacy policy expansion.
- **Incidents:** Gemini prompts leaked to Google Search index (Feb 2024), GeminiJack zero-click exfiltration vuln (2025).
- Sources: [Google logs policy](https://ai.google.dev/gemini-api/docs/logs-policy), [CNN Incognito settlement](https://www.cnn.com/2024/04/01/tech/google-to-delete-data-records-to-settle-incognito-lawsuit/index.html)

## xAI / Grok

- **API without data sharing:** No training, 30-day retention. Reasonable terms.
- **Data sharing program ($150/mo credits):** Uses all API data for training. **Irrevocable** — cannot opt out once enrolled.
- **X platform pattern:** Opt-out-by-default training toggle (hidden 7 steps deep), discovered ~2 months after activation.
- **Regulatory:** Irish DPC emergency action (2024), formal GDPR inquiry (2025), Grok image investigation (2026), €120M DSA fine (2025).
- Sources: [xAI Enterprise ToS](https://x.ai/legal/terms-of-service-enterprise), [TechCrunch DPC action](https://techcrunch.com/2024/09/04/irelands-privacy-watchdog-ends-legal-fight-with-x-over-data-use-for-ai-after-it-agrees-to-permanent-limits/)

## OpenAI

- **API:** Not used for training since March 2023. 30-day retention for abuse monitoring.
- **ZDR:** Requires enterprise sales approval — not self-serve for typical API users.
- **Corporate shift:** Nonprofit → capped-profit → for-profit PBC (Oct 2025). Microsoft holds 27%.
- **Incidents:** ChatGPT Redis bug exposed payment info (Mar 2023), unreported internal hack (2023).
- **Worldcoin:** CEO Sam Altman's iris-scanning project banned/suspended in Kenya, Portugal, Hong Kong.
- **Regulatory:** €15M Italian GDPR fine (annulled Mar 2026), active FTC investigation.
- Sources: [OpenAI data controls](https://platform.openai.com/docs/guides/your-data), [NPR Worldcoin](https://time.com/6300522/worldcoin-sam-altman/)

## Anthropic

- **API:** Not used for training. 7-day retention (shortest of all major providers).
- **ZDR:** Available via addendum. Applies to API and Claude Code with commercial keys.
- **Corporate:** Delaware PBC with Long-Term Benefit Trust for board independence.
- **Concerns:** Consumer opt-in training dark pattern (Aug 2025), $1.5B copyright settlement (pirated books).
- **Incidents:** CMS leak of unreleased model details (Mar 2026), Claude Code source accidental publish (Mar 2026). Neither involved customer data.
- **No regulatory fines** as of April 2026.
- Sources: [Anthropic privacy center](https://privacy.claude.com/en/articles/10023548-how-long-do-you-store-my-data), [TechCrunch consumer opt-out](https://techcrunch.com/2025/08/28/anthropic-users-face-a-new-choice-opt-out-or-share-your-data-for-ai-training/)
