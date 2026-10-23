# Machine-task query contract audit

Date: 2026-07-27

## Purpose

This document defines the existing backend/client contract before task-query
scoping is tightened. It separates legitimate product requirements from
accidental unfiltered loading so the backend can be bounded without breaking
web, iOS, Android, contact visibility, active-work recovery, or reports.

## Current backend contract

| Endpoint | Response | Accepted scope | Current danger |
| --- | --- | --- | --- |
| `GET /task/machine/all` | Full machine-task objects | machine, location, date range, status, task IDs, refill task IDs, or none | Zero filters materializes every accessible task. Visit metrics default on. Used by Android and legacy/full-object callers. |
| `GET /task/machine/list` | List machine-task objects | Same scopes, or none | Zero filters materializes every accessible task. Visit metrics default on. Used by web. |
| `GET /task/machine/contact/list` | Contact-redacted list objects | Same scopes, or none | Zero filters materializes every task for all accessible contact machines. Visit metrics default on. Used intentionally by contact-mode clients. |
| `GET /task/machine/report/list` | Compact report objects | Required start and end dates | Date-bounded, but the server currently imposes no maximum range. |
| `GET /task/machine/contact/report/list` | Contact-redacted compact report objects | Required start and end dates | Date-bounded, but the server currently imposes no maximum range. |
| `GET /task/machine/dashboard/list` | List objects without visit metrics | Required date range plus overdue cutoff | Bounded by explicit inputs, although an old overdue cutoff can still create a large result. |
| `GET /task?id=...` and contact equivalent | Single full task | One task ID | Naturally bounded. Correct for single-ID hydration/detail. |
| Typed machine-task detail endpoints | Single full task | Type plus one task ID | Naturally bounded. |

All three general list endpoints currently:

1. Permit a request with no data scope.
2. Convert the complete queryset to a Python list.
3. Default `include_visit_metrics` to `true`.
4. Return a bare JSON array with no cursor, count, limit, or truncation signal.

`task_ids` and `refill_task_ids` are unbounded comma-separated strings.
Date ranges have no maximum span. `status` alone is not a sufficient memory
bound because an organization can accumulate an unlimited number of tasks in a
status.

### Visit-metric expansion

Visit metrics are not just two scalar fields during computation. For every
machine/location pair in the requested result, the backend loads assignment
windows and prior completed-task history. The recent scalar-output rewrite
reduces retained response state, but an unbounded input result still produces:

- an unbounded initial task list;
- an unbounded set of machine/location pairs;
- potentially large assignment and historical completed-task query results;
- an unbounded serialized response.

Therefore `include_visit_metrics=false` is an optimization, not an adequate
scope boundary.

### Permission and redaction invariants

Any replacement contract must preserve:

- organization and selected-organization access filtering;
- operator read restrictions;
- location-contact machine/location filtering;
- suppression of pickup-inventory tasks for contact-only access;
- removal of contact-only notes;
- optional suppression of metrics, financials, refill inventory, and
  confirmation photos according to location contact policy;
- identical authorization on task-ID hydration and detail endpoints.

## Caller contract matrix

| Product flow | Web | iOS | Android | Required scope |
| --- | --- | --- | --- | --- |
| Organization startup/main route | Some generic `loadTasks()` paths remain unfiltered; dashboard and route-specific paths are scoped | Current week | Current week | Current week. Generic web startup must migrate. |
| Calendar/day/route planner | Date or week scopes | Date or week scopes | Date or week scopes | Requested day/week; adjacent weeks loaded explicitly. |
| Dashboard | Dashboard endpoint with date range and overdue cutoff | Not a general full-history dependency | Not a general full-history dependency | Dashboard-specific bounded projection. |
| Machine detail | Machine ID | Uses locally loaded task data and targeted refreshes | Uses locally loaded task data and targeted refreshes | Machine ID, preferably with pagination for history. |
| Location detail | Location ID, but `OverviewTab` contains an unfiltered fallback | Contact detail can request the contact full set; organization views use loaded/scoped data | Contact detail uses contact task state | Location ID for organization views. Contact behavior needs the paged contact contract below. |
| Task detail | Task ID plus targeted refresh | Single task detail | Single task detail | One task ID. |
| Realtime changed tasks | Task IDs; contact mode also refreshes affected locations | Task IDs; contact mode also refreshes affected locations | Task IDs, machine IDs, or location IDs | IDs supplied by the event. Never all tasks solely because an event lacks IDs. |
| Active-work restoration | Loaded ranges plus active task IDs where available | Persisted active task IDs now hydrate before restore | Persisted active task IDs hydrate before restore | Bounded active task-ID set. |
| Contact portal startup/tasks | Unfiltered contact list | Unfiltered contact list | Unfiltered contact list | Product currently needs cross-date contact history. Replace with paged contact summaries, not silent week scoping. |
| Reports/history | Required date-range report endpoints | No startup dependency on full report history | No startup dependency on full report history | Explicit date range, compact projection, maximum range or pagination. |
| Mutation reconciliation | IDs, entity scopes, or loaded date scopes; some explicit “all scope” legacy fallbacks remain | IDs, then per-ID retry | IDs; failure falls back to current week | IDs first; reload only already-loaded bounded scopes on failure. |

## Fields clients depend on

The general task-list contract cannot be reduced to IDs/status alone. Across
route planning, task cards, workflow restoration, contact display, and mutation
reconciliation, clients consume these groups:

- identity and grouping: task ID, type, service parent, prerequisites/children;
- assignment and lifecycle: status, assignee, public flag, created/scheduled,
  started/done timestamps;
- routing: machine ID/name, location ID/name/address/coordinates;
- execution: duration, distance, notes, confirmation assets;
- collection financials: gross, cash, card, refunds, commission, net, payment
  type, surcharge and transaction count;
- refill/pickup linkage and completion context;
- last-visit date and days-since-last-visit where the screen requests metrics.

The compact report response is intentionally partial and must continue to be
merged as a partial snapshot. It cannot replace the operational list response
for task execution.

## Required backend contract

### 1. Explicit scope rule

General list requests must contain at least one *bounded* selector:

- `task_ids`;
- `machine_id`;
- `location_id`;
- both `scheduled_from` and `scheduled_to`; or
- `refill_task_ids`.

`status` alone does not satisfy the rule.

Initially, violations should be observed and logged under a compatibility flag,
not rejected, until released web/iOS/Android versions no longer depend on them.

### 2. Hard validation limits

Recommended initial server limits:

- `task_ids`: at most 100 unique IDs;
- `refill_task_ids`: at most 100 unique IDs;
- operational date range: at most 31 days;
- report date range: at most 366 days until reports are paginated;
- reject one-sided date ranges;
- reject inverted ranges;
- cap comma-separated input length at the web-server and application layers.

The exact values should be confirmed against production telemetry, but the
limits themselves must be server-enforced.

### 3. Projection rule

`include_visit_metrics` should default to `false` on a versioned endpoint.
Callers requiring last-visit fields must opt in. The existing endpoints should
retain their current default during migration so older clients do not silently
lose data.

### 4. Pagination rule

Contact history and long reports are legitimate broad datasets. They require:

- stable ordering, e.g. scheduled date descending then ID;
- cursor pagination;
- a fixed server maximum page size;
- `items` and `next_cursor`;
- filters encoded into or validated against the cursor;
- the same contact redaction on every page.

Do not reinterpret “all contact tasks” as “current week”; that would change the
contact product contract and hide historical visits.

### 5. Active-ID hydration rule

Active restoration on every client must:

1. load its ordinary bounded startup scope;
2. read persisted active task IDs;
3. request only those IDs;
4. merge returned tasks;
5. treat omitted/404 tasks as deleted or inaccessible;
6. decide whether work is still active only after hydration.

The backend must authorize every requested ID and must not reveal whether an
unauthorized task exists.

### 6. Failure rule

A failed bounded request must not fall back to an unfiltered request.

Allowed recovery:

- retry the same scope;
- split a bounded ID batch into single-ID requests;
- reload the current week/day;
- reload machine/location scopes already mounted by the UI;
- retain stale local data with an error indicator.

## Caller migrations required before enforcement

### Web

Migrate or remove:

- generic organization `loadTasks()` initialization;
- `OverviewTab` unfiltered fallback;
- generic `TasksTab` unfiltered fallback;
- realtime paths that reload `taskScopeKeys.all`;
- pending-invite and route-change fallbacks that call unfiltered `loadTasks`;
- contact startup, after the paginated contact store contract exists.

Preserve:

- dashboard queries;
- date-range route/calendar queries;
- machine/location scopes;
- task-ID realtime refresh;
- compact report endpoints and partial-snapshot merging.

### iOS

Already safe for organization startup and active restoration:

- startup uses current week;
- foreground uses the current mode’s bounded organization scope;
- active restoration hydrates persisted IDs;
- realtime refresh uses IDs and affected location scopes.

Still requiring migration:

- contact-mode `loadTasks()` is intentionally unfiltered;
- any error fallback calling unfiltered `loadTasks(force:true)` must be changed
  to the last loaded scope before backend rejection is enabled.

### Android

Already safe for organization startup and active restoration:

- startup uses current week;
- active restoration hydrates persisted IDs;
- ordinary realtime fallback reloads the current week.

Still requiring migration:

- contact-mode startup is intentionally unfiltered;
- generic public `loadTasks()` remains capable of an unfiltered request and
  should require an explicit scope or be made private;
- ID-refresh failure currently reloads the week, which is safe but should
  preserve an active ID error rather than imply successful hydration.

## Compatibility-safe implementation sequence

1. Add backend scope classification and telemetry without changing responses:
   endpoint, scope kind, date span, requested ID count, DB count, response
   count, response bytes, visit-metric flag, duration, and authenticated client
   version/platform where available.
2. Add validation unit tests for empty, malformed, oversized, and valid scopes.
3. Add bounded versioned list endpoints or an opt-in strict query mode.
4. Migrate web organization initialization and every unfiltered fallback.
5. Add cursor-paged contact loading to all three clients while preserving
   history/contact display behavior.
6. Migrate report consumers if production ranges exceed the agreed maximum.
7. Release clients and observe legacy unscoped traffic by version.
8. Change metric defaults only on the versioned contract.
9. Reject unscoped requests on strict/versioned endpoints.
10. After the supported-client window, reject unscoped legacy requests.

## Tests required before deployment

- Backend rejects empty strict scopes without evaluating a queryset.
- ID and date limits are enforced before database work.
- Contact redaction matches existing endpoints for every page.
- Pagination has no duplicates or omissions across equal scheduled dates.
- Visit metrics are identical when explicitly enabled.
- Organization, selected-organization, operator, and contact permissions remain
  unchanged.
- Web startup, realtime, task detail, dashboard, route calendar, machine detail,
  location detail, contact history, and reports request their declared scopes.
- iOS and Android restore an active task outside the current week.
- Deleted, final, unauthorized, partially returned, and temporarily failed
  active-ID batches do not resurrect or silently discard active work.
- Load tests assert query count, peak process memory, response size, and latency
  at the maximum permitted scope.

