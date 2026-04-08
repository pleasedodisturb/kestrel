# Wolt / Mx-CRM — Capability Evidence Digest

> Built at Wolt as TPM for the Merchant Experience CRM program. Started with a blank slate and 4 API keys. Built a full AI-augmented TPM operating system inside Cursor IDE — ending up nearly replacing himself with an AI agent.

## The System He Built

A private Git repo (`Mx-CRM-Program`) functioning as a persistent AI agent "operating system" for TPM work:

- **Persistent cross-session AI memory** — structured context index (`CONTEXT_INDEX.md`), session protocols, daily digests. AI never starts cold.
- **15+ Python automation scripts**: Google Drive sync (`gdrive_sync.py`), Confluence auto-publishing (`push_confluence_news.py`, `push_confluence_weekly.py`), document registry builder (`build_document_registry.py`), preflight auth checker with auto-fix (`preflight_check.py`), Markdown→Google Docs pipeline (`upload_to_docs.py`), link extractor, team roster generator, agent marker reader
- **Custom Glean enterprise search CLI** (`glean-search`) — query Wolt's internal knowledge base and Slack from terminal. Supports workspace/channel filters, date ranges, domain filtering, multi-channel OR queries, JSON output
- **AI provenance tracking** — machine-readable agent markers on every AI-created document: `appProperties` in Google Drive, `mxcrm.agent_marker` content properties in Confluence. Full governance audit trail.
- **Write guardrail architecture** — all Google write operations blocked by default, require `ALLOW_GOOGLE_WRITE=1` env var. Optional `GOOGLE_WRITE_ALLOWLIST` for file/folder restriction. Safe AI by design.
- **1,140 documents indexed** across Drive, Confluence, Jira, and Slack — 474 classified (42%), with document lifecycle tracking

## Integrations Built / Operated

| System | How Used |
|--------|----------|
| Google Drive/Docs/Sheets | OAuth 6-token system, auto-sync, auto-upload with markdown formatting conversion |
| Confluence (Atlassian) | Auto-published daily + weekly digests, 40+ pages maintained |
| Jira (Atlassian) | MCRM board, 5 custom dashboards, 15+ JQL filters, sprint tracking |
| Slack | 8+ channels tracked, Workflow for feedback, digests ingested into private context |
| Glean (enterprise AI search) | API + MCP, custom CLI tool built on top |
| GitHub | `salesforce-connector-service`, `ext-salesforce-crm`, `Mx-CRM-Program` repos |
| Salesforce | CRM platform being deployed, coordinated admin + connector service |
| FDR (Wolt financial system) | REST API + Pub/Sub integration via salesforce-connector-service |
| MongoDB | SOX-compliant audit logging, 12-month retention |
| DocuSign | Contract integration via Salesforce |
| Sentry + DataDog | Production monitoring coordination |
| HashiCorp Vault | Salesforce credential rotation |
| TickTick | Task management with GCal sync |
| ContextStream MCP | Persistent memory, session snapshots |
| Cursor IDE | Primary AI agent runtime |

## Program Delivered

**Pipedrive → Salesforce CRM migration** for Wolt's Merchant Experience org:

- Shipped Commission Change Request workflow to ~50 Account Managers in Finland 🇫🇮 and Denmark 🇩🇰 — December 1, 2025, on schedule, zero critical launch bugs
- Managed 3 parallel streams: AM CRM, Sales CRM, Wolt Commercials (Drive/Storefront)
- 12+ stakeholders across Engineering (Director + EM + 4 engineers), Product, S&O, BSC, 3 executive sponsors
- Post-acquisition complexity: coordinating Wolt → DoorDash Atlassian migration simultaneously
- SOX-compliant architecture: Salesforce → anti-corruption connector → FDR → MongoDB audit logs
- €200k+ annual savings via DocuSign replacing Juro for contract management
- Grew to 72 logged users with 35% weekly active usage within 2 weeks of launch
- Led London Pedregal workshop (17 prep files + 7 session notes) for in-house CRM platform roadmap
- Delivered TPM Ownership Framework: "Come with proposals, not questions" — reduced stream owner cognitive load by pre-drafting templates, plans, and reports

## Proof Points for Applications

- "Built an AI-augmented TPM operating system from scratch — persistent memory, 15+ automation scripts, 1,140 documents indexed, zero budget, 4 API keys"
- "Delivered Wolt's Merchant CRM migration (Pipedrive → Salesforce) for 50 AMs across 2 markets — on time, zero critical bugs"
- "Built custom enterprise search CLI on Glean API, enabling AI agent to query Slack + internal docs from terminal"
- "Designed AI provenance and write-guardrail systems for production AI usage in a compliance-sensitive (SOX) environment"
- "Indexed 1,140 documents across 6 enterprise systems and built a unified governance registry"

## The Wolt Environment Context

Wolt was post-DoorDash acquisition: political chaos, M&A integration stress, burnt-out TPM org resistant to change. IT organization optimized for closing tickets, not solving problems. Staff TPMs saw AI tooling as a threat, not an opportunity. Despite this, the system was built and the program was delivered.

The 94 Jira tickets in 3 months were not a user problem — they were a system signal. The right environment will recognize this as relentlessness, not irritation.
