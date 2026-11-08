/Users/mohamedkatary/pro-claws/docs/session-handoff-2026-09-17.md Continuation handoff — Sales, appointments, Inbox and homepage intake

Prepared September 17, 2026, America/New_York. This is the starting point for the next chat, consolidating the conversation and the existing project notes. It records the final agreed behavior rather than every intermediate design. Implementation and test results below are local; they are not production deployment or live-provider certification. This handoff preparation is a documentation/source-review pass, not a fresh application test run.

## Executive summary

Vendistri now has a substantial connected web/backend implementation for Marketplace, acquired Growth leads/tasks, internal Sales, connected Inbox, and Cal.com-backed appointments. This chat refined Sales and appointment management to match the existing portal, clarified qualification versus pipeline membership, audited provider setup, and added public homepage demo inquiries to Sales intake.

The last completed implementation connects the homepage **Book Demo** form to a durable ContactRequest and a new or existing Sales lead. Company name is required. Unknown business information remains blank and a new lead's Sales fit is **Not assessed**. Conservative matching protects existing businesses, contacts, stages and ownership. Ambiguous matches are retained for staff review. Form retries are idempotent; a failed save no longer opens the booking calendar and loses the inquiry.

**The next implementation step remains: correlate a saved homepage inquiry with a trusted Cal.com booking confirmation, attach the Appointment to its Sales lead, and apply only appropriate Sales stage transitions. This is NOT implemented by the latest intake change.** The existing Cal.com webhook updates known Appointments; it does not yet convert an unrelated public homepage booking into a linked Sales appointment.

Credentials are necessary for live use, but they are not the only remaining work. A Celery Beat configuration override is an important unresolved operational issue. Ambiguous inquiry review/resolution and practical completion of missing business details also need end-to-end review. Live provider acceptance, PostgreSQL concurrency and release journeys remain outstanding.

## Read order and how older notes apply

1. [AGENTS.md](../AGENTS.md): canonical working instructions. Preserve unrelated dirty worktrees.
2. This handoff: current decisions, latest intake work, next priorities and limitations.
3. [September 15 session review](session-review-2026-09-15.md): concise Sales/Inbox/appointments baseline before this chat's later refinements.
4. [Marketplace/Growth working roadmap](marketplace-growth-next-steps-2026-09-08.md): detailed chronological implementation history through September 13. Later entries supersede earlier “remaining” lists, including missing booking UI, task links and reconciliation.
5. [September 3 Marketplace handoff](../marketplace-handoff-2026-09-03.md): domain/commerce/privacy policy baseline. Its missing customer sourcing UI and migration ceilings are historical, not current instructions.
6. [September 7 Marketplace/Growth handoff](../vendistri/docs/marketplace-handoff-2026-09-07.md), [Growth ownership notes](../vendistri/docs/growth-workspace.md), [September 8 journey review](marketplace-journey-review-2026-09-08.md), and [claim remedies](marketplace-claim-remedies.md): preserve ownership, commerce, corrections and operational constraints.
7. [Connected mailbox runbook](../backend/runbooks/connected_mailboxes.md): actual configuration and acceptance requirements.

The [August 25 administration handoff](../marketplace-administration-handoff-2026-08-25.md) is older design context. Do not rebuild features merely because an early roadmap calls them missing. Inspect current source before acting. No credentials belong in this document or chat output.

## Goals and domain boundaries

| Domain | Purpose and authoritative records |
| --- | --- |
| Business/prospect | BusinessEntity, venues, contacts and retained discovery/source evidence. Can exist before any Sales lead. |
| Vendistri Sales | Acquire customers for Vendistri software. SalesLead links a BusinessEntity, owner, stage, follow-up and eventual customer organization. Accepts discovery, manual/CSV and now homepage demo intake. |
| Sales fit assessment | Evaluate recorded business evidence against a versioned customer profile; retain assessment history. Pipeline stage and customer fit are separate. |
| Marketplace | Discover and sell qualified vending-placement opportunities with authoritative tier, publication, pricing, quote, purchase and entitlement policy. |
| Customer Growth | Work an acquired opportunity under its entitlement, using contacts, activities, tasks, follow-ups and conversion to an operating location. |
| Inbox | Authorized mailbox conversations, drafts, replies, attachments, delegation and links to supported records. Record access alone never grants mailbox access. |
| Appointments | Shared provider-backed scheduling and retained lifecycle events for authorized subjects. Reuse the existing Appointment model and Cal.com adapter. |
| Support | Contact requests, support notification email, Help feedback and Inbox support links exist. A complete support-ticket workflow is not implemented. |

A business contacting us may already have been found/called through discovery, or may be entirely new. Discovery and prior qualification are **not prerequisites** for inbound Sales intake. Existing customer support requests must not all become Sales demos. Public “Request vending at my location” intake and venue self-service are still unimplemented/deferred; do not route these blindly into software Sales.

## Decisions and requirements established in this chat

### Shared UI, responsive behavior and editing

- Reuse existing Expense, Marketplace, recurring-expense detail and location scheduling patterns. Do not invent alternate tables, dropdowns, draft stores, loading systems or calendar workflows.
- Match Marketplace table typography. Primary row content generally uses the shared 14px/text-sm treatment; secondary metadata uses the established smaller style. Do not enlarge a modal/table independently. An app-wide pixel audit has not been certified.
- Expanded-row View/action controls belong at the **right end of the top label/title row**, including small screens, rather than below the expanded fields. Apply this through shared patterns when touching additional tables.
- No page-level horizontal overflow. Keep the Messages / Appointments / Appointment Types selector above the table, like the Marketplace Discovery sub-tabs; do not place it inside the final table column.
- Read and edit modes must keep labels, field order, columns, typography and occupied space consistent. Do not add left padding to read-only values just to imitate input padding.
- Detail footers stay at the bottom of short pages on small and large screens, and appear across all detail tabs. They must remain part of a layout that allows longer content to scroll normally.
- Edit belongs to the active editable tab. Reuse persisted drafts, meaningful dirty comparisons, clean reversion, stale-save protection and unsaved-change confirmation. Do not remove concurrency protection to mask a false conflict.
- Modal Save/submit remains available for validation of incomplete input; guard duplicate submission while running. Reuse two-Escape close behavior and dirty discard confirmation.
- Use the existing centered action-loading feedback when appropriate and topbar success/error toast pills. Keep inline actionable validation where needed. Background reads should not blank already loaded content.
- Skeletons replace data only. Titles, labels, filters, dropdowns, table headers and action controls remain visible; disable controls that require unavailable data.
- Use portal Dropdown/SearchableSelect and standalone Marketplace Select from @vendistri/ui. No new native visible selects. Icons use the established renderIcon wrapper where required by React icon typings.
- Search includes relevant visible/related fields and respects permissions. Use authoritative server filters, pagination, counts and summaries rather than deriving totals from the loaded page.
- Use the existing timezone-aware formatting. Booking shows a friendly date-appropriate label, e.g. **Timezone: Eastern Daylight Time (EDT) · America/New_York**. Do not hard-code EDT year-round or assume every date is daylight time.

### Sales layout and qualification feedback

- Discovery Profiles / Searches sits at the right of its table title/header row (Profile / Version / Status, or Search / Country / Latest Run). An active profile is not proof that a discovery run is currently executing; check actual run state and launch guards before deciding whether another launch is allowed.
- Overview Recent Activity belongs beneath Pipeline by Stage.
- Lead Notes belongs only on Overview; the ID/created footer remains on all tabs.
- Primary Contact is visible in both read and edit modes. Contacts is labeled **Contacts (X)**. On narrow screens, contact editing/add actions align to the right of the Primary Contact heading row; they must not unexpectedly appear underneath as a separate layout.
- On narrow screens, lead header actions (Inbox, Book Appointment, Edit) use an orderly row below the identity/title area instead of stacking awkwardly beside Back and the stage pill. Long assignee emails must wrap without page overflow.
- A prospect/business can already be in the Sales pipeline and still be reassessed. For an existing lead the action is **Reassess fit**, not misleading first-time qualification wording.
- Reassessment navigates to the lead's **Qualification** tab, focuses/highlights the returned assessment and reports the score through the success toast. Keep owner, stage, follow-up and past assessments intact.
- Customer qualification rules are the active versioned Sales discovery/customer profile. The example shown in this chat was **Vending ecosystem v2 (Active)**. Older versions were Ended/Disabled. This is sample state, not a permanent hard-coded profile name or ID.
- Keyword/segment matches and available contact/multiple-source evidence contribute to screening scores. A score is not independent verification or a probability of becoming a customer. Business Operational status, Sales stage and fit score mean different things.
- New inbound leads get no fabricated fit assessment. **Not assessed** is distinct from a failed assessment or score zero. A zero default pipeline priority must not be described as an assessed fit score.

### Appointment management: final design supersedes earlier iterations

- Appointment Types is integrated into the existing Administration Inbox workspace, alongside Messages and Appointments. Do not restore a separate top-level sidebar page merely for this list.
- Remove the redundant Inbox page title. In Appointment Types, **Add Type is on the Back button row**, aligned right. The Appointments tab does not need its redundant Manage Types link because the adjacent tab is already available.
- A type table row expands with a View Type action, and opens a **real type detail page**. Detail includes Overview, Appointments, Activity, top metrics, editable configuration, Save/Cancel/dirty-state handling, related upcoming/history appointments, and ID/created/updated footer.
- Type creation stays in a modal. From ordinary lead/detail appointment sections, **Manage Types is a blue text navigation link**. Inside the **Book Appointment modal**, Manage Types remains an in-context modal so booking context is retained.
- Reuse the same type fields in modal creation and detail editing; do not build competing form schemas.
- **Duration** and **Reminder Before** use NumberInputWithUnit with a separated **minutes** suffix; do not include “(Minutes)” in their labels.
- Both fields can be cleared completely with Backspace and restored as blank in drafts. Validate on Save; do not immediately coerce empty input to zero. Current implemented integer ranges remain duration **5–480**, reminder **1–10,080** minutes. The request to allow blank editing did not authorize zero/negative values or remove these limits.
- Code is generated uniquely from name when blank on creation. **Provider Event Type ID is not auto-provisioned**: use the actual provider event type, with matching duration. Current validation requires an event type ID before enabling a type. Code/provider remain immutable in the existing detail flow.
- Available For is a multi-select supporting Sales, Marketplace or both. Shared audience support is implemented; one type need not belong exclusively to one audience.
- Enabled for New Bookings has the shared help tooltip: disabled types stop new selections while preserving prior appointments/history. Enabled also depends on the provider being usable; an enabled UI flag is not proof of valid credentials.
- `503 {"detail":"Scheduling is not configured."}` is a backend configuration failure, not an empty availability result and not proof that an appointment was booked. Thirty minutes is a configured default, not a fixed application limit.

## Latest completed implementation: homepage demo → Sales intake

### Actual behavior

1. Homepage requires company, first/last name and work email before submitting. Backend also validates demo requests and company name; server enforcement cannot be bypassed by omitting the browser required attribute. This requirement is specific to Book Demo; general support contact requests may still omit company.
2. Existing public `/contact` rate limiting and captcha verification are retained. The frontend generates a submission UUID; retries of unchanged values reuse it during the current page session. Changed input gets a new identifier. This identifier is not currently persisted across a full page reload.
3. `sales/intake.py::intake_demo_inquiry` transactionally stores the ContactRequest and matches using normalized company name plus a current usable exact contact email tied to an active entity. Entity- and venue-owned contacts are considered. A domain or name alone is insufficient.
4. One unambiguous name/email match reuses the entity and existing SalesLead, or creates a lead if that entity has none. Existing lead stage, owner, primary contact, notes, score/segment and existing contact data are not overwritten. The service uses the existing business intake lock; it does not weaken the administrator guard on manual Sales commands.
5. If there are possible but insufficient/ambiguous, inactive or suppressed matches, retain the inquiry as **Needs matching review**, with no speculative merge or duplicate business/lead creation.
6. With no candidates, create a minimal BusinessEntity, unverified contact email, contact and New SalesLead. Country is now permitted to be blank on BusinessEntity. Do not fabricate a venue, address, coordinates, country, business verification, company size or fit assessment.
7. Linked inquiries append **Homepage demo inquiry received** to Sales activity and appear as **Homepage demo inquiry** source evidence, rather than falsely attributing it to Staff intake.
8. Retrying the same UUID/payload returns the saved inquiry without another lead/activity. Reusing it with different content is rejected. A genuinely new inquiry from the same known person can add a new history entry while reusing the lead.
9. Support notification uses the existing EmailDelivery deduplication. Notification failure does not roll back the saved inquiry/lead or force the user to lose their submission. Review-required notifications call out the matching issue.
10. The browser opens Cal.com only after the save succeeds. Failed saves retain the form and show validation/retry feedback. If saving succeeded but the embed failed, the direct Cal.com link is still available. Submission is guarded against double clicks.
11. The public response does not expose internal matching results or Sales lead IDs. Browser booking-success feedback is not used to update backend Sales stage.

### Files to start from

- `home_page/src/sections/RequestAccessForm.html`
- `home_page/assets/js/book-demo.js`
- `home_page/tests/book-demo-embed.test.js`
- `backend/support/api.py`, `schema.py`, `models.py`
- `backend/sales/intake.py`, `queries.py`, `lifecycle.py`, `models.py`
- `backend/app/admin/support.py`
- `backend/tests/support/contact_request_test.py`
- `vendistri/src/vend/administration/sales/SalesQualification.tsx`

Latest local migrations: `prospecting.0026_alter_businessentity_country_code` and `support.0003_contactrequest_sales_intake_reason_and_more`. Both were applied and migration/model drift checks passed in the implementation turn.

### Boundaries that must remain explicit

- Staff can see/filter the matching-review state in the existing backend ContactRequest admin. **There is not yet a purpose-built portal review-and-resolve workflow**, and the current support admin is read-only. Do not describe flagged cases as automatically resolved or automatically entered in the Sales pipeline.
- Missing data is not locked into invented defaults and can be supplied later at the data-model level. **Verify/complete the actual portal edit and assessment path for entity-only inbound leads** before promising that every missing company/address field can already be edited in the current lead page. The current discovery qualification journey is venue oriented.
- Matching is deliberately conservative, not universal entity resolution. Alternate names, shared emails, new contacts at an existing company, or opportunity-only contacts can require further review. Do not silently broaden matching to domain/name only.
- Homepage inquiry UUID-to-booking correlation is not implemented yet. The existing homepage embed uses `mohamedvendistri/15min`; a working embed is not proof the backend appointment provider is configured.
- The final code change was local. It was not deployed, and no live inquiry email or provider booking was sent as validation.

## Immediate next work, in order

### 1. Complete homepage confirmation → appointment → Sales history

Inspect `backend/appointments/services.py::process_calcom_webhook`, provider adapter, appointment models/lifecycle, and the homepage embed before designing anything new.

- Establish an opaque server-recognized correlation between the saved inquiry and provider booking. Do not accept arbitrary client Sales lead IDs or trust the browser success callback as booking authority.
- Use verified signed Cal.com events, the configured provider event type, stable booking UID and existing Appointment/Event identity. Validate the inquiry/type/attendee relationship. An unmatched or review-required inquiry needs durable review/recovery, not a guessed link or lost booking.
- Attach the confirmed appointment to the existing/new Sales lead once, preserving discovery calls, activities, owner and assessment history.
- Change to Demo scheduled only where the domain transition makes sense. Do not regress Trial/Customer or silently reopen Lost; define and test these rules through existing lifecycle code. Inquiry submission alone never means Demo scheduled.
- Preserve existing handling of duplicate/out-of-order events, early webhooks, replacement booking UIDs, cancellation/reschedule and terminal outcomes. Make replay/reconciliation safe after deployment or temporary failure.
- Acceptance: new inbound business and previously contacted discovered business each produce one inquiry/lead/confirmed appointment with the right history; retries do not duplicate; invalid signatures cannot change records; ambiguous cases are visible; cancel/reschedule stay connected.

### 2. Make intake review and completion operational

- Provide a reviewed, authorized way to resolve retained ambiguous inquiries to the correct existing or new entity/lead, with audit history and no duplicate contact creation.
- Confirm how staff fill missing company/country/address/contact information and explicitly assess entity-only inbound leads. Reuse existing editable-detail and evidence patterns; do not fake a BusinessVenue just to satisfy a scoring UI.
- Keep original submitted evidence, current working data and later assessments distinct. Preserve suppression and contact revision rules.

### 3. Repair scheduler composition before relying on automation

**Unfixed finding:** `backend/conf/bg_tasks.yaml` defines a broad schedule (26 entries at the session audit), but `backend/src/settings.py` later assigns a fresh `CELERY_BEAT_SCHEDULE` containing three Marketplace tasks, then adds mailbox sync. The recorded effective runtime had only four tasks. Discovery dispatch, appointment reminders, outreach and other configured jobs can therefore be absent.

The assignment is still present in source at this handoff. Repair the composition using the established configuration mechanism, inspect duplicate task names/cadences, and add a focused effective-settings regression. Do not simply start Beat/workers: they can process existing queues and trigger external work. Inspect pending jobs and activation settings first. Scheduler repair itself does not authorize campaign sends.

### 4. Configure selected providers, then run live acceptance

The user asked whether getting API keys is next. Answer: partly; finish the connection/configuration gaps and obtain the credentials needed for the chosen providers. Do not imply every provider is mandatory or that “government” is a single supported API.

| Integration | Configuration / setup | Recorded local state and remaining work |
| --- | --- | --- |
| Google Places discovery | `GOOGLE_PLACES_API_KEY`; enable the required Places service and intended billing/restrictions | Adapter exists. Session audit found a test placeholder, not verified live credentials. |
| Yelp discovery | `YELP_API_KEY`; provider access/limits and retention rules | Adapter exists; recorded key was a test placeholder. |
| Foursquare discovery | `FOURSQUARE_API_KEY`; appropriate API product/access | Adapter exists; recorded key was a test placeholder. |
| Government/registry sources | Choose the actual jurisdiction/dataset and implement/verify its adapter and terms | Capability concepts exist; no generic government discovery adapter was found. A key alone does not implement it. |
| Cal.com backend | `CALCOM_API_KEY`, `CALCOM_WEBHOOK_SECRET`, intended event type IDs, signed webhook URL; optional `CALCOM_API_URL` | Key/secret were absent in the local audit. Homepage embed already exists independently. Verify hosts, availability, durations, timezone, invitee links and reminders. |
| Google connected Inbox | `MAIL_GOOGLE_CLIENT_ID`, `MAIL_GOOGLE_CLIENT_SECRET`, registered OAuth redirect, Gmail API/consent | Absent at audit; no connected mailbox records. Existing service-account sending does not satisfy this. |
| Microsoft connected Inbox | `MAIL_MICROSOFT_CLIENT_ID`, `MAIL_MICROSOFT_CLIENT_SECRET`, app registration/consent/redirect | Absent at audit. Current integration connects the signed-in mailbox; arbitrary shared mailbox selection is not implemented. |
| Shared mailbox setup | `MAIL_OAUTH_REDIRECT_URI`, `AWS_KMS_TELEMETRY_CONFIG_KEY_ID` and required KMS permissions, private attachment storage, API/worker/Beat deployment | Redirect and KMS setting were absent at audit. Run `manage.py check_mailbox_setup`; it reports configuration without revealing secrets or sending mail. |
| Existing Vendistri service email | Existing `GMAIL_SERVICE_ACCOUNT`, `EMAIL_ID`, Gmail delegation | Configured file/sender were present at audit; not a real-send acceptance result and not Google Inbox OAuth. |
| Public form protection | Existing Turnstile site/server configuration and token lifecycle | Preserve captcha; do not weaken it to make demo intake or tests work. |

These environment findings are dated observations, not a claim that credentials cannot have changed. Recheck presence/configuration without printing values. Store secrets only through the established backend/deployment configuration. Real email sends, bookings, campaigns, payments and production deployment were not authorized just by requesting this handoff.

### 5. Release verification and later product work

- Use dedicated test accounts for authorized live Google/Microsoft connect, refresh, receive, reply, draft, attachment, delegation, disconnect, throttling and uncertain-send reconciliation.
- Verify Cal.com real booking/reschedule/cancel/outcomes/reminders, webhook signatures/replay, availability and DST boundaries. Do not blindly retry an uncertain provider write.
- Run PostgreSQL concurrency/locking acceptance, migrations in each target environment, worker/queue health, private media/storage/CSP and shared Marketplace artifact checks.
- Complete authenticated cross-surface Marketplace purchase → entitlement → Growth → task/visit → conversion and refund/revocation checks. Mock browser fixtures are not authenticated release acceptance.
- Retain future scope: public venue-request intake; fuller Support triage/tickets if desired; approved connected-mailbox campaign automation and cross-channel reply/bounce/booking/conversion stop rules; provider push updates; Sales weekly/monthly reporting; administration-scoped Sales task ownership; native iOS/Android lead-task parity; optional in-house scheduling.
- Do not present current pipeline shares or assessment score comparisons as period-over-period growth/conversion reporting.

## Existing platform contracts not to undo

- Backend owns Marketplace sellability, qualification tier, publication, quotes, pricing, subscriber/allowance eligibility, reservations, claims/remedies and financial totals. Products define tiers/pricing; opportunities are inventory.
- Researched requires affirmative eligible evidence; failed higher-tier candidates are not automatically sellable. Publication is published/unpublished; publishability review is separate; Held belongs to discovery demand and never reserves inventory.
- Versioned prices/policies and accepted purchase snapshots are immutable. Subscriber discounts and allowance issuance differ; allowance grants require a successful subscription charge. Keep currencies grouped and cash/credit/points distinct.
- Public previews do not expose exact addresses, contacts, private evidence or precise coordinates. Public maps use the canonical approximate areas; exact data/media requires authorized entitlement. One Marketplace artifact serves public and secure hosts.
- Appointment Ready means verified venue interest and readiness for follow-up, not guaranteed placement or a necessarily booked meeting. The existing central 60-day validity, unpublish-on-apply, explicit republication and purchase-acceptance boundary remain authoritative. Later date expiry alone does not revoke an accepted purchaser's rights or generate an expiry email.
- Growth tasks keep entitlement/organization/assignment permissions. Field tasks route; remote tasks do not. Do not fabricate machines or customer Growth leads for platform Sales. Provider reschedules/cancellations must preserve started/completed work and expose synchronization issues.
- Inbox mailbox scope/delegation is independent from linked-record access. Keep private message bodies/attachments out of general activity projections. Provider acceptance does not prove delivery; uncertain sends reconcile without automatic resend.
- Realtime invalidates authoritative resources; it is not a second database. Preserve private scope, cache partitioning, stale-response rejection and draft stability.
- Follow the existing [claim remedy contract](marketplace-claim-remedies.md), including retained corrections, idempotent compensation, refund status and entitlement consequences.

## Source map for continuation

| Area | Primary owners |
| --- | --- |
| Sales domain | `backend/sales/{models,lifecycle,intake,scoring,queries,responses,api}.py`; `backend/prospecting/` |
| Sales UI | `vendistri/src/vend/administration/sales/` — LeadDetailPage, LeadActions, LeadContacts, Qualification, SourceEvidence, DiscoveryPage, Overview widgets, Routes tests |
| Appointment domain | `backend/appointments/{models,management,services,lifecycle,queries,task_link,api,tasks}.py`; `providers/calcom.py` |
| Appointment UI | `vendistri/src/vend/appointments/` — AppointmentBooking, AppointmentControls, LeadAppointments, AppointmentTypesManager, AppointmentTypeModal, AppointmentTypeFields, AppointmentTypeDetailPage, AdministrationAppointments |
| Combined Inbox | `vendistri/src/vend/communications/InboxPage.tsx`, MailComposer, RecordInboxLink; `backend/communications/` |
| Public demo intake | `home_page/assets/js/book-demo.js`, `src/sections/RequestAccessForm.html`; `backend/support/`; `backend/sales/intake.py` |
| Shared UI | Existing detail headers/footers, InfoRow, ExpandableDataTable, SummaryMetric, NumberInputWithUnit, ModalShell, ConfirmModal, NotesField, edit/draft guards, action feedback, timezone utilities; canonical `ui` / `@vendistri/ui` |
| Workers/configuration | `backend/conf/bg_tasks.yaml`, `backend/src/settings.py`, existing worker scripts and mailbox setup runbook |

Example records from the screenshots, for local navigation only: Sales lead `6e890723-62f7-4d3f-8dbd-de4f0d8b49c8`; prospect venue `2662fd70-3fa4-559c-a97b-68610a23f0b6`; profile `6e465b6c-175c-44e2-9237-c6209ace929d`. They are not production identifiers or fixed test dependencies. Qualification is `?tab=qualification`; combined type list is `/administration/inbox?view=types`.

## Verification record and working-tree cautions

Recorded completed runs from this chat; do not add these together as disjoint coverage or claim they were all rerun for this document:

- Broad Sales/Inbox/appointments follow-up: 443 frontend tests across 70 suites and 275 backend tests; portal production build passed. Mocked real-component Chromium checks at 320, 390, 768 and 1440 widths included header/contact layout, navigation, draft guards and action feedback.
- Blank appointment minutes change: 59 focused tests, TypeScript and scoped lint passed; a mocked Chromium check exercised actual Backspace at phone width.
- Latest inbound intake: 57 backend Sales/support/intake/scoring tests passed; final 13 support tests reran after the final targeted edits. 82 Sales route tests passed; TypeScript passed. Homepage full suite passed 175 tests before the last added validation-feedback regression, then the final 10 demo/captcha tests passed. Local homepage build passed.
- Latest migrations were applied, `migrate --check` passed, and `makemigrations --check --dry-run` reported no changes. Recheck after future development; old migration ceilings are not deployment truth.
- Existing warnings included Sales asynchronous React `act` warnings, Browserslist freshness, and earlier unrelated portal lint/bundle warnings. Passing focused suites do not certify every file or production performance.
- No live provider booking, inquiry email, campaign, payment or production deployment was performed as validation. Test provider calls and browser fixtures were mocked. PostgreSQL concurrency/live providers remain unverified.

Workspace is `/Users/mohamedkatary/pro-claws`, with nested repositories/worktrees (`backend`, `vendistri`, `home_page`, `marketplace`, shared `ui`, native projects and others). There are extensive pre-existing modified and untracked files. **Do not reset, bulk-stage, clean, rewrite or discard unrelated work.** Inspect status/diffs per repository. Many source files/migrations are uncommitted/untracked; filesystem state is important.

Useful scoped commands (run from the relevant directory):

```sh
# backend
.venv/bin/python manage.py test tests.support.contact_request_test tests.sales.intake_test tests.sales.api_test tests.sales.scoring_test --keepdb --noinput
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py migrate --check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py check_mailbox_setup

# home_page
npm test
npm run build:local

# vendistri
node node_modules/typescript/bin/tsc --noEmit
CI=true npm test -- --watch=false --runInBand --runTestsByPath src/vend/administration/sales/SalesRoutes.test.tsx
```

Run appointment lifecycle/provider/API suites when changing booking correlation; select checks appropriate to the affected slice. Test accounts and fixtures must not send real external communications accidentally. Previous browser fixture files in `/tmp` are disposable and may not survive; recreate from real components if needed rather than treating them as repository artifacts.

## Separate unresolved accounting follow-up

The September 7 handoff records a local commission-completion fix and an unrepaired production task `2756204e-e1b1-4e76-aade-1cba8aee3ab8`. Manual zero was overwritten by calculated commission on completion; linked accounting records require a reviewed correction plan. The historical investigation did **not** prove an actual check was delivered. This chat did not deploy or repair it. Re-audit current deployment/records before any action, keep it separate from Sales intake, and never directly set a production commission column to zero as a shortcut.

For any user/organization deletion, first read `backend/runbooks/safe_user_delete.md` and follow its ownership checks. No deletion or production accounting action is authorized by this handoff.

## Suggested opening message for the next chat

Read `/Users/mohamedkatary/pro-claws/AGENTS.md` and `/Users/mohamedkatary/pro-claws/docs/session-handoff-2026-09-17.md`, then the linked notes as needed. Inspect the current dirty working trees and preserve unrelated changes. Continue from the implemented homepage demo-to-Sales intake: company is required, unknown information stays unknown, new fit is Not assessed, and reliable matches preserve existing leads/history. Next implement trusted Cal.com confirmation correlation and appointment/stage linking through the existing lifecycle, with replay, matching and permission tests. Preserve the agreed UI/draft/loading/feedback patterns. Keep ambiguous intake resolution, missing-business-data editing, the Celery Beat override, provider setup and live acceptance visible as remaining work. Do not rebuild completed features or treat historical test results as fresh verification. Do not send live email/bookings/campaigns or alter production records without explicit authorization.
