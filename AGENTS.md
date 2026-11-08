# Pro Claws Agent Notes

## File Discipline and Shared UI

Do not create unsolicited review, summary, handoff, or rule documents. Keep durable project instructions in this existing AGENTS.md. Add source files only when a required component or module has a clear responsibility that existing code cannot reasonably own.

Before implementing UI or business logic, inspect and reuse the existing Expense, Marketplace and opportunity patterns. Keep shared behavior in its existing source of truth; avoid duplicated helpers or page-specific replacements. Match established typography, spacing, buttons, tables and responsive layouts. Use title case for visible input labels. Mobile forms on both iOS and Android must outline invalid required inputs in red after a submit attempt. Derive validation from current values so each outline and its field error clear as soon as that input is valid, and reappear if it becomes invalid again. Reuse shared field validation controls, preserve domain-specific validity checks, and keep submit available to reveal missing-field feedback.

Apply these ownership and reuse rules throughout every project directory. Prefer small, cohesive responsibilities in existing modules; avoid both scattered one-off helpers and oversized functions. Keep one authoritative owner for each behavior within each platform, with equivalent behavior across platforms. Avoid repeated geometry processing, rendering, or allocations in frequent update paths; verify performance claims with measurements. Before adding a helper or component, search for the existing owner of that behavior. Extend that owner when appropriate; extract a small shared component only when multiple callers need the same responsibility. Keep transport, domain rules, and presentation separate, and avoid generic abstractions without actual callers. Add focused regression tests for changed behavior, including loading, refresh, access, and draft preservation where relevant; do not claim project-wide security or performance guarantees from a narrow review.

Editing belongs to the active tab. Show Edit only where there is editable data; preserve the established unsaved-change guard when leaving an edited tab. Creation actions such as Record Activity use a modal. Keep modal submit actions available for incomplete forms and show validation feedback when clicked, rather than silently disabling them. Guard duplicate submissions while a request is running. Reuse the existing two-Escape behavior: first Escape highlights Close/Cancel, second requests closing, with dirty-state confirmation where applicable.

Activity changes must retain before/after values when applicable and render through existing change-history UI. Search must include relevant displayed and related fields (including assignees and media IDs), respect access restrictions, and use server-side sorting/pagination where needed. Keep static labels and controls visible and retain current data during background refresh.

User-triggered request actions, including refresh buttons, must report success or failure through the existing topbar toast. Report the result after the request finishes; automatic background refreshes must not produce success toasts.

Treat every iOS request and screenshot as applying to Android too, and every Android request as applying to iOS, unless the user explicitly limits the scope. Keep the phone apps and their CarPlay/Android Auto equivalents aligned when applying navigation and other mobile feedback, including feedback shown only in iOS screenshots. Inspect both implementations and apply equivalent behavior and spacing using each platform’s existing controls.

Physical iPhone installs must use the Release configuration and the existing `com.vendistri.operations` bundle ID with the live backend. Verify the built bundle ID before installing. Do not install a separate Debug/development app on the user’s phone. Honor requests to defer phone installation.

Exception explicitly authorized October 29, 2026: install a separate Release-configuration `com.vendistri.operations.hardwaretest` app on the user's iPhone 17 Pro Max for local development hardware acceptance, preserving the installed production app. Use the specified local Demo User account, isolated app storage and verified local HTTPS. Keep acceptance flags, certificates, bundle/profile overrides and hardware changes out of ordinary store releases; the normal Release hardware gate remains disabled.

Subsequent October 29 instruction: while new-app provisioning is blocked by Apple's team agreement, use the reachable iPhone 12 Pro Max for a Release hardware-acceptance build under the existing `com.vendistri.operations` ID and cached valid profiles. This replaces that phone's Vendistri app with the local Demo test version. Leave the iPhone 17 Pro Max and its production installation untouched. Preserve the iPhone 12 app container; do not uninstall or erase its app data to install the test build.

Android phone testing that needs Android Auto uses Google Play Internal App Sharing: prepare the `.aab`, let the user upload it and return the sharing link, then open that link on the intended phone and install through Google Play. Do not replace that installation with an adb-installed APK or Debug app. Preserve the existing Android Auto entry points and verify them in the intended bundle.

Use existing question-mark help controls, tooltips or accessible help popovers for secondary explanations in existing and new UI. Keep essential instructions, required decisions, validation errors and actionable failure feedback visible on the page. On phones, help must work by tap and accessibility navigation rather than relying on hover.

## Account Views

Personal is an optional view under the existing login, not a separate account or business role. Do not add it to discovery merely because a user is signed in or belongs to an organization. Reuse the account lifecycle preference and existing custody/history compatibility checks; explicit Personal setup or accepted personal hardware establishes the view. Preserve legacy custody and pending-transfer access. Adding Personal must retain the selected business/contact/factory view, roles, devices and drafts. Users without Personal need the existing invitation acceptance path for incoming personal transfers. Availability never grants business permissions or transfers device custody.

Marketplace extensions must preserve independent Personal, business, location-contact and factory-operator views, including users holding several roles. Reuse existing commerce and billing owners with explicit purchase and financial scopes. Verify allowed and denied access to carts, cards, charges, orders, receipts, shipment entitlements and refunds across views; account-owned cards may be shared across the owner’s Personal and existing authorized business views, while Personal purchases, charges, orders and refunds stay explicitly Personal. Personal checkout must not change business payment defaults. Personal checkout or card changes must not collect business balances or grant contact/factory users business authority. Test stale requests and role revocation, and measure request/query budgets and timings before making performance claims.

## Web Dropdowns

Use the existing custom dropdown components for all visible web dropdowns: `Dropdown` / `SearchableSelect` in the portal and `Select` from `@vendistri/ui` in the standalone Marketplace. Do not introduce native `<select>` controls or new dropdown implementations. Hidden browser-autofill controls may remain behind the custom UI and must stay out of keyboard navigation and the accessibility tree.

Table height follows content until the established maximum height is reached; then rows scroll inside the table. Use maximum-height constraints rather than forced heights or minimum heights that reserve blank space for empty or short tables. Apply this consistently on desktop and mobile, including expanded rows.

## Loading States

Use skeleton bars for data values only. Keep titles, static text, field labels, dropdowns and action controls visible while data loads; disable controls that require unavailable data. Reuse existing loading components and preserve visible data during background refresh.

## User Deletion

If asked to delete or clean up a user, read the safe-delete runbook first:

- `backend/runbooks/safe_user_delete.md`

Do not directly delete a user from the admin, shell, or database until the runbook checks have been reviewed. The runbook includes ownership guards, related cleanup targets, and the expected confirmation output.

## Local Development Migrations

Always apply pending migrations to the local development database during development, and verify that none remain pending before reporting completion. This is part of the development workflow and does not require asking the user again.

Local development uses the existing PostgreSQL 17 server at `127.0.0.1:5432`, with database and role `proclaws_dev`. Connection settings are in the ignored `backend/.env`; reuse this server and database rather than creating another cluster. The former SQLite database and the verified cutover backup in `backend/private_data/postgres-migration-20260917/` are retained for recovery, not active development.

## Development Tooling and Disk Use

Hardware is currently unsupported in store releases for every account, including demo/reviewer accounts. Android's `BuildConfig.HARDWARE_ENABLED` is true only in debug builds and false in release; iOS's `HardwareAvailability` follows the same Debug/Release policy. Preserve development hardware access. Verify release navigation, notification/realtime entry points and hardware-specific permissions/services when changing this boundary; hiding the menu alone is insufficient. Preserve the previous signed Android bundle, use the existing upload key and verify its certificate against the previous release. Keep signing passwords in the existing credential store, never source files or command output.

Keep workspace analysis, search and watcher exclusions in the root `.vscode/settings.json`. Exclude dependencies, generated output and private runtime data; keep application source, tests, diagnostics and autocomplete available.

Reuse the existing Xcode DerivedData and SourcePackages caches instead of creating package copies for each task. Check available disk space before large native builds and avoid concurrent full Android/iOS builds when disk space is constrained. Preserve active incremental build caches where possible.

For cleanup, distinguish rebuildable caches from source, installed environments, simulator app data, hardware identities, uploads, archives and recovery backups. Check for active builds before deleting build caches. Verify references before consolidating Python environments; both existing backend environments have callers. Do not delete simulator devices or their app data as routine cache cleanup.

Application log rotation belongs to `backend/utils/logger.py`: the default is 10 MiB per active file and five gzip rotation files. `LOG_FILE_MAX_BYTES` and `LOG_FILE_BACKUP_COUNT` must match across web and worker processes. Restart all local backend/worker processes after logging-handler changes. Dated historical archives under `backend/logs/archive/` are preserved separately from automatic rotation; do not delete them as routine cache cleanup.

## Production Deployment Backups

Always check production health before and after deployment. Scale backups and rehearsal work to the actual changes: small code or UI fixes without schema, data, storage, or infrastructure changes should not automatically create full database/media/runtime copies or restore rehearsals. Preserve a usable previous code/build release for rollback and reuse suitable existing backups. Changes affecting persistent data or recovery need an appropriate fresh backup and validation. Check backup size and retention before creating redundant copies; this preference does not authorize deleting existing backups. The installed deployment helper currently performs full backups on every run, so adjust the deployment path before using it for a lightweight release.
