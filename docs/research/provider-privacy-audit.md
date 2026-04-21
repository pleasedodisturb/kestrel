# Provider Privacy Audit

*Research date: 2026-04-21 | Purpose: Factual privacy disclosures for Kestrel's AI provider selection*

## Trust Matrix Summary

| Provider | API Training | Retention | ZDR | GDPR Fines | Trust Signal |
|----------|-------------|-----------|-----|------------|-------------|
| **Anthropic** | No | 7 days | Yes (addendum) | None | Strongest API privacy |
| **OpenAI** | No (since 2023) | 30 days | Enterprise only | EUR 15M (annulled) | Moderate |
| **Google/Gemini** | Free: YES / Paid: No | 55 days | Vertex only | EUR 575M+ | Free tier is a data trap |
| **xAI/Grok** | No (paid) / Yes (data sharing) | 30 days | No | Multiple active | Irrevocable data sharing |

---

## Google / Gemini

### API Data Policy
- **Free tier:** Prompts and responses ARE used to improve Google's models. May be reviewed by human annotators.
- **Paid tier:** Not used for training by default. 55-day log retention. Logging opt-in.
- **Vertex AI (Google Cloud):** Contractual no-training guarantee. Zero data retention available.
- **EU/EEA/UK/Swiss users cannot use free tier** per Google's Additional Terms: "You may use only Paid Services when making API Clients available to users in the European Economic Area, Switzerland, or the United Kingdom."

### Track Record
- **EUR 575M+ in CNIL fines** (France) for cookie consent violations and displaying ads without consent (EUR 100M in 2020, EUR 150M in 2021, EUR 325M in September 2025)
- **$5B Incognito Mode class action settlement** (April 2024) — Google tracked users in Chrome "Incognito" mode. Settlement required deleting "billions of data records" but zero monetary damages.
- **July 2023 privacy policy expansion:** Unilateral broadening to explicitly allow using publicly available data for AI training.
- **November 2025 Gmail/Gemini controversy:** Lawsuit accused Google of giving Gemini default access to Gmail, Chat, and Meet content via policy change.

### Gemini-Specific Incidents
- **February 2024:** User prompts briefly appeared in Google Search results. Resolved within hours.
- **2025 GeminiJack:** Zero-click indirect prompt injection vulnerability could exfiltrate user data without interaction. Discovered by Noma Labs, patched.
- **2025 API key exposure:** 2,863 publicly exposed Google API keys could access Gemini; one developer hit with $15,400 in fraudulent charges.

### Sources
- [Google Logs Policy](https://ai.google.dev/gemini-api/docs/logs-policy)
- [Vertex AI ZDR](https://docs.google.google.com/vertex-ai/generative-ai/docs/vertex-ai-zero-data-retention)
- [CNN: Incognito Settlement](https://www.cnn.com/2024/04/01/tech/google-to-delete-data-records-to-settle-incognito-lawsuit/index.html)
- [Gemini API Terms (EU restriction)](https://ai.google.dev/gemini-api/terms)

---

## xAI / Grok

### API Data Policy
- **Paid API (no data sharing):** No training on user content. Auto-deleted within 30 days.
- **Data sharing program ($150/mo credits):** xAI uses ALL API interactions for training. **Irrevocable** — once enrolled, cannot opt out. Requires $5 minimum prior spend. Only team admins can enable.

### X/Twitter Platform Pattern (parent company)
- **November 2024 ToS update:** Grants "worldwide, non-exclusive, royalty-free license" to use all X user content for AI training. Non-EU users cannot opt out.
- **Mid-2024 opt-out-by-default toggle:** X silently enabled Grok training data sharing. Users had to navigate 7 steps to find and disable it. Discovered ~2 months after activation.
- **Private accounts:** No longer explicitly excluded from data usage.

### Regulatory Actions
- **Irish DPC emergency action (Aug 2024):** Forced X to permanently suspend processing EU/EEA public post data for Grok training and delete already-ingested data. No fine imposed.
- **Irish DPC formal GDPR inquiry (April 2025):** New investigation into X using posts for Grok training.
- **Irish DPC image investigation (Feb 2026):** GDPR investigation into Grok generating non-consensual sexualized images of real people, including children.
- **EU DSA fine (Dec 2025):** EUR 120M for advertising transparency and user verification breaches.
- **EU Commission (Jan 2026):** Formal DSA investigation, ordered preservation of all internal documents until end of 2026.

### Sources
- [xAI Enterprise ToS](https://x.ai/legal/terms-of-service-enterprise)
- [xAI Data Sharing Program](https://cloudcredits.io/providers/xai/programs/data-sharing-program)
- [TechCrunch: DPC Action](https://techcrunch.com/2024/09/04/irelands-privacy-watchdog-ends-legal-fight-with-x-over-data-use-for-ai-after-it-agrees-to-permanent-limits/)
- [CNN: X ToS Update](https://www.cnn.com/2024/10/21/tech/x-twitter-terms-of-service)

---

## OpenAI

### API Data Policy
- **Not used for training** since March 1, 2023 (default off for API).
- **30-day retention** for abuse monitoring (vs Anthropic's 7 days).
- **Zero Data Retention:** Available but requires enterprise sales approval — not self-serve for typical API users.
- Exception: suspected CSAM content retained even under ZDR.

### Corporate Structure
- **October 2025:** Completed restructuring from capped-profit to Public Benefit Corporation. Microsoft holds 27% equity. Data governance commitments from nonprofit era now governed by for-profit PBC with investor obligations.

### Track Record
- **March 2023 (Redis bug):** ChatGPT exposed chat titles and payment info of 1.2% of Plus subscribers.
- **Early 2023 (unreported hack):** Hacker accessed internal messaging systems. OpenAI chose not to disclose publicly.
- **2023-2024:** 225,000+ OpenAI credentials found for sale, stolen via infostealer malware.

### Worldcoin / World ID (CEO Sam Altman)
Sam Altman co-founded Worldcoin, which collects iris biometric scans:
- **Kenya:** Court-ordered biometric data deletion
- **Portugal:** Suspended over minor data protection
- **Hong Kong:** Ordered to cease, calling collection "excessive and unnecessary"

Separate from OpenAI but reveals CEO's stance on aggressive data collection.

### Regulatory Actions
- **March 2023:** Italy temporarily banned ChatGPT (first country to do so).
- **December 2024:** Italy fined OpenAI EUR 15M for GDPR violations (annulled by Rome court March 2026).
- **July 2023:** FTC opened consumer protection investigation (active).
- **January 2026:** Court ordered OpenAI to produce 20M ChatGPT conversation logs in NYT lawsuit discovery.

### Sources
- [OpenAI Data Controls](https://platform.openai.com/docs/guides/your-data)
- [OpenAI Enterprise Privacy](https://openai.com/enterprise-privacy/)
- [TIME: Worldcoin](https://time.com/6300522/worldcoin-sam-altman/)
- [CNBC: Corporate Restructuring](https://www.cnbc.com/2025/10/28/open-ai-for-profit-microsoft.html)

---

## Anthropic

### API Data Policy
- **Not used for training.** Explicit policy.
- **7-day retention** (shortest of all major providers; reduced from 30 days in September 2025).
- **Zero Data Retention:** Available via addendum. Applies to API and products using commercial org API keys (including Claude Code).

### Corporate Structure
- Delaware Public Benefit Corporation with Long-Term Benefit Trust (LTBT) — independent trustees gradually gain board control.
- Purpose statement: "responsible development of advanced AI for the long-term benefit of humanity."
- PBC status doesn't create enforceable privacy obligations but provides legal latitude to weigh externalities.

### Concerns
- **August 2025 consumer opt-in controversy:** Introduced opt-in training on consumer (free/Pro/Max) chat data with 5-year retention. Criticized for dark-pattern UI (large "Accept" button, tiny opt-out toggle defaulted to On). **API and commercial customers explicitly excluded.**
- **$1.5B copyright settlement (September 2025):** Anthropic's use of lawfully acquired books was fair use, but maintaining ~7M pirated book copies was infringement. $3,000 per book for ~500K titles. Training data sourcing issue, not API user data.

### Security Incidents (2026, neither involving customer data)
- **March 2026:** Internal CMS exposed ~3,000 unpublished assets including unreleased model details.
- **March 31, 2026:** Claude Code source (512K lines) accidentally published due to missing config line.

### No regulatory fines as of April 2026.

### Comparison
| | Anthropic API | OpenAI API | Google Vertex AI |
|---|---|---|---|
| Training on API data | No | No (default) | No (contractual) |
| Retention | 7 days | 30 days | Varies |
| ZDR option | Yes (addendum) | Yes (Enterprise) | Yes (contractual) |
| Consumer training | Opt-out (Aug 2025) | Opt-out | Opt-out |

### Sources
- [Anthropic Privacy Center — Data Retention](https://privacy.claude.com/en/articles/10023548-how-long-do-you-store-my-data)
- [Anthropic Privacy Center — ZDR](https://privacy.claude.com/en/articles/8956058-i-have-a-zero-data-retention-agreement-with-anthropic-what-products-does-it-apply-to)
- [TechCrunch: Consumer Opt-Out](https://techcrunch.com/2025/08/28/anthropic-users-face-a-new-choice-opt-out-or-share-your-data-for-ai-training/)
- [NPR: Copyright Settlement](https://www.npr.org/2025/09/05/nx-s1-5529404/anthropic-settlement-authors-copyright-ai)
- [Anthropic: Long-Term Benefit Trust](https://www.anthropic.com/news/the-long-term-benefit-trust)
