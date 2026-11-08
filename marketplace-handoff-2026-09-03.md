# Vendistri Marketplace handoff — September 3, 2026

> Continuation note (September 17): start with [the current session handoff](docs/session-handoff-2026-09-17.md). The policy baseline below remains useful, but its implementation gaps, test results and migration ceilings are historical and are superseded where later notes record completion.

## Executive summary

The original handoff is substantially out of date. Marketplace is no longer primarily an unfinished Administration Product Inventory project. The repository now has an end-to-end Marketplace domain spanning discovery demand, qualification, publication review, privacy-safe public inventory, personalized organization pricing, signed quotes, idempotent checkout, payment and fulfillment, entitlements, original-media access, claims, allowances, credits, activity, and Administration reporting.

There are three cooperating applications:

- `backend`: authoritative Marketplace policy, persistence, validation, security, queries, checkout, fulfillment, claims, discovery, reporting, media, and privacy.
- `vendistri`: the secure Vendistri host plus the full Marketplace Administration experience.
- `marketplace`: one host-neutral customer Marketplace artifact that runs in public and secure modes and is embedded by Vendistri as a custom element.

The backend remains the sole source of truth for sellability, tier, pricing, subscriber eligibility, allowance and credit allocation, reservations, claim policy, private data, totals, and remedies. Frontends render backend decisions and never reconstruct financial or eligibility policy.

## Current product and allowance model

The four canonical lead products remain:

| Product | Public | Subscriber | Allowance cost/current coverage |
|---|---:|---:|---|
| Researched Lead | $25.00 | $22.50 | 1 point / $22.50 |
| Qualified Lead | $75.00 | $67.50 | 3 points / $67.50 |
| Premium Lead | $125.00 | $112.50 | 3 points / $67.50 |
| Appointment Ready Lead | $250.00 | $225.00 | 3 points / $67.50 |

These are seeded policy values, not browser constants. Pricing rules and allowance policies are versioned. Orders, lines, grants, and entitlements preserve immutable snapshots.

Subscriber Marketplace pricing applies only to full organizations in `trial`, `active`, `grace`, or `exempt` subscription states. Allowance issuance is a separate policy: grants require a successful subscription charge. Entering a trial does not issue allowance points.

Lead-only and full organizations are distinct backend account modes. Both may use the secure Marketplace experience. Upgrade eligibility and the 14-day trial decision belong to the organization lifecycle backend; Marketplace and Growth data survive an upgrade.

## Opportunity tiers and Researched inventory

Researched opportunities now exist. They are not a fallback bucket for candidates that failed higher qualification.

An opportunity receives an eligible Researched assessment only when baseline safety/evidence requirements pass, including permitted venue type, complete address, coordinates, and recent verification. Qualified and Premium then require stronger thresholds. Effective Marketplace tier is selected in one backend eligibility module, with Appointment Ready highest, followed by Premium, Qualified, and Researched.

Development data now seeds Researched inventory explicitly, including available, reserved, acquired, and review examples. Product-scoped Researched inventory is therefore supported by the current checkout contract.

The invariant remains: weak, failed, duplicate, stale, closed, unsafe, or otherwise ineligible candidates must never become sellable merely because they failed a higher tier.

## Publication, review, Held, and checkout

Opportunity publication accepts only:

- `published`
- `unpublished`

Opportunity review/publishability is separate:

- `publishable`
- `blocked`

`held` belongs to Discovery demand. A held demand pauses sourcing because of Administration control, policy, or budget conditions. It does not publish, reserve, or hold an opportunity for checkout.

Checkout now has an explicit revalidation path. `create_lead_checkout` requotes and verifies the signed quote. The canonical sellability query rechecks publication, qualified opportunity state, venue merge/closure, required complex-venue area, title, verification, fresh eligible assessment, acquisition, active reservation, and selected tier. A stale or newly blocked opportunity is rejected even if it was published earlier.

One cart/order may contain multiple product tiers but only one currency. The backend produces all totals and allocations. Cash, credits, and allowances remain distinct; non-cash funding never creates a fake Stripe charge or payment-account expense.

## Backend implementation status

Implemented backend areas include:

- Public canonical product catalog.
- Public and personalized opportunity pages and detail.
- Server-side search, facets, sorting, cursor pagination, and privacy-normalized map bounds.
- Customer Discovery demand and combined search/demand endpoints.
- Organization Marketplace preferences.
- Signed public cart intents for public-to-secure continuation.
- Signed, expiring authoritative quotes.
- Idempotent checkout, reservations, cancellation, payment, and fulfillment.
- Order history and acquired-opportunity entitlements.
- Permission-checked original Marketplace media for active entitlements.
- Claims, backend eligibility, evidence requirements, Administration review, replacements, refunds, credit, and allowance restoration paths.
- Versioned allowance policies, charge-backed grants, balances, redemptions, adjustments, and ledgers.
- Immutable pricing rules plus pricing-rule and product-wide sales summaries and paginated order lines.
- Product Activity and global Marketplace Activity.
- Administration Marketplace overview, attention queue, operational health, and flow reporting.
- Discovery searches, runs, sources, observations, demand signals, demand controls, inventory policies, proposals, and activity.
- Opportunity review, verification, reassessment, publication/withdrawal, notes, editable review fields, and media management.
- Currency-grouped financial summaries. Monetary aggregates are arrays such as `{ currency, totalCents }`; currencies are never silently combined.
- Marketplace and Prospecting realtime invalidation plus scheduled `nextChangeAt` transitions.

The canonical privacy policy is in `backend/marketplace/privacy.py`: public coordinates are quantized to a 0.1-degree grid, public areas use an 8-mile radius, and map bounds are expanded to that public grid before internal filtering to reduce coordinate reconstruction risk.

## Administration Marketplace status

Marketplace Administration has these top-level areas:

- Overview
- Catalog
- Discovery
- Opportunities
- Claims
- Allowances
- Activity

Catalog product detail includes Overview, Pricing, Inventory, and Activity. Product Inventory now has authoritative scope and filtered summaries, server filtering/pagination, explicit table layouts, currency-grouped potential and acquired values, review state, reservation/evidence/pricing transition scheduling, and reusable opportunity components.

Pricing sales and Product Activity are implemented, not future placeholders. Administration also has global activity, claims review/detail, allowance policy/ledger views, Discovery detail surfaces, and operational Marketplace overview reporting.

Opportunity Administration includes a media manager. Uploaded media can be approved, represented, ordered, removed, and selected as cover. The generated approximate-area map is a synthetic permanent final gallery item: it is not persisted as uploaded media, cannot be reordered or removed, and cannot become the cover. Administration sees the exact operational map and the customer privacy preview side by side.

Discovery `held` help text appears only when the Held metric/filter is selected. It explains sourcing behavior and explicitly states that held demand does not reserve checkout inventory.

## Customer Marketplace status

The customer application is one React/TypeScript build deployed in two modes:

- Public: browsing, opportunity detail, cart composition, and signed continuation into secure Marketplace.
- Secure: organization context, personalized pricing, allowance/credit-aware checkout, orders, acquired opportunities, private entitlement detail, original media, and claims.

Current routes include catalog, opportunity detail, continuation, cart, orders, acquired opportunities, acquired-opportunity detail, and claims.

Access distinguishes public, missing session, missing organization, explicit organization selection, lead-only organization, and full organization. A remembered organization is accepted only if the authenticated context still returns it.

Catalog state has one URL-backed query model for product, search, territory, category, sort, cursor, view, and map bounds. Requests abort when superseded and stale responses cannot overwrite current state.

The list/map selector uses the shared segmented control. Map view uses server-filtered bounds and shows privacy-radius polygons without exact pins. Programmatic map fitting no longer updates URL bounds, and map data is retained during a viewport refresh so the canvas is not destroyed/recreated. This prevents the prior URL/API feedback loop and tile flicker.

Opportunity detail includes approved redacted media plus a generated privacy map as the permanent final slide. The detail map is interactive; users can pan and zoom while the geographic privacy circle remains anchored. Exact address, contacts, and approved original media are available only through an active purchased entitlement.

## Shared UI and session changes

`@vendistri/ui` now owns reusable primitives used by both Marketplace and Vendistri:

- `AreaMap`, circle geometry, bounds types, and miles-to-meters conversion.
- `SegmentedToggle` with an accessible group label.
- `InlineSearchInput` with Escape/clear behavior and restored focus.
- Existing buttons, selects, state panels, skeletons, tooltips, geography constants, and layout primitives.

The two checked-out shared-UI sources were kept byte-identical for map code. MapLibre is dynamically imported so the large map engine does not enter the initial Marketplace bundle.

The shared search-input CSS was corrected so the tooltip-wrapped clear × stays inside the field at the right edge across Expenses, Marketplace Administration, Organizations, Audit, and every other consumer.

Unrelated small Vendistri cleanup completed in this session: Today's Tasks now displays Time before Miles.

## Verification evidence from this session

- Customer Marketplace: 91 tests passed after map-loop fixes.
- Customer Marketplace strict TypeScript passed.
- Customer Marketplace production build passed; initial bundle remained about 94.43 kB gzip and MapLibre remained lazy.
- Shared UI checkouts: 11 and 10 tests passed respectively; builds and typechecks passed.
- Focused Marketplace backend/privacy/API/publishing suite: 49 tests passed.
- Django system check passed.
- Vendistri TypeScript passed after Administration/shared-UI changes.
- Focused Administration reorder tests passed.
- Diff checks passed in the touched repositories.

This is strong focused evidence, not a claim that every test in every repository has been run after all accumulated uncommitted work.

## Current operational state

No process was listening on port 5173 when this handoff was prepared. Marketplace Vite is stopped as requested. Start it manually from `marketplace` with `npm run dev` (or the secure-mode environment command documented in `marketplace/README.md`).

The worktrees contain extensive uncommitted changes, including changes that predate this session. Do not reset, discard, or bulk-stage unrelated work.

## Recommended next steps

### P0 — Complete and validate the remaining customer demand journey

The backend already supports organization preferences, Discovery demand, and combined search-plus-demand, but the current customer route set does not expose a complete demand/preferences experience. Design the smallest customer flow for insufficient inventory:

- Clearly distinguish zero current inventory from a failed request.
- Let an authenticated organization request sourcing using backend-supported territory/category/product inputs.
- Show the resulting demand state, including pending, scheduled, satisfied, and held.
- Never imply that held demand reserves inventory.
- Reuse the existing catalog query and backend demand contracts rather than creating parallel search state.

### P0 — Browser-level commerce and privacy verification

Run an end-to-end secure session covering:

- Lead-only and full organization selection.
- Public cart intent to secure continuation.
- Personalized subscriber/public pricing.
- Mixed-tier, single-currency quote and checkout.
- Allowance and credit allocation.
- Payment-pending recovery and fulfillment.
- Acquired entitlement, exact private data, and original media permissions.
- Claim submission and Administration review.
- Public/list/detail maps with no address or exact coordinate leakage.
- Map pan/zoom without repeated URL rewrites, remount flicker, or request storms.

### P1 — Close remaining Administration media/review test gaps

Add focused component coverage for the full opportunity media manager, especially zero uploaded media, permanent-last map behavior, exact/privacy comparison, save while the map is selected, and suppression/removal behavior. Re-run the broader Marketplace Administration suite.

### P1 — Full repository verification and migration audit

- Run the complete backend Marketplace test package, not only focused suites.
- Run the full Vendistri test suite and production build.
- Run all customer Marketplace tests/build again after subsequent work.
- Confirm migrations through Marketplace `0026` and Prospecting `0020` are applied in each target environment.
- Verify media/private-media storage and production web-server access rules.

### P2 — Realtime and expiry endurance testing

Exercise reconnect/focus recovery, burst coalescing, reservation expiry, evidence expiry, pricing transitions, and allowance-policy transitions. Verify that authoritative HTTP refreshes remain deduplicated and that stale pages cannot overwrite current query state.

### P2 — Production deployment integration

Validate that the same Marketplace artifact is served by public and secure hosts, nested routes fall back correctly, the secure Vendistri custom-element loader resolves the artifact, CSP allows the chosen basemap resources, and private original-media responses remain authenticated and `no-store`.

## Decisions not to reverse

1. Products are tier/pricing definitions; opportunities are inventory.
2. Researched requires explicit eligible evidence and is never a failure fallback.
3. Publication is published/unpublished; Held is Discovery demand only.
4. Review state is publishable/blocked and remains separate from publication.
5. Checkout requotes and revalidates canonical sellability.
6. Pricing and allowance policies are versioned; historical snapshots are immutable.
7. Subscriber pricing and allowance issuance are separate policies.
8. Allowances require a successful subscription charge.
9. Mixed tiers may share one order only when currency is singular.
10. Currency totals stay grouped.
11. Public data never includes exact addresses, contacts, evidence, or exact coordinates.
12. Privacy maps show circles without exact pins; exact maps remain operational/authorized views.
13. Claim eligibility and remedies come from the backend.
14. Realtime triggers authoritative reloads; it is not another database.
15. Server filtering, pagination, and summaries must not be recreated from partial browser data.
16. Keep the shared UI package as the source of reusable map, search, select, and segmented-control behavior.
