# Sales, Marketplace/Growth, Inbox and appointments: session review

> Continuation note (September 17): start with [the current session handoff](session-handoff-2026-09-17.md) for the later Sales/appointment UI refinements, implemented homepage demo intake, remaining Cal.com correlation work, provider setup and scheduler issue. This document remains the September 15 baseline.

Reviewed September 15, 2026 against the conversation, current source and the dated implementation notes in [the working handoff](marketplace-growth-next-steps-2026-09-08.md). This describes the final behavior; earlier intermediate implementations were superseded by later corrections. Historical test results are evidence from their recorded runs, not a claim that the entire repository was retested today.

## Sales administration

- Built out Overview, Pipeline, Prospects and Discovery. Overview includes metric dots/tooltips, pipeline percentages, Needs Attention, Upcoming Follow-ups, Recent Activity and stage summaries. Updated timestamps moved to the top; section titles and presentation were aligned with the portal.
- Pipeline and Prospects use shared debounced search, match highlighting, inline clear, header counts and pagination. Removed redundant footer counts and separate search/reset controls. Expanded rows reuse compact View actions and preserve filters/return navigation.
- Sales detail uses Overview, Qualification and Activity tabs. Main data is read-only until Edit; owner, stage, follow-up, optional activity and qualification changes share the established persisted draft/save flow. Dirty state reflects meaningful changes, reverting values restores clean state, and stale saves are rejected.
- Notes edit through the shared NotesField workflow, independently of the detail edit. Notes and the ID/Created footer are bottom-aligned. Activity keeps its table headers when empty or loading.
- Contacts always use the shared table. Saved contacts and additions have independent Edit Contacts/Add Contact/Save/Cancel behavior, including editing/removal and primary selection. Blank additions do not falsely activate Save or discard warnings. Contact ownership, revisions, suppression and retained history are validated server-side.
- Follow-up selection uses the compact shared calendar; newly changed follow-ups must be future times. Existing overdue dates remain visible and can be kept or cleared.
- Business addresses come from recorded source fields, with formatted/structured fallbacks and multiple offices where available. A city/region-only record remains partial: a street or headquarters is not invented.
- Sales sidebar memory reuses Marketplace administration navigation storage. Header actions, row actions, Back controls and mobile wrapping reuse existing components.
- Added repeatable fictional vending-business development fixtures: 24 businesses, including eight prospects and sixteen staged leads, with contacts, addresses, activity, notes and varied ownership/follow-up states. Demo customer records do not create paid subscriptions.

## Customer qualification and intake

Sales targets vending operators and related service businesses that could become Vendistri subscribers. Placement venues are a separate Marketplace opportunity use case. The original unmodified Vending ecosystem default was replaced by Vending operators rules; customized profiles are preserved. Matching business evidence is required before qualification promotes a discovered result. Keyword matching is screening evidence, not independent verification.

Discovery exposes the existing provider search/run/budget controls and profile version management. Manual business entry and CSV intake use preview, validation, matching and idempotent commits. Qualification detail includes retained source evidence and explicit primary contacts. Qualification history compares scores using the existing comparison component, including warnings for changed profiles or locations.

Weekly/monthly Sales growth comparisons are **not implemented**. Current-pipeline percentages and historical qualification-score comparisons must not be presented as week-over-week conversion/growth metrics.

## Marketplace and Growth

The related handoff records appointment-ready venue confirmation/reconfirmation/withdrawal, canonical validity and sellability checks, preserved purchase evidence, and administration opportunity contact handling. Purchased rights and source evidence remain distinct from editable customer working data.

Growth connects acquired leads to assignment, contacts, activities, follow-ups, field/remote tasks and location conversion. Lead tasks reuse existing task access, scheduling, bulk operations, route/day grouping and detail pages; remote work does not become a physical route stop. Started/finished work and revoked access are protected. Task-linked activity and source/location links preserve context. The later appointment work integrates these existing contracts rather than introducing a parallel task system.

## Shared Inbox

Administration and customer Inbox share one communications implementation: Google Workspace/Gmail and Microsoft 365/Outlook connections, disconnect, explicit mailbox delegation, incremental inbound/Sent sync, compose/reply, drafts, attachments, assignment and open/closed state. Conversations can link to authorized Sales, opportunity, Support or Growth records. Customer mail uses the connected mailbox identity.

OAuth state is scoped and single use; stored credentials require encryption. Attachments are private authorized downloads. Record access does not automatically grant mailbox access. Activity projections do not expose private message bodies. Send states distinguish provider acceptance, failure and uncertainty; uncertainty is reconciled without automatic resending. Provider acceptance does not prove recipient delivery.

Inbox navigation, page padding and Back controls were aligned with the portal. Customer Inbox sits below Reports. Search, labels, dropdowns and actions stay visible during data loading.

## Appointments

Cal.com is the current provider behind the existing scheduling adapter. Sales and Growth share availability/booking controls and appointment status tables. Confirmed booking, rescheduling, cancellation and outcome changes appear in existing Activity tables. Authorized staff/managers have reschedule/cancel controls; invitees use the provider's configured secure management links.

Growth appointments can link eligible existing tasks. Confirmed changes synchronize eligible task schedules/cancellation; started or finished work is retained and synchronization problems are shown for review. Sales does not repurpose customer operational tasks.

Booking attempts persist server-side. Reload recovery and Check Status reconcile uncertain requests instead of blindly submitting another booking. Duplicate identities, replacement provider booking IDs, stale responses and explicit rejections are handled. Unchanged checks avoid writes/activity duplication. Known-unsent configuration failures can be closed after reload so they do not block later booking. Provider recovery is bounded; an absent search result is not proof that a booking never existed.

## Shared implementation and verification

The work reuses existing tables, buttons, status pills, tooltips, notes, custom dropdowns, date inputs, draft/discard guards, domain resources, pagination, realtime and audited backend commands. Skeletons replace data only; same-scope background refresh preserves visible content. Targeted query-budget, ownership, stale-save, idempotency, loading, responsive and lifecycle tests were added throughout the work. This is not a certification that every project directory has zero duplication or that production latency has been benchmarked.

The last appointment review passed 210 distinct backend tests across its recorded runs and 110 UI tests, with TypeScript, scoped lint, compilation and migration checks. Earlier feature-specific results and limitations are in the handoff.

## September 15 banner adjustment

The shared SessionBoundary message now uses 0.75rem text and a matching compact Retry button with smaller spacing. Canonical shared source and both consumer checkouts are synchronized. Session verification and account protection behavior are unchanged. This presentation fix does not diagnose or resolve the screenshot's underlying fetch/session connectivity failure.

## Remaining work

- Configure Cal.com credentials, webhook secret and event types; verify real booking, rescheduling, cancellation, invitee links and notification behavior with test accounts.
- Register/configure Google and Microsoft OAuth, callback, encryption/storage permissions and workers; run real-account receive/reply/draft/attachment/sharing/send acceptance. See [connected mailbox setup](../backend/runbooks/connected_mailboxes.md).
- Verify deployment/worker scheduling, production database concurrency and full release journeys. Local mocks/builds do not replace these checks.
- In-house Vendistri scheduling, connected-customer-mailbox campaign automation, additional reply/bounce suppression, provider push updates, Sales period reporting and native/mobile task parity remain separate follow-up work.

No real provider booking, invitation, email, campaign or production deployment was performed for this review.

Today's banner validation: six shared SessionBoundary tests, two portal session-identity tests and six Marketplace session tests passed. Portal TypeScript and shared/Marketplace/public-host builds passed; the rebuilt Marketplace artifact was synchronized into the local hosts. All three shared UI checkouts have identical session source and built JavaScript. Local migration/model checks are current. Build output retains existing bundle-size and Browserslist freshness warnings. No new browser screenshot or live connectivity diagnosis was performed today.
