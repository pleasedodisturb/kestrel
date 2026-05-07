# Mobile App

*Part of the [Kestrel roadmap](../../ROADMAP.md).*

## Goal

Check your pipeline and review scores from your phone.

## What This Delivers

Your job search does not pause when you step away from your desk. The mobile app brings Kestrel to your phone so you can review new scores on your commute, check pipeline status between meetings, and respond to time-sensitive opportunities without opening a laptop. Push notifications for follow-up reminders and high-scoring discoveries keep you in the loop without checking the app constantly.

The web experience comes first. Kestrel's web frontend already works on mobile browsers, and improvements to responsive design will continue before the native app ships. The dedicated iOS and Android apps add push notifications, offline access, and a touch-optimized interface that goes beyond what a mobile browser can offer.

## Design Considerations

The mobile app will share the same REST API backend as the web frontend, which means no duplicate business logic. React Native with Expo is the planned framework, allowing a single codebase to target both iOS and Android. A React Native scaffold already exists in the repository, though development was paused to focus on the web experience first.

Offline support matters for a mobile app in ways it does not for the web version. Users may want to browse their pipeline on a plane or in an area with poor connectivity. This requires a local data cache that syncs when a connection is available, with conflict resolution for any changes made offline. Push notification infrastructure also needs to be built: which events trigger notifications (new high-scoring job, follow-up due, application status change) and how aggressively they should be delivered.

## Current Status

*Status: Planned -- not yet started*

A React Native and Expo scaffold exists in the repository but is paused. The web frontend is the priority. Mobile development resumes when the web experience is solid.

## Related Milestones

- **[Web Frontend](web-frontend.md)** -- The mobile app provides the same core interface on a smaller screen
- **[Desktop App](desktop-app.md)** -- Another form factor for accessing Kestrel

---

*For Contributors*

## Open Questions

- Expo managed workflow or bare workflow? Managed is simpler but limits native module access. Bare gives full control but adds complexity
- Push notification infrastructure: Firebase Cloud Messaging (cross-platform) or separate APNs/FCM implementations?
- Offline data sync strategy: full pipeline mirror or selective caching of recent items?
- How should conflict resolution work when the same application is edited on both mobile and web while offline?
- App Store submission process for iOS (Apple review guidelines, TestFlight beta) and Google Play (review timeline, content policies)
- Should the mobile app support all features or a focused subset (pipeline view, scores, notifications)?

## Research Needed

- [Mobile UX Findings](../research/mobile-ux-findings.md) -- UX findings from the initial React Native and Expo exploration, including navigation patterns and screen inventory considerations

No dedicated mobile architecture research exists beyond the UX findings. Research areas include: offline-first data architecture for React Native, push notification trigger design, App Store submission checklists, and cross-platform testing strategies.

## BMAD Integration

**PRD Status:** Not started

A PRD would specify the screen inventory and navigation patterns, offline data synchronization behavior, push notification trigger rules, and the App Store submission checklist for iOS and Google Play.

To start a PRD: `/bmad-create-prd` in Claude Code.
See the [planning hierarchy](inventory.md#how-planning-works) for how PRDs connect to implementation.
