Paste the following into the next session. It replaces every earlier Marketplace synthesis and reflects work completed through August 25, 2026.

---

# Marketplace Administration — Current Engineering and Product Handoff

## 1. Objective and current position

We are continuing Marketplace Administration in:

```text
/Users/mohamedkatary/pro-claws
```

Primary applications:

```text
backend/
vendistri/
```

The following Marketplace areas are now substantial working implementations:

- Catalog and Product detail
- Immutable pricing versions and pricing-version sales
- Claims list, Claim detail, remedies, refunds, corrections, and replacements
- Marketplace-wide Opportunities list
- Canonical Opportunity detail with Overview, Evidence, Commerce, Claims, and Activity
- Opportunity review, verification, publish, withdraw, and audit flows
- Operational and Financial Opportunity views
- Activity tables and audit expansion
- Allowance and Discovery backend foundations
- Deterministic development Marketplace data

Catalog, Claims, and Opportunities are the most-developed top-level tabs. Discovery is the recommended next implementation. Allowances follows Discovery. Finish top-level Activity consistency and Overview after their underlying systems are complete.

## 2. Worktree warning

Both backend and frontend worktrees contain extensive existing changes and untracked Marketplace files belonging to ongoing work.

Do not:

- Reset or clean either worktree.
- Delete untracked files.
- Revert changes you did not create.
- Mass-format unrelated code.
- Assume Marketplace files are tracked by Git.
- Treat unrelated dirty files as part of the current task.

Inspect exact files before editing and preserve unrelated work.

## 3. Applied local migrations

Current relevant local migrations are applied through:

```text
marketplace.0020_marketplaceleadclaim_corrected_information
prospecting.0017_placementopportunity_marketplace_administration_notes
prospecting.0018_placementopportunity_verified_by
```

If a migration is added, apply it locally:

```bash
cd /Users/mohamedkatary/pro-claws/backend
proclaws_be_env/bin/python manage.py migrate
```

Do not leave local Marketplace/Prospecting migrations unapplied.

## 4. Non-negotiable engineering rules

### Backend authority

The backend owns lifecycle state, publication, reservations, checkout, pricing, financial snapshots, claims, remedies, allowances, verification, blockers, and audit history. The frontend must not reconstruct authoritative state or financial truth from mutable display values.

### Financial integrity

- Use integer cents where required by existing contracts.
- Pricing versions and purchase snapshots are immutable.
- Acquired financial values come from purchase/order-line snapshots.
- Current listing values must never rewrite historical purchase values.
- Keep currencies separate when aggregation spans currencies.
- Never calculate refunds or credits from client-supplied totals.

### Performance

- Server-side search, filtering, sorting, pagination, and aggregates.
- Use server `totalCount`, never `items.length`, for filtered table counts.
- Avoid N+1 requests.
- Preserve data during background refresh.
- Use request deduplication and stale-response protection.
- Realtime signals invalidate; authoritative HTTP reload supplies state.
- Loading counts use a small skeleton, never flash `(0)`.

### Security

- Preserve Administration authorization.
- Validate UUIDs and schemas.
- Do not expose purchased/private lead information publicly.
- Replaced/revoked entitlements retain history but lose sensitive access.
- Never weaken production validation to accommodate development data.

### Reuse

Search for existing components before creating new ones. Stable behaviors must have one source of truth: status presentation, money, reconciliation, copy controls, filters, expandable tables, sorting, modals, warnings, dropdowns, tooltips, date ranges, skeletons, and metadata footers.

Never use a native browser select when the application has a custom dropdown.

## 5. Established UI language

### Metrics, search, and filters

Match the Catalog and Organization Expense Overview patterns:

- Top-level all-time metrics are independent of table filters unless explicitly labeled otherwise.
- Search is left aligned.
- Filters are ordered coherently to the right on desktop and responsive on mobile.
- Date filters use the shared custom date-range selector, including Custom.
- Status/category summaries sit between filters and the table where appropriate.
- Selected metrics/summary states use the established colored highlight treatment.
- Table view toggles use the Expenses/Merchants segmented-control style.
- Saved filter preferences follow the Administration preference mechanism and clear through the same sign-out cleanup path.

### Tables

- Headers remain visible during loading, empty, error, and refresh states.
- Skeletons preserve final geometry.
- Row matches use the shared search highlighter.
- Expanded-row `View …` actions stay at the upper-right of expanded content.
- Mobile status belongs at the right edge of the row.
- IDs, addresses, and immutable references use shared copy controls.
- Responsive layouts preserve information parity.

### Tooltips

Pinned/clicked tooltips must remain open while users select and copy tooltip text. Hover-leave behavior must not close an actively pinned tooltip during selection.

### Confirmation modals

- Use shared modal structure and compact sizing.
- Titles use correct title capitalization, e.g. `Verify Marketplace Opportunity`.
- Validation remains inside the open modal.
- Permanent consequences are explicit.

## 6. Canonical Opportunity detail

There is one reusable Opportunity detail page. All sources navigate to it:

- Product Inventory
- Pricing-version sales
- Marketplace Opportunities
- Activity
- Claims
- Future Discovery results

Do not create source-specific Opportunity detail implementations.

Tabs remain:

```text
Overview
Evidence
Commerce
Claims
Activity
```

The header, statuses, actions, warning/review block, and metadata footer remain consistent across tabs. Review warnings appear directly below the tab selector on every tab.

### Overview

Stable operational fields include:

- Tier
- Publication
- Inventory
- Verification timestamp
- Verified by: administrator name and email when available
- Net cash
- Public price
- Subscriber price
- Subscriber discount
- Allowance eligibility with colored dot
- Point cost
- Allowance coverage value
- Pricing version
- Effective period
- Venue, venue type, area, address with copy
- Territory, timezone, categories

Venue/location data follows a four-column desktop grid.

Marketplace Description and Administration Notes share one desktop row, half width each, and stack responsively.

Marketplace Description help text:

```text
Shown to Marketplace purchasers when this opportunity is published.
```

Administration Notes help text:

```text
For internal administration use only. These notes are not visible to purchasers or other Marketplace users.
```

Administration Notes exist for all opportunities and are audited.

For acquired Opportunities, Marketplace Description is not an editable post-sale notes field. Show the immutable Description at Acquisition. Legacy acquisitions without a captured snapshot explicitly state that the acquisition snapshot is unavailable. Do not render read-only historical copy as an input.

### Evidence

Evidence includes:

- Category and eligibility state
- Assessment tier
- Suitability, Confidence, and Sales Readiness percentages
- Rule version, assessed timestamp, explanation
- Three scoring-breakdown groups
- Total score at each group’s upper right

Show the canonical signal names consistently. A signal only receives a positive weight when it was hit. Supplemental remainder is shown as `Additional Evidence` only when its score is greater than zero; do not invent a zero-value row. Acquired records distinguish `Eligible at acquisition` from current actionable eligibility.

### Commerce

Commerce deliberately preserves the Purchase Details grid for every lifecycle state, including available listings. Unsold values remain `—`; do not remove fields based on state.

Section order:

```text
Purchase Details
Listing Terms
```

Use title capitalization and compact spacing. A separator distinguishes the sections.

Purchase Details includes State, Product, Organization, Reservation Expires, Gross, Discount, Credit, Allowance, Cash Charged, Refunded Cash, Net Cash, and Acquired.

Listing Terms includes Public Price, Subscriber Price, Subscriber Discount, Allowance Eligibility, Point Cost, Allowance Coverage Value, Pricing Version, and Effective Period.

Acquired reconciliation uses the shared snapshot-based Reconciliation component.

### Claims and Activity

Both use the shared expandable-table language. Activity must refresh immediately after verification, review-field updates, publish, and withdraw—no refocus or browser refresh should be required.

## 7. Opportunity review and verification workflow

`Needs Review` is a reusable blocker/action system, not a decorative warning.

Current blocker examples:

- Opportunity requires verification.
- Complex venues require a specific opportunity area.
- Opportunity is reserved by an active checkout.
- Other backend publication blockers must remain explicit.

Rules:

1. The backend computes blockers and actionability.
2. The warning block appears immediately under the tabs on every Opportunity tab.
3. Each actionable blocker has a specific action at the warning header’s right edge, e.g. `Verify Opportunity` or `Add Area`.
4. The top action may show `Resolve Review (N)` and must open the appropriate resolution flow.
5. Warning content uses compact spacing; do not leave a large gap between heading/action and blocker text.
6. Publish remains backend-authoritative and cannot bypass blockers.

Verification captures:

- Method: Human review, Phone, Email, Provider, or Inbound confirmation
- Acting administrator
- Timestamp
- Optional internal evidence/note

Successful verification:

- Stores `last_verified_at` and `verified_by`.
- Reruns assessment when required.
- Clears the verification blocker when valid.
- Refreshes Opportunity and Activity immediately.
- Produces an expandable Activity entry containing method, evidence, and verified timestamp.

Add Area/title review actions update only supported review fields, rerun blocker evaluation, and produce before/after audit history.

Publish and Withdraw are confirmed actions. Withdraw requires a reason retained in Activity. Re-publish after withdrawal must preserve the complete audit sequence.

## 8. Opportunity list

### Operational view

Top metrics:

- Total Inventory
- Available
- Reserved
- Acquired
- Needs Review

Metrics show count and value. Current-price amounts are potential listing value; Acquired uses realized snapshot revenue. The explanatory tooltip must preserve this distinction.

Operational columns include Opportunity with server `totalCount`, Tier sorting by canonical tier order, Territory, Publication, Inventory, Verification, and Updated.

Expanded data includes Address with copy, Area, Review, Categories, Blockers, and View Opportunity.

### Financial view

The Operational/Financial toggle sits at the right end of the Published/Unpublished summary row, including mobile.

Financial view has the shared date-range control and uses acquired snapshot data. Columns include Opportunity, Organization, Acquired, Gross, Discount, Funding, Refunded, and Net Cash.

`Filtered totals` is a distinct totals row beneath headers, sourced from server aggregates, not the loaded page. Funding breakdown must remain fully readable and not be uselessly truncated. Mobile totals preserve compact spacing.

Metric clicks respect table mode. A metric that only makes sense operationally, such as Needs Review, switches to Operational before applying its filter.

### Reservations

Reserved state is an active checkout, not automatically a data-quality review failure. Where reservation context is shown, use the shared reservation lifecycle data: started time, expiration/countdown while active, and ended/expired time in history. Preserve auditability rather than inferring times client-side.

## 9. Marketplace search contract

Every Marketplace table search includes the table’s own primary record ID and visibly highlights matching displayed values.

Implemented coverage:

### Opportunities

Searches server-side across:

- Exact Opportunity UUID
- Title, description, and area
- Venue name, type, address, locality, administrative area, and country
- Category name/code
- Verified-by administrator name/email
- Tier and rendered blocker/detail context on the frontend

Rows display and highlight Opportunity ID, title, venue, tier, territory, address, area, categories, and blockers where applicable on desktop/mobile.

### Catalog

Searches Product ID, product name, and SKU. Matching values are displayed/highlighted. Placeholder communicates Product/SKU/ID support.

### Claims

Search includes Claim ID and existing related Claim/organization/purchaser/Opportunity fields. Claim ID and visible contextual matches are highlighted on desktop/mobile.

### Activity

Search includes exact Activity Event ID plus action, summary, actor, email, source, and related record context. Event ID is visible/highlighted in table results.

### Pricing sales

Search includes Opportunity ID, Order ID, Order-Line ID, and Pricing-Rule ID plus existing purchaser/organization context. Visible IDs use highlighting and copy controls where appropriate.

### Public/replacement inventory

Search supports exact Opportunity UUID plus title, description, area, venue/location, and category fields without exposing protected data.

Backend UUID matching is exact. Text matching remains case-insensitive. Search stays bounded, server-paginated, and distinct where joins could duplicate rows.

## 10. Counts, filters, and preferences

- Table header counts use the backend’s filtered `totalCount`.
- Counts represent all matches, not only the loaded page.
- While a filter/search request is loading, show the count skeleton instead of `(0)`.
- Top metrics remain global/all-time and do not change with table filters unless a metric explicitly states filtered scope.
- Marketplace filters use the same saved-preference and sign-out cleanup mechanism as other Administration tables.

## 11. Catalog, pricing, claims, remedies, and entitlements

Preserve all prior established behavior:

- Pricing versions are immutable.
- Pricing sales exclude zero-dollar remedial replacement order lines lacking a pricing rule.
- Financial history uses order-line snapshots.
- Claims support Replacement Lead, Marketplace Credit, Payment Refund, Subscriber Allowance Restoration, and Corrected Information across every layer.
- Remedy availability is backend-authoritative and explains why unavailable remedies cannot execute.
- Replacement uses the reusable searchable Opportunity picker; administrators never paste UUIDs.
- Corrected Information keeps original access active and must differ from the acquisition snapshot.
- Replacement/revocation removes sensitive original access while retaining history.
- Resolved Claims permanently display remedy-specific resolution data, reviewer name/email, timestamps, notes, and references.
- Missing development evidence is warned about but does not automatically block approval.
- Claim response schemas must retain `resolution`.
- Administrative Opportunity detail explicitly supports acquired Opportunities without broadening ordinary review queries.

## 12. Reusable components/sources of truth

Important shared pieces include:

```text
MarketplaceSearchFilterRow
MarketplaceOpportunityTable
MarketplaceOpportunityFilters
MarketplaceOpportunitySummary
Marketplace Opportunity detail shell
Marketplace Activity table
Marketplace review warning/action block
PricingSalesSummary
PricingSalesTable
Reconciliation
Replacement Opportunity picker
Claim remedy dropdown
ExpandableDataTable
TableHeaderCount
SummaryMetric
StatusFilterSummary
StatusPill and status dots
CopyButton
custom DateRangeSelect
custom dropdown/select controls
shared confirmation modal
shared tooltip
DetailMetadataFooter
```

Do not independently recreate statuses, dropdowns, warning blocks, table actions, date ranges, tooltip behavior, or skeleton geometry.

## 13. Navigation

Navigation is deterministic, not generic history-based:

```text
Pricing sales -> Product Pricing
Product detail -> Catalog
Opportunity detail -> explicit origin/list context
Claim detail -> Claims or originating Opportunity Claims
Allowance detail -> Allowances
Marketplace top level -> Administration root
```

Preserve origin query/filter context. Investigation/history links open a new tab where already established.

## 14. Development data

```bash
cd /Users/mohamedkatary/pro-claws/backend
proclaws_be_env/bin/python manage.py migrate
proclaws_be_env/bin/python manage.py seed_marketplace_development_data --confirm-development
```

Cleanup:

```bash
proclaws_be_env/bin/python manage.py seed_marketplace_development_data --clear
```

Development records intentionally exercise available, reserved, acquired, review-blocked, claims, remedies, replacements, funding mixes, refunds, activity, long content, and responsive layouts. Never relax production validation for seed data.

## 15. Latest verification baseline

The latest focused search work passed:

```text
Frontend TypeScript: passed
Frontend Marketplace suites: 5 suites, 30 tests passed
Backend publishing/sales/activity: 33 tests passed
Django system check: no issues
```

Frontend route tests emit existing missing-CSRF-cookie console noise in the test environment; it does not fail tests.

Earlier broader Marketplace audits also passed their focused suites. Do not claim manual browser verification solely from automated tests.

## 16. Recommended next work: Discovery

Discovery is next because it is upstream of Opportunities:

```text
Catalog defines products
Discovery finds/evaluates inventory
Opportunities review/publish/sell it
Claims remediate sold inventory
Activity audits all transitions
```

Implement Discovery incrementally:

1. Inspect existing Discovery models, APIs, migrations, budgets, policies, demand records, and development data before designing UI.
2. Add global metrics using the established top metric bar.
3. Add server search—including Discovery Search/Run/Candidate IDs—filters, custom date range, saved preferences, filtered `totalCount`, skeletons, and visible highlighting.
4. Build a compact Discovery Searches/Runs table with operational statuses, provider/source, territory/category, results, accepted/rejected counts, cost/budget information where authoritative, timestamps, and expandable details.
5. Build canonical Discovery detail/run detail rather than duplicating per-entry views.
6. Show candidate evidence, scoring, duplicates, policy decisions, provider metadata, and failure/retry history.
7. Provide explicit review actions to accept/promote an eligible candidate into the canonical Opportunity flow, reject with reason, retry failed runs, or hold as supported by backend policy.
8. Make every transition auditable in Activity.
9. Keep provider calls bounded, idempotent, budget-aware, and backend-authoritative.
10. Add focused backend/frontend tests and manually check desktop/mobile.

After Discovery:

1. Allowances administration and audited corrections.
2. Top-level Activity consistency/polish.
3. Marketplace Overview last, using authoritative metrics from completed subsystems.

## 17. Next-session operating procedure

Before editing:

1. Read this handoff completely.
2. Inspect dirty worktrees and exact current files.
3. Inspect the live route and nearest existing reusable pattern.
4. Trace backend query/service/schema and frontend API/state/rendering together.
5. Make the smallest robust backend-authoritative change.
6. Preserve desktop/mobile parity, skeletons, highlighting, filters, and audit behavior.
7. Add proportional regression tests.
8. Run focused backend tests, frontend tests, and TypeScript.
9. Apply new migrations locally.
10. Manually verify changed routes when possible.

Do not perform a speculative rewrite. Continue from the established reusable Marketplace system.

---
