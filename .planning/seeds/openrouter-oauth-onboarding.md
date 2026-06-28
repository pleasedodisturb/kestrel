---
title: OpenRouter OAuth Onboarding Flow
trigger_condition: When onboarding UX phase starts or provider setup UI is built
planted_date: 2026-04-21
---

# OpenRouter OAuth Onboarding

Instead of "paste your API key," build a one-click OAuth flow:
- Button creates OpenRouter account
- Auto-generates API key
- Stores key in Kestrel (expo-secure-store on mobile, integration_configs on backend)
- Prompts user to add $10 balance (unlocks rate limits + free model access)

This turns provider setup from a 5-step manual process into a single click.

Research needed: OpenRouter's OAuth/account creation API capabilities.
