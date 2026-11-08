# Marketplace claim remedies

Implementation contract, September 9, 2026.

| Remedy | Live records and purchaser access | Compensation |
| --- | --- | --- |
| Corrected information | Selected contact remains visible as **Superseded**; its replacement is **Current**. Approved field corrections update the live opportunity or venue. Access stays active. | No financial compensation. |
| Replacement | Original access becomes **Replaced**. A new entitlement and Growth lead are created. The replacement link appears in claim and purchase details. | No additional charge. Search defaults to the same tier; the reviewer can include other tiers. The order line uses the selected tier's product. |
| Marketplace credit | Original access is revoked. | Defaults to the entire funded price after discount, including cash, credit, and allowance value. A reviewer may explicitly reduce this amount. No additional point or cash return. |
| Payment refund | Original access is revoked. The approval decision and payment processing status are separate. | Cash to the original payment method, previously spent credit as a new Marketplace credit grant, and consumed allowance points restored. Only confirmed cash refunds reduce order and expense totals. |
| Allowance restoration | Original access is revoked. | Consumed points restored; both the cash difference and previously spent credit are issued as Marketplace credit. |

Restored points retain the original grant expiration. Expired grants require an explicit future extension before approval, including before a payment refund is requested. Credit compensation uses the existing administrative-credit grant policy. Every compensation operation has a stable claim-based idempotency key. Replacement and credit remedies do not also return the funding components again.

## Correction history

`marketplace/corrections.py` owns the correction allowlist and the review form's field definitions. Supported fields include contact details; title, description and placement area; business name, address components, map coordinates, time zone and location type; and vending categories. Financial, ownership, publication and qualification controls cannot be changed through this payload.

The contact identifier must belong to this opportunity and identify a current contact. The replacement is a new record, and the predecessor is retained. Both are visible in customer contact tables. Superseded contacts are excluded from future acquisition snapshots and current Marketplace contact eligibility. Acquisition snapshots and original claim submissions are never rewritten. Corrections record previous/current values and a Growth activity. Venue corrections affect other opportunities at the venue; the review form calls this out and inventory is refreshed.

Historical corrections are linked only where the saved history identifies a single predecessor. Ambiguous historical records require review.

## Resolution projections and delivery

`claim_resolution_response` provides the same replacement, credit and allowance data to Administration, customer details, and email. The customer `MarketplaceClaimResolution` component is reused inside claim details and the purchase's claim overview. Original-submission photos and later evidence continue to use the universal viewer.

Resolution emails use the existing branded email templates, Celery queue and `EmailDelivery` log. The recipient is the claim submitter, provided they are still an active organization member. Approval/rejection and later refund-state changes have separate deduplication keys. Content is HTML-escaped. Historical decisions are not bulk-emailed when the migration is applied.

The `marketplace-claim-followups` Celery Beat entry runs every five minutes. It retries undelivered resolution notifications and queues refund status checks. Notification attempts rotate behind unattempted claims, so skipped recipients or persistent failures cannot monopolize a batch. Attempt timestamps are separate from successful delivery and customer-visible update timestamps. Pending refunds are checked every five minutes; succeeded refunds are checked daily for 30 days for late bank failures. Poll timestamps are also separate from customer-visible update timestamps. Workers and Beat must run the deployed code for these background operations.

Refund requests preserve a **Requested** state before contacting Stripe. An interrupted request can recover the existing refund using provider metadata, including after the provider's idempotency-key retention window. **Pending**, **Succeeded**, and **Failed** come from provider state. Failed/canceled refunds remain visible for administrator follow-up. Status checks retrieve existing refunds; they do not issue new payments. Late failures reverse the cash-refund projection and notify the customer.

Automated tests mock all Stripe and email delivery calls. They cover contact ownership/history, snapshot preservation, field validation, cross-tier replacement, mixed funding, refund transitions/recovery, duplicate compensation/delivery, customer resolution links and the reviewer form.

## Structure review, September 9

This review follows the claim remedies through customer and Administration APIs, correction and funding services, customer resolution presentation, and background notifications. It does not certify every unrelated project directory or measure production latency.

- `claim_policy.py` owns remedy eligibility. Administration computes it once per response; availability labels are a pure projection of that result.
- Replacement search and fulfillment use the same inventory predicates, including the requirement for an active product in the selected tier. Candidate retrieval stays at three queries as eligible tiers expand.
- `corrections.py` supplies field names, labels, scope and address grouping to the review form. The frontend no longer maintains its own address-field and venue-scope lists.
- `marketplace_contact_snapshot` accepts already loaded contacts. Corrections reuse their locked, prefetched contacts instead of fetching them again. Rendering that snapshot requires no queries.
- Credit remedies share one call to the existing credit service and one access-revocation block. Each remedy retains its own amount, audit metadata and stable idempotency key; allowance restoration continues through the existing allowance service.
- Claim email jobs reuse `EmailDelivery` and the shared resolution projection. Related allowance grants and replacement venue data are loaded in batches, and attempted delivery is recorded without falsely marking skipped mail as sent.
- A refund in progress cannot be rejected by submitting its current remedy alongside a rejection. Historical corrected-information claims do not display allowance compensation granted by a later claim against the same purchase.

These changes keep existing domain boundaries instead of introducing another generic helper or service framework. Regression coverage includes inactive replacement products, bounded query counts, skipped recipients, and queue fairness beyond a full batch of attempted notifications.
