# Marketplace journey review — September 8, 2026

## Customer and administration flow

1. **Discovery:** saved searches and explicit sourcing requests aggregate into demand segments. Administration → Marketplace → Discovery exposes the demand queue, originating organizations/signals, run links, policy creation, pause/resume controls, and audit history. A missing inventory policy holds a request for review; it does not silently promise inventory. Provider budgets, cooldowns, and policy coverage still apply.
2. **Classification:** evidence supplies the automatic Researched / Qualified / Premium tier. Administration → Marketplace → Opportunities → an opportunity → Evidence now also provides **Review tier**. An active administrator can choose one of those tiers or restore automatic classification, with a required evidence/reason note. Existing assessments remain intact. Changing classification withdraws the listing, requiring review and republication at the new tier/price. Acquired and reserved opportunities are protected. Appointment Ready remains dependent on its separate appointment evidence.
3. **Publication:** existing publication blockers check current eligible evidence, verification, venue status, title, and specific area for complex venues. Public listing, tier filtering, ordering, quoting, and reservations share the effective classification. A manual tier does not bypass expired evidence or publication requirements. Internal review notes are returned only by administration responses.
4. **Search and updates:** the existing catalog uses debounced search, cancelable requests, scoped caching, paginated results, and lazy map loading. Websocket changes are coalesced in 100 ms bursts; revision/ETag catch-up handles reconnect and tab return. Healthy websocket connections do not use the 15-second fallback polling loop. Discovery-run changes now also refresh the customer sourcing view.
5. **Purchase:** existing quote confirmation, reservation exclusivity, payment idempotency, and fulfillment controls remain. Reservation creation and renewal now recheck the effective tier under the opportunity lock, preventing an earlier quote from purchasing a subsequently reclassified opportunity.
6. **Sourcing:** requests appear at `/growth/marketplace/my-opportunities?tab=sourcing`. The submitting user receives a queued acknowledgment and meaningful progress updates using the shared email template/delivery engine. Requests retain recipient and organization scope. Delivery rechecks current membership and status, deduplicates messages, retries failures, and links back to the sourcing tab. Discovery finishing is shown as review, not a guaranteed available listing.
7. **New matches:** existing match emails already used the shared email engine. Delivery now respects currently active notification preferences and active accounts; deduplication includes organization. A republished opportunity with a changed tier updates existing match links to the current product.
8. **Saved searches:** a separate row is maintained for each tier and geographic scope. The previously identical-looking rows now expose the tier. Active/Paused use green/amber status dots; paused searches show notifications as paused. Existing Edit/Pause/Resume controls remain. Help text explains matching versus sourcing. Extra section/nested-card padding is removed.

## Correctness and scale fixes

- Customer sourcing and new-match tables previously fetched only the first 100 and 50 records. The customer hub now uses an organization-scoped, searchable, server-paginated engagement endpoint, 25 records per page.
- The legacy saved-search list no longer silently drops records after 100. The customer hub uses bounded pages; catalog request deduplication can inspect the complete preference list.
- Inactive customer tabs no longer fetch full feeds, and feed pagination/search does not refetch acquired-record pages.
- Periodic inventory/preference evaluation now orders by a separate evaluation timestamp, explicitly putting unevaluated records first on PostgreSQL as well as SQLite. A bounded batch advances instead of starving records beyond the first 100.
- Typed engagement response schemas preserve numeric map coordinates and avoid accidentally exposing internal demand review reasons.
- Previously implemented organization-deletion protections and global session-switch boundaries are retained; this work does not delete accounts, clear queues, or relist acquired inventory.

## Validation and operational limits

- Backend regression suites cover discovery, publication, classification, catalog, lifecycle/checkout, preferences, realtime, API contracts, pagination beyond 100 records, email deduplication, and organization isolation.
- Frontend suites cover search, payment, cart, realtime, customer records, and administration tier review. A timing-sensitive embedded-card test now waits for the completed selection effect rather than merely the appearance of radio controls.
- Marketplace build and portal TypeScript checks passed. The built Marketplace artifact was copied into the portal's served assets.
- Served stylesheet fixtures checked at 320, 390, 768, and 1440 pixels: no added section/expanded-card padding; green/amber dots; no horizontal layout overflow. These checks do not represent an authenticated live purchase.
- Local migrations `marketplace.0033` and `prospecting.0022` applied; no pending migrations or model changes.
- No live charge, provider discovery request, or customer email was sent as validation. Email delivery was mocked.
- No local Celery worker was found. Background discovery and queued emails require the existing core worker (`backend/bg_tasks.sh`, queues `default,automation`) and scheduler; these were not started because doing so can process existing queued jobs. Production workers must be restarted to load the new task.
- This review does not establish a production latency guarantee or replace load testing with representative inventory and concurrent buyers.

## Customer hub and focus follow-up

- Session verification keeps the current layout and drafts visible. It silently blocks interaction until identity is verified; a confirmed mismatch conceals the old identity and uses the existing full session reset. Network failures use a compact bottom notice with Retry instead of a full-screen StatePanel.
- Acquired detail publishes its lead action to the portal's Back row, scoped by entitlement ID and cleared on unmount. Standalone detail has the same top-row layout.
- Saved-search editing puts Save changes and Cancel before the inputs. The hub explains purchased opportunities, new matches, sourcing requests, and saved filters separately; View results opens the search again.
- Customer sourcing requests now have organization-owned state distinct from shared discovery work. Migration 0034 backfills historical customer and preference signals. Internal inventory signals do not create customer requests; ordinary browsing does not subscribe anyone to email.
- Customers can inspect progress, date, target quantity and request ID, browse listings, cancel their organization's request, and request again. Cancellation does not stop another organization's work, does not delete history, suppresses queued email updates, and is not reversed by periodic saved-search evaluation. Explicitly requesting again reopens the request.
- The email worker requirement documented above still applies. Validation uses mocked delivery; no live email or payment was sent.

## Maintainability audit

The review covered the customer application (`app`, `access`, `api`, `catalog`,
`cart`, `claims`, `components`, `config`, `continuation`, `entitlements`, `orders`,
`records`, `session`, `state`), backend Marketplace domain and API modules, and
the portal's Marketplace administration components/state. Shared billing, email,
Growth, session, realtime and UI code was checked where Marketplace depends on it.
The reusable owners are documented in `marketplace/README.md`.

Concrete changes:

- **Order queries:** the customer table was overriding the shared line prefetch,
  triggering extra preview/product/media queries. It now reuses
  `marketplace_orders()` and `marketplace_order_lines()`. Order responses resolve
  prefetched purchaser, charge and expense relationships and supply lead links in
  one serializer, without the table rebuilding those fields afterward.
- **Search:** customer engagement tables reuse the existing bounded word search
  function. Effective sourcing status is annotated by the scoped query using the
  same run-status mapping as display; a cancelled request cannot match an old
  held/running state merely because its shared discovery job still has that state.
  Out-of-range pages clamp consistently with other customer tables.
- **Sourcing commands:** cancel/resume live with the existing discovery service,
  leaving API handlers to authorize, call the command and serialize. Resumption
  reloads the demand and organization request together.
- **Customer boundary:** sourcing creation and the legacy search endpoint no
  longer return internal hold reasons or run/search IDs. Ordinary browsing reports
  no customer sourcing request unless one exists for that organization. Queued
  sourcing emails require a current, uncancelled organization request as well as
  current recipient membership.
- **Client boundary:** engagement page types are selected by their record kind;
  create/edit/resume/cancel responses use the same validators as reads. Numeric
  counts and cent amounts reject unsafe integers. Account-context envelopes are
  validated before destructuring. A context change blocks a mutation still waiting
  for CSRF setup and rejects responses belonging to the previous context.
- **Shared interactions:** checkout and order-history payment/cancellation actions
  share a synchronous in-flight guard and suppress callbacks after unmount. Backend
  idempotency and reservation locks remain authoritative. Customer hub links reuse
  the existing catalog URL serializer rather than reconstructing query strings in
  separate components.

Boundaries deliberately retained: domain-specific commerce services, the existing
resource loader/realtime connection, shared email delivery and shared UI primitives.
The three UI working directories are checkouts/submodules of one UI repository,
not three intended implementations. No generic mutation framework, alternate
payment engine, new production helper file, or replacement global store was added.

Validation includes malformed API responses, same-tick payment clicks, unmounts,
account changes during CSRF/response waits, status parity, tenant isolation,
pagination beyond 100 records, and query-count growth as records are added.
Production latency and concurrent PostgreSQL load have not been measured by these
local tests; this review cannot establish that all future changes are duplication-
free or that the entire project is maximally optimized.

Final audit checks passed: 299 backend Marketplace tests (SQLite test database),
546 customer application tests, and 160 portal administration tests. Marketplace
and portal TypeScript checks and the Marketplace production build passed. The
query-growth regressions confirm constant query counts for one versus ten orders
and one versus 25 sourcing requests. All eight built asset files match the portal
copy. `migrate --check` reports no pending local migrations and
`makemigrations --check --dry-run` reports no model changes.
