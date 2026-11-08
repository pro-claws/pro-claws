# Service-bundle execution contract

This is the shared execution contract for iOS and Android. A service parent and
its child tasks are one machine visit; they are not independent route starts.

## Required task shape

- The parent is a `machine_service` task.
- Every bundled child (`machine_refill`, `machine_collection`, `machine_clean`,
  `machine_refund`, and other service work) references that parent through
  `service_task_id`.
- The active execution scope must contain the parent and all applicable,
  unfinished children. A route/display choice must not remove the parent.

## Lifecycle

1. A pickup-inventory task is a standalone execution: it starts for the
   warehouse route and owns its own time and miles through pickup completion.
   If its linked destination work contains a service bundle, the next route
   starts that bundle's service parent; pickup does not become its metric owner.
2. Starting navigation for a service bundle starts the service parent only. It
   owns the visit timer and route/visit distance.
3. On arrival, start the first applicable unfinished child in the bundle's
   configured execution order. For the common subset this is Refill, then
   Collection, then Clean.
4. A child records its own `started_at`, completion time, and child-level
   metrics while it is active.
5. Completing a child starts the next applicable unfinished child in the same
   bundle. Missing task types are skipped without changing the order of those
   that remain.
6. When the last child is final, mark the service parent Done, then advance to
   the next task on the machine or the next machine.

## Metric ownership

- The service parent is the bundle-level metric owner and is the only source
  counted in aggregate visit totals.
- Child metrics remain visible at task level but are excluded from the aggregate
  bundle sum, preventing double counting.
- Cancelling a bundle finalizes the started metric owner(s) with the accumulated
  duration and distance.

## Partial bundles and standalone tasks

- Bundle order is filtered, never rewritten. A bundle containing Service,
  Refill, and Collection ends after Collection; it does not wait for Clean.
- A standalone task has no `service_task_id`: navigation starts that task, and
  it owns its metrics continuously until it is completed or cancelled.

## Non-negotiable boundaries

- Route/UI presentation must not choose a later child as the execution start.
- A completed child is skipped only for execution; it does not reorder the
  remaining children.
- If a child is started directly, investigate the execution scope and its
  `service_task_id`; it is a contract violation unless that task is genuinely
  standalone.
