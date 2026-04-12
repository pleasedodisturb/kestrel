# Validation Contract — Milestone 5: Integrations & Voice Mode

**Milestone:** M5 — External Integrations & Voice Interaction
**Status:** Draft
**Assertion count:** 24

---

## TickTick Integration

### VAL-TICKTICK-001: Bidirectional sync — pipeline action creates TickTick task
When a user creates a pipeline action (e.g., "Send follow-up email to Acme Corp") in Career OS, a corresponding task appears in the configured TickTick project within 60 seconds. The task title, due date, and priority map correctly.
**Pass:** TickTick task exists with matching title, due date, and priority.
**Fail:** Task missing, delayed beyond 60s, or fields mismatched.
Evidence: TickTick API `GET /project/{id}/tasks` response showing the synced task; Career OS action log entry.

### VAL-TICKTICK-002: Bidirectional sync — TickTick completion syncs back
When a user marks a TickTick task (that originated from Career OS) as complete in TickTick, the corresponding pipeline action in Career OS updates to "completed" status within the next sync cycle (≤15 minutes).
**Pass:** Career OS action status is "completed" after TickTick task completion + sync.
**Fail:** Status remains unchanged after sync cycle.
Evidence: Career OS database query showing updated status; sync worker logs confirming the round-trip.

### VAL-TICKTICK-003: Follow-ups created as TickTick tasks
When a follow-up reminder is set for a job application (e.g., "Follow up with Recruiter X on 2026-03-20"), a TickTick task is created with the follow-up date as the due date and the application context in the task description.
**Pass:** TickTick task exists with correct due date and description referencing the application.
**Fail:** Task missing or due date incorrect.
Evidence: TickTick task detail; Career OS follow-up record.

### VAL-TICKTICK-004: Learning goals synced as TickTick tasks
When a user adds a learning goal (e.g., "Complete system design module"), it appears as a TickTick task in a designated learning list/tag with the target completion date.
**Pass:** Task present in TickTick with correct list/tag and due date.
**Fail:** Task absent or miscategorized.
Evidence: TickTick task list filtered by learning tag; Career OS learning goals view.

---

## Calendar Integration

### VAL-CAL-001: Interview scheduling creates calendar event
When the user schedules an interview for a tracked application, a calendar event is created containing: company name, role, interview type, location/link, and any prep notes. Supports iCal export at minimum.
**Pass:** Calendar event appears with all required fields populated.
**Fail:** Event missing, or required fields (company, role, time) absent.
Evidence: Exported .ics file content; calendar app screenshot showing event.

### VAL-CAL-002: Follow-up dates appear as calendar events
When a follow-up date is set on an application, a corresponding all-day or timed calendar event/reminder is created so the user is prompted on that day.
**Pass:** Calendar event exists on the follow-up date with application context.
**Fail:** No calendar entry for the follow-up date.
Evidence: Calendar view showing the follow-up event; .ics file contents.

### VAL-CAL-003: Prep reminders fire before interviews
When an interview is scheduled, a prep reminder event is created 24 hours before the interview time (configurable) with a link to the application's prep materials.
**Pass:** Reminder event exists at T-24h (or configured offset) with prep link.
**Fail:** No reminder, wrong time, or missing prep link.
Evidence: Calendar entry at reminder time; notification log or .ics alarm field.

### VAL-CAL-004: Multi-provider calendar support
Calendar events can be exported/synced to at least two of: iCal (.ics file), Google Calendar (API), Fantastical (callback URL or API). Configuration UI allows selecting the active provider.
**Pass:** Events appear in at least two calendar providers after configuration.
**Fail:** Only one provider works, or provider selection UI absent.
Evidence: Screenshots of event in two different calendar apps; settings page showing provider selection.

---

## Pushover Integration

### VAL-PUSH-001: Follow-up reminder push notification
When a follow-up date arrives, a Pushover notification is sent to the configured device with the application company name, role, and suggested action.
**Pass:** Pushover notification received on device with correct application context.
**Fail:** No notification, wrong content, or delivered to wrong device.
Evidence: Pushover notification history (API or app screenshot); Career OS follow-up trigger log.

### VAL-PUSH-002: Ghost alert notification
When an application has had no response for a configured threshold (e.g., 14 days past follow-up), a "ghost alert" Pushover notification is sent indicating the application may be stale.
**Pass:** Notification received after threshold with correct application reference.
**Fail:** No notification after threshold, or sent prematurely.
Evidence: Pushover message content; Career OS ghost detection log with timestamps.

### VAL-PUSH-003: New job discovery notification
When the job discovery pipeline finds a new high-scoring match (score ≥ configured threshold), a Pushover notification is sent with company, role, score, and a link to review.
**Pass:** Notification received with accurate job details and score.
**Fail:** No notification for qualifying jobs, or score/details incorrect.
Evidence: Pushover notification content; Career OS discovery log showing the matched job.

### VAL-PUSH-004: Interview reminder notification
A Pushover notification is sent at a configured interval before a scheduled interview (e.g., 2 hours before) with company, role, time, and meeting link.
**Pass:** Notification arrives at configured lead time with complete interview details.
**Fail:** Notification missing, wrong timing, or incomplete details.
Evidence: Pushover message timestamp vs. interview time; notification content.

### VAL-PUSH-005: Pushover auth failure handled gracefully
When Pushover credentials are invalid or the service is unreachable, Career OS logs the failure, does not crash, and surfaces the error in the integrations settings UI.
**Pass:** Error logged, UI shows integration error state, application continues operating.
**Fail:** Crash, silent failure with no indication, or error not surfaced in UI.
Evidence: Application error log; integrations settings page showing error status.

---

## Voice Discussion Mode

### VAL-VOICE-001: Voice input accepted for conversational UX
When the user provides speech-to-text input (e.g., via SuperWhisper or any STT tool pasting text), Career OS accepts it in the voice discussion interface and responds conversationally. The system does not require a specific STT provider.
**Pass:** Transcribed text from any STT tool is accepted; conversational response generated.
**Fail:** Input rejected, requires specific STT provider, or no response generated.
Evidence: Voice discussion session transcript showing input → response flow.

### VAL-VOICE-002: Voice-driven cover letter brainstorming
The user can start a voice brainstorming session for a cover letter by referencing a specific application. The system asks clarifying questions, suggests angles based on the user's profile and the job posting, and produces a draft cover letter.
**Pass:** Session produces a cover letter draft that references the target role and incorporates profile strengths.
**Fail:** No draft produced, draft is generic/unrelated to the role, or session cannot be initiated.
Evidence: Session transcript; generated cover letter draft; comparison with target job posting.

### VAL-VOICE-003: Voice coaching session
The user can initiate a voice coaching session (e.g., "Help me prepare for my Stripe interview"). The system conducts a mock interview or coaching dialogue, asking relevant technical/behavioral questions and providing feedback.
**Pass:** Coaching session runs with role-relevant questions and constructive feedback.
**Fail:** Questions unrelated to the role, no feedback provided, or session fails to start.
Evidence: Coaching session transcript; relevance of questions to the target role's requirements.

### VAL-VOICE-004: Voice job evaluation discussion
The user can verbally describe a job opportunity and have a discussion about fit, pros/cons, and scoring. The system references the user's target roles and profile to give a grounded evaluation.
**Pass:** System provides a scored evaluation with pros/cons referencing user profile criteria.
**Fail:** Evaluation is generic, doesn't reference profile, or scoring is absent.
Evidence: Discussion transcript; evaluation output with score and reasoning.

---

## AI Provider Health Dashboard

### VAL-AI-HEALTH-001: Provider connectivity check
The AI provider health dashboard displays the connectivity status (reachable / unreachable) for each configured provider: Anthropic, OpenAI, Gemini, OpenRouter, Together AI, droid exec.
**Pass:** Dashboard shows a status indicator per provider; reachable providers show green/OK, unreachable show red/error.
**Fail:** Dashboard missing, provider list incomplete, or statuses not reflecting actual connectivity.
Evidence: Dashboard screenshot; manual verification of one provider's actual status vs. displayed status.

### VAL-AI-HEALTH-002: Credit and rate limit display
For providers that expose credit balance or rate limit info via their API (e.g., Anthropic, OpenAI), the dashboard displays remaining credits/quota and current rate limit usage.
**Pass:** Credits and/or rate limits displayed with values matching the provider's API response.
**Fail:** Data missing for providers that expose it, or values stale/incorrect.
Evidence: Dashboard values; direct API call to provider showing matching data.

### VAL-AI-HEALTH-003: Auth failure surfaced in dashboard
When a provider's API key is invalid or expired, the health dashboard shows an authentication error for that specific provider without affecting the status display of other providers.
**Pass:** Invalid-key provider shows auth error; other providers display normally.
**Fail:** Auth error cascades to other providers, dashboard crashes, or error not shown.
Evidence: Dashboard screenshot with one deliberately misconfigured provider; other providers showing correct status.

---

## Cross-cutting: Configuration & Error Handling

### VAL-PUSH-006: Integration configuration UI
Each integration (TickTick, Calendar, Pushover, Voice, AI providers) has a configuration section in the settings UI where the user can enter credentials, toggle the integration on/off, and see the current connection status.
**Pass:** Settings page lists all integrations with credential fields, on/off toggle, and status indicator.
**Fail:** Any integration missing from settings, or no way to configure credentials.
Evidence: Settings page screenshot showing all integration panels.
