# Marketplace alignment and next steps — updated September 12, 2026

> Continuation note (September 17): [the current session handoff](session-handoff-2026-09-17.md) consolidates the later conversation and current priorities. Read it before treating any earlier “next step” below as unfinished; this file intentionally retains its chronological implementation history.

## Scope and executive summary

This plan follows a source review of public/secure Marketplace, Marketplace Administration, Growth/task integration, native task execution, Sales, Outreach, Support, and Appointments. It revisits the [September 3 executive summary](../marketplace-handoff-2026-09-03.md), [September 7 handoff](../vendistri/docs/marketplace-handoff-2026-09-07.md), [Growth ownership notes](../vendistri/docs/growth-workspace.md), and [September 8 journey review](marketplace-journey-review-2026-09-08.md). Older statements about missing customer sourcing and claims UI are superseded by the current implementation.

The connected journey is:

**Discover/request → purchase → work the acquired Growth lead → contact/book/visit → follow up → convert to an operating location → install/service machines.**

Vendistri's own sales acquisition is a related but distinct journey:

**Discover a business → qualify a Sales lead → contact/book/demo/propose → onboard an organization.**

Reuse identity, evidence, contact, delivery, appointment, UI and task infrastructure. Keep purchase entitlements, customer Growth leads, and Vendistri Sales leads distinct authoritative records with explicit links and permissions. A shared visual component is appropriate; a single giant workflow that combines all three domains is not.

## September 9 implementation update — web and qualification slice

The historical source-review findings below are superseded where addressed by this slice:

- Opportunity **Evidence → Venue confirmation** now uses the shared dropdowns, date/time input, draft/unsaved-edit store, buttons and confirmation modal. Staff can qualify or reconfirm an unpurchased opportunity and explicitly record verified withdrawal of interest. Drafts do not affect the listing; applying a confirmation unpublishes and requires pricing/publication review.
- The backend enforces active administrator access, current scoped contact and usable contact details, confirmation date/evidence, reservations/acquisitions, and a centrally defined 60-day lifetime. Expired, withdrawn or unusable confirmation evidence fails canonical sellability; lower-tier review after expiry is explicit. Audit/activity retain previous and current evidence.
- Legacy confirmation expiry is backfilled from its actual date. The cleanup worker automatically unpublishes invalid unsold confirmations; a one-minute scheduler entry dispatches it. A five-minute entry runs existing enabled inventory/demand policies and preference evaluation, retaining holds, cooldowns and budgets. Worker/scheduler deployment remains necessary; no live workers or outbound campaigns were started in this implementation session.
- Accepted purchases retain confirmation timestamps and agreed next action in the existing purchase snapshot. Payment may complete across qualification expiry while the purchase remains accepted; abandoned attempts must revalidate. Customer opportunity and Growth detail show the saved confirmation/next action. Booking eligibility uses the acquired tier, so elapsed sale validity does not invalidate a completed purchase or trigger an expiry email.
- Web Routes now map/order field lead visits from their own coordinates, normalize the lead address for shared consumers, exclude remote lead tasks from travel, link to the existing Growth task detail and omit machine revenue for lead-only stops. Shared bulk notes/rescheduling/status/cancellation now use the existing Growth access and mutation services. Task lists/details reject revoked lead access; claim resolutions refresh affected task data.
- Marketplace/prospecting events now reconcile through domain adapters instead of falling back to task reloads. Open Demand Queue, Discovery, Claims and replacement selection subscribe to relevant revisions; shared fallback refresh remains. Opportunity detail schedules refresh at its next qualification/reservation boundary. Public/private Marketplace share the rebuilt Marketplace artifact.

Still to deliver: complete the remaining web task-consumer audit and browser acceptance journeys; Sales discovery-launch/profile controls, contact management and connected outreach/booking flows; support/email conversations and manual replies; calendar-to-task synchronization; and then broader outreach automation. Location-side source history and task contacts/outcomes/follow-ups are implemented in the updates below. Native/mobile work and public venue-request intake remain deferred. Production latency, real provider delivery, worker deployment and full browser journeys are not certified by local unit tests/builds.

Verification for this slice: the broad backend suite passed 722 tests (3 existing skips); the customer Marketplace suite passed 597 tests; targeted portal suites passed 159 tests. Portal TypeScript, selected ESLint checks, Marketplace build/artifact synchronization and the local public host build passed. Backend system checks passed; local prospecting migrations 0024 and 0025 are applied, with no pending migrations or ungenerated model changes. The Marketplace full-suite result used two test workers after two timing-sensitive tests failed under default concurrency and passed in isolation. No production deployment or real payment, booking, email or campaign was used for verification.

After the final transaction, membership and bulk-serialization safeguards, all 58 focused qualification and lead-task tests passed, including rollback of qualification when history cannot be saved and denial of task access to a removed organization member.

### Follow-up maintainability review

Reviewed qualification commands and API contracts, canonical eligibility, task query preparation and serialization, Growth task history, and the qualification UI's shared draft/modal integration. The review found and corrected duplicated Growth task loading and missing eager loading of the rescheduling actor. Growth now reuses `prepare_task_queryset`; both Growth and shared task serialization are covered by a two-query budget for ten rescheduled lead tasks. No new helper module or dependency was introduced.

The qualification response now has an explicit schema, with compatibility for legacy evidence channels. Qualification requests reject extra fields, including a client-supplied expiry. The UI reads the validity duration from the backend policy rather than repeating 60 in its implementation. Withdrawal passes its promise to the existing confirmation modal so the shared action lifecycle awaits completion.

Verification: 114 qualification, publishing, catalog and lead-task tests and 34 existing machine-task performance/organization-context tests passed; 74 opportunity UI tests passed; portal TypeScript and selected lint checks passed; local migrations remain current with no ungenerated model changes. This review does not certify every directory or production latency. Remaining cross-surface work stays listed below.

### Continued web lead-task integration

- Reviewed venue corrections now update addresses and coordinates of pending/unassigned field visits that have not started, through the existing lead-task service. Task creation and correction share the destination projection. Batched writes and task audit entries commit together; started/completed/canceled tasks, remote work and revoked entitlements are excluded. Purchase snapshots remain unchanged. This applies when a correction is approved; it is not a retrospective production data repair.
- Task detail, reached from either Tasks or Growth, exposes the linked operating location after conversion while retaining its lead-task identity. Full accounts get the location link; lead-only accounts follow the existing upgrade action. Location-side source-lead history is addressed in the next update.
- Growth participates in the shared realtime revision coordinator, including reconnect reconciliation. Resource caches include the Growth revision while retaining visible data during refresh, and unchanged form options do not reload. Ordinary notes avoid the former broad task fallback. Destination changes and conversion invalidate task views; claim resolution invalidates Marketplace, Growth and Tasks in one notification. Other purchasers at a shared corrected venue receive an authorized private refresh even when they have no tasks.

Verification: 107 backend and 116 web tests passed, including correction/history preservation, transaction rollback, active-administrator enforcement, revoked access, shared-venue notifications, conversion links, cache refresh and realtime reconciliation. Portal TypeScript and production-file lint passed; no local migrations are pending. Existing DOM-access/render-result lint violations remain in two older Growth test files; the tests themselves pass. Full browser/deployment verification and native clients remain outside this slice.

### Working context and location history review

- Lead tasks now display venue/area, the purchased venue's requested next action, current follow-up, and the existing shared contact editor (including visible superseded contacts, formatting, copy controls and suppression rules). A typed working-context projection is reused by lead/task detail; task responses exclude purchase, media and unrelated lead metadata. The working-context loader uses four queries with multiple contacts/contact points; source-location lookup uses one query after organization authorization. These are query-count checks, not production latency measurements.
- Recording an outcome from a task uses the existing Growth activity command and modal. A typed task reference is validated against the lead, organization and actor's assignment, then retained in the same activity record. Task-specific history is a filter on the existing paginated activity query/component, and the complete lead history links back to its tasks. Options load when the activity modal opens. Recording an activity does not change task status or automatically mark the lead Won.
- Follow-up can be set or explicitly cleared through the existing date picker. An unchanged follow-up is omitted from activity requests, preserving the server's current value when another session changed it. Backend updates remain under the lead transaction, and revoked/missing lead access produces validation feedback rather than an uncaught lookup error.
- Location Overview uses the actual conversion relationship to show the source lead and its existing paginated task/activity history. The lookup follows internal location permissions and active entitlements; no Growth data was added to generic location/contact-portal responses. Existing Growth revision/cache handling refreshes these views after activity/contact updates and reconnects.
- No new model, dependency, helper module, contact store, activity store or task status engine was introduced. Native work, Administration Sales, inbox and calendar integration remain separate roadmap steps. Requiring an outcome as part of task completion is not implemented; recording activity and completing a task remain separate actions.

At that review, the existing shared `ModalShell` lacked dialog semantics/focus management (addressed locally in the shared modal update below). Its accessibility needs a dedicated shared-component change and regression checks across modal consumers; this slice reuses it without creating a parallel modal implementation. Browser/production performance and deployment remain unverified.

Verification: 112 backend tests passed across Growth models/tables, lead tasks and Appointment Ready qualification; all 80 Growth UI tests passed. Portal TypeScript, changed production-file ESLint and scoped whitespace checks passed. The local database has no pending migrations. Coverage includes contact suppression/history, bounded query counts, tenant-scoped conversion lookup, revoked access, task-reference validation, task/lead status preservation, follow-up omission/set/clear, lazy options and filtered history pagination.

### Web task consumer audit — September 9

This slice fixes demonstrated web presentation/grouping gaps; it does not complete browser or release acceptance.

| Consumer | Source review / local verification | Remaining verification |
| --- | --- | --- |
| Today’s Tasks | Lead objectives and field/remote labels replace fabricated machine labels. Lead groups omit machine revenue. Remote-only groups open their Growth task; remote work is excluded from travel summaries. Mixed widget rendering/navigation regression passes. | Real account, responsive layout and multiple-device refresh |
| Weekly task chart / report breakdown | Reuses the existing report type/color definitions and date parser. Growth, pickup inventory and unknown types count consistently in legends, segments and totals; unknown types appear under Other. Weekly/donut and existing revenue chart tests pass. | Browser tooltip/layout acceptance |
| Route Planner / Day Detail | Reuses Routes’ ID-based grouping instead of grouping by display name. Same-name leads/locations stay separate for group actions, expansion and notes. Remote tasks remain in the day queue but do not become map stops or contribute travel/stop totals. Regression covers independent expansion and mixed field/remote/machine days. Existing pickup grouping tests still pass. | Exercise bulk reschedule, reassign, cancel and completion against the backend in a mixed day |
| Routes / navigation | Existing route selectors exclude remote work and retain field lead coordinates; existing Routes, planner state and navigation tests pass. | Active execution, route progress and reconnect journey in browser |
| Tasks / task deep links | Source review confirms shared task list and Growth detail delegation for lead tasks. Previous slice tested the Growth task working context and history. | Tasks list filters/pagination and direct-link lifecycle acceptance |
| Location / machine detail | Previous slice connected converted-location source history with authorized Growth lookup. Machine detail remains machine-scoped; no fabricated machine was introduced for lead visits. | Conversion/revocation refresh across open detail pages |
| Travel reports | Uses the same route eligibility predicate as routing. Remote work is excluded from travel reports while generic task work-duration metrics remain available. Regression passes. | Real recorded field-visit metrics and timezone boundaries |

Reuse: one route eligibility predicate in existing task helpers (Routes retains its existing export), existing route grouping, existing financial row, and existing report chart definitions. No new backend endpoints, dependencies or per-row network calls were added. Calculations use already-loaded task data; production latency has not been measured.

Verification: 31 tests passed across seven targeted suites (the corrected widget/Day Detail suite was rerun separately). Portal TypeScript, changed production-file ESLint and scoped whitespace checks passed. Local development migrations are current. At this point, shared ModalShell accessibility work and the mixed-route lifecycle/browser acceptance matrix remained prerequisites; the shared modal implementation is now covered by the update below.

### Follow-up structure review — September 9

Reviewed the web task changes against existing routing, report and dashboard modules. Route Planner now composes the existing Routes grouping, stop entries and map projection instead of maintaining separate location/lead map builders. This also shares finite-coordinate validation and preserves zero coordinates and lead-title fallback labels. The weekly chart computes bars, legend counts and total in a single memoized task pass. Report display order derives from its color registry; TypeScript requires coverage of every task type except the intentional default-to-Other fallback. Today’s Tasks uses a boolean group check without allocating an extra lead array.

No new helper file, dependency, endpoint, network request or authorization path was introduced. This is a scoped structure review, not certification of every directory or a measured production performance claim. Thirty-two tests across seven suites pass, including shared map validation, same-name group separation, field/remote routing and weekly/report totals with invalid/out-of-range dates. TypeScript, changed production-file ESLint (zero warnings), whitespace checks and local migration checks pass. Remaining roadmap/browser/shared-modal work is unchanged.

### Shared modal keyboard and accessibility update — September 9

The portal ModalShell now exposes a named dialog, description association and a focusable panel. It and the shared UI Modal use one modal-behavior hook for initial focus, Tab/Shift+Tab boundaries, focus restoration, topmost Escape handling and reference-counted body scroll locking. Focusable controls include textareas; disabled, hidden and negative-tabindex controls are skipped. Empty/busy dialogs retain keyboard focus. Callback changes no longer tear down/recreate the focus lifecycle. Custom Dropdown consumes Escape before its containing dialog.

Existing presentation and caller validation/discard logic remain in their components. Regression tests cover mixed ModalShell/ConfirmModal nesting (including existing two-Escape behavior), blocking Escape during processing, restoring the trigger, removing an underlying modal first, and embedded shadow-root focus. Both UI consumer checkouts use the canonical shared source and rebuilt output.

Verification: 60 shared UI tests, 126 portal tests (Growth, modal, dropdown/date picker and expense consumers), and 30 Marketplace claim tests passed. Shared UI/portal typechecks, Marketplace production build, zero-warning portal lint and local migration checks passed. The Marketplace artifact was rebuilt and copied into the secure/public local hosts. No deployment or browser/screen-reader acceptance was performed; full keyboard behavior in real browser layouts and mixed-route lifecycle acceptance remain open.

Follow-up modal structure review: a new regression reproduced incorrect focus ordering when a modal was rendered inside another modal rather than as its sibling. The existing shared behavior module now receives modal ancestry through React context, keeping registration order correct across portals and Strict Mode without DOM wrappers. Both modal presentations use this same context; the custom dropdown also restores trigger focus on Escape. No additional helper file, dependency or business-rule implementation was added.

Reverification: 61 shared UI tests, 127 portal tests and 30 Marketplace claim tests passed (218 total). Shared UI/portal typechecks, zero-warning changed-file lint, Marketplace/home local builds and migration checks passed. Canonical shared source/builds and both local host artifacts were synchronized. This scoped review does not certify all project directories or replace real-browser/screen-reader and performance verification.

## Current roadmap status and next step

This table reflects the implementation updates throughout this document, including September 12 Sales intake and inbox work. Historical findings explain the original gaps; they must not be used to schedule already completed implementation again. Local completion remains distinct from live-provider and deployment verification.

| Area | Present in current source | Work still needed |
| --- | --- | --- |
| Marketplace / Growth | Public and secure commerce, sourcing, claims/remedies, acquired Growth leads, assignment, activities, task scheduling and location conversion | Release verification and completion of cross-surface workflows |
| Lead tasks | Shared field/remote task lifecycle, route/day integration, task photos, working contacts, task-linked activity/follow-up, converted-location/source-lead links and Growth realtime | Finish the web consumer matrix and mixed-route acceptance checks; native execution/widgets remain deferred |
| Administration Sales | Overview, pipeline/detail, independent contact editing and primary selection, qualification/evidence, discovery-launch/profile controls, manual/CSV intake and inbox links | Authenticated end-to-end acceptance; connected booking and subscription lifecycle integration |
| Email / support | Shared Gmail/Microsoft inbox, OAuth grants, inbound/Sent sync, drafts/replies, private attachments, sharing/assignment and scoped Sales/opportunity/Support/Growth links; existing service-account outreach | Provider registration/consent, production workers and real-account acceptance; approved customer-mailbox automation, reply/bounce suppression and push subscriptions |
| Appointments | Types, Cal.com adapter, booking/cancellation, webhook ordering and terminal-state guards, idempotent outcomes/reminders, acquired-tier eligibility, explicit Growth task links and provider schedule/cancellation projection | Availability/booking UI, task-link/conflict controls, uncertain-request reconciliation, administration-scoped Sales tasks and live provider validation |
| Appointment Ready | Staff qualification API/UI in Evidence, central 60-day validity, unpublish-on-apply, explicit republication, expiry worker, reconfirmation attention and purchase snapshots | Browser/release validation and worker/scheduler deployment; verify live queue freshness and expiry behavior |

**Next implementation step:** connect subject-scoped availability/booking UI to the explicit Growth task association, and finish provider reconciliation before release. Calendar lifecycle hardening and task-link scope are recorded in the September 12 updates below. Internal Sales still requires an administration-scoped task contract. Email activation separately requires configuring the selected providers and completing the real-account acceptance checklist in `backend/runbooks/connected_mailboxes.md`; local calendar work does not require enabling mail delivery. Sales discovery-launch/profile controls, manual/CSV intake and primary-contact management are implemented locally. Approved customer-mailbox automation remains subsequent work. Authenticated mixed-route, conversion/revocation and cross-page refresh acceptance also remains open; the existing API and isolated Chromium regressions below should not be repeated as new implementation. Native apps and public venue-request intake remain deferred. Outcome recording remains separate from task completion.

### Mixed task lifecycle verification — September 10

Added API regressions using real machine, field-visit and remote-call tasks together: reschedule/reassign, completion/cancellation, rollback of earlier edits/audit/notifications when a later item fails, revoked access rejecting a whole batch, retained canceled records, and converted leads retaining task identity without creating machines. Web bulk-response tests cover all three task kinds through the same edit/status/cancel endpoints.

The refresh regression reproduced three Growth events for a single mixed edit (two per-task events plus the batch event). The existing notification suppression now also covers direct `notify_users` calls. Successful bulk operations emit one Growth and one Tasks event per recipient after commit. No new production helper, dependency, endpoint or competing task lifecycle was introduced. Nested suppression/error recovery is covered in the existing realtime test suite.

Verification: 90 backend tests passed across lead tasks, realtime revisions, machine API performance and organization task context; 64 web tests passed across task API/normalization, refresh/listener, Growth task detail and Routes. Portal TypeScript and changed-test ESLint passed. Local migrations were applied/checked and none remain pending. Production code changed by two lines in the existing notification layer; performance evidence is reduced refresh-event count, not measured production latency. No deployment or real-browser acceptance was performed.

**Assignment contract resolved:** the user confirmed that operators must be assignable to lead tasks. A task assignee can work that task independently of Growth lead ownership. The operator-access implementation below supersedes the earlier ownership restriction; the existing organization-member dropdown remains appropriate.

**Execution follow-up:** source review found execution-session ownership checks are separate from current task/entitlement access. Verify revocation/reassignment across session reads, transitions, location ingestion and monitoring before enabling native execution for lead tasks. Native client work remains deferred; this pass does not certify those sessions, real-browser accessibility, concurrency under PostgreSQL, or production performance.

### Operator-assigned lead task access — September 10

- Managers can assign an active organization operator to a lead task without changing its Growth lead owner. Task assignment grants the task's working contact context, notes, photos, status actions and task-linked activity/follow-up. General lead activity without an authorized task reference retains its existing lead-owner/manager rule. Assignment/stage/conversion management permissions remain separate.
- The shared task access predicate now recognizes the task assignee while retaining organization membership and active-entitlement checks. Growth task detail, edit, audit, status and task-filtered activity reads use the existing task lookup; the edit endpoint no longer incorrectly requires organization-manager access for an operator's notes/date changes. Existing mutation/photo services share the task authorization check.
- Reassignment, membership removal and entitlement revocation remove task access. Activity validates and locks the actual task/lead association before writing; it cannot attach an operator's activity to another task. Task mutation locks target the task rows, avoiding locks on the nullable assignee join. No new permission flag, helper module, dependency, endpoint or client-side role engine was added.
- Existing custom dropdowns already offer organization members to managers. Existing web task controls consume the server's `canEdit`, `canManage` and working-context capabilities; no separate operator UI was needed. Regression coverage exercises operator working contacts/activity, manager assignment, task notes/status, photos, routing, mixed bulk completion, reassignment/revocation and unchanged lead ownership.

Verification: 96 backend tests and 59 web tests passed. Portal TypeScript, Python compilation and scoped whitespace checks passed; local migrations were applied/checked with none pending. The modal test file passes ESLint. Full-file ESLint for `GrowthTaskDetailPage.test.tsx` still reports 10 existing Testing Library DOM-query errors in its layout/photo/modal assertions; the assertions changed in this pass add none. Browser acceptance and PostgreSQL concurrency verification remain outstanding.

### Operator task structure review — September 10

Task detail capabilities now reuse the existing task mutation authorization check instead of repeating its role/assignment rules. Growth membership checks reuse the organization's canonical membership query; with the required task relations loaded, the operator authorization check uses two queries and the owner check uses none. Shared task-photo serialization reads foreign-key IDs directly, eliminating per-photo task/uploader queries. No new helper module, dependency or permission model was introduced.

Added regressions for read-only task access not granting mutation capabilities, the authorization query budget, and zero-query serialization of multiple photos including a missing uploader. Task-detail UI tests now use accessible dialogs and the existing upload drop zone instead of DOM traversal. This resolves the ten test-file lint errors noted in the preceding implementation entry.

Verification: 99 backend tests and 32 web tests passed; portal TypeScript, zero-warning lint for both Growth task test files and scoped whitespace checks passed. Local migrations were applied/checked with none pending. These are scoped correctness and query-count checks, not a whole-project certification or production latency measurement. The next roadmap step remains web consumer/browser acceptance, followed by Administration Sales; native execution remains deferred.

### Tasks page workflow integration — September 10

The web consumer review found that the paginated Tasks endpoint still queried only machine tasks even though shared task feeds supported leads. The existing page query now includes authorized field and remote lead tasks, preserves one server ordering/count/cursor across both kinds, and reuses the existing access predicates, filter validation, cursor signing and serializers. Machine/location filters remain machine-specific; contact-portal pages and financial report pages retain their existing machine scope. Lead responses preserve their task identity and work context without fabricated machines. Lead search includes the task title and venue snapshot.

The shared custom type dropdown now includes Growth Lead. The Tasks page uses the existing URL filter hook, so status/type/search deep links are applied by the server and retained when opening task detail. Invalid URL types fall back to valid defaults. The table shows the lead task title in its Machine / Task column. Existing entity tabs retain their own scoped filters.

Paginated results subscribe to the existing Tasks domain revision and are keyed by account context. The shared cursor hook clears old-scope rows, rejects late responses and resets pagination when scope changes. Successful Add Stop creation refreshes the page after its note updates even when the local realtime echo is suppressed.

Verification: 81 backend tests and 69 web tests passed. Added coverage includes mixed page ordering and filters, operator assignment, membership removal, entitlement revocation, contact isolation, URL navigation, custom dropdown selection, realtime refresh, local creation and account/pagination races. Fetching 25 lead rows uses the same query count as fetching one. Portal TypeScript, changed-file lint and whitespace checks passed; local migrations were applied/checked with none pending. Live browser/screen-reader acceptance was not performed in this environment; these results do not certify production latency or PostgreSQL concurrency.

### Browser layout and keyboard acceptance — September 10

Ran isolated headless Chrome against the actual Tasks page, custom dropdown and lead-task detail/confirmation components at 320, 390, 768 and 1440 CSS pixels, with application CSS/zoom. Fixtures supplied task responses and in-memory identity; live API writes were disabled. This verifies browser presentation and interaction, not authenticated backend integration.

The first pass reproduced a 24-pixel horizontal overflow at tablet width: the shared TableSearch input's fixed minimum width pushed its buttons beyond the viewport. The existing component now respects its allocated flex width, and its icon-only submit button has an accessible Search label. No new component, dependency or per-page sizing workaround was introduced.

The final browser pass had no viewport overflow. Pointer selection applies the lead filter to the URL, task refresh removes records that no longer match, and completion confirmation stays within the viewport. Initial focus, repeated Tab/Shift+Tab containment, cancellation without mutation and focus restoration passed at every width. Screenshots were visually inspected for tablet task rows and phone confirmation layout. Real screen-reader use, authenticated operator/admin journeys, mixed-route execution and cross-session changes still require acceptance.

Verification: 36 web tests passed across Tasks, Growth list/detail, Marketplace filters and ModalShell; new regressions cover search-button/Enter submission and clearing while retaining task filters. Portal TypeScript, changed-file lint and whitespace checks passed; local migrations were applied/checked with none pending. No live records, emails, payments or external bookings were changed.

### Administration Sales browsing and detail — September 10

Added a lazy-loaded, superuser-gated Sales section to Administration with Overview and Pipeline tabs. The overview shows existing backend metrics and links stage counts to the filtered pipeline. The pipeline uses the shared custom dropdown, search and expandable table with server pagination. Lead detail shows ownership, follow-up, current contact, notes, customer-organization link and paginated activity. Search/stage filters survive detail navigation and Back. This slice is read-only; assignment, stage changes, activity/outcome entry, follow-up editing and conversion controls remain next.

Stage options come from the backend Sales enum. Lead cursors now contain signed priority/timestamp/ID boundaries bound to the search and stage instead of rereading a mutable boundary record; malformed or mismatched cursors produce validation feedback. Contacts and their points load in bulk. Suppressed points and suppressed/superseded primary contacts are excluded from the current-contact projection without changing the source history. The lead list uses three queries for both one and 25 rows; this is a bounded-query test, not a production latency benchmark. Concurrent edits can change live ordering; domain refresh resets the page rather than claiming a frozen snapshot.

Sales now participates in the existing realtime domain coordinator and reconnect refresh. Growth's existing resource loader was extracted into a shared domain-resource hook; Growth retains its mutation/options behavior while Sales reuses the bounded in-memory cache, identity partitioning, abort registration, focus refresh and stale-response guards. No new dependency, parallel store or persisted private-data cache was introduced. The shared cursor loader also clears displayed rows if a refresh or next-page request returns 401/403/404.

Verification: 20 Sales backend tests and 51 web tests passed across Sales screens, Growth resources, cursor pagination, Tasks, realtime and Administration navigation. Portal TypeScript, scoped lint and whitespace checks passed. Isolated headless Chrome passed pipeline/detail layout, custom filtering, Back navigation and revision-refresh checks at 320, 390, 768 and 1440 pixels; a phone detail screenshot was visually reviewed. Browser fixtures used in-memory identity and mocked responses, so authenticated acceptance and production/PostgreSQL concurrency remain open. Local migrations were applied/checked with none pending; no live Sales records, communications or bookings were changed.

### Sales structure and request-lifecycle review — September 10

Reviewed the new Sales pages against shared pagination, resource loading, task transport, backend projections and Prospecting notifications. A new regression reproduced duplicate next-page requests from two calls before React rerendered. The existing cursor hook now uses one request/success/error path for first and subsequent pages, guards concurrent pagination immediately, and cancels superseded or unmounted requests through the existing global abort registry. Both Sales and Tasks pass its signal to their existing transports. A refresh supersedes pending pagination; canceled responses cannot append stale records. Disabled pages do not fetch through manual refresh.

Removed the cursor hook's duplicate focus/visibility listeners in favor of the existing `useStaleRefresh`, including its reconnect handling and event coalescing. No additional helper module, dependency or state store was introduced. The Sales query no longer joins the organization just to read its foreign-key ID. Invalid Sales cursors are rejected before database access; the existing three-query list budget remains covered.

The review also found that shared business/contact edits refreshed Prospecting but not Sales. The existing Prospecting notification now includes the Sales revision for BusinessEntity, ProspectContact and ContactPoint changes, using the same administrator-only notification and no additional dependency lookup. Placement/qualification/discovery events do not invalidate Sales. Tests cover notification routing and removal of a contact from an already-open Sales detail after refresh. Historical records and purchase snapshots are untouched.

Verification: 26 backend tests and 72 distinct web tests passed, including duplicate pagination, cancellation, account changes, disabled pages, access loss on both refresh and pagination, focus/reconnect coalescing, contact refresh and existing task API behavior. Portal TypeScript, changed-file lint and scoped whitespace checks passed. Local migrations were applied/checked with none pending. This is a scoped maintainability/correctness review; it does not certify every project directory, production latency or authenticated end-to-end journeys. The next implementation remains the Sales assignment/stage/activity/follow-up forms.


### Sales assignment, stage and activity actions — September 10

Sales detail now supports assigning/unassigning an active administrator, changing stage with required loss reasons or a linked customer organization, and recording activity with an optional follow-up change. Stage/activity options come from the backend policy. Assignee searches are bounded to 50 results; customer organization search reuses the existing Administration endpoint with 25 results and cancellation. Linking a customer uses an existing organization; this does not create/onboard a new organization or book/send anything.

The three forms share `DraftFormSection`, a thin wrapper around existing `useDraftEdit`, draft persistence/unsaved indicator, discard confirmation, saving overlay and feedback. No separate draft store, modal, dropdown, date picker or Sales lifecycle was introduced. Failed saves retain drafts; leaving and returning preserves edits; unchanged saves explain what is needed; writes are guarded against double submission. Successful writes use the existing Sales revision to refresh detail, pipeline, metrics and history.

The backend retains administrator authorization and atomic lifecycle/history writes. Customer linking locks the selected organization and rejects links already used by another Sales lead. Omitted follow-up dates preserve existing follow-ups; explicit null clears them and records the change. Backdated contact activity cannot move Last contacted backward. Future/naive activity times and invalid stages are rejected. Same-stage detail changes now have an honest audit summary. The shared date picker was also corrected to clear the complete value when time is enabled, fixing the same clear-follow-up behavior used by Growth.

Verification: 30 Sales backend tests and 31 web tests passed, including validation, CSRF-bearing writes, refresh, duplicate clicks, failed-save retention, discard confirmation, customer linking and explicit follow-up clearing. Portal TypeScript and scoped lint passed. Isolated Chromium fixtures passed at 320, 390, 768 and 1440 pixels for stage validation/save, discard/keep-editing, activity/follow-up save and overflow checks. Local migrations were applied/checked with none pending. Fixtures do not certify live authentication/provider delivery or production latency; PostgreSQL concurrency and authenticated cross-page acceptance remain release checks.

Next: expose prospect intake and Sales-fit qualification using existing discovery, identity and scoring APIs. Then connect inbox/manual replies and appointments; do not mistake manually recording an email or demo for sending or booking one. Mobile and public venue-request intake remain deferred.

### Sales action structure review — September 10

Reviewed the new action forms against existing lookup transports, draft ownership, mutation contracts and backend audit behavior. The customer selector now reuses `fetchSuperuserOrganizations`, the existing lightweight options endpoint used by Support, rather than loading the organization directory's reporting aggregates. The shared transport now accepts an optional abort signal; existing callers are unchanged. No new endpoint, lookup helper, dependency or store was added.

Assignment selection now lives in the existing draft rather than a second component-local selection state. A restored draft retains its selected administrator's name/email even if they fall outside current search results; only the authoritative ID is submitted. The shared draft section accepts the existing hook's equality contract so a display-name change does not make an assignment dirty. Duplicate error clearing was removed, and Sales mutation payloads are typed per action.

Unchanged stage submissions return without saving, creating history, changing pipeline order or publishing a model refresh. Follow-up audit metadata is built from the locked backend record, disregards caller-supplied follow-up history, and counts toward the existing activity size limit before any write. Oversized history rolls back without altering follow-up/contact timestamps.

Verification: 33 Sales backend tests and 30 web tests passed, covering no-op SQL writes, metadata provenance/size rollback, restored assignment selection, bounded/cancelable lookup transport and the existing action/draft journeys. Portal TypeScript, scoped lint and whitespace checks passed; local migrations were applied/checked with none pending. This review does not certify every repository directory or production latency. The next roadmap phase remains prospect intake/qualification, then inbox and appointments.



### Sales prospects and qualification journey — September 10

Added a Prospects tab to Administration Sales for searching existing discovered businesses by name/address. It reuses the shared expandable table, search, cursor loader, confirmation modal and private resource cache. Qualification shows the active backend profile, calls the existing venue-scoring command and opens the resulting Sales lead. Requalification updates the same business lead, preserves previous assessments, and records an attributed Research activity atomically. Sales detail now displays paginated qualification history, current/previous assessment, profile version, score, segment and explanation. Navigation back preserves the prospect search.

New administrator-only read projections expose bounded prospect pages, the active scoring profile and lead-scoped qualification history; they do not include tenant/private purchased contacts. Prospect listing takes two database queries for both one and 25 businesses. Existing merged-venue validation and active-profile selection run again when qualifying. The manual assessment and activity write share a transaction, so failed history does not leave a partially created business/lead/assessment. No new data model, migration, scoring engine or discovery provider was introduced.

Venue edits now include the Sales refresh domain in the existing administrator-scoped notification. The prospect list also listens to the existing Prospecting revision because bulk discovery ingestion emits that domain without individual venue-save signals. Qualification refreshes Sales detail/history/pipeline/overview through the existing domain mechanism. Marketplace tier, publication, purchase and claim policy are unchanged.

Verification: 45 backend tests and 34 web tests passed across Sales APIs/lifecycle/scoring/prospects, Prospecting notifications, cursor loading and the shared modal. Checks include authorization, one lead across repeated qualification, retained assessment history, rollback on failed audit writes, missing profiles, merged-venue revalidation, query counts, confirmation cancellation/errors, navigation and both refresh domains. Portal TypeScript/scoped lint passed; isolated Chromium fixtures passed the qualification-to-lead-and-back journey at 320, 390, 768 and 1440 pixels with no page overflow. Local migrations were applied/checked with none pending. No provider search, live lead mutation, email or booking was executed.

Still open for Sales: launching new discovery searches and managing profiles from the Sales workspace; reviewing source evidence and selecting/managing primary contacts; manual/import intake for businesses not already discovered; inbox/manual replies, appointments and organization onboarding. Existing-customer linking is implemented. This slice qualifies existing discovered venues; it does not claim the complete discover/import-to-onboarding journey. Authenticated deployment checks and production latency remain unverified. Mobile and public venue-request intake remain deferred.

### Sales qualification structure review — September 10

The qualification command now reuses the existing assessment response projection instead of maintaining a second serializer. Prospect and assessment-history queries select only their response fields; the active-profile response contains only its ID, name and version. No new helper module, dependency or scoring engine was added.

The confirmation modal retains the profile staff reviewed and submits its ID. The backend rejects a changed active profile before writing any lead, assessment or activity. On failure the portal refreshes the profile; staff must close and reopen confirmation to review it before retrying. Existing command callers that omit an expected profile retain their current behavior.

Verification: 48 backend tests and 35 web tests passed. Prospect pages use two queries and qualification-history pages use three, for both one and 25 records. Tests cover stale-profile rejection with no writes, review-and-retry in the modal, permission checks, history rollback and the existing navigation/refresh journeys. Portal TypeScript, scoped lint and whitespace checks passed. Local migrations were applied/checked with none pending. Query counts establish bounded reads for these paths, not production latency or a project-wide performance guarantee. The remaining Sales roadmap above is unchanged.

### Sales contact-evidence consistency review — September 10

The scorer now excludes superseded contacts, contacts marked do-not-contact and individual contact points marked do-not-contact from its existing contact bonus query. This aligns assessment evidence with the Sales detail's current-contact rules, using the existing canonical flags and batched scoring command. No new helper, model, dependency or request was introduced. Reassessment updates the same lead and retains prior assessments; historical scores are not rewritten automatically when a contact changes.

When no profile segment terms match, the explanation now identifies the fallback segment instead of claiming a match. Profile scoring weights and fallback priority are unchanged. Regression coverage exercises each suppression flag, an available-contact control, lead priority updates, retained contact records and unmatched evidence. The existing single/batch query-budget tests cover the modified scorer.

Verification: all 50 Sales API/lifecycle/scoring/prospects and Prospecting realtime tests passed, including the single/batch query budgets. Scoped whitespace checks passed. Local migrations were applied/checked with none pending. Frontend code was unchanged in this review. Production performance and the complete repository remain outside this verification scope.

### Sales UI alignment — September 10

Sales Overview, Pipeline, Prospects and lead detail now follow the existing Marketplace Administration and Expense presentation patterns. Summary metrics use shared colored indicators and short explanations; stage distribution links use the shared status pill with one Sales stage presentation component reused across overview, lists and detail. A zero-lead overview explains how to start instead of displaying eight empty stage cards.

Pipeline and Prospects reuse shared table counts, skeletons and empty states. Empty filtered results provide clear/reset actions; an empty pipeline links to Prospects. Prospect rows indicate whether a business is already in Sales and explicitly identify missing addresses. The qualification profile sits alongside the search toolbar. Lead detail has the shared header status, clearer section boundaries, wrapping action buttons, readable segment names, and a copyable lead ID with creation date. Existing draft/unsaved-edit, confirmation, loading, authorization and refresh logic stays in place. No new backend requests, dependency or data model was added.

Verification: 37 targeted web tests passed, including empty-overview navigation and filter recovery. Isolated Chromium fixtures checked Overview, Pipeline, Prospects and the qualification-to-lead-and-back journey at 320, 390, 768 and 1440 pixels without page overflow. Portal TypeScript and scoped lint/whitespace checks passed; local migrations were applied/checked with none pending. Fixtures use local mock data; authenticated deployment verification remains separate.

### Sales indicators, help and comparisons — September 10

Sales stage pills now include contextual help through the existing shared status component. Overview metrics use the shared tooltip with keyboard-operable label buttons, colored dots, compact values and current-pipeline percentages. Help explains the overlapping due-today/overdue counts, excludes closed stages where the backend does, and distinguishes demo-stage counts from actual calendar bookings and customer share from a period conversion rate.

Qualification history compares each loaded assessment with the preceding historical assessment using the existing comparison builder/badge: point delta, relative percentage, prior score/date/profile in the tooltip, and a warning with neutral comparison coloring when profiles differ. A zero previous score uses the shared undefined-percentage treatment. Assessments display the business and historical evidence indicators for segment matches, available contacts and multiple sources. No extra fetches, backend changes or dependencies were introduced; missing older history produces no inferred comparison.

A follow-up structure review separated assessment-row presentation from history loading within the same file, consolidated evidence label/tone/help mappings, and added a neutral comparison warning when business locations differ. The comparison tooltip retains the previous location. Unknown evidence types remain visible. No new helper module, dependency or request was added.

Verification: 41 targeted Sales/tooltip/cursor tests passed, covering increases, decreases, unchanged scores, zero baselines, changed profiles/locations, evidence indicators, metric explanations and lazy comparison across history pages. TypeScript, scoped lint and whitespace checks passed. Isolated browser fixtures passed at 320, 390, 768 and 1440 pixels, including tooltip bounds, assessment history and navigation. Local migrations remain current. Period-over-period Sales trends still require historical reporting data; the UI does not invent them.

### How Appointment Ready worked at the earlier source review

**Historical findings, superseded by the implementation and current status above.** The missing staff workflow, validity lifecycle and booking-eligibility mismatch described here have since been addressed locally.

- Discovery scoring produces Researched, Qualified or Premium. Ordinary tier review cannot choose Appointment Ready.
- `backend/prospecting/models.py` defines `AppointmentQualification`: opportunity, contact, confirmation method, requested action, confirmation time, optional scheduled time, verifier and evidence metadata. It requires a qualified opportunity and a contact belonging to its business/venue/opportunity.
- The canonical `backend/marketplace/eligibility.py` derives readiness from existence of this record. Acquired tier snapshots remain authoritative for historical purchases. Readiness alone does not bypass publication and sellability checks.
- Outside tests, the current creation paths found are development/demo seeds in `marketplace/browse_samples.py` and `marketplace/development_data.py`. There is no operational staff qualification flow yet. Method names such as human verification or outreach response describe supported data, not finished integrations.
- Marketplace booking is intended for an active entitlement that is already Appointment Ready. Booking an ordinary lead does not currently qualify it. In addition, `appointments/services.py` filters `opportunity__appointment_ready`, and `appointments/api.py` reads that attribute on an ordinary related object, although it is now a Marketplace query annotation rather than a persisted opportunity field. Align both paths with canonical eligibility and add endpoint tests before enabling this workflow. This is a source-review finding, not a provider runtime test.
- Current qualification evidence has no explicit expiry/revocation lifecycle; an existing record alone supplies the readiness annotation. Validity, stale contacts and withdrawn consent must be handled before operational qualification is released.

### Agreed Appointment Ready contract

1. Staff may work an unpurchased opportunity while it is published at its existing Researched/Qualified/Premium tier, or while unpublished. Outreach does not require withdrawal. Draft evidence must not change its live tier or price. Staff may withdraw it; invalid existing information must prevent continued selling.
2. In the existing opportunity detail **Evidence** tab, record a named, authorized contact's explicit confirmation of interest in relevant vending equipment at the exact venue/area and agreement to operator follow-up. Record role, usable contact details, actual confirmation date/channel, evidence and verifier. A documented phone conversation is sufficient. Callback, meeting, walkthrough or proposal can be the next action; no booked appointment is required. Appointment Ready means confirmed interest and readiness for operator follow-up, not guaranteed placement.
3. Apply qualification through one authorized backend command, checking evidence, current contact, opportunity state and reservations/acquisitions under the existing locking rules. A reserved or purchased opportunity cannot be upgraded for sale. Preserve evidence history and separate drafts from activated qualification within the existing domain, without introducing a competing readiness flag.
4. Applying qualification follows ordinary tier review: **unpublish**, derive the new tier, invalidate affected views/quotes, review catalog pricing and explicitly republish. Do not implement automatic live upgrade/republication. Publication must recheck validity.
5. Qualification is valid for **60 days from actual confirmation**, using a central backend policy. Editing notes or republishing does not reset the clock. Renew only through fresh confirmation and retained new evidence, followed by review and explicit republication.
6. Before purchase, expiration automatically unpublishes the opportunity and marks it **Reconfirmation required**. The background job performs the transition; canonical listing/quote/checkout checks enforce expiry even if the job is late. No automatic price reduction, downgrade or renewal. A reviewer may choose a lower tier only when its evidence remains valid, using the existing review and republication flow.
7. Purchase grants full authorized data and creates the buyer's Growth lead through existing fulfillment. If valid at purchase, subsequent qualification expiry causes **no expiration email, access removal, purchase change or reconfirmation requirement**. Preserve tier, price and evidence snapshots. An actual later factual change is distinct from date expiry and follows the existing customer record/claim process.

### Qualification release checks and follow-ups

- **Agreed payment boundary:** qualification must be valid when the backend accepts the purchase. A purchase accepted before expiry may finish payment and fulfillment afterward; qualification expiry alone must not interrupt it. Page views and cart additions do not establish purchase acceptance. Failed/abandoned purchases retried after expiry require fresh eligibility checks. Map this boundary to the existing authoritative purchase lifecycle and preserve provider retry/recovery behavior during implementation.
- **Concurrent operations:** purchase/reservation, applying qualification, expiry and reconfirmation must share locking/state checks. A stale reviewer or duplicate job cannot undo a purchase or expire a freshly renewed qualification.
- **Clock and evidence:** use timezone-aware timestamps, reject future confirmation dates, derive expiry centrally, and retain the confirmation/expiry used for the decision. The agreed 60-day policy must not silently rewrite historical purchases if configuration changes.
- **Legacy records:** expiry backfill is implemented from actual confirmation dates. Verify deployed migrations and affected records; do not invent fresh confirmation dates or treat old evidence as newly verified.
- **Staff visibility:** reconfirmation-required inventory is included in the existing Attention Queue. Verify live invalidation/counts and queue transitions; a pre-expiry filter/reminder remains optional follow-up scope. No expiry email goes to a completed purchaser.
- **Contact changes:** revoked interest, superseded contacts or materially changed venue information require a validity review of unsold inventory. For the initial manual workflow, a Vendistri administrator records and verifies an explicit venue communication (for example, a call or email). A purchaser/support report is a review signal, not automatic proof of withdrawal; unanswered outreach is not withdrawal. Record source, date, reason and actor, and withdraw affected unsold inventory when withdrawal is confirmed. Internal evidence must remain separate from the buyer-authorized projection and public preview.

There are three separate concepts to connect: pre-sale venue qualification, purchaser follow-up after acquisition, and Vendistri's software-sales meetings. Ordinary Growth scheduling should not require upgrading a purchased lead's commercial tier. Define the appointment audience/permissions for that scheduling when extending the current entitlement-only booking gate.

**Deferred:** iOS/Android task implementation and native widgets, plus the public “Request vending at my location” flow, its accounts and venue self-service. Retain the native lead-visit model below as future scope; it is not a prerequisite for the current web/backend work.

**Vendistri Sales is internal customer acquisition:** Vendistri staff prospect for organizations/users who will sign up for and use Vendistri. Its outcome is a linked/onboarded Vendistri customer organization, not a Marketplace placement purchase. Placement outreach and internal Sales may reuse contacts, communication, calendar and activity infrastructure, with separate ownership and lifecycle rules.

## Implemented: withdraw a claim

- Customer action: **Withdraw claim**, on claim detail, followed by the shared confirmation modal. **Cancel** dismisses it; **Confirm** withdraws the claim. The portal and Marketplace share the confirmation presentation in `@vendistri/ui`.
- Persisted terminal status: **Withdrawn**, with withdrawing user and timestamp. Original submission, evidence, photos, updates, purchase and financial records remain intact.
- Only organization members with the existing write access can withdraw; the service rechecks active membership. This follows existing claim/update permissions rather than introducing a second role policy.
- Submitted claims and in-review claims with no remedy in progress may be withdrawn. A processing refund cannot be withdrawn. Approved/rejected claims cannot be withdrawn.
- Backend policy supplies `canWithdraw`; the mutation locks/reloads the claim before deciding. Repeated requests return the existing withdrawal without another audit event.
- Withdrawal blocks further updates and administrative resolution, including a stale refund/approval attempt. Refund processing reserves its remedy under the same claim lock, before calling the payment provider.
- Existing claim windows remain authoritative. Withdrawal does not restart the deadline, restore allowance, issue credit/refund, revoke access, relist inventory, or erase risk history. A new claim is a separate submission, permitted only if the existing eligibility policy allows it.
- Customer lists, acquired-record claim status, administrative filters/counts, opportunity claim history, detail metadata and activity retain the withdrawn claim. Withdrawn is distinct from an approved/rejected review outcome.
- Success uses the existing topbar/center-loading feedback. Customer realtime invalidation stays canonical. Administration claim list/detail now reuse silent focus/online refresh and a visible-page 30-second refresh interval; reviewer drafts stay intact. This interval is not a new global realtime system.
- Migration: `marketplace.0037_claim_withdrawal`, including withdrawal metadata and database constraints.

## Marketplace alignment review

| Connection | Current source / result | Remaining release verification |
| --- | --- | --- |
| Public and secure browsing | Same Marketplace artifact, catalog/query model, privacy-safe preview, explicit alternative filters and sourcing entry | Run authenticated public-to-secure continuation with mixed filters, account switching and expired sessions |
| Inventory → checkout | Backend eligibility, quotes, reservations, payments and fulfillment own the decision | Exercise concurrent buyers, quote/reservation expiry and payment-pending recovery against PostgreSQL and payment sandbox |
| Orders → charge/expense → entitlement | Shared record responses and existing reconciliation links | Verify all cash/credit/allowance combinations and reversals; currency totals remain separate |
| Entitlement → Growth | Existing fulfillment/`ensure_growth_lead` ownership, private access and conversion workflow | Complete the route/day/native integration below; no duplicate lead/location on retry |
| Claims → customer/admin | Shared submission, evidence, query/response and remedy services; withdrawal added with race protection | Browser-check admin/customer sessions together, including a refund already processing |
| Sourcing → Discovery → publication → matches | Organization sourcing state, shared discovery demand and queued match/progress emails exist | Verify policy/budget holds, worker scheduling, suppression, retries and production delivery configuration |
| Photos and private details | Existing authenticated private media endpoints, entitlement checks and validated uploads | Check deployed storage/CSP/cache rules; verify access after claim remedies and organization switching |
| Live changes | Customer invalidation plus authoritative refresh; admin claims now refresh silently | Audit remaining administration pages for equivalent invalidation and expiry behavior before declaring global parity |
| Operations | Broad local regression coverage and current local migrations | Worker/scheduler health, alerts, staging deployment, production migrations, representative latency and endurance tests remain release work |

No source review proves that every integration is production-ready. Local tests use mocks for external delivery/payment and do not replace device testing, PostgreSQL concurrency tests or a staging journey.

## Delivery sequence

### 1. Complete the shared lead-task contract, then web task surfaces

**Existing owners to extend:** `backend/task/models/location_lead.py`, `backend/task/schema/location_lead.py`, `backend/task/services/location_lead.py`, `backend/task/api`, `backend/growth`, `vendistri/src/vend/growth`, `taskDetail.tsx`, `components/routePlannerHelpers.ts`, `components/routes/routeHelpers.ts`, and existing task/route stores.

Growth already creates `location_lead` tasks with action, remote/field mode, schedule, assignee, field address snapshot and coordinates. The main task detail and route helpers contain initial support. This is an integration pass, not a new task subsystem.

1. Inventory every task consumer: Tasks page, Today's Tasks/dashboard widgets, route planner, routes, day detail, active execution, map/navigation, location detail, machine detail, activity/history, reports, push links and rescheduling.
2. Document one task contract: discriminator, Growth-lead ID, optional operating-location ID, mode, action/custom label, dates/timezone, assignee, permissions, outcome, notes/photos and transition rules. Add shared JSON fixtures for web/iOS/Android decoding and transition tests.
3. Field lead tasks become real route stops using authorized lead coordinates. Remote work appears in task/day queues but never contributes travel, arrival or route mileage.
4. Group visits by an explicit lead/venue stop identity. Do not require a machine, invent a machine, or silently create an operating location just to make routing work. Multiple prospects at a complex venue must not merge solely by street address.
5. Route/day/task widgets consume existing task selectors and totals. Support mixed machine and lead stops without double-counting tasks, time, distance or completion.
6. Location detail shows relevant linked lead/task history after conversion. Machine detail shows only tasks actually associated with that machine/location, not all sales work at a matching address.
7. Preserve lead assignment, stage, next follow-up and conversion through the backend commands. Task completion records an outcome; it must not automatically mark a lead Won unless the authoritative workflow explicitly permits that transition.
8. Define behavior for rescheduling, reassignment, cancellation, overdue work, revoked/replaced entitlement, won/lost/archived leads and tasks already in progress. Keep historical outcomes; block unauthorized new work using the existing access rules.

**Acceptance:** one field visit and one remote follow-up created in Growth appear in the correct Tasks/day/widget surfaces; only the visit routes. Completing from any surface updates all other surfaces once. A mixed route survives reassignment, rescheduling, cancellation and refresh. Lead conversion creates/links exactly one location and preserves purchase/task history.

### Deferred: iOS and Android task parity and a lead-specific at-location experience

**Existing owners:** native `features/work/TaskExecutionResolver`, `TaskExecutionPlanner`, `TaskExecutionCoordinator`, at-location task lists, task models/grouping/status controls, route previews, task stores and notification/widget projections.

Source inspection did not find explicit `location_lead`/Growth-lead/work-mode handling in either native client's Swift/Kotlin sources. Existing resolvers primarily group and execute machine work. Treat native decoding and destination assumptions as a concrete gap, not something the web change automatically solves.

- Extend native task decoding and exhaustive type handling from the shared contract. Preserve backward compatibility with unknown future task types.
- Reuse travel/arrival, task status, notes/photo upload, retry, navigation and completion infrastructure.
- At a lead visit, show venue/lead identity, authorized contact actions, visit objective, notes/photos, outcome and follow-up. Hide irrelevant machine cash, stock, collection and service controls.
- Remote lead tasks open a work/contact flow without starting navigation or location tracking.
- Reuse existing offline/outbox behavior where present; first verify its capabilities. Queue mutations with stable identifiers, reconcile server rejection, preserve drafts and prevent duplicate completion after reconnect. Account switches clear private caches.
- Update widgets/notifications/deep links and cold-start navigation. Test missing coordinates, revoked entitlement, deleted/unassigned membership, interrupted uploads, background/resume, safe areas and accessibility text sizes.

**Acceptance:** the same contract fixtures and route scenarios pass on both platforms; real-device field/remote execution matches web/backend outcomes. Complete a task offline, reconnect, and observe one completion/activity record and consistent widgets.

### 2. Administration workbench: manual qualification and Sales

**Existing owners:** `backend/sales/models.py`, `lifecycle.py`, `queries.py`, `scoring.py`, API and realtime; `backend/prospecting` business/contact/evidence/discovery models; existing Administration tables, detail headers, metrics, filters, skeletons, maps and activity components.

`SalesLead` already links a `BusinessEntity`, primary contact, assignee, stage, follow-up and optional converted organization. Preserve that model. Marketplace opportunity/entitlement ownership remains separate.

The manual Appointment Ready journey above is implemented locally in opportunity Evidence. Administration Sales overview/pipeline/detail and assignment, stage, activity/follow-up and existing-customer linking forms are implemented locally (see September 10 updates). Continue prospect intake/qualification and outreach/booking connections on the existing Sales backend, reusing contact display, evidence, follow-up and activity components where their semantics match. Keep placement qualification and software-sales stage transitions in their existing domain services. `LocationLeadTask` currently belongs to an organization Growth lead: do not attach platform Sales or pre-sale opportunities by fabricating a customer lead. Inspect the shared Task ownership contract before introducing those work items.

- Map existing Sales APIs and permissions before designing pages: queue/overview, searchable pipeline, lead detail, assignment, qualification evidence, activity, stage changes and follow-up.
- Reuse discovery source adapters, identity/deduplication, evidence display, geography, contact components and keyed loaders. Reuse only components whose semantics match; do not copy the Marketplace opportunity page wholesale.
- Keep Sales-fit scoring separate from Marketplace lead-tier/sellability rules. An eligible prospect for software sales is not automatically a sellable vending placement.
- Connect outreach, appointments, proposals and organization onboarding using stable lead links. Preserve provenance and prevent duplicate BusinessEntity/SalesLead/organization records on retries.
- Separate automatic recommendations from approved actions. Report funnel conversion, overdue follow-ups, delivery health and ownership using authoritative server summaries.

**Acceptance:** discover/import one prospect → qualify → assign → record contact → book/demo → follow up → convert/link organization, with one continuous audited history. Tenant/private purchased contacts are not exposed by general-purpose sales searches.

### 3. Portal email communication and automated outreach

**Existing owners:** `backend/outreach` mailboxes/campaigns/sequences/recipients/messages/suppression/delivery events; `email_log.EmailDelivery`; shared email rendering/delivery; `backend/support` contact requests/feedback; existing support realtime and portal components.

Outreach already supports approved drafts, scheduling, limits, deduplication, recovery, unsubscribe/suppression and reply events. `OutreachRecipient` currently points to a Sales lead. Support contact/feedback records and delivery/reply events do not by themselves form a full inbox with message bodies, threads, attachments, assignment and customer replies.

1. Build the communication view around durable messages/threads and existing delivery records. Inspect current provider ingest before extending it. Record provider message/thread IDs, direction, participants, timestamps, attachments and explicit authorized subject links.
2. Define platform-support versus customer-organization mailboxes and sender permissions. Add explicit links for support records, Sales leads and authorized Growth leads; extend current ownership rather than placing purchased private contacts in global campaigns.
3. Add portal compose/reply/draft, conversation history, assignment, unread/needs-reply state and delivery status. Sanitize inbound HTML, serve attachments privately, deduplicate webhook/reply ingestion and preserve audit history.
4. Extend campaign enrollment to any approved additional subject types through the same send/suppression engine. One-off replies and automated campaigns share delivery/idempotency, while campaign approval and support-reply permissions remain distinct.
5. Stop or pause automation when a recipient replies, unsubscribes, bounces, books, converts or loses authorized contact access, according to explicit policy. Confirm existing handlers before adding another one.
6. Expose queue/retry failures and worker health. Claim-resolution email already uses the shared resolution projection and delivery pipeline (`marketplace/tasks.py::deliver_claim_resolution_email`); verify deployed workers, retries and delivery rather than creating another sender. Additional update/withdrawal notifications require an explicit notification policy.

**Acceptance:** one inbound support email becomes one assigned conversation; replying from the portal stays in that conversation and has one delivery record. An approved Sales sequence stops on reply/unsubscribe. Retry and duplicate webhooks do not resend. No campaign sends before its required approval.

### 4. Calendar, booking and task synchronization

**Existing owners:** `backend/appointments` types/providers/appointments/events/services, Cal.com adapter, signed webhook processing, idempotent booking, cancellation, outcomes and reminders; `backend/user/organization_calendar.py`, existing portal Calendar/date utilities.

An Appointment already belongs to either a Sales lead or Marketplace entitlement and records host, invitee timezone, provider booking, start/end, reminder and outcome. Extend this model rather than building a second booking database.

- Finish administrative/customer booking UI and permission checks for each appointment audience.
- Reuse provider availability and booking identity. Add a calendar/agenda view that distinguishes appointments from tasks while linking them.
- Define one idempotent booking-to-task association for field appointments and remote meetings. A reschedule/cancellation updates the linked task through existing task commands; it must not create duplicate tasks or overwrite completed work.
- Prevent loops between provider webhooks, appointment updates and task updates. Handle out-of-order events, cancellation during booking, missing provider confirmations and manual reconciliation.
- Test host availability, buffers, duration, organization timezone, invitee timezone and DST transitions. Reuse reminder delivery/suppression and record no-show/completed/cancelled outcomes with provenance.
- Align booking eligibility with the canonical qualification query before adding UI. Add authorized subjects for pre-sale venue meetings or ordinary Growth scheduling only through explicit model/API rules. Confirm which provider event supplies qualification evidence through the same qualification command; frontend booking alone cannot change its Marketplace tier.

**Acceptance:** book from Sales and an acquired opportunity, see the correct calendar/task entry, reschedule and cancel from either authorized surface, and receive one reminder with correct local times. Native clients see the linked task and safe deep link.

## Additional work not to lose

- **Deployment/operations:** reconcile artifact versions, migrations, private media configuration, queues/scheduler, webhook secrets, retry/recovery and monitoring. Starting workers can process old queues; inspect those queues before enabling them.
- **Permissions matrix:** public visitor, lead-only organization, full organization, owner/manager, assigned operator, support access and administrator. Test read/write/media/export/background job permissions at the backend.
- **Revocation and conversion:** define what happens to pending work, communications and meetings when a remedy revokes/replaces an entitlement or a lead converts. Historical records must remain correctly attributed.
- **Reporting:** distinguish withdrawn claims from adjudicated claims, booked meetings from completed meetings, and tasks from route stops. Monetary summaries remain grouped by currency. Add reconciliation checks rather than client-calculated financial policy.
- **Data quality:** duplicate businesses/venues/contacts, complex venue areas, stale evidence, contact corrections and consent/suppression changes must propagate through authorized relationships.
- **Performance/reliability:** set measurable page/query/upload budgets using representative data; check constant query counts, indexed paging, lazy map loading, bounded caches, reconnect storms and large histories. Do not call local unit-test speed a production latency guarantee.
- **Native rollout:** older clients must tolerate new task types; coordinate API compatibility, staged releases, widget cache versions and an operational fallback for unsupported tasks.
- **Separate unresolved production accounting item:** the September 7 handoff documents a commission task correction that was fixed locally but neither deployed nor repaired in production. Re-audit current deployment/records before acting. Keep it separate from this plan and do not directly rewrite payment/expense history.

## Implementation order and decision points

1. Close Marketplace release checks for the implemented claims/remedies and current commerce journey. Do not rebuild completed UI.
2. Finish the task contract and web routing/day/detail integration.
3. Verify the implemented Appointment Ready journey and its release requirements; build the internal Vendistri Sales workspace using shared existing components and distinct domain commands.
4. Deliver the email inbox and manual reply workflow, then calendar/booking-to-task integration. Enable broader automated sequences after reply, suppression, booking and conversion stop conditions work together.
5. Keep native implementation as a separate future phase; it does not block these web/backend deliverables.

Calendar backend contract checks can happen during step 2; booking UI depends on a stable task association. Prepare Sales/inbox ownership alongside the web task contract without introducing competing identity or activity models. Preserve compatible backend task contracts for the deferred native phase.

Before their respective phases, settle: which roles may use each mailbox; provider/account connection and inbound email support; additional notification policy; meeting ownership/availability; and, when native work resumes, offline lead-task behavior. Legacy evidence backfill is implemented; its deployment remains a release check. The qualification meaning, 60-day sale-validity window, purchase-acceptance boundary and unpublish/republication behavior above are agreed. These remaining decisions do not block the web task integration inventory.

Each implementation slice should deliver one complete journey across its affected surfaces, focused permission/race/contract tests, visual checks on narrow and normal screens, current local migrations, and a short list of verified versus unverified deployment behavior.

## Verification for this change

- 591 customer Marketplace tests and 322 backend Marketplace tests passed. Follow-up API/detail tests and the 18-test claim update/service suite passed after the final adjustments.
- 164 Administration/Growth Marketplace checks passed, including a silent refresh during a reviewer draft and removal of decision controls after withdrawal.
- Customer build, portal TypeScript checks and public host build passed. The customer artifact was copied into the secure host.
- Isolated browser fixtures exercised confirmation, cancellation, withdrawal, retained history, title placement and removed mutation controls at six viewport sizes in standalone and embedded modes. Portal/detail blue status parity was also checked. These use mocked claims, not live customer records.
- Local migration 0037 applied; no pending migrations or model changes were detected. No real claim, payment, email, discovery request or production record was changed for validation.

### Sales Overview action widgets — September 10

Added Needs attention, Upcoming follow-ups and Recent activity. The two lead queues share a compact component; all widgets reuse the existing expandable table, status pills, tooltips, typography and skeleton bars. Lead links retain Overview as the return destination. Errors remain distinct from empty states, and expandable rows provide stage, owner and full activity text.

The existing administrator-only dashboard now returns previews of six leads per queue and eight latest activities in one response. Needs attention deduplicates leads across overdue, unassigned and missing-follow-up reasons and prioritizes overdue records. Upcoming excludes overdue and terminal leads. Lightweight projections avoid contacts and per-row database reads: five queries for both one and 26 leads. The existing private resource cache/realtime refresh remains authoritative; its shared visible/online refresh hook supports an optional interval, used here every minute for time-sensitive follow-ups.

Verification: 54 backend tests and 35 frontend tests passed, including authorization, exact follow-up boundary, queue ordering, query/payload limits, skeletons, failures, return navigation, realtime updates and hidden-tab interval suppression. TypeScript and scoped lint passed; isolated browser fixtures passed at 320, 390, 768 and 1440 pixels without page overflow. Local migrations were applied/checked; none remain pending. No new model, dependency or separate widget API was added. Production-scale latency has not been benchmarked.

### Sales widget structure review — September 10

Reviewed the Overview additions against existing UI, private resource loading, response projections and comparison code. Attention badges now use annotations from the same database predicates as queue selection and aggregate counts, removing the second Python implementation of those conditions. The API restricts attention reasons to its three supported values. Added the global activity date/ID index needed by the newest-events query; the existing lead-specific index remains for lead history.

No new UI helper, state store, dependency or comparison engine was added. Expense already uses `buildSalesComparison` and `SalesComparisonBadge`; future Sales period comparisons should reuse them with count formatting and explicit elapsed-period boundaries. Historical comparison widgets remain proposed, not implemented. This is a scoped review of the Sales additions, not a repository-wide certification or production latency benchmark.

Verification: 56 backend tests passed, including independent attention conditions, rejected unknown reason values, permission boundaries and the unchanged five-query budget. Local migration applied successfully; database introspection confirms the new index, and the migration check reports none pending. Scoped whitespace checks passed. Frontend code was unchanged during this review; its previous 35 tests and browser checks remain applicable.

### Sales customer targeting and portal consistency — September 12

Prospects now filters discovered businesses using the active customer qualification rules instead of listing every placement venue. The shipped, unmodified Vending ecosystem default is retired in favor of Vending operators v1 (vending operators/companies/services, micro-market operators/services and office-coffee services); administrator-customized profiles are preserved. Default provider searches derive from the same profile. Qualification requires a matching segment signal before creating/updating a Sales lead; unmatched venues cannot enter the pipeline through manual qualification or a discovery batch. Disabled/expired profiles cannot promote results from older runs. Historical leads and assessments are retained; historical unmatched current assessments display a customer-fit warning. Keyword evidence remains a screening signal, not independent verification of a company's business model.

Pipeline and Prospects reuse Expense's shared inline search input at the same maximum width, with debounced live queries, inline clear and shared match highlights. Removed redundant footer counts; retained header counts and pagination. Pipeline expanded rows provide primary contact and a View prospect action rather than a country-only territory field. Cursor resources retain same-query rows during focus/realtime refresh while changed searches and identities reset; initial loads retain shared skeletons.

Sales detail now has Overview, Qualification and Activity tabs and a single header action area. Shared draft sections support placing triggers in the header while forms remain below it; draft persistence/validation/discard behavior remains shared. Notes use NotesField and an administrator-only, bounded, transactional notes command with attributed activity. Activity uses one table component shared with Overview, including fixed columns, empty states, skeletons and full expandable summaries. Tab changes preserve the original search destination for Back. Overview timestamps sit at the top and widget headings use title capitalization.

Verification: 59 backend tests and 52 frontend tests passed. Coverage includes unmatched/retired-profile rejection, independent queue rules and query limits, notes authorization/validation/audit, live highlighting, stable refresh, Activity loading/empty columns, and search-preserving navigation. Isolated browser fixtures passed at 320, 390, 768 and 1440 pixels, including header actions, narrow edit forms, tabs and table layouts. Scoped lint, TypeScript and whitespace checks passed. Local migrations applied; none pending. No live provider search, outreach message or booking was initiated. Discovery launch/profile UI, fuller contact/source management, inbox and booking remain roadmap work.


### Sales detail finishing — September 12

Removed redundant Sales tab introductions and the qualification explainer. Removed the leading dividers from Qualification and Activity. Notes and the ID/Created footer now share a bottom-aligned group across all detail tabs, following the Expense viewport layout, with matching initial loading placeholders. Notes edit directly and save on blur through the existing notes command and shared entity draft storage; failed saves retain the draft and offer Retry. The unused draft-section read-content option was removed.

Verification: 39 Sales route tests passed, including direct notes saving, failed-save retry, and notes/footer visibility across tabs. TypeScript, scoped lint and whitespace checks passed. Local mocked browser checks passed at 320, 390, 768 and 1440 pixels, including bottom alignment and no horizontal overflow. Local migrations are current. The portal still displays the qualification profile name/version only; full profile configuration is available through the administrator discovery-profiles API. A profile viewer/management UI remains roadmap work.


### Sales responsive structure review — September 12

Reviewed Sales against Expense table/detail and Marketplace row patterns. Compact View actions now reuse a shared table style used by Expense, Marketplace and Sales; expanded Sales rows have consistent spacing and top-right actions. Pipeline, attention/upcoming queues and overview activity retain return navigation. Sales header actions use the existing shared top-bar next-row option and a two-column mobile group. Long mobile values wrap inside the row instead of crowding the expansion arrow. Mobile skeletons match the different row shapes; detail tabs remain mounted during initial loading and field skeletons retain their labels. Removed empty pagination wrappers and aligned loading guards.

Validation: 51 Sales route and Expense table tests passed, including request-free row expansion, filtered return navigation and initial loading. TypeScript, scoped lint, whitespace checks and local migrations are current. Responsive checks use isolated mocked data; no production latency claim or project-wide architecture certification is implied. Profile management, contact/source management, inbox and booking remain the next roadmap work.


### Sales sidebar memory — September 12

Sales now records visited Pipeline, Prospects and lead detail routes through the existing Marketplace administration navigation recorder. Search/filter parameters and the latest detail tab are retained. The existing per-identity two-shortcut limit, removal, collapse and restore-last-visited preference apply without a Sales-specific store or additional requests. Eight navigation/layout/sidebar tests passed, including Marketplace regression coverage and identity isolation. Local migrations are current.


### Sales unified inline editing — September 12

Replaced the four detail header actions with shared EditControls. Overview renders owner/stage/follow-up as read-only data, then custom inputs in edit mode. The Activity tab accepts an optional new activity; Qualification can queue reassessment using the displayed active profile. One persisted detail draft spans tabs and route revisits; dirty Save styling and discard confirmation reuse existing controls/hooks. Direct Notes editing remains the existing separate field workflow.

The detail draft submits one administrator-only PATCH transaction composing the existing assignment, stage, activity and qualification services. Qualification follows discovery's venue/entity/lead lock order and cannot target another business. A required record timestamp prevents stale saves and duplicate activity on replay; failures roll back all changes and retain the frontend draft. Follow-up-only changes retain audit history without falsely recording contact. Corrected the assignee schema to use the user model's bounded string IDs rather than UUID coercion.

Validation: 42 backend lifecycle/API/scoring tests and 43 frontend route tests passed, including rollback, stale replay, cross-business rejection, single-request cross-tab saves, reviewed-profile reassessment, failed-save persistence and clear follow-up. TypeScript, scoped lint and whitespace checks passed. Local mocked browser checks passed at 320, 390, 768 and 1440 pixels; narrow-screen header and date fields were visually reviewed. Local migrations are current.


### Sales contact table and intake — September 12

Sales detail now always renders the shared Opportunity contact table, including empty field labels, copy controls and matching loading skeletons. It shows current business contacts with a primary label. Add Contact starts or extends the existing detail draft; added rows can be changed or removed before the shared Save, and remain in the draft across tabs. Existing canonical contacts remain read-only in this pass.

The administrator-only detail transaction appends contacts to the existing BusinessEntity/ProspectContact/ContactPoint records, validates contact points, selects the first added contact as primary when none exists, and records an attributed activity. Stale retries cannot duplicate additions; invalid contacts or a later failed edit roll back the entire transaction. Suppressed/superseded contacts and suppressed contact points are excluded from the detail response. Detail reads remain three queries with multiple contacts and use existing realtime refresh signals.

Validation: 46 backend lifecycle/API/scoring tests and 45 frontend route tests passed. TypeScript, scoped lint and whitespace checks passed. Local mocked browser checks covered add/save, tab persistence and overflow at 320, 390, 768 and 1440 pixels; desktop and narrow layouts were visually reviewed. Local migrations are current. Saved-contact editing/removal was delivered in the later September 12 contact-editing update below. Explicit primary-contact selection, broader source management, profile management, inbox and booking remain roadmap work.


### Independent Sales contact editing — September 12

Contacts now owns its persisted contacts draft and local Save/Cancel controls next to Add Contact, separate from the top-level detail Edit flow. Both use the existing shared table, edit controls, discard confirmation and unsaved-draft store. Saving or cancelling either section leaves the other draft intact. A successful local save advances sibling drafts only when they reference the exact revision just saved; external refreshes retain stale-write protection. Contact-only saves reuse the existing audited backend mutation and do not submit owner, stage, follow-up or qualification changes.

Validation: 48 Sales route tests passed, including saves in either order, independent discard and tab persistence. TypeScript and scoped lint passed. Mocked browser checks passed at 320, 390, 768 and 1440 pixels; the narrow contact controls were visually reviewed. No pending local migrations.


### Sales meaningful drafts and future follow-ups — September 12

Contact dirty state and saved additions now use trimmed, non-empty rows; adding an empty row or clearing its contents leaves Save clean and cancellation does not prompt. Detail comparisons trim free text and compare follow-up instants rather than timestamp spelling, so reverting fields or reselecting the same time remains clean.

The Sales follow-up picker uses the existing compact calendar at 248px with a future minimum. Save revalidates against the current clock, and the shared backend activity lifecycle rejects newly changed non-future follow-ups. Existing overdue follow-ups remain visible and may be retained or cleared. The shared date input's clear action remains available with a minimum date.

Validation: 56 frontend Sales/date-input tests and 38 backend Sales lifecycle/API tests passed. TypeScript and scoped lint passed. Local migrations are current.


### Sales addresses and working demo pipeline — September 12

Sales detail now projects the current BusinessEntity venue addresses from shared prospecting records, including street, city, region/state, postal code and country when recorded. Structured address fields provide the fallback when formatted address is absent. Multiple offices remain visible, merged venues are excluded, and copy controls/loading labels use existing components. No address is inferred as headquarters. Detail reads use four fixed queries including all contacts and offices; listing queries remain unchanged.

Added `python manage.py seed_sales_development_data --confirm-development`, guarded by DEBUG and explicit development confirmation. It adds 24 fictional vending businesses: eight unqualified prospects and sixteen leads (two per Sales stage), contacts, addresses, notes, assessments, attributed activity and varied follow-up/ownership states. Two Customer-stage examples link to isolated demo organizations with inactive login-disabled owners and no subscription/payment creation. Deterministic company IDs make reruns preserve existing edits and prevent duplicate activity/organizations. Historical overdue states are fixture-only backdating; ordinary follow-up validation remains future-only.

Expected staff workflow: review a discovered vending business, qualify customer fit, assign an owner, contact and follow up, schedule/complete a demo, trial the service, then link a Vendistri customer organization. Stage progression is staff-managed; stages do not themselves send email, book calendar events or activate billing. Inbox/outreach, booking and subscription lifecycle integration remain roadmap work.

Validation: 17 backend API/demo-data tests and 53 Sales UI tests passed; TypeScript and scoped lint passed. Mocked browser checks covered multiple addresses at 320, 390, 768 and 1440 pixels. Local migrations are current.


### Saved Sales contact editing — September 12

Sales Contacts now has its own Edit Contacts / Save / Cancel controls for saved contacts as well as additions. Name, role, email and phone changes and removals stay in the persisted contact draft until Save; reverting values or adding an empty row leaves Save clean. Contact editing remains independent of page details and Notes. Older addition-only drafts remain usable. Initial loading retains the table skeleton and reserves space for both contact controls.

The existing administrator-only detail mutation now accepts a bounded contact list with owned, unique IDs and the expected lead revision. Entity/lead locks and the transaction cover all edits, additions, removals, primary-contact fallback and attributed activity. Unchanged contacts are not rewritten. Email/phone synchronization is shared with administration Marketplace contact editing and retains verification for unchanged normalized methods. Suppressed methods and contacts referenced by history are protected. Business Address continues to show the recorded full or partial address without inventing a street address.

Validation: 72 backend Sales/Marketplace tests and 66 frontend Sales/shared-contact tests passed. TypeScript, scoped lint and whitespace checks passed. Mocked browser checks passed at 320, 390, 768 and 1440 pixels, including saved-contact edits, independent page controls and no horizontal overflow; the narrow saved layout was visually reviewed. Local migrations applied and verified with none pending.

### Sales intake and connected inbox — September 12

Sales now has a Discovery tab using existing provider controls, provider budgets, reusable searches and runs. Staff can create qualification-profile versions and enable/disable profiles. Launch requests retain an idempotent receipt so retrying the same request does not launch another set of provider searches. Prospects supports manual businesses and CSV imports with a server-side preview, whole-batch validation, identity matching, and idempotent commit. Importing a business creates a reviewable Sales lead; it does not fabricate a venue, coordinates, or qualification. Contact changes support explicit primary-contact selection, and qualification detail shows bounded retained discovery/manual source evidence.

The shared Inbox implementation is available at `/administration/inbox` and `/inbox`. Google Workspace/Gmail and Microsoft 365/Outlook were the selected first providers. It reuses the canonical OutreachMailbox identity, EmailDelivery ledger, private storage, existing activity feeds, realtime revisions, domain caches, draft state, dropdowns, tables, skeletons and modal components. The new communications app owns OAuth connection grants, conversations, messages and attachments. OAuth state is actor/workspace-bound, expires in ten minutes and is single use; tokens require KMS encryption. Mailbox delegates remain separate from record and organization access.

Implemented locally: connect/disconnect, explicit mailbox sharing, bounded incremental inbound/Sent sync, compose/reply, saved drafts, private attachments, assignment, open/closed state, linked Sales/opportunity/Support/Growth records, generic activity updates, and provider acceptance/failed/uncertain states. Sales and opportunity detail and customer Growth detail link into the corresponding filtered inbox. Draft conflicts, ambiguous-send recovery and private-body boundaries are enforced on the backend. Background refresh retains visible content; compose uses the existing remembered draft workflow.

**Not live yet:** provider OAuth registration/credentials and consent approval, production worker/beat rollout and real-account acceptance for both providers. Existing service-account outreach remains separate; customer mailbox campaign automation, campaign reply/bounce suppression, push delivery subscriptions and calendar booking are still next-phase work. Setup and live acceptance checklist: `backend/runbooks/connected_mailboxes.md`. No real mail was sent during implementation.

Validation: 86 backend tests and 70 frontend tests passed. Portal TypeScript, scoped ESLint and whitespace checks passed. Offline Chromium checks covered inbox/conversation layouts and compose controls at 320, 390, 768 and 1440 pixels, including clean cancellation and reply recipients; desktop and narrow compose layouts were visually reviewed. Local migrations are applied, with no pending migrations or ungenerated model changes. Provider requests were mocked; these checks do not establish live delivery or production latency.

### Inbox synchronization and setup review — September 12

Gmail incremental ingestion now applies the same Inbox/Sent boundary as initial sync, excluding provider drafts, Spam and Trash. Replaying unchanged messages and refreshing tokens no longer advances user-edit revisions. Mailbox sharing returns its actual saved revision and invalidates conversation assignments when access is removed. The send query locks the message itself rather than the nullable reply join, supporting PostgreSQL locking rules.

Sent-folder confirmation now reconciles the existing message and EmailDelivery receipt through one acceptance service. A late request timeout cannot overwrite confirmed acceptance, repeat ingestion does not duplicate activity, and delayed completion cannot move the conversation's latest-message timestamp backward. Reconciliation never resends mail.

`python manage.py check_mailbox_setup` reuses the connection API's configuration checks and checks the private-storage path and scheduled sync task without provider requests or secret output. The current local environment is missing both providers' client IDs/secrets, the OAuth callback URL and the KMS key setting. Those settings and real-account acceptance remain required; no live connection or send was performed.

Validation: 48 backend inbox/outreach tests passed, including sync replay, timeout races, edit revisions, setup validation and secret-output checks. Python compilation and scoped whitespace checks passed. Local system/migration checks passed, with no pending migrations or ungenerated model changes. This slice did not change frontend code; the previous UI verification remains recorded above.

### Sales and inbox UI structure/loading review — September 12

Loading skeletons now replace data values only. Inbox mailbox controls, provider buttons, search and table headers remain visible during initial loading; unavailable actions are disabled. Sales discovery keeps its real profile dropdown. Contact actions, qualification field labels, mobile pipeline labels, and lead footer labels remain visible while values load. Restored drafts keep the compose dialog, labels and disabled actions; OAuth progress uses a status message rather than a data skeleton.

Inbox, conversation and composer actions reuse the shared Button component, and mailbox sharing uses shared EditControls. Existing InfoRow, NotesField, table, draft and resource components remain authoritative; no dependency, request or backend mutation was added. Regression tests now wait for visible controls to become enabled before interacting.

Validation: 69 Sales/inbox UI tests, TypeScript, scoped ESLint and whitespace checks passed. Offline Chromium checks passed at 320, 390, 768 and 1440 pixels, including compose/reply controls and no horizontal overflow; the narrow composer was visually reviewed. Local migrations are current with no ungenerated model changes. Existing Sales-assignee test act warnings remain; no test failed. This was a scoped UI review, not a repository-wide audit or production latency measurement.

### Appointment lifecycle hardening — September 12

The existing appointment service now preserves signed webhook updates that arrive before a booking HTTP response, keeps uncertain creation/cancellation requests pending instead of dispatching them again, and permits safe retries after a known local configuration failure. Request identity normalizes UUID subjects and retains the requested start separately from a provider reschedule. Accepted bookings can be replayed after their original start or type disablement without making another provider request. New requests still require an enabled type/provider, an existing subject and a future aware start; Marketplace entitlement authorization/eligibility checks remain enforced.

Webhook handling uses the provider envelope's `createdAt` timestamp as documented in [Cal.com's webhook reference](https://cal.com/docs/developing/guides/automation/webhooks). The existing event history retains delayed events, while a watermark on the appointment prevents an older reschedule from overwriting newer state. Completed, no-show and cancelled appointments are not reopened by booking events. Duplicate creation/same-schedule notifications do not restart reminders, and reuse of an event identifier with changed payload is rejected. Legacy payloads without timestamps use receipt time, so their reschedule ordering cannot be guaranteed. Cancellation response handling re-locks the appointment and preserves concurrent webhook metadata.

Outcome recording now requires a scheduled appointment that has started. An identical repeat returns the saved result without another Sales activity; changing an already finalized outcome requires a future explicit correction workflow. This slice reuses Appointment/AppointmentEvent, provider errors, existing Sales stage/activity commands and realtime signals; it adds no competing calendar, task or UI state and requires no model migration.

Remaining before booking release: availability and audience-scoped booking UI, one authoritative booking-to-task link, provider-confirmed reconciliation for uncertain requests, provider reschedules that replace the booking UID, and live end-to-end verification. A request left pending after timeout is deliberately not resubmitted automatically; a signed provider event can resolve it, but there is not yet an operator reconciliation UI. No real bookings, invitations, reminders or emails were sent by this verification.

Validation: 59 tests passed across appointment services, the Cal.com adapter/API and Marketplace qualification, including request replay, early webhook responses, stale reschedules, terminal-state preservation, reminder deduplication and outcome idempotency. Python compilation and scoped whitespace checks passed. Local migrations were applied/checked with none pending. Provider calls were mocked; deterministic interleaving tests do not establish PostgreSQL concurrency behavior, live provider compatibility or production latency.

### Appointment structure and loading review — September 12

Consolidated acquired booking rights and enabled appointment types in the existing `appointments/queries.py`. The eligibility API and booking command use the same entitlement rule; both type-list consumers exclude inactive providers. Eligibility reads only the required entitlement data and evaluates the type list once, removing an unused opportunity load and the separate existence query. Regression budgets cover one query for an ineligible entitlement and two for an eligible entitlement with multiple types. Booking retries now lock through the existing `get_or_create` query, removing the additional lock query and repeated retry condition; email normalization is performed once.

The Sales/inbox loading review verified visible titles, labels, dropdowns and actions with skeletons confined to data. It also exposed a nested button in the mobile inbox summary. The summary now uses the shared table's expand control and its existing View Conversation action; the new regression verifies accessible expansion, no nested buttons, no request on expansion and correct navigation without writes. No new component, helper file, dependency or model was introduced.

Validation: 62 appointment/Marketplace backend tests and 70 Sales/inbox UI tests passed; TypeScript, scoped ESLint and whitespace checks passed. Local migration execution reported no pending migrations. Existing Sales async act warnings remain in the broader UI suite; the inbox nested-button warning is resolved. This is a scoped structure review with measured query budgets, not a repository-wide duplication/security certification or production latency claim. The roadmap's booking/task association, reconciliation and live-provider acceptance work remains open.

### Explicit Growth appointment task links — September 12

An existing confirmed Marketplace appointment can now be linked to an existing call, meeting or visit task through `PUT /appointments/{appointment_id}/task`. The task must belong to the same acquired Growth lead, be unstarted and unfinished, and have the appointment's date in the organization's timezone. The endpoint reuses task access and superuser write-context checks; the service revalidates ownership and active entitlement under the transaction. Repeating the same link is idempotent. A database one-to-one constraint prevents competing links, and a subject constraint excludes Sales appointments from customer task ownership.

Signed provider reschedules update the existing task date through the shared task edit/audit service. Confirmed cancellations use the canonical task cancellation lifecycle. Started or finished work and revoked entitlements are preserved; the appointment response exposes `taskSyncIssue` for review. Provider outcomes do not automatically complete task work. Uncertain or failed cancellation requests leave task work unchanged. Task date changes and cancellation cannot bypass an active linked booking; after provider cancellation, preserved work can still be explicitly cancelled by an authorized user. Existing Growth and task realtime notifications cover the link and synchronization changes. Unlinked appointments do not query tasks.

This is a backend integration slice. It does not create tasks automatically or add booking controls to the web pages. Next: subject-scoped availability/booking controls and task selection, display linked appointment details and synchronization conflicts, then provider reconciliation (including replaced booking UIDs). Internal Sales appointments still need an administration-scoped task contract; customer operational tasks are not repurposed for Sales. Live provider acceptance and Inbox credential/worker activation remain open. No real booking, invitation, reminder or email was sent.

Validation: 23 new task-link regressions and 109 existing appointment, Marketplace qualification and lead-task tests passed across the broad and focused runs. Coverage includes tenant/operator/superuser restrictions, unique links, timezone/DST boundaries, stale/replayed events, cancellation uncertainty, preserved work, revoked access and transactional rollback. The broad run's remaining fixture error was corrected and the complete new suite rerun successfully. Python compilation, scoped whitespace checks and Django system checks passed. Migration `appointments.0009` is applied locally; migration and model-state checks report no outstanding changes. Providers were mocked and the test database was SQLite; PostgreSQL concurrency behavior and live delivery remain unverified. No frontend files or loading states changed in this slice.

### Appointment/task structure and loading follow-up — September 12

The shared lead-task edit core now emits task/Growth refresh notifications only when values actually change. Unchanged trimmed notes and unchanged scheduling perform no writes or audit inserts. Removed the repeated assignment-normalization call because `Task.save` already owns it. Synchronization uses the task command's existing notifications when a schedule change also clears a sync issue; warning-only changes still notify. Cancellation no longer computes an unused local date or depends on timezone parsing.

Growth task detail now renders its existing venue labels, Contacts table and disabled Record activity action during initial loading. It reuses the existing nullable-lead contact component and shared field skeletons; headings, field labels and controls remain visible, while background refresh retains loaded values. Expanded the existing loading regression rather than retaining duplicate tests. No new helper module, dependency or competing business-state implementation was added.

Validation: all 135 targeted backend tests and 17 Growth task UI tests passed. TypeScript, scoped zero-warning ESLint, Python compilation and whitespace checks passed. Local migrations are applied and model-state checks report no changes. This review covers the appointment/task integration and related loading presentation; it does not certify every repository directory, PostgreSQL concurrency, live provider behavior or production response times.

### Shared Sales and Growth booking form — September 12

Sales lead detail and acquired Growth lead detail now open the same appointment form. It reuses the existing modal, buttons, dropdown, compact calendar, draft/discard guard and resource cache. Availability loads only after choosing a type and date; labels and controls remain visible during loading. Past dates and invalid contact details are blocked. Confirmed Growth bookings can link an existing unstarted call, meeting or visit through the existing appointment/task endpoint. Sales bookings do not expose customer tasks.

The backend now supplies subject-scoped booking options and bounded availability. Booking and availability reuse the same audience/entitlement checks. Customer booking requires organization write access; operator, other-organization and implicit superuser writes are rejected. Task choices are bounded to 100 eligible rows. The Cal.com adapter queries `/v2/slots` using its documented `2024-09-04` version, validates aware timestamps, deduplicates slots and clips results to the requested interval. Reference: https://cal.com/docs/api-reference/v2/slots/get-available-time-slots-for-an-event-type . No second calendar or task lifecycle was introduced.

Once submitted, the form retains the exact request and idempotency key across modal close/reopen and route changes in the current session. Double submission is blocked; retries reuse the same request. Confirmation remains available when closing with the modal close control; Done explicitly clears the form. The current entity draft store is in memory: this is not durable recovery after a full browser reload. Successful mutations refresh only the relevant Sales or Marketplace/Growth domains, plus tasks when linked.

Validation: 96 backend tests passed. The existing Sales/Growth detail suites plus the initial form tests passed (78 tests); the final expanded form/API suites passed all 13 tests, for 84 distinct UI tests across these runs. TypeScript and scoped zero-warning ESLint passed. Offline Chromium checks passed at 320, 390, 768 and 1440 pixels with the real calendar open and no horizontal page overflow; visual review corrected the date input width and footer padding. All provider responses were mocked and the browser fixture blocked real writes. Local migrations have none pending and model-state checks report no changes. An unrelated existing whitespace warning in `administration/billing.py` was left untouched.

Remaining: contextual appointment history, reschedule/cancel and synchronization-conflict UI, durable recovery/reconciliation of uncertain bookings (including provider replacement UIDs), and live provider acceptance. Inbox credentials and scheduled worker activation remain outstanding. This is a booking UI/service slice, not completion of the entire booking or inbox release.

### Appointment lifecycle and reload recovery — September 13

Sales and acquired Growth details now share an Appointments table with current status, confirmed time, scoped reschedule/cancel controls, and linked task navigation. Growth task detail displays its linked appointments and synchronization issues. Confirmed booking, rescheduling, cancellation and outcome events project into the existing Activity tables. The existing task lifecycle remains authoritative: provider changes update eligible work and preserve started or finished work with a visible review message. Organization operators can read appointment history; management requires existing organization write permissions, while Sales management requires administration access.

The shared controls reuse the existing modal, confirmation/discard guard, compact calendar, custom availability dropdown, status pills and responsive table. Static labels, controls and table headings remain visible during loading; loaded data stays in place during background refresh. Rescheduling validates future time and only enables the primary Save action for a changed selected time.

Uncertain writes persist on the server and appear after a browser reload. Check Status reads Cal.com before resolving an attempt; it never resubmits a booking. Subject locking and matching attempts prevent a new browser idempotency key from creating the same booking again. Replacement booking UIDs follow verified provider lineage. Explicit provider rejection permits another selection; timeouts remain unresolved until checked. Recovery intentionally searches a bounded provider page and replacement chain: absence from that search is not proof that no booking exists and does not authorize a repeat write. Unresolved cases can still require provider-side review.

Cal.com remains the current provider. Invitees use its configured secure management links and provider rules; this slice does not build an in-house scheduler or a public Vendistri attendee-management portal. Provider integration remains behind the existing adapter. References: https://cal.com/docs/api-reference/v2/bookings/reschedule-a-booking , https://cal.com/docs/api-reference/v2/bookings/get-a-booking , https://cal.com/docs/api-reference/v2/bookings/get-all-bookings . Live provider acceptance, attendee notifications, inbox OAuth credentials and worker activation remain outstanding. No real booking, invitation or email was sent.

Local appointment migrations 0010 and 0011 are applied; migration and model-state checks report no outstanding changes. Offline Chromium checks at 320, 390, 768 and 1440 pixels passed with the calendar open, without horizontal page overflow or network writes. TypeScript and scoped ESLint checks passed; an existing Growth detail test file still has unrelated testing-library lint errors. This is a scoped lifecycle implementation, not a repository-wide cleanliness or production-performance certification.

Validation: the broad backend run covered 205 appointment, Growth and task tests; its sole failure was a mixed-task fixture using the system date across location timezones. The fixture now uses the tasks' local completion dates and its focused rerun passed. All 14 lifecycle/permission tests also passed, including the added operator read-only regression. Across these runs, 206 distinct backend tests passed. The UI checks covered 109 distinct tests across broad detail-page and final appointment suites. Python compilation and scoped whitespace checks passed.

### Appointment final code review — September 13

The pending-booking confirmation now offers the same Check Status control as appointment history, so receiving a pending response does not require another booking submission or a browser reload. Reconciliation avoids writes and Activity inserts when the provider returns unchanged state. Equal-timestamp responses cannot undo a recorded schedule, while cancellation retains its tie-breaking precedence. An explicitly rejected attempt cannot be reopened by a late snapshot.

A known configuration failure is handled separately from an uncertain provider request: Check Status closes the unsent attempt as Not Booked under the existing row lock without calling the provider. This removes a reload-related blocker when credentials are configured later. The original same-request safe retry remains supported. New tests cover pending-form recovery, no-op reconciliation, stale timestamp handling and recovery from missing credentials.

Deferred activation: configure backend `CALCOM_API_KEY`, `CALCOM_WEBHOOK_SECRET`, the intended event-type IDs, and the signed webhook endpoint; then use dedicated test accounts for booking/reschedule/cancel and invitee-link acceptance. `CALCOM_API_URL` is optional. Google/Microsoft mailbox configuration and live acceptance remain documented in `backend/runbooks/connected_mailboxes.md`. No credentials are needed to run the mocked test suites, and no real booking or email was sent during this review.

Final validation: the broad backend suite passed all 209 tests; the final recovery/permission suite passed all 18 tests, including the subsequently added configuration-recovery case (210 distinct backend tests across runs). All 110 UI tests across six appointment, Sales and Growth suites passed. TypeScript, zero-warning appointment-scoped ESLint, Python compilation and scoped whitespace checks passed. Existing broader Sales async act warnings remain. Migrations were applied/checked and model-state validation reported no changes. Live provider acceptance remains deferred until credentials are supplied.
