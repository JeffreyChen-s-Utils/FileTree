# FileTree Architecture

Short overview of how FileTree is put together. Keep it current: a change to any section below updates
this file in the same commit.

## 1. Purpose

A disk-usage viewer: scan a folder or drive, add up every file, and show where the space goes — a folder
tree sorted largest first, a squarified treemap, the largest files and the space per file type — with a
safe way to free space (move to the Recycle Bin / Trash, never a permanent delete).

## 2. Layers and directories

| Layer | Path | Depends on | Holds |
|---|---|---|---|
| Core | `je_file_tree/core/` | standard library only | `node.py` (the tree), `scanner.py` (parallel scan), `allocation.py` (size on disk), `protected.py` (system and program folders), `exclusions.py` (folders to skip), `analysis.py` (largest files, per-type and per-age totals), `search.py` (find by name), `duplicates.py` (same content), `cleanup.py` (clean-up suggestions), `compare.py` (against a saved scan), `pacing.py` (background work gives way to the window), `treemap.py` (layout), `sunburst.py` (rings), `tree_layout.py` (bounded hierarchy rows), `formatting.py`, `export.py` (CSV / JSON) |
| GUI | `je_file_tree/gui/` | PySide6, core | `app.py` (start-up), `main_window.py`, `welcome.py`, `scan_bar.py`, `results_view.py`, `charts.py` + `bar_chart.py` + `sunburst_widget.py` + `tree_diagram.py`, `search_panel.py`, `cleanup_panel.py`, `duplicates_panel.py`, `grouped_list.py`, `changes_panel.py`, `tree_model.py`, `tables.py`, `treemap_widget.py`, `delegates.py`, `scan_worker.py`, `file_actions.py`, `help_dialog.py`, `i18n.py` + `strings.py`, `qt_translation.py`, `elevation.py`, `icon.py` (drawn in code) |
| Entry script | `start_file_tree.py` | GUI | Starts the window from a source copy; the file Nuitka compiles |
| Tools | `tools/` | GUI | `make_screenshots.py` (README pictures), `build_nuitka.py` (stand-alone builds, see `nuitka.md`) |
| Tests | `test/` | both | one file per area; Qt tests on the offscreen platform |

The Tests workflow supports manual dispatch as well as push/pull-request checks. If a pushed
commit has no execution record, `gh workflow run test.yml --ref dev` requests the complete suite
and owned native probes on that ref. This does not invoke the release workflow; a dispatch request
alone never establishes a passing result or native evidence.

The Windows owned SMB job creates a fresh loopback share with read access limited to the runner's
current account and one nonpersistent unused drive mapping. `validate_windows_share.ps1` refuses
non-hosted/nonadministrative sessions, existing roots/shares/mappings and redirected fixture entries.
`windows_share_probe.py` compares UNC/mapped scans and native allocation units with the local tree at
one/four workers, verifies denied-listing incomplete coverage and no empty-folder proposals, and
pauses new reads while removing only that receipt-checked share mid-scan. Source identity/content and
the exact owned denied-directory DACL are rechecked before guarded fixture cleanup. Partial JSON is
retained on failure. This fixture cannot establish slow remote-link performance or owner share behavior.

The core never imports Qt or the GUI (`test/test_layers.py`).

The macOS 15 arm64 CI job runs the full suite plus `validate_macos_sources.py` in a separate native
cocoa process. This tool exclusively creates disposable temporary sources, uses production verified
copy/link APIs, hashes complete resource forks/xattrs, preserves source identity and renders CJK/all
chart modes. Phase JSON/PNG survive later failures; host Trash and Finder automation are not invoked.
Same-volume source proofs do not establish cross-volume behavior, Finder consent or APFS recovery.
Reviewed macOS 15.7.9 arm64 / Qt 6.11.2 cocoa artifacts confirm these scoped same-volume
copy/link/CJK/source-preservation checks, with complete owned-fixture cleanup.

`core.change_watch` captures complete physical metadata scopes on a worker, capped at one million
folders and 65,536 shared inodes. `windows_watch` reads only existing NTFS USN journals and uses
one recursive overlapped directory handle when unavailable; partial shared-file roots refuse that
fallback because external aliases are not covered. `linux_watch` uses one inotify descriptor with
anchored folder and captured shared-inode watches, exposing kernel limit failures. Bounded events
map to captured folder paths; overflow/gaps request full scans, malformed records fail visibly.
Native cancellation joins outstanding Windows I/O before freeing storage. Notifications are
observational rescan requests and never operation authority. Reviewed native CI confirms ordinary
and outside-alias events on both Windows USN and Linux inotify, with source preservation/joined cancellation.

`gui.change_watch.FollowChanges` owns one default-off monitor per result tab. Its worker builds maps
and coalesces native events under a lock to avoid unbounded Qt signal queues. The one-second GUI
timer defers dirty folders during scans/analysis, source reviews, modal questions and Undo offers;
bounded ancestor selection reuses rescan_folder and branch replacement. Events continue during
branch scanning, then monitoring joins before tree replacement. Lost scopes/overflow, counted
hard-link totals, operation gaps and five-minute periodic reconciliation force full roots. Branch
rearming preserves the periodic deadline and unrelated pending paths; new roots discard old data.
Shared OperationGroup exclusion quiesces peer monitors before source mutation/tree changes. Native
failures remain visible without retry loops; opt-out/tab close cancel/join through wait_for.

`core.background` separates strict default-off monitor configuration, selected-root schedule claims
and bounded capacity warning transitions from GUI services. Versioned configuration stores no
commands or action permissions. Claim receipts bind root, timestamp and schedule fingerprint;
failed/canceled claims suppress same-period redispatch, missed periods coalesce once and clock
rollback postpones work. OS available capacity is distinct from scan allocation; unknown values do
not reset low-space latches. These metadata APIs never scan or mutate sources. Strict bounded
attempt serialization rejects action fields, duplicate normalized roots and overflowing timestamps.

`gui.background_monitor` is one passive workspace service with Options configuration and a native
tray. start_services activates only persisted opt-in; factories never show a tray or schedule scans.
CapacityWorker copies bounded OS available-capacity scalars without bin queries; crossings are
informational notifications plus plain-text status/tooltips. QLockFile and synchronized QSettings
claim before scheduled dispatch; malformed/locked/unpersistable receipts fail closed. ScheduledWorker
forces gentle/one-thread scans and normal bounded history, recording incomplete scopes/errors while
leaving foreground tabs untouched. Foreground scans/source reviews cancel and join gentle work.
Explicit Quit joins everything; window close hides only with enabled/available tray, and tray loss
restores the window. --background skips elevation and only hides a configured native tray session;
it never enables monitoring. `gui.autostart` exposes actual native registration and an explicit separate
login choice. `startup_windows` uses one HKCU Run value and a durable private receipt; `startup_posix`
uses owned canonical metadata, descriptor-anchored no-follow directories and exclusive publication.
Foreign/changed/shared/linked entries are refused; removal rechecks captured metadata. No shell,
global registration, immediate process launch, KeepAlive or elevation is used. The setting affects
future logins; native metadata presence does not prove OS login approval. Remaining desktop proof is #38.
`tools/validate_background` requires native Qt rendering, private sources/settings/history and retained
phase JSON/CJK captures. Linux's private X11 session starts an owned XEmbed tray and requires visible
notification capture; other platforms explicitly retain unavailable trays or dispatch-only evidence.
CI never registers host login jobs, and notification calls never imply actual OS permission.

`core.recurring` captures immutable bounded candidate metadata and whole-captured-tree fingerprints
on workers, reusing recorded snapshots without payload/stat calls or Node fields. Effective policy
fingerprints include built-in definitions, risk and disabled/empty-folder overrides. Optional 100-row /
48-KiB Baseline metadata binds to the normal owned history header and retention cap; legacy history
stays readable and incomplete/truncated/mismatched baselines cannot prove new candidates. File-only
errors also flag saved history incomplete. Root device/inode binding refuses a replacement physical
scope at the same path. ProposalContext binds one schedule claim/date and expiry
at the next due time; validation rejects missed periods, replaced/failed/canceled receipts, changed
policy or any captured descendant metadata. Valid observations grant no action authority.
ScheduledWorker captures strict current policy and the durable claim/interval, reads the latest bounded
history/baseline and prepares observations on its thread before saving the bound baseline. Optional
proposal failures retain ordinary saved history plus a visible error; cancellation publishes neither.
Capture reserves the maximum history-date length within the 48-KiB bound before truncating candidate
rows. Their original count remains intact, so omitted rows cannot prove a new path. An oversized
header fails visibly even when no candidate rows remain, rather than looping or relaxing the limit.
BackgroundMonitor retains metadata-only current-session reports for at most 32 selected roots. The File
menu opens RecurringDialog under OperationGroup ownership: three read-only 100-row lists, plain dates/
coverage/expiry/unknowns, literal full-path tooltips and copy. A small settings/receipt binding check
refreshes status without walking sources on the GUI thread. Explicit review starts an ordinary new-tab
foreground scan. RecurringFlow discards canceled/replaced/closed intents; ValidationDialog joins its
worker under OperationGroup ownership, comparing the full captured digest and native no-follow tree.
Only actual current scan nodes matching bounded rows/effective rules reach the existing CleanupReview
queue. MainWindow retains protected-folder/Trash confirmations and rechecks metadata after modal review.
TrashWorker revalidates the whole source before the batch and expiry/settings/receipt before each item,
then applies ordinary per-item native source guards. ProposalSettings captures scalar backend/group/
fallback location on the GUI thread and constructs distinct QSettings instances on operation threads;
it preserves namespace fallbacks and refuses changed storage locations. Validation remains observational.

`gui.app.main` creates a `ScanWorkspace` containing up to sixteen independently owned `MainWindow`
result tabs. Each tab retains its own `ResultsView`, scan/analyser/search/export lifetimes and captured
sources; close cancels and joins only that owner, while workspace Quit joins every tab. `OperationGroup`
checks all local source-operation owners on the GUI thread and synchronizes action availability without
processing events. Trash/Undo and modal copy/namespace/link/compression/compaction/bin reviews block peer
mutations; completed scans still undergo their normal per-source snapshot/approval checks. Language
retranslation crosses every tab. Only the running entry point schedules update services; factories are
passive. `create_window` remains the single-window integration factory; `create_workspace` is additive.

`core.similar_photos` groups 64-bit signatures by an observed representative, without transitive
chains or exact-duplicate authorization. Disjoint d+1 bands guarantee a matching band for distance d;
the 0..8-bit index preserves the earliest matching representative, with linear fallback for 9..16.
Six-thousand random signatures, five interleaved runs at distance four: linear 2.36056 s versus bands
0.04139 s; a measured BK-tree was slower than linear and is absent from the implementation.
`photo_reader.py` keeps Pillow outside the stdlib-only core and decodes only recorded image categories
using fixed native formats, guarded source snapshots, EXIF orientation and the first animation frame.
It compares grey 9x8 neighbour pixels, re-reads only displayed members for memory-only thumbnails,
refuses changed/link/cloud entries, deduplicates observed hard-link names and caps source bytes,
pixels, successful signatures and thumbnails. Decoder calls finish before Stop/close can join.
DuplicatesWorker captures a separate photo mode and threshold; DuplicatesPanel reuses the grouped
list with bounded icon rows, disables exact keeper/extra selection and recovery estimates, and drops
photo results on tree edits. Mode changes/new scans invalidate worker identities, all workers join
at close, and manual file actions retain MainWindow's confirmation/protection/snapshot flow. Hash
collisions remain possible; group members need not match each other, only their representative.
Runtime requirements and all five build guides include Pillow; executable releases install a verified
pinned Windows 3.12 wheel from .github/requirements/photos.txt, outside the publishing job.

`core.archives` reads guarded ZIP directory metadata and builds an iterative virtual inventory,
separate from real Node.children. Third-party 7z/RAR adapters in `archive_formats.py` keep the core
stdlib-only; they use metadata listing APIs, never extraction, CRC testing or external commands.
RAR requires an unrar/bsdtar PATH entry and otherwise remains a plain file with a tooltip reason.
No preview hydrates known cloud placeholders or follows source links. Physical metadata reads have a
32 MiB cumulative budget; encoded 7z headers also have a declared decoded-size guard before decoding.
Inventories cap entries/names/depth and reject member links, unsafe paths and conflicts with visible
omission counts. Declared uncompressed bytes are separate from allocation and verified content.
FolderTreeModel exposes expandable completed archive files and attaches display-only children through
an overlay; NODE_ROLE and node(index) return None for virtual rows, preventing all filesystem actions.
Charts, lists, history and exports continue traversing only real scan children. Virtual rows are marked
in all languages, have no allocation/share/date fields and are hidden while the real-entry text filter
is active. ArchiveController owns at most two lazy workers; the source context menu can stop a read.
New scans and tree edits invalidate replies/overlays, and close joins current decoder calls. Failed,
unavailable and encrypted-header archives remain plain files with reasons; a rescan permits retry.
Installed py7zr/rarfile decoder dependencies are collected by Nuitka; Windows 3.12 executable releases
install verified pinned wheels from .github/requirements/archives.txt outside the publishing job.

`core.programs` reads only fixed HKLM/HKCU uninstall keys in both registry views, including optional
EstimatedSize KiB and InstallLocation, never uninstall command fields. It deduplicates mirrored records,
limits enumeration to 20,000 keys per view and reports inaccessible/omitted entries. Recognized scanned
Steam appmanifest ACF uses a bounded iterative quoted-KeyValues reader; Epic item JSON comes from the
scan and the fixed Windows ProgramData metadata folder. Manifest content reads are bounded to 1 MiB,
guard scan/path/descriptor snapshots through duplicate hashing's metadata checks and refuse known
cloud/link states. No installation folder is rescanned. Iterative recorded-folder matching plus coverage
delivers up to 1,000 rows/full counts to gui.programs; reported, logical and named allocation stay
separate and overlapping installations are never summed. The owned dialog worker supports Stop/close,
Ctrl+C and exact recorded-node activation. Its only uninstall action opens a fixed ms-settings URI;
the menu is visible on Windows with completed results. No uninstall subprocess or registry writes.

`core.history.ScanHistory` writes stable completed full trees on the existing ScanWorker, before
publishing its outcome. Compatible file-tree/1 JSON has a bounded first-line owned history header and
one serialization fragment per line; history's reader uses an iterative stack for deep trees. Root
buckets are SHA-256 of normalized absolute selected paths. Defaults are enabled and a global 1 GiB cap;
QSettings options are captured for each future scan. Stopped scans and branch rescans do not save; read
errors are recorded as incomplete. Save failures report separately and preserve successful scan results.
After atomic publication, retention completes and the completed outcome stays complete even if Stop
arrives late. Oversized snapshots fail before publication. Oldest validated owned metadata is removed
across all buckets under the journal's native file-lock helper, never its recorded source paths. POSIX
retention is descriptor-relative with O_NOFOLLOW; Windows root/bucket handles use GENERIC_READ and no
FILE_SHARE_DELETE to pin paths and reject reparse points. Unrecognized/linked/damaged metadata is retained
and reported, not removed to satisfy the cap. Lower caps apply on the next save; disabled history remains
readable. `gui.history` owns bounded header/tree readers, a palette-based line chart, a read-only copyable
table and settings dialog. Selecting history loads a stable SavedScan on the dialog worker, closes/joins,
then reuses CompareWorker and the existing Changes tab. Stop/close rejects queued replies. History does
not schedule scans or authorize cleanup.

MainWindow validates persisted scan concurrency (1–32, existing CPU-bounded default on invalid values) and
passes it through the shared ScanOptions factory for full and branch scans. Changes affect only
subsequent workers; welcome text explains UNC account/coverage behavior without initiating network I/O.

`gui.bin_dialog` extends the volume survey with explicit Windows single-drive native emptying.
Two GUI questions capture drive/bytes/item count and permanent-operation scope; EmptyBinWorker
rechecks totals through core.trash_size before SHEmptyRecycleBinW. Empty/null, nonlocal, incomplete,
empty and changed totals are rejected. The modal view blocks Stop/close/activation while the native
call executes, joins owned threads and refreshes capacity/bins on completion or partial failure.
Welcome, Clean up and View share this entry point. No scanned path deletion is added.

Linux `BinApprovalWorker` inventories `core.bin_empty.prepare_bin_empty` before two default-No questions
listing every exact recognized current-uid files/info path, logical payload bytes and top-level count.
Canonical mount roots, private uid directories and full bounded no-follow metadata/receipt matching
are mandatory; unknown, special, foreign, linked scope or nested mount entries disable approval.
`empty_posix_bin` re-derives the entire plan before deletion and pins component directories with
O_NOFOLLOW plus descriptor mount IDs/ancestor identities. Reverse-order unlink/rmdir removes only
captured payloads and their matching receipts, never original paths or bin containers; payload links
are unlinked without following targets. Concurrency is not transactional: changed entries and partial
errors remain visible with removed counts. Survey Stop/close joins and suppresses late approval; active
emptying blocks Stop/close. Completion refreshes volume rows/bin labels and invalidates the old main
capacity ledger, including stale analyser replies; rescan rebuilds recorded tree/accounting.
The private ext4 validation tool tests native scoped removal and unchanged outside symlink targets.
macOS `core.finder_bin` surveys the private home `.Trash` and mounted `.Trashes/<uid>` through a
trusted complete `QStorageInfo` provider injected by the GUI. Unavailable/omitted/oversized root sets
disable global approval; physical scopes are deduplicated, total metadata capped at 100k entries/128
levels and no-follow descriptor surveys reject foreign/special/linked/mounted/changed entries.
`SCDynamicStoreCopyConsoleUser` must match the unelevated process uid (never root); its copied CFString
is released. The account home comes from pwd rather than an overridden HOME. Unknown/switched user
identity disables approval. Native console/account behavior is included in the pending Mac validation.
Two default-No plain-text questions list all scopes/roots, logical bytes/items and Finder-wide
irreversibility, independent of row selection. The worker compares a fresh entire plan, invokes only
fixed `/usr/bin/osascript -e 'tell application "Finder" to empty the trash'` and awaits replies without
shell/path interpolation or termination. Finder can also remove new arrivals. Automation/native errors
and remaining/inaccessible Trash produce visible failures and fresh metadata; Finder may continue after
an error. All lifecycle/capacity invalidation paths are shared with Windows/Linux.
Disposable POSIX fixture tests and mocked subprocess checks do not prove native macOS/Finder/APFS
semantics; #4/#21 remain blocked by the absent native environment.

`gui.bin_labels.BinLabels` owns cancellable metadata-query threads independently of scans and cleanup
suggestions. Manual Refresh, completed Trash operations and bin-manager close query at most 256 ready
mounted roots off the GUI thread, prioritizing the current scan's Qt-resolved drive. Labels begin
unqueried, distinguish partial/unknown totals from zero, and show known amounts/errors as plain text.
Welcome caches per-root values; Clean up receives only its scan's drive. Unit/language changes reformat
cached values without OS queries. Replacement/full scan cancels and invalidates old replies; closing
joins all owned threads. No bin totals are summed into tree accounting or cleanup eligibility.

`core.trash_size` exposes read-only Windows SHQueryRecycleBinW totals or iterative POSIX logical
payload inventories with cancellation, omitted metadata and explicit incomplete/error states.
`core.allocation.allocation_unit` distinguishes known Windows clusters/POSIX fragment granularity
from the scanner's fallback estimate. VolumesDialog owns a worker that refreshes Qt storage values,
retains up to 256 ready mounted roots and complete counts, queries bins and delivers scalar rows to a
numeric-sort proxy and native free-space delegate. Welcome/View entry points activate the same modal
flow; double-click joins the worker then asks MainWindow to scan a root. Closing discards late replies.

`core.report` prepares immutable translated scalar tables from the recorded whole scan, with bounded
largest-folder/file and type lists, complete counts, overlap/coverage notes and cancellable traversal.
It writes escaped script-free HTML atomically with inline PNG bytes. GUI report adapters capture a
separate whole-root ChartStack on the GUI thread without changing navigation, encode owned QImages on
the worker and write Excel through openpyxl outside the stdlib-only core. A ReportDialog owns/joins its
worker, rejects late replies and makes tree mutations unavailable while preparation/writing runs.
Excel tables retain numeric bytes/counts, escape formula-like/XML-control text and preserve oversized
integers as exact text. Every writer checks cancellation before atomic destination replacement.

`core.projects` surveys recorded manifests/markers iteratively without filesystem reads. Its shared
RebuildableMatcher uses clean-up evidence without age eligibility; separate current-policy clean-up
results gate review by age, coverage and exclusions. Coverage construction accepts cancellation.
Generated and managed-store internals are skipped; bounded heaps keep the largest 1,000 project rows
with complete counts, and each row retains at most 1,000 eligible entries with a full eligible count.
Nested projects propagate known bytes to ancestors and overlap. ProjectsDialog owns/joins its worker,
rejects late/canceled replies, selects existing tree nodes and sends explicit eligible review requests
to MainWindow.move_to_trash. Standalone environments/Maven/global Gradle/Docker stores remain read-only.

`core.git_history` pipes fixed read-only rev-list --all object IDs into cat-file metadata, retaining
only 1,000 largest objects in a heap plus complete counts and a loose-object count. Bounded independent
stdout/stderr readers prevent pipe deadlocks; cancellation/deadline reaps only owned processes/readers.
Global Git routing/config environment is excluded, optional locks/maintenance/fsmonitor hooks are off,
and --no-lazy-fetch prevents missing-object downloads or fails on unsupported Git. Object names and
recoverable-space estimates are deliberately absent. GitHistoryDialog owns/joins its worker and explains
that reachable objects survive gc; no repository operations are offered.

`gui.tree_filter` debounces a case-insensitive name query and inspects recorded children only beneath
expanded nodes on cancellable owned threads. Accepted node identities and ancestors form an O(1)
membership proxy without Qt recursive descendant filtering. FolderTreeModel owns numeric/name sorting
and persistent source indexes. The tree swaps to the proxy only while a query is active, preserving
header/expansion/selection state; ResultsView maps source targets and reads NODE_ROLE for proxy selection.
Cross-view navigation to a hidden target clears the filter. Model reset/layout/row changes invalidate
stale queries; closing joins every worker. The complete scan continues to drive all totals and exports.

`core.live_compare` matches exact relative names from two fresh scanner trees iteratively, preserves
unknown missing paths under unreadable scopes, and bounds displayed rows to 10,000 while keeping the
complete count. Explicit requested pairs reuse snapshot-guarded full-file hashing and revalidate both
paths after both reads. Metadata equality never establishes content equality. The independent modal
LiveCompareDialog owns/joins gentle scan/hash and CSV export workers, rejects canceled/closed replies,
and offers no copy, move or synchronization action.

`tools/linux_desktop` is a separate native desktop test harness: a digest-pinned container wraps Xvfb
and a private D-Bus session. A separate Qt service declares the strict FileManager1 string-array/string
signature; the client introspects it and verifies an actual wire call. Owned Trash fixtures go through
MainWindow review, protection, journal and QFile, checking freedesktop path/content receipts. Native CJK
glyph support and a screenshot provide rendering evidence. CI mounts the repo read-only, limits runtime
resources and retains evidence even on failures. This tooling introduces no application dependency.
An isolated disconnected-bus process exercises QDesktopServices with a logging xdg-open to verify
the containing-folder fallback. MainWindow accepts dropped folder references only as Copy, rejecting
Move-only sources so scan initiation never authorizes a file manager to remove its original.
Owned Openbox and Thunar processes plus xdotool exercise external X11 drag negotiation while Qt
continues processing events; the probe verifies the completed root and original payload identity.

`core.special_files` surveys existing packed snapshot attributes on a cancellable iterative walk,
giving way per folder and retaining at most 1,000 largest matches plus full matching totals. It uses
no filesystem reads or new Node fields. The modal GUI SpecialFilesDialog owns/joins its worker,
rejects canceled/closed replies and supports sorting, clipboard and selection in the existing tree.
Recall/offline rows expose logical full content length; provider/local-content ratio and allocation
after download are unknown. Low allocation without flags retains an unknown cause, including on POSIX.

`tools/measure_streams.py` is an independent Windows metadata survey, not a scanner extension.
It times ordinary gentle scans, bounds its additional file/directory sample and enumerates named
streams through FindFirstStreamW/FindNextStreamW, always closing search handles. Reparse/changed/error
entries are unknown; it neither opens stream contents nor treats logical stream lengths as allocation.

`shell_integration` installs a marked current-user Directory verb only on explicit Options dialog Save.
Native registry creation disposition prevents claiming an existing unowned key; ownership and key-shape
checks limit updates/removal to this verb. Commands quote the executable and absolute `launcher.py`
entry, whose source path bootstrap works independently of Explorer's working directory; Nuitka starts
its original executable. Native Properties uses ShellExecuteExW with a fixed verb and item path.

`themes` owns one QApplication controller: System restores native style and a zero-resolve-mask
palette, while explicit Light/Dark use Fusion and complete colour roles. ThemeMenu persists the choice
and startup restores it before constructing windows. Palette/style events discard chart caches.
`colours` selects label ink by sRGB contrast; treemap shading is retained only when its endpoints
meet the same minimum contrast. Sunburst/age labels share this logic; bars use palette text roles.

`chart_accessibility` attaches one QObject event filter per chart, exposing translated accessible
names, current-root/selection facts and keyboard instructions. It navigates only cached/bounded layout
nodes, coordinates normal node-click selection, scrolls bar/card selections into view and leaves
modified shortcuts plus Tree diagram expand/collapse behavior intact. Enter never opens links/files;
Backspace follows the shared root-change flow. Language/unit changes refresh accessibility properties.

`core.system_files` recognizes anchored Windows-managed namespaces and returns stable explanation/tool
keys. Details displays translated guidance with explicit GUI-only tool launch (fixed settings URIs or
absolute System32 executables, no cleanup commands). MainWindow hides/filters direct managed targets;
operations rejects managed resolved paths and managed descendants even after general protection approval.
Recognition never relies on an arbitrary basename, and extended local Windows path prefixes are normalized.

`core.type_locations` computes largest matching files and direct containing-folder totals in one
cancellable iterative pass. Both heaps are bounded at 1,000; the denominator includes all matching
bytes, while nested folders do not overlap. TypeLocationsWorker replaces the GUI-thread type/age
drill-down walk. ResultsView rejects obsolete replies on scope/scan/branch changes and exposes the
folder table alongside matching largest files, with selection, context actions and clipboard support.

`list_transfer` snapshots Qt models only on the GUI thread in ≤128-row / 4 ms turns, observing model
changes to invalidate mixed captures. Current-list CSV sends text batches over an eight-batch bounded
ListStream to ExportWorker and core.export_table_csv, which writes atomically with formula escaping.
Ctrl+C is scoped to each view and produces quoted TSV of selected rows. MainWindow cancels captures
before joining writers on close, preventing blocked queue consumers; failed writers stop producers.

`details_panel` is a persisted collapsible selection pane below the tree. Selection facts use existing
Node fields; only expanded, completed scans launch a debounced DetailsWorker. `core.details.breakdown`
keeps bounded category/age totals in a cancellable iterative pass, giving way per folder and separating
unusable dates. New selections/scan roots invalidate old replies; MainWindow joins workers on close.

`breadcrumbs` binds clickable ancestors and a bounded 100-visit folder history to the current scan.
ChartStack navigation updates all charts and records one visit; stepping history does not append it.
Detached nodes are pruned after edits, new scans reset references, and deep ancestor paths use a
scroll area with a collapsed menu instead of widening the chart. Shortcuts apply while Chart is visible.

`printing` captures the visible results before opening QPrintDialog, then QPrinter fits those pixels
on one printable page. PDF export uses the same fitted layout via QPdfWriter on ExportWorker, avoiding
native printer enumeration. Its temporary sibling is flushed and atomically replaced after successful
painting. Lossless image encoding keeps text/colours intact; PDF is a captured view, not a paginated
inventory. MainWindow disables these actions during scans/moves and joins PDF writes on close.

`graphics_export` captures PNG pixels or SVG geometry on the GUI thread, then ExportWorker performs
PNG encoding and atomic QSaveFile writes with direct-write fallback disabled. PNG captures the current
chart viewport; SVG renders bounded full bar rows or sunburst paths/text directly, bypassing the ring
pixmap. File/context actions track supported modes. MainWindow owns and joins each export on close.

Treemap and sunburst share type/folder/modified-age preferences through ChartStack. `age_colours`
uses `analysis.AGES` and a scan/summary reference time without any extra tree walk. Unusable or future
dates are grey, grouped treemap tiles retain their separate grey presentation, and age labels choose
contrasting ink. Folder colours use the scanner's newest recorded modification. ResultsView shows the
matching legend and exposes colour controls for both charts; this does not infer access or inactivity.

`ScanOptions.gentle` lowers CPU and I/O priority only inside disposable crawler threads via
`core.priority`: Windows background mode (restored at exit), Linux per-thread nice / ioprio_set.
Errors and unsupported platforms are returned in `ScanResult.warnings`, separate from file coverage.
MainWindow persists the opt-in setting and shows warnings; CLI/scale measurements accept `--gentle`.
The GUI and reusable caller threads never receive priority changes.

`scan(..., pause=event)` checks the pause event while crawler workers wait for their next folder.
In-flight reads finish, progress callbacks and live refresh continue, cancellation bypasses the pause,
and resuming retains the same nodes and totals. `ScanWorker` owns the event; the scan bar forwards
Pause/Resume through MainWindow. Its analysis phase disables pause and all workers still join on close.

`TreeColumns` persists optional tree columns by stable keys in QSettings and builds the header menu
in the current language. The name remains visible with a readable initial width; extra columns scroll.
`FolderTreeModel` uses the worker-computed capacity ledger for logical percent-of-volume values,
rejecting unavailable capacity and foreign-device entries. Branch edits invalidate the denominator
until another ledger arrives; model relayouts preserve existing node indexes.

`core/coverage.py` surveys folder coverage on the cleanup worker, marking incomplete branches and all
their ancestors unsafe to remove as a whole. Unseen bytes remain unknown.

`cleanup.Rule.details` records category, minimum age, risk and stable explanation/rebuild keys.
The newest descendant disqualifies active folders. Exact cache namespaces and project/generated-file
evidence replace bare-name guesses; package stores are excluded. Manual-risk groups start unchecked
in `CleanupReview` and are excluded from bulk selection; `cleanup_text` translates metadata in all
five languages. `CleanupGroup` carries the effective details through to the review.
CleanupReview recomputes the wrapped recovery summary's minimum height on estimate/width changes
and activates layout before enabling Continue. Native review evidence refuses clipped summary geometry.

`core.cleanup_policy` validates versioned JSON rule enable/age overrides and independent clean-up
exclusions. Excluded descendants block whole-ancestor proposals while remaining in scan accounting.
`CleanupPolicyDialog` previews before/after candidates on cancellable workers, invalidates replaced
replies and requires an unchanged preview to save. MainWindow persists the policy in QSettings and
refreshes suggestions; invalid stored settings disable every rule until reviewed. No custom commands
or risk overrides are accepted, and each review receives the effective age metadata.

`core/savings.py` (also exported from `allocation`) estimates reviewed selections without reading file
contents: outermost paths, logical bytes, unique hard-link allocation, conservative recoverable file-data
range after emptying Trash, and current free space. A hard-linked file whose other names remain offers
zero recoverable data. Unknown identities/coverage make recovery unknown; shared extents and directory
metadata remain outside the estimate. Windows cluster-rounded allocation is explicitly an estimate.

`duplicates.estimate_duplicate_savings` uses each group's explicit `kept` copy; undecided groups have
unknown allocation/recovery. `DuplicateGroup` retains the verified full digest and open-file metadata
proofs only for its members. Hashing checks no-follow path snapshots and handle identity/metadata
before/after reading, skipping known cloud placeholders. Windows handle change time is compared to
itself because path/handle ctime can differ. `DuplicateSavingsWorker` checks every member's coverage,
membership, protection, hard-link aliases and original proof before extras can be selected.
`DuplicatesPanel` requires a user choice, marks the kept path, recalculates estimates and discards stale
workers. After approval, `TrashWorker` fully rehashes and rechecks each group immediately before its
batch; a failed check skips all selected members and queues a rescan. Platform move failures can still
produce a partial batch; path-based Trash calls are not an atomic group transaction. All workers join
on close. The displayed extra-copy sum is explicitly logical; shared extents remain unknown.

`core.duplicate_folders` builds iterative bottom-up folder signatures from the verified file-group
digests, without extra content reads. Every nonempty file must be hashed and relative names, sizes and
empty-directory structure must agree; unknown/error/link branches invalidate ancestors. Outer matches
collapse covered nested pairs while preserving an additional outside copy. `DuplicateResult.folders`
is shown as bounded read-only comparison lines above file groups, cleared by tree edits. It is never
used as authorization to move whole folders.

`core/capacity.py` builds a worker-computed estimated capacity ledger: OS total/used/available free,
unique allocation on the root device, hard-link overcount, included Trash allocation seen, foreign
allocation excluded and mount-boundary counts. Only complete whole-volume scans with known identities
can compute an unaccounted remainder; omitted bytes, filesystem metadata and other-volume totals remain
unknown. `gui/capacity_panel.py` shows the ledger and its limits. Tree edits invalidate it immediately;
whole-tree analysis after a branch rescan refreshes it. Replaced analysis signals are ignored and all
analysis threads are joined at close. CLI scan JSON includes the same ledger. Accuracy validation on
isolated owned NTFS/ext4/APFS volumes has passed its scoped native CI cases; independent shared/reserved bytes remain unknown. Different-device mounts are listed without
traversal. `core.mounts` reads the Linux process namespace before traversal and before publication, strictly parsing mountinfo
and decoding escaped whitespace/backslashes exactly once. The immutable directory boundary set is
rebased for ancestor aliases and shared by crawler threads. A `MountSurvey` opens each Linux directory
with O_DIRECTORY/O_NOFOLLOW and holds that descriptor through fd-based scandir and all entry stat calls.
A transient entry adapter retains original display/exclusion paths while metadata remains descriptor
relative. Per-folder mount IDs reject new same-device mounts before reading their contents. Linux 5.8+
uses libc statx with AT_EMPTY_PATH/NO_AUTOMOUNT/DONT_SYNC and only STATX_MNT_ID requested, validating
the returned mask and nonzero ID. Its fixed UAPI buffer is 256 bytes, mount ID at offset 144. Absent
libc symbol, unsupported/denied queries or missing masks fall back to checked proc fdinfo; no assumed
ID can bypass the guard. The native probe verifies both backends agree and records the active backend;
fstat device/inode checks reject replaced queued folders. Descriptors close on success, errors and stop.
Unreadable roots retain incomplete coverage. A final scope/root-mount check refuses changed namespaces
with `MountChangedError`; the GUI translates it, produces no successful outcome and writes no history.
Changes outside the selected scope are ignored. Linux requires proc mount IDs (kernel 3.15+). This
does not provide transactional consistency. Darwin also pins directory reads as described below.
Same-device boundaries are listed as links with a translated omission reason, so coverage remains
incomplete and the ledger counts those mounts without attributing their contents. An unknown table
stops before directory traversal. Explicit mount roots remain scannable. Other-platform volume reconciliation still requires validation. The isolated Linux bind case below passed CI.

`tools/validate_linux_volume.py` launches a fixed `sudo unshare --mount --propagation private` probe
on the Linux test runner. It refuses the host namespace and nonfresh scratch roots, builds only its own
64 MiB ext4 loop image, flushes fixtures and compares statvfs reservations, st_blocks, unique hard-link
allocation, logical Trash payload versus ledger receipt/payload allocation, and measured free changes
for duplicate copies, both hard-link removals and sparse files. A real same-device directory bind mount
must be omitted with incomplete coverage. Live same-device binds created before opening a queued folder
must prevent traversal; binds created after opening must leave metadata pinned to the original folder
and prevent successful publication. CI records interleaved five-run medians for statx-guarded, fdinfo-guarded and path-based
folder reads over 1,001 folders/2,000 files, with one/four workers. The child unmounts before the parent removes the owned scratch
directory and atomically saves JSON evidence. Native NTFS/APFS, compression, cloud placeholders, shared
extents remain unverified; this harness does not promote the ledger
or recovery ranges to guarantees.

`core.compression.compression_plan` surveys recorded extension-based candidates on a worker, excludes
hidden/system/compressed/sparse/reparse/cloud/offline/unknown records and keeps the largest 1,000 files
with full counts. Potential savings are only 0..recorded candidate allocation, not a predicted rate or
recoverable-space guarantee. Windows filesystem/cluster queries retain unknown state; no file payloads
are read. `gui.compression.CompressionDialog` owns/cancels/joins its preview worker, reuses numeric
tables/Ctrl+C and routes exact recorded-file activation back to ResultsView. The Windows folder menu
offers NTFS/XPRESS8K compression and restoration for only the listed (at most 1,000) files. Restoration
lists all safe recorded types because WOF flags can be absent. A default-No plain-text question names
scope/mode/count/size/partial/performance/free-space risks; no command runs before approval.
`core.compression_ops` checks current fixed local NTFS, recorded folder identity and exact file paths,
pins all ancestors/files with read/no-delete handles and revalidates snapshots, single-link local
regular state, protection/system-managed exclusions and allocation. Per-file compact runs from the
OS system directory without a shell, recursion, wildcards or directory defaults; restoration invokes
both /u and /u /exe. Owned `CompactWorker` retains failures/partial results. Stop/close terminates,
waits and joins the current subprocess; the dialog cannot start another operation or select files.
On attempted operations MainWindow rescans the exact branch/root with a transient per-file allocation
override, preserving the user's default scan option. Matched before/after known allocation remains
separate from unknown measurements and is not guaranteed freed capacity.
`tools/validate_windows_compression.py` creates only fresh owned NTFS fixtures, checks SHA-256 and
restoration, an owned junction's untouched peer and hard-link refusal, and atomically writes evidence.
The Windows CI matrix runs this probe on Python 3.10–3.14 and preserves its artifacts.

Optional ScanOptions.exact_windows_allocation routes Windows allocation through no-follow
FILE_READ_ATTRIBUTES handles and FILE_STANDARD_INFO, validating full FILE_ID_INFO device/inode (or
legacy stat device/inode on Python before 3.12), size, mtime and non-link/cloud state; every handle
closes. Unknown/changed/unsupported results fall back to
the documented estimate. POSIX keeps existing stat blocks. GUI settings default off, persist and are
captured for subsequent full/branch workers. Native 9,695-file interleaved five-run medians off/on:
0.29709/0.66070 s. An owned 2 MiB XPRESS8K file with ordinary attributes/no reparse tag retained 73,728
allocated bytes on an exact rescan versus 2,097,152 default estimated bytes. Native NTFS and XPRESS8K
compression/restoration preserved SHA-256 contents with read/no-delete pins. Native compact /s followed
an owned junction outside the chosen folder, so future operations must use exact approved file paths.

`core.owner_id` captures regular-file POSIX uid from the existing stat, or optional Windows owner SID
through OWNER_SECURITY_INFORMATION/GetNamedSecurityInfoW with LocalFree ownership. Windows capture
skips cloud/offline/link records and rechecks no-follow metadata after querying; failures become unknown
owners without making readable content incomplete. ScanOptions.windows_owners is off by default and
captured with other options for full/branch scans. Node.owner is a shared immutable uid/SID key or None:
100k-node retention measured one slot at +8 bytes/entry versus +28 for a copied SID suffix, with a bounded
4,096-key canonical cache. Identity/operation snapshots and file timestamps are unchanged.

`core.hard_links.account_hard_links` supplies optional once-per-observed-identity accounting after full
or interrupted scan rollup. ScanOptions.count_hard_links is off by default; ScanResult.hard_links records
alias reductions/unknowns. The survey uses existing stat snapshots (Windows already obtains missing
DirEntry identity through lstat), groups only multiple-link regular identities and refuses inconsistent
size/time/attribute/allocation records. The lexical first observed path contributes counted bytes;
others use one shared zero tuple. Node.size/allocated/counts/snapshots stay named/unchanged; separate
accounted_size/accounted_allocated fall back to named totals. A canceled survey makes no assignments;
callers must reapply after tree mutation. Shared extents and directory metadata remain unknown.
One optional accounting pointer measured 100k nodes at 222.828→230.820 bytes/entry (+8); the root and
changed folder totals allocate tuples. The root tuple marks active accounting even without aliases.
Baseline recorded-identity grouping: 9,770 files, five-run median
0.02091 s. Integrated one-worker 9,774-file interleaved scans off/on: 1.09788/1.14110 s, no extra OS query
or payload read. MainWindow persists the off-by-default option and captures it per worker. Two optional
tree columns expose counted bytes; charts and their category legends use counted weights, while file,
type, age and owner lists and parent/drive shares retain named totals. Summary.counted_categories is
computed in the existing analysis pass only when accounting is active. A counted-mode branch rescan or
completed Trash operation starts a whole-root scan, transferring contribution to surviving names;
compression's transient exact-allocation override is preserved. The captured old tree remains stable
until replacement. CSV appends counted bytes and a mode flag; folder JSON adds counted fields and a mode
flag without changing file-tree/1 or named saved-scan/history comparison. GUI HTML/XLSX reports append
counted entry and summary fields; older API label mappings retain their original columns. CLI exposes
--count-hard-links, counted totals and the accounting metadata alongside named byte totals.
`core.owners.owner_stats` traverses whole-root recorded files with cancellation/pacing, full byte/file/
owner-group counts and a 1,000-row largest-group limit. Unknown owners are separate; omitted data stays
unknown. It resolves only displayed account names on the worker and retains uid/SID on lookup failure.
`gui.users_panel` runs lazy analysis only on Users activation, owns/replaces/joins all threads, invalidates
totals after moves/branch replacement and reuses read-only numeric tables, Ctrl+C/current-list CSV.
It never assigns directory ownership to descendants or turns ownership into cleanup eligibility.
Native Windows 9,626-file interleaved five-run scans: capture off/on 0.41176/1.01844 s; aggregation/name
resolution 0.01346 s; all owners captured with one shared SID object. Results describe this fixture only.

`ScanOptions.file_times` optionally appends two double timestamps to regular-file snapshots from the
existing stat: 76→92 bytes, with no Node slots or per-file timestamp syscall. Access/creation properties
read that suffix, while snapshot validators and live content verification compare stable identity/
size/change metadata only. Directory/link dates remain absent; POSIX ctime is not birthtime. The core
file_times query iterates recorded nodes with pacing/cancellation, a 1,000-row heap and full match/unknown
counts. It reads only the fixed NTFS policy registry value, validating DWORD bits including initialization;
disabled/unknown NTFS configuration refuses access-age matching, not creation matching. This config is
not an effective policy guarantee; POSIX/provider timestamp limits remain explicit. The GUI captures the
off-by-default option for each new full/branch worker, offers hidden tree columns and an owned modal
read-only File times query with date kind/day controls, Stop/close joining and stale-signal rejection.
Changed controls cancel/join the previous query. Exact-node activation cannot prepare cleanup. File CSV
adds optional accessed/created ISO columns (empty if absent); folder-only JSON/history is unchanged.

`core.namespace_moves` prepares bounded read-only source/destination plans and executes explicitly
approved same-volume namespace changes. `core.no_replace` captures every ancestor identity and anchors
Windows handles or descriptor-relative POSIX components. Windows os.rename, Linux renameat2
RENAME_NOREPLACE and macOS renameatx_np RENAME_EXCL provide exclusive native rename, without an unsafe
fallback. Revalidation refuses protected/unavailable/incomplete/changed sources and
protected/descendant/colliding/cross-volume targets; outcomes include both affected parents.
Verified post-rename inode receipts permit subsequent hard-link aliases despite rename ctime changes,
without changing the captured tree or ordinary Trash validation. An unexpected receipt attempts
exclusive rollback; failures retain visible paths. Concurrency is not transactional. `gui.namespace_dialog` owns immutable-request preview and approval
workers, exposes every outermost pair in a read-only copyable table, invalidates plans on input changes,
and requires a default-No plain-text question with all eligible pairs in Details. All shared tree,
Search and Largest context routes preserve exact Node selection and reject detached/root/busy scopes.
Options freeze during operations; stop/close cancel and join, while identity guards reject old replies.
Per-item outcomes remain visible, including errors received while closing/joining. Snapshot validation
also rejects changed cloud attributes/link counts even if content dates and lengths stay the same.
The operation worker rescans affected parents outside the current root
and reports counts/errors; after joining, MainWindow invalidates capacity/old analyser replies and
rebuilds the current root, refreshing both affected parents within it. Native macOS remains unverified.

`core.verified_copy` prepares exclusive ordinary-folder copy plans, including cross-volume targets,
and returns CopyProof observations after complete name/count/length comparison and SHA-256 comparison
below 64 MiB. Larger streams remain length-only. Reverification is mandatory before the existing
approved MainWindow Trash route; core copy APIs never remove/Trash/redirect originals. Protected
ordinary sources can be read, without granting Trash approval. Links/special/cloud/reparse/incomplete/
changed/mounted sources and protected/descendant/colliding targets are refused. Partial copies are
retained and named, cancellation preserves originals and failure stops the batch.
`core.copy_io` anchors directories and verifies no-follow source descriptors/path metadata across reads,
uses exclusive creation and bounded chunk reads, rejects destination filesystem/Linux mount changes,
and applies metadata after children. `core.copy_platform` wraps exclusive native Windows CopyFileExW
with PROGRESS_STOP (keeps partial data), bounded ADS queries/comparison, and macOS descriptor fcopyfile
with bounded resource-fork/attribute comparison. POSIX xattrs copy/compare strictly; native APIs have no
unsafe fallback. Files retain platform-supported metadata; Windows directory security inherits its
destination and POSIX setuid/setgid/sticky bits are omitted. Native macOS same-volume copying is
verified on owned CI fixtures; cross-volume and later Trash/redirect remain unverified.
Concurrency is observational, not transactional.

`gui.copy_dialog` reuses the owned namespace-preview lifecycle, refuses same-volume GUI pairs,
shows filename progress and retains CopyResult before queued delivery. Frozen CopyApproval proofs
are offered only after a successful uncanceled batch. No original Trash follows copying automatically.
A separate finish action routes through MainWindow.move_to_trash, existing protected-source
questions, a default-No plain-text copy/Trash confirmation and the existing operation journal.
TrashWorker anchors copied destinations/source parents, re-verifies immediately before each OS
Trash, stops remaining moves on failure, and optionally invokes core.copy_approval.redirect_copy
only after success. Native exclusive junction/symlink creation refuses occupied original paths;
redirect errors retain the copy/Trash receipt and report paths separately from verification errors.
Windows may retain an empty source directory on native junction failure. Destination parents
rescan on the copy worker; source parents rescan after Trash. Declining Trash rescans the current
root. MainWindow tracks path dialogs and joins them on parent close before destroying scan trees.
TrashWorker retains MoveResult before queued delivery; parent close joins it and reports late copy
verification/redirect failures before dismissing the window.


`core.trash_restore` freezes pre-Trash origin/parent identities and prepares only actual recognized
current-user freedesktop destinations with matching percent-decoded Path/DeletionDate receipts.
Linux descriptors/mount IDs anchor files/info/original parents; iterative complete payload snapshots
reuse bounded no-follow bin inventory (100k entries/128 levels), without traversing other bin items.
An explicitly selected plan is fully rechecked before native exclusive restore. Post-rename changes
attempt exclusive rollback; failure reports the actual retained original/Trash locations. Successful
restoration removes only its captured recognized `.trashinfo`; metadata failure reports restored=True
and a retained receipt, never a false payload-preservation claim. The rule in CLAUDE permits only
this scoped receipt cleanup, never payload deletion. Native fixture proof runs without Qt/elevation
in its own Linux CI job. `core.recycle_shell` owns a bounded current-user Shell enumeration, exact canonical original-path /
payload-identity matching and canonical `undelete` through a native context menu. It owns STA COM
initialization, interface/string/menu release and native collision UI without answering it.
`core.windows_restore` captures bounded no-follow payload/receipt/parent observations, rechecks them
before invocation and observes actual restored identity/location and receipt cleanup. It performs
no manual Windows payload or receipt deletion; retained receipts and unconfirmed native completion
remain visible. Native fresh CJK-folder validation confirmed identity/hash/empty-folder restoration
and recorded this Shell's retained receipt. `TrashWorker` captures origins before native Trash and prepares complete frozen inverse plans after
successful receipts. `gui.trash_undo` owns the 8s status-bar offer, frozen root/deadline and timer;
`gui.undo_worker` owns native restoration and new durable inverse approvals. Original audit records
remain intact; new undo records have distinct ids/batches and additive restored outcomes. Captured
parent references avoid GUI tree traversal and detached-path reuse. Offer expiry, new scans/actions,
path dialogs and close discard authority. MainWindow serializes inverse work with scanning/Trash,
postpones automatic source-parent rescans while Undo is offered and joins native work before close.
Late partial/receipt/audit results remain visible in plain text; a replaced tree receives no rescan.
An occupied copy redirect is refused without removing it. Native Windows owned-fixture GUI proof
confirmed button/action/hash/empty-folder/audit/rescan behavior; Native Linux CI verified normal GUI capture, exact private-bin restoration, receipt cleanup/container preservation
and source-parent rescan on fresh fixtures.

`core.duplicate_links` previews exact explicit-keeper replacement pairs without payload reads or
mutations. It freezes path/scan/handle/parent observations and limits selection to 1,000 extras,
refusing protected/changed/special/cloud/already hard-linked decisions and other device/mount rows.
Full verification rereads both main files and every Windows ADS without a large-file length fallback,
checks the original duplicate digest, strict POSIX xattrs and bounded complete native resource forks.
Native macOS attribute payload has a 64 MiB aggregate cap; unavailable complete values are refused.
Cancellation never grants mutation authority. `core.duplicate_link_ops` executes explicitly reviewed
plans with fresh complete group/pair verification, anchored same-volume temporary hard links,
exclusive old-copy backups and exclusive publication. `core.link_io` permits retirement only of the
captured owned backup after complete re-verification and temporary-alias cleanup with another live
keeper name. Windows pins DELETE handles and uses disposition-on-close plus DELETE-sharing ADS
readers; POSIX unlinks only from the captured parent descriptor. Own keeper link-count/ctime changes
are carried forward; unrelated changes stop the group. Exclusive rollback never overwrites arrivals.
Outcomes retain actual published state and backup/alias paths after cancellation or failure. Both
keeper and extra parents need a fresh scan; freed capacity is unknown. The scoped CLAUDE exception
requires explicit review explaining shared future data/metadata and no Trash copy. Native owned
Windows multiple-copy/ADS/rollback/cancel/collision tests passed; Linux CI passed the native executor.
`gui.duplicate_link_dialog` owns frozen bounded explicit-keeper previews with literal path/refusal
tables and default-No review (shared future data/metadata/security; no Trash copy or automatic Undo).
Similar-photo/folder matches never enable linking. `gui.duplicate_link_worker` persists distinct batch
approvals before execution and original-extra-identity per-outcome audits via the additive completed
callback. Approval failure prevents mutation; result-audit failure cancels later work while preserving
published aliases. Both workers retain/guard results and cancel/join on stop or dialog/parent close;
late partials and retained paths remain visible. MainWindow's operation_busy includes owned path
dialogs to serialize scan/Trash/Undo; only the same current root receives a complete post-attempt
rescan, invalidating keeper/extra snapshots, capacity and duplicate decisions. Native Windows owned
CJK/ADS GUI proof verified three aliases, independent original audit identities and full-root refresh;
native Linux CI passed the same owned workflow, audits and complete-root refresh. Native macOS CI
verified ordinary core linking and full metadata; protected GUI approval remains #4.

`core.virtual_disks` discovers recorded virtual-disk extension candidates and bounded current-user
WSL/default Docker locations from `core.virtual_disk_sources`. Iterative per-folder pacing and a
1,000-row largest-file heap retain full discovered/error/omitted counts without retaining every
candidate. Recorded node observations are estimates; outside-provider final-file no-follow metadata
and guarded Windows allocation queries preserve unknown/missing/cloud/link/change state. Paths
merge provider labels but never grant stopped-state/format/ownership or mutation authority. Guest
used bytes and virtual capacity stay unknown; no header/guest reads, launches, mounts or commands.
Native Windows inventory found two backing files without guest launches. The 100,000-candidate
in-memory fixture measured 2.853 seconds and 544,072 additional peak traced bytes for 1,000 rows.
Explicit `core.virtual_disk_info` queries captured ordinary VHD/VHDX headers separately, through
System32-only virtdisk.dll. Nonlinked parent anchors/file pins plus complete before/after snapshots
guard Version2 GetInfoOnly/ReadOnly access NONE and NO_PARENTS. Fixed ABI/version/size/device/vendor/
subtype/loaded checks reject unknown native state and all handles close. Frozen observations expose
provider physical bytes, virtual capacity, disk UUID and fixed/dynamic/differencing/mounted state;
they grant no compaction or stopped-machine authority. Guests remain unopened and their usage unknown.
Native owned fixed/dynamic VHD/VHDX fixtures passed without elevation, exact UUIDs/unchanged full hashes.
`gui.virtual_disks` wraps discovery in an owned modal table and explicit selected-header worker.
Backing-file observations, native capacity/provider bytes and unknown guest usage are separate numeric
columns with literal status/tooltips; unsupported/unknown/errors/counts/coverage stay visible. Only
original scan nodes may activate the tree. Stop/close suppresses late replies and joins both workers;
MainWindow tracks the dialog to serialize scans/file operations and process deferred rescans after
close. Six GUI tests and a fresh owned native CJK VHDX GUI proof preserve bytes/identity/UUID.
`core.virtual_disk_compaction` prepares a frozen read-only plan and executes one reviewed detached
dynamic VHD/VHDX through fixed synchronous CompactVirtualDisk (zero blocks, no guest attachment).
Complete source snapshots/local NTFS/protection and nonlinked parent identities are rechecked before
writable Version2/NO_PARENTS opening; native UUID/type/detachment/capacity are checked again on that
same handle. `core.virtual_disk_runtime` captures bounded native process metadata and fixed WSL
running-list metadata for current-user registrations; known guest/Docker workers, running WSL,
incomplete sources or changed signatures refuse execution. Conservative absence observations also
require user stopped-machine review and cannot prevent other programs starting guests. No UAC,
shutdown, guest launch, arbitrary command or fallback. Attempted/success/allocation/error remain
separate; active calls join, post-success failure cannot hide completion, zero saving is valid and
every attempted outcome requires rescan. Native owned blank VHDX proved zero-saving success and
preserved exact UUID/capacity/file identity/sibling arrivals, with unrelated host runtimes isolated.
`gui.virtual_disk_compaction` owns the selected frozen source's read-only preview, literal full-path/
UUID/capacity/backend review and default-No stopped-machine confirmation. Durable approved events
precede the native executor; actual outcomes persist before queued delivery and compacted audit
status survives later observation/audit failure. Preview/native close joins, canceled reviews grant
no authority and unobserved actual outcomes are reported before dismissal. The outer inventory owns
the child lifetime; attempted writes clear observations/disable stale review and trigger a complete
captured-root rescan after close. MainWindow serializes operations and expires prior Trash Undo on
execution request. Permission errors reuse manual administrator restart with fresh scan/approval;
no plan crosses that boundary. Seven GUI cases and native blank CJK VHDX execution/audit/UUID/capacity
proof passed, with the known unassigned fixture's unrelated host runtime isolated. Populated
privileged guest-data preservation remains #59.
Unsupported formats need their own backend rather than passing them
to VHD-only Windows tools.

## 3. Entry points and public interfaces

`tools.windows_owned_volume` provides administrator-only fresh validation VHDX/NTFS fixtures, never
an existing path/disk selector. It enables only the current token's volume privilege, creates a fresh
UUID and derives the physical number from its live virtual-disk handle. A fixed PowerShell script
refuses boot/system/nonvirtual/non-RAW/nonempty/wrong-size disks before formatting; Windows assigns
the drive letter. Every validation mutation rechecks handle/device mapping and OS volume GUID.
`validate_windows_volume.py` checks capacity/allocation/hard links/compression/sparse savings and
`windows_bin_probe` confines GUI surveys/questions and real native Shell emptying to the owned drive.
It verifies No, changed approvals, two questions, close guards and metadata refresh. Detach joins
before captured scratch/image cleanup; a failed detach retains the image. The dedicated Windows CI
job saves JSON for seven days. Native Windows private-volume proof passed, including exact capacity,
allocation/hard-link bounds/compression/sparse guards, No/arrival refusal, two questions and one scoped
native bin-empty call, active-close refusal, joined metadata refresh and owned detach/cleanup. The
unreadable System Volume Information branch retained incomplete/null remainder; zero OS bin items
still had observed metadata bytes, so bin allocation remains a subset. The new `windows_recovery_probe` measures individual one/last/all hard-link names and compressed/
sparse files, recording OS free before Trash, after Trash and after native emptying, plus reviewed
savings bounds and the remaining alias identity/full hash/link count. It shares a joined private-bin
dialog with native device/GUID checks, one exact drive and two questions. Each completed case saves
phase evidence; raw free deltas do not independently measure file data or directory/bin metadata.
Native one/last/all hard-link, compressed and 8 MiB sparse recovery passed on both fresh formats
with confirmed cleanup; observed sparse net/empty recovery was 65,536 bytes. Provider placeholders, shared
extents, independent reserved bytes and APFS stay unverified/unknown. Phase JSON survives later native
failures, with detachment/cleanup confirmed only on complete success; the private-bin probe reuses the
application's bool/tuple-compatible Qt Trash receipt adapter.
Validation ledger serialization retains scalar coverage counts and the unsafe-folder count rather
than deep-copying/serializing Node authorization graphs; unknown buckets remain null.
The validation fixture accepts only a fresh VHD/VHDX format choice, never an existing image selector.
Successful body/detach/handle-close may enter a callback guarded by original scratch/image identities,
anchors and file pins; failed bodies skip it, failed callbacks retain the image and initial stat
failure still closes the creation handle. `windows_compaction_probe` captures fresh guest full main/
ADS hashes, namespace/IDs/lengths/link counts and written/zeroed blocks, then uses production preview/
runtime/executor and durable operation-worker audit while detached. Only the captured UUID is
reattached read-only without a drive letter/formatting and compared through its original volume GUID.
Read-only detach failure retains the image. CI runs both fresh formats and saves separate phase JSON;
populated VHD/VHDX native proof passed with full guest records/audit and confirmed cleanup.
Observed backing reductions were 31,518,720 bytes and zero respectively. Each format has a separate command
step so PowerShell cannot mask earlier failure. After setup/detachment, the original pinned backing
identity is queried read-only and its current UUID becomes the fresh review baseline; creation UUID
is retained separately as evidence. Production frozen UUID/snapshot checks remain unchanged.
Guest usage/guaranteed recovery remain unknown.

The supported core library imports, result fields, ownership and error/cancellation contracts are
documented in [the core API guide](docs/core-api.md); private helpers and packed snapshots are internal.

- `je-file-tree [folder]` (the `gui-scripts` entry `je_file_tree.gui.app:run`), `python start_file_tree.py [folder]`
  and `python -m je_file_tree [folder]`: all three call `app.run()`, which opens the window and scans `folder`
  right away if given (`test/test_start_script.py`).
- `je-file-tree-cli scan <root>` (`project.scripts`: `je_file_tree.cli:main`) and `python -m je_file_tree.cli`
  scan/export/compare without Qt imports or a display. Stdout/stderr use fixed newline-delimited JSON;
  exit codes are 0 complete, 1 partial, 2 arguments, 3 I/O/invalid saved scan, 130 interrupted. SIGINT
  cancellation returns and exports the partial snapshot; a second signal aborts. Each export is atomic
  independently. The console offers no filesystem removal.
- `python tools/build_nuitka.py [--onefile | --app] [Nuitka options]`: compiles `start_file_tree.py` into
  `build/<mode>/`, copying Qt's translation catalogues listed in `qt_translation.CATALOGUES`.
- `je_file_tree.core.scanner.scan(path, *, options, progress, cancel)` → `ScanResult(root, errors, elapsed)`.
- `je_file_tree.core.analysis.summarise(root, limit)` → largest files and per-extension totals in one pass.
- `je_file_tree.core.treemap.layout(root, rect, ...)` → `Tile`s; `export.export_*` write CSV / JSON.
- `python tools/measure_scale.py <root>` measures real scans with explicit memory/time budgets, optional
  Qt painting/live-model refresh and bounded duplicate hashing. Partial measurements are identified.

## 4. Main flows

**Scan.** `MainWindow.start_scan` opens the results page with its `ScanBar` and starts a `ScanWorker` (a
`QThread`) running `scan()`: worker threads (default 4, measured) share one stack of folders; each lists a
folder with `os.scandir`, turns entries into `Node`s without following links, and pushes subfolders back.
Folders matching `ScanOptions.exclude` (`exclusions.exclusion_test`: name patterns, or one folder by path;
the setting `exclusions`) are listed with `error == EXCLUDED`, size 0, and never read or counted as folders.
A file's size on disk (`Node.allocated`) comes from `allocation.allocation_for(root)`: `st_blocks` on POSIX;
on Windows by default the size rounded up to the volume's clusters, the system asked for compressed or sparse
files, 0 for files whose data is elsewhere (cloud placeholders, offline), never opening those.
Each finished folder's files are added to the running totals of every folder above it. The root is handed
out first (`started`), so `FolderTreeModel` shows the tree in live mode while it grows: each folder's
children are a sorted copy frozen until the next `refresh()`, which the window calls every 700 ms (a layout
change that moves persistent indexes, so expanded folders, selection and scroll position survive). The
calling thread reports progress about ten times a second and watches the cancel event. When every folder
is read, totals are added up again bottom-up and children sorted largest first; `analyse()` (largest
files, per-type totals) runs still off the GUI thread and `succeeded(ScanOutcome)` ends live mode. Stop
raises `ScanCancelledError` carrying the partial tree (unread folders marked `NOT_SCANNED`), shown as an
incomplete outcome. Signals of a replaced worker are ignored.

**Background work gives way.** In CPython one thread runs Python at a time, and every call Qt makes into
Python (each cell the folder tree paints, every event handler) needs that lock, so a worker walking the
tree used to make the window queue behind it. `core.pacing.WINDOW` is a gate: `scan_worker.pace_workers`
(called once by `app.main`) closes it when the GUI thread's event loop wakes (`awake`) and opens it when the
loop is about to wait (`aboutToBlock`). Every walk over the tree calls `pacing.give_way()` once per folder
(the scan's workers, `_add_up`, the analysis, clean-up, search, compare, export, each file hashed), which
waits while the gate is closed, at most `PAUSE_LIMIT` (50 ms) and never on the thread that closed it, so
nothing can hang on it. Emergency/destruction joins go through `scan_worker.wait_for`, which opens the
gate first. Normal whole-root scan replacement uses `worker_lifecycle.ThreadFence`: GUI-owned timers poll
`QThread.wait(0)` until owned scans/watchers/gentle work have fully joined, then dispatch only the latest
request. Pending replacements retain the ordinary scan/source-operation exclusion and Stop discards them.
Old workers stay owned until joining; no thread is terminated. Background receipts are finalized before
foreground dispatch. Folder validation runs in ScanWorker. Welcome DriveWorker discovers volumes once
per coalesced request and publishes immutable scalar DriveSnapshot values; language/unit/action updates
render the cache without storage I/O. Tab destruction still cancels/joins these owned workers.

**Show.** `ResultsView.show_outcome` hands the tree to `FolderTreeModel` (which wraps the `Node`s, sorts
per folder lazily, and never copies), the tables to their models, and the root to `TreemapWidget` (layout
and drawing cached in a pixmap, recomputed on resize or zoom). Selecting anything selects it in the tree and
outlines it in the treemap.

**Free space.** Context menu or Delete → a first question when system or program folders are among the entries
(`protected.protection_of` against `protected_places()`, read once from the environment; the most specific
place decides, temporary folders are free) → one confirmation → background validation and
`QFile.moveToTrash` per entry → `ResultsView.forget` → affected-parent rescans. The tree and the largest-files
list allow several rows to be selected; the entries acted
on are `node.outermost` of the selection without the scanned folder (an entry inside a chosen folder goes with
it). `FolderTreeModel.remove` detaches each node and subtracts its totals from every folder above; the
largest files, per-type and per-age totals and treemap are updated once before the rescans. Entries the system
refuses stay and are named in a warning.

For platform failures, `TrashWorker` calls the read-only `core.lock_holders` diagnostics: Windows
Restart Manager registers up to 256 scanned files; Linux compares `/proc/*/fd` identities. Warnings
name observed holders and disclose incomplete visibility. Cancellation stops additional queries;
no process is shut down, and macOS reports that diagnosis is unavailable.

`Node.snapshot` holds compact packed device/file identity, kind, size, nanosecond timestamps, attributes
and link count (`core/snapshot.py`). Windows listings lack identity, so the scanner makes an additional
no-follow stat (10k calls measured at 0.67 s). After confirmation, `TrashWorker` runs `core.operations`:
ancestors must keep their identity and not become links; resolved protection must match the approval;
each selected entry and all folder descendants must retain metadata and child names. A changed/missing
or incomplete entry is skipped; successful, skipped and platform-failed entries are reported separately.
The GUI detaches only moved entries, keeps failed entries and queues rescans of affected parents. Scans
and model changes are blocked during the batch; Stop cancels remaining entries and close waits for it.
These are immediate no-follow checks; Qt's path-based Trash call is not an atomic transaction with the
identity check, so it does not provide an OS guarantee against concurrent malicious path substitution.

**Audit.** MainWindow captures rule/manual/duplicate reasons in a `JournalApproval`. `TrashWorker`
writes all approved events before acting and appends each platform result immediately, preserving Qt's
optional destination in `MoveReceipt`/`MoveResult.destinations`; skipped entries are appended too.
A failed approval write prevents moves, while a failed result write preserves the observed success,
cancels remaining moves and warns about incomplete history. `core.operation_journal` owns atomic
append-only daily/4 MB JSONL segments under Qt's application-local data directory, with native
cross-process locks, fsync-before-replace and 90-day/50 MB retention of owned segments only.
`RecentActions` loads metadata on a worker, shows the latest 500 outcomes and reports damaged/unavailable
segments. An approved-only record is unknown after a crash; it is not a restoration receipt. CSV
exports are atomic worker writes with home-prefix redaction. Close joins all reads/exports.

**Chart tab.** `ChartStack` holds the treemap, the bar chart (`BarChartWidget`: the `MAX_BARS` largest
entries of one folder, the rest on one line), the sunburst (`SunburstWidget`: `core.sunburst.layout`
gives arcs as fractions of the circle, at most `RINGS` rings, arcs thinner than `min_span` and past
`max_segments` left out, drawn into a cached pixmap), and the hierarchy tree (`TreeDiagramWidget`:
`core.tree_layout.layout` returns at most 240 folder cards, expands branches and pages wide sibling lists;
the GUI caches that layout and scrolls/zooms it). It shows one at a time, the treemap first
(`charts.DEFAULT_MODE`); the mode and tree direction are saved in `chart_mode` / `tree_orientation`.
All views offer the same interface (`set_view_root`, `zoom_out`, `set_selected`, `invalidate`,
`node_clicked`, `view_root_changed`, `context_menu_requested`); when one moves to another folder the stack
moves the others and signals the page once, so the results page drives the stack as a single chart.
The treemap draws `levels` levels (2 unless chosen, saved as `treemap_levels`); `treemap.layout(header=…)`
keeps a strip at the top of every opened folder that is at least three strips wide and tall, where the
widget prints the folder's name and size; colours come from the file type or, with `treemap_colours` =
`folder`, from a hue per top-level folder (the legend is hidden then). No tile is narrower than `min_side`
(the widget passes `MIN_SIDE`, 14 px): a folder's entries too small for that share one *group* tile
(`Tile.grouped` entries, `Tile.grouped_size` bytes, its node the folder), drawn grey and hatched, and a
folder opens only when at least one entry in it gets a tile of its own.

**Lists for one folder.** *Largest files*, *File types* and *Age* show the outcome's whole-scan lists, or,
with *Selected folder only* (the tab bar's corner), `analysis.summarise` of the folder selected in the tree,
run on an `AnalyseWorker` 250 ms after the selection settles. The outcome keeps the whole scan's totals up to
date after a move to the Recycle Bin, so switching back needs no recount.

**Rescan one folder.** The context menu's *Rescan this folder* runs a `ScanWorker` on that branch alone,
then `FolderTreeModel.replace` swaps it in (`Node.replace_with` corrects every total above it; persistent
indexes inside the old branch are dropped, the rest follow their nodes) and an `AnalyseWorker` recomputes
the largest files and per-type and per-age totals of the whole tree off the GUI thread.

**Search.** The Search tab (`SearchPanel`, Ctrl+F; conditions in `SearchFilters`, saved searches as JSON in the
`saved_searches` setting) waits for typing to pause, then runs `core.search.search` with a `Query`
on a `SearchWorker` thread: names are matched case-insensitively (plain text anywhere in the name, `*`/`?`
patterns against the whole name, several separated by `;`) and the 1,000 largest matches are shown with the
count and size of all. A new search stops the one before (it checks once per folder) and only the latest
result is shown. The box is disabled while a scan fills the tree; the search runs again after a scan, a
move to the Recycle Bin or a folder rescan.

**Clean up.** The Clean up tab has two pages. *Suggestions* (`CleanupPanel`): after every scan a
`CleanupWorker` runs `core.cleanup.find_cleanup`, one walk that tests each folder against the rules' path
endings (indexed by their last name) and each file against their name patterns, suggesting a matching
folder whole without looking inside it, then adds `empty_folders` (only folders known to be empty, the
outermost); it runs again after a move to the Recycle Bin or a folder rescan. The rules are data
(`cleanup.RULES`). *Duplicates* is the page below; both list their groups with `grouped_list`.

Before matching, `coverage_of` checks excluded, unread and inaccessible folders and propagates unknown
coverage to ancestors. Folder nodes start with `NOT_SCANNED`; successful reads clear it, hidden omissions
and failed entry stats leave the parent incomplete. A matching incomplete folder is never proposed whole;
empty-folder detection also requires successful reads. The worker returns coverage with its groups;
the panel displays a coverage banner and disables bulk selection on partial scans. Refresh discards old
rows immediately and ignores replaced workers; acting on incomplete branches requires their rescan.

Group selection emits `CleanupPanel.review_requested`; `MainWindow.move_to_trash` also intercepts manual
selections containing a current suggestion. `gui/cleanup_review.py` shows a lazy checkbox table of all
outermost proposed entries, their rules/reasons/consequences, metadata and protection. Unchecked entries
never reach the existing protection and Trash questions; rejection does nothing. A cancellable estimate
worker updates the count and logical/allocated/recovery/free-space fields; Continue waits for that result.
Full row explanations appear below the table and containing folders can be opened from the dialog.

**Duplicates.** The Duplicates page (`DuplicatesPanel`) runs `core.duplicates.find_duplicates` on a
`DuplicatesWorker` only when asked: files of the same size (1 MB and up unless another size is chosen) are
hashed on a thread pool, first their first 64 KB, then, for those still alike, the whole file; hard links
(same device and file number) count once. Progress reaches the window at most ten times a second; Stop is
checked before every file and every 1 MB. The groups are dropped on a new scan and pruned (`Node.is_in`)
after a move to the Recycle Bin or a folder rescan.

**Compare with a saved scan.** A saved scan is the Folder tree JSON export (`"format": "file-tree/1"`, with
`"saved"`, the time it was written). *Compare with a saved scan…* hands the file to a `CompareWorker`, which
reads it (`compare.load_saved` checks every field and raises `SavedScanError` with the reason) and
matches folders by their path below the scanned folder (`folder_key`, case-insensitive where the file
system is). The Changes tab, hidden until then, lists changed, new and gone folders; the comparison runs
again after each scan, move to the Recycle Bin and folder rescan until *Stop comparing*. Reading and
comparing took 0.68 s and 0.49 s on 86,000 folders, hence the worker.

**Export.** CSV rows and nested folder JSON stream into a temporary sibling. JSON uses an iterator stack
proportional to depth, never a second folder tree or a recursive JSON encoder. Only a successful close
replaces the destination; failure preserves its existing contents and removes the temporary file.

**Taskbar (Windows).** `app.main` first gives the process FileTree's own AppUserModelID (`icon.claim_taskbar_button`), so run from Python its windows get their own taskbar button with FileTree's
icon instead of being filed under `python.exe`.

**Administrator rights (Windows).** Before the window opens, `app.main` asks `elevation.relaunch_elevated`
to start a second copy through the "runas" verb (the UAC prompt) unless the `ask_admin_at_start` setting is
off or FileTree already is elevated; if that copy starts, this one exits, and a declined prompt just
continues. The File menu and the Problems tab (shown when folders were denied) offer the same restart, with
the scanned folder as its argument. A built program restarts itself; from Python it is `-m je_file_tree`.

**Language.** `i18n.set_language` + `qt_translation.apply_qt_translation` (Qt's own buttons and dialogs),
then every widget's `retranslate()`. The choice is stored in `QSettings` with the unit, window layout and
recent folders.
English, Traditional/Simplified Chinese, Japanese and Korean have the same complete key/placeholder
contract. ja/ko system locales select their language on first use. Native Qt ja/ko catalogues provide
standard buttons/dialogs and all four non-English catalogues are required in runtime/package checks.
README/Nuitka parity and generated screenshots cover all five languages; OS fonts provide glyphs.
locale_font chooses installed Japanese/Korean UI families on each retranslation while preserving
the captured system size/style, restoring that base for other languages. It neither bundles nor
installs fonts; missing families retain normal system fallback across workspace and result tabs.

## 5. Extension points

- **A language**: a table in `je_file_tree/gui/strings.py`, an entry in `i18n.LANGUAGES`, a Qt catalogue in
  `qt_translation.CATALOGUES`, a README translation and a screenshot (`tools/make_screenshots.py`).
- **A file-type group**: `analysis.CATEGORY_EXTENSIONS`, a colour in `treemap_widget.CATEGORY_COLOURS`
  and a `category_<name>` text in every language (tests check all five).
- **An export format**: a function in `core/export.py` (atomic write) and an action in `main_window.py`.
- **A result tab**: a widget added in `ResultsView._assemble`, fed from `ScanOutcome`.
- **A chart view**: a widget with the treemap's interface, added to `charts.MODES` and `ChartStack`, with
  `chart_<mode>` and `chart_<mode>_tip` texts in every language (the mode button appears by itself).

## 6. Cross-project boundaries

`tools/validate_windows_share.ps1 -DisposableRunner` is a hosted-Windows-only native validation
entry point, never a caller-selected source/share cleanup API. It persists `windows-share.json`,
including transport scope, completion/failure and owned cleanup; `windows_share_probe.py` is its
receipt-checked helper. Mid-scan disconnect removes only the newly created share registration,
after pausing new reads; it never deletes scanned payloads. Loopback timings do not imply remote
performance, and source preservation does not establish complete coverage after native failures.
Only the fresh denied-directory fixture's DACL is initialized before capturing the native denial
baseline; original/restored descriptors are retained and exact equality is required. Set-Acl's
legacy-to-automatic inheritance conversion must not be counted as successful restoration.
Reviewed native SMB proof at `5034a0c` records four complete UNC/mapped one/four-worker parity
cases across 1,026 files, matching 4,096-byte allocation units, four denied-listing cases, and a
real share removal after six files were observed. The latter records 254 errors/incomplete coverage
and zero empty-folder proposals; exact DACL restoration and final source identity/hashes passed.
`docs/updates/share-20261009-native.json` retains provenance and observed timings, with no slow
remote-link or concurrency speed claim. Both push/PR Tests runs at that head passed all 14 jobs.

The owned macOS image tool retries hdiutil detach exit 16 at most three times, rechecking the exact
private image/device/mountpoint before each call. Other native failures and ownership changes refuse
immediately; no force option or host unmount is used. Native image absence and unmounted fixture root
must still be verified before cleanup. Failed APFS cleanup retains bounded native stdout/stderr and
the disposable scratch path; retained fixtures never become a successful cleanup claim.

`tools/package_posix.py` packages completed native compiler outputs without launching FileTree.
`gui/icon.icns_bytes` supplies native ICNS with Qt-encoded PNG blocks at 128/256/512/1024 pixels;
build_nuitka passes that file directly on macOS, avoiding optional external PNG conversion.
Linux x86_64 uses fixed SHA-256-pinned appimagetool 1.9.1 and type2 runtime 20251108, supplied explicitly,
with complete Qt runtime/catalogues, generated icon and literal AppRun. The tool runs without FUSE;
the owned image is extracted into fresh scratch and the full AppDir compared. macOS uses fixed
`/usr/bin/ditto` to archive/extract an identity/version/executable-checked bundle; internal framework
links and metadata are copied into an owned canonical FileTree.app, compared before archiving, then
compared again after extraction. The compiler's actual start_file_tree.app stays untouched. Internal
links remain links and external/special entries are refused. Every source hash/mode/identity/time
and anchored ancestor is rechecked. Artifact/proof publish as one exclusive fresh directory; arrivals
and source changes refuse publication. Proof distinguishes extraction/source checks from app launch,
signing/notarization, Finder consent and publishing. `.github/workflows/posix-build.yml` is a read-only
reusable native build for a checked-out ref. Desktop builds retains development artifacts; Release
calls it only with `FILETREE_POSIX_RELEASE_VERIFIED=true` after #4, attaching both native archives only
on success. The variable is not set by these tools. Compiled Linux autostart uses the runtime's
absolute ordinary executable `APPIMAGE` origin instead of an ephemeral mount; source and other
platform registrations ignore that environment variable.

`tools/build_msi.py` compiles one complete Windows standalone `.dist` inventory with pinned WiX
6.0.2 into an atomic versioned x64 MSI. `tools/installer/FileTree.wxs` fixes the upgrade identity,
machine-wide Program Files destination and advertised Start-menu shortcut, harvests every runtime
file and defines no custom actions/startup registration. MSI version limits and no-follow payload
identities/hashes are rechecked before publication; Windows Installer validation is not suppressed.
The existing release tag's standalone build supplies the MSI; the release uploads/downloads it
beside the EXE/ZIP. `tools/validate_msi.ps1` installs only fresh disposable hosted-runner fixtures,
refuses existing directories/shortcuts/related products, checks hashes and uninstalls its exact
hash-checked MSI. It never executes the fixture PE or proves compiled-app launch; native phase/log
evidence is retained. An owned 1.2.3-to-1.2.4 upgrade changes a library fixture and requires exactly
the new related product/version, unchanged source hashes and removal of the upgraded installation.
Store publishing and signing require external accounts/credentials.
`tools/install_compiler.py` is the shared pinned desktop compiler/runtime installation contract
for native Windows/Linux/macOS. Compiler runtime locks retain exact versions and all published
non-yanked wheel SHA-256 values. `tools/lock_compiler_wheels.py` regenerates only the three
fixed runtime locks from bounded PyPI metadata with four read-only request workers; unsupported
pins/releases, changed lock inputs and missing/invalid hashes fail before writes. It downloads or
executes no packages and leaves the isolated PyPI publishing lock unchanged. Native pip still requires
hashes and wheels only; only the separately pinned Nuitka compiler may be an sdist.
Release and Desktop builds share this installer. The latter keeps unsigned compiled ZIP/MSI and owned installation
evidence without a release token. `validate_msi.ps1 -DisposableRunner -CompiledPayload` accepts only
the fixed hosted workspace's sole standalone output, copies no-follow contents into fresh runner
scratch, verifies every original/installed hash, checks a package-version upgrade, and uninstalls
only the captured MSI. It refuses existing products/shortcuts and never launches the application.

`tools/prepare_packages.py` prepares unpublished winget/Scoop/Chocolatey review drafts for a canonical
MSI version from the exact ordinary MSI and complete standalone ZIP. `tools/msi_metadata.py` uses
read-only Windows Installer database access, a fixed parameterized property query and bounded summary
metadata; no install session or custom action is run. Identity/version/architecture/upgrade identity,
runtime/plugin/catalogue ZIP layout and before/after SHA-256 identities must match. A fresh output
folder is published exclusively under an anchored parent; existing or concurrent arrivals are retained.
Draft provenance records actual hashes/ProductCode and published=false. CI archives drafts; the release
attaches their ZIP without store credentials or submissions. URLs require those exact published assets.

`core/mft.py` is the stdlib-only NTFS 3.1 raw metadata foundation: immutable FILE segments,
sequence-qualified names/attribute-list entries, resident sizes (never DATA payloads), nonresident
VCN runs/allocation and distinct FILETIME dates. Record sizes, USA arrays, forms, lengths, name
offsets, instances, mapping widths, signs, extents and list counts are bounded and fail closed.
Sparse holes do not alter previous LCNs; extension sizes remain unknown outside LowestVcn zero.
Known FILE system/view-index bits are retained without treating view indexes as directories;
unknown flag bits are refused alongside the existing geometry and identity checks.
Zero-link live records are retained as metadata; formatted unused records may have sequence zero.
Only independently checked live names/parents/native directory visibility can become tree entries.
The parser performs no volume I/O. `core/mft_reader.py` owns an exclusively read-only raw volume
handle with bounded aligned reads, checked NTFS 3.1 geometry/physical mapping, streaming batches and
an LRU record cache. It checks extension sequences/base ownership and refuses nested/split lists.
No elevation/privilege changes, volume mutations or public DATA payload access are provided. This
metadata reader connects to `scan` only through off-by-default ScanOptions.experimental_mft. The
serial core/mft_scan candidate requires ordinary visible directory entries and per-path no-follow
stat authority before matching raw sequence/name/parent/date/link/type/size metadata. Only the known
NTFS internal 0x10000000 DIRECTORY bit is normalized for comparison when native listing and stat
both independently identify an ordinary nonreparse/noncloud directory. Full snapshot attributes
are retained; regular files, unknown bits, identity/time changes and other attributes still refuse. Shared Node
helpers retain ordinary allocation, owner, exclusion, hidden, link and hard-link semantics. Ancestors
are pinned; worker pause/cancel checks precede entries and attribute-list extensions. Native reader
and mount observations reverify before completion. Success/cancellation adopts a sorted staged tree
into the single on_root object; unsupported/raw failures discard it and restart ordinary traversal
after checking root identity, so progress can restart. User callback errors propagate without fallback.
ScanResult.backend identifies ordinary or the explicit mft audit; raw I/O stays serial despite workers.
Large-real-drive MFT parity and throughput remain required before considering default enabling.
Candidate refusal logs a bounded metadata-only reason at DEBUG; default logging remains quiet. Native
private-image validation enables those diagnostics, including directory/stat ID/attribute/time values,
so an ordinary fallback never supplies parity evidence without the actual refusal being inspected.
`tools/validate_mft.py` accepts only a new owned private
NTFS image, compares native identities/names/sizes/allocation/dates and preserves main/ADS payloads;
CI retains phase evidence. Synthetic tests are not proof of native metadata parity.
`tools/mft_tree_probe.py` compares ordinary versus explicitly selected audit snapshots, owners,
allocation, hard-link accounting, hidden/excluded/link coverage and cancellation on that private image.
Three whole-private-drive pairs retain medians without extrapolating to large real volumes. Each
owned-folder/options/DACL comparison requires the actual MFT backend. Whole-private-drive pairs
also validate a permitted ordinary fallback when Windows-managed metadata refuses the audit;
every Node/snapshot/coverage/accounting field and the single published root must still agree.
The evidence names the actual backend and separates requested-audit timings from actual MFT
samples; no successful MFT sample means its median is null. Completed denied/cancel/drive phases
are retained immediately, including later failures. Production time/identity checks remain strict.
Each comparison measures both complete calls with perf_counter, avoiding zero-duration baselines from
the coarse Windows clock used by older runtimes. The ACL child receives only the fixed Windows
PowerShell system Modules directory in PSModulePath; parent environment and host settings remain
intact, and incompatible inherited PowerShell 7 modules cannot override the native ACL cmdlets.
An owned denied-listing branch freezes its original DACL and restores it in finally, including failed probes;
phase evidence retains the exact original/restored descriptors before enforcing equality, so failed
native restoration cannot be mistaken for completed validation or lose its permission metadata.
The fixed ACL script preserves the captured inheritance model: ordinary Set-Acl handles an already
auto-inherited DACL; legacy non-auto-inherited fixtures use System32 SetFileSecurityW with only
DACL_SECURITY_INFORMATION, without propagating to children or writing owner/group/SACL sections.
This use of the obsolete API is confined to the owned fixture because Set-Acl converts the legacy
model. Exact descriptor equality remains mandatory; no AI flag or ACE differences are ignored.
The fixed mft_fixture_acl.ps1 additionally requires the exact fresh path pattern, volume GUID, unique
fixture label and nonreparse directory before ACL access. It denies only LIST_DIRECTORY on that owned
folder. Phase evidence retains comparisons/refusal and original payload/ADS identities/hashes; no host
ACL, privilege change or source removal occurs. Native artifact review is required before parity claims.
The newly created fixture symlink freezes its complete no-follow snapshot and actual readlink target
before scanning. Final equality preserves native Windows namespace prefixes and refuses replaced
identity/type/metadata or changed targets; comparing against the input display path is insufficient.
`core/windows_directory.py` streams bounded FILE_ID_EXTD_DIR_INFO under ordinary scandir listing
permission, checked native file ID/volume and a no-follow handle pinned against rename/delete.
It rejects unsafe/corrupt chains, reparse/cloud directory scopes and changed identities, propagates
worker checks, and closes only its own handle. Callers must anchor ancestors. It makes no raw-volume
or privilege calls; private-image validation compares native names/IDs/sizes/attributes/birth/modified
dates across a reply larger than one buffer. Directory allocation is retained separately. Node/options
validation passed on owned native fixtures; large-real-drive MFT parity/throughput remain
required before considering default enablement.
Reviewed evidence in docs/updates/mft-20261009-native.json comes from successful native run
37808218838/job 113417986654 at 85490ec (Windows administrator, Python 3.12, fresh 512 MiB NTFS image).
It proves 238 raw/native observations, five actual MFT options comparisons, actual denied-listing
incomplete coverage with exact DACL restoration, counted single-root MFT cancellation, original
source/ADS/payload and exact symlink snapshot/target preservation, and completed image cleanup.
Three whole-private-drive comparisons proved ordinary fallback parity after System Volume Information
listing/path modification times disagreed. Ordinary/requested-audit medians were 0.0067914/0.0114338 s;
all three actual backends were ordinary, so successful whole-drive MFT samples were zero and the MFT
median is null. Those timings do not prove MFT throughput or extrapolate to large real drives. Default
enablement remains false. This native evidence does not substitute for owner desktop/cloud/UNC/signing
or same-device macOS/POSIX mount validation.
Raw resident DATA allocation is zero separate clusters. Its logical byte length and bounded
ValueOffset..RecordLength capacity (including padding) are distinct. FILE_STANDARD_INFO may report
the resident space, not logical length. Diagnostics preserve these fields separately and require
exact native capacity comparisons; a size/truncation matrix must pass before Node construction.

The GUI entry point accepts `--background` for an explicitly enabled monitor. It skips elevation
and hides the workspace only when the saved opt-in configuration and native system tray are usable.
The flag alone never enables monitoring. Window close may keep an opted-in monitor in the tray;
`Workspace.quit_application` is the explicit exit boundary and joins every owned worker.
Per-user login registration passes only absolute FileTree launcher arguments and `--background`.
Its native entry names and strict ownership marker are persistent removal contracts; app preferences
never substitute for actual registration or authorize overwriting another application's entry.
Saved history keeps its existing folder-JSON format and optional versioned `recurring` scalar header.
Historical candidate metadata never reconstructs operation Nodes or approves actions; rule fingerprints,
physical root identity and dated schedule receipts are comparison/expiry contracts only.
`recurring.binding_status` checks small schedule/policy/receipt metadata without a tree walk;
`proposal_status` additionally checks the whole captured tree and belongs on a worker. Workspace-only
report viewing leaves the standalone create_window factory passive. Session reports are not persisted
as actions; only bounded observation baselines use the existing history format/retention contract.
Optional `MainWindow.move_to_trash(..., proposal=RecurringReview)` requires matched current nodes and
dated metadata, reuses the same editable queue/confirmations and never grants historical source authority.
`operations.validate_tree(root, cancel=...)` performs a read-only native snapshot/name recheck on a worker;
it does not replace immediate per-item guards or authorize mutations. A separate QSettings instance is
required for worker metadata reads, including integrations supplying explicit INI/plist/registry groups.

None. FileTree is standalone: no other repository imports it or calls its command line, and it depends on
no other repository in the workspace — only on PySide6.

Outside the workspace it is published as `je_file_tree` on PyPI (command `je-file-tree`): the names
`file_tree` and `file-tree` belong to FSL's `file-tree`, which installs a module and a command of that
name, so they must not come back. `.github/workflows/release.yml` releases on every pull request merged
into `main`: `tools/bump_version.py` raises the version in `pyproject.toml` and
`je_file_tree/__init__.py` together, the sdist and wheel go to PyPI (secret `PYPI_API_TOKEN`; the job
stops before pushing anything when it is missing), and a Windows runner builds `FileTree-<version>.exe`
with `tools/build_nuitka.py --onefile` and a separate standalone build for the GitHub release.
`tools/package_standalone.py` atomically archives the sole complete Windows `.dist` folder with all
libraries/plugins/catalogues into a versioned ZIP; the workflow requires both artifacts and downloads
both before publishing the EXE and ZIP together. The job that holds the token installs
nothing but `.github/requirements/publish.txt` (`build`, `twine`, the build backend `setuptools` and
what they need): wheels only, at locked hashes, generated from `publish.in` beside it, before the
version is pushed. It builds with `python -m build --no-isolation`, so the backend is that locked
`setuptools` and nothing is downloaded during the build; the lock has to satisfy
`build-system.requires` in `pyproject.toml`. `test/test_workflow_actions.py` fails when that job runs
any other `pip install`, builds with isolation, or when the lock does not satisfy
`build-system.requires`. The source distribution carries no tests (`MANIFEST.in`,
`test/test_sdist_manifest.py`).

## 7. Design constraints

- Scanning speed, measured on an SSD with a warm cache: 62,000 files in 0.67 s with 4 threads (1.27 s with
  one); 740,000 entries in 6–8 s; analysis 0.65 s; treemap layout under 0.1 s (at most 20,000 tiles).
- The window during a scan (125,000 entries, the folder tree repainted every 50 ms): 37 ms per repaint as
  when idle, against 80 ms, and up to 2.1 s while the clean-up suggestions ran, before the workers gave way;
  the scan itself took as long either way with an idle window (2.6 s).
- Memory: about 250 bytes per entry (740,000 entries ≈ 185 MB); only the root stores a full path.
- System-drive check (U-20261007-01): 2.02 million entries / 57.95 s with two workers, 634 MB resident
  memory (about 301 incremental bytes/entry); 768 MiB diagnostic budget. Analysis/search about 2 s;
  compact streaming folder JSON 92.8 MB / 4.33 s. Unreadable branches remain unaccounted.
- With identity snapshots (U-20261007-03), the same system drive takes 207.60 s for 2.02 million entries
  with two workers, 872 MB resident memory (419 incremental bytes/entry). Snapshot storage is 76 packed
  bytes / 109-byte Python bytes object plus an 8-byte Node slot. Diagnostic budget: 1 GiB / 240 s.
- Links are never followed; unreadable folders are recorded, never fatal.
- Nothing is deleted permanently; every move to the trash is confirmed.

## 8. When to update this file

When a module is added, removed or changes layer; when a flow in §4 changes; when an extension point or a
constraint changes; when another repository starts depending on FileTree (§6).

The 64 MiB sparse fixture reported successful Qt Trash but no native bin item; its emptying was
not approved or claimed. It remains in the allocation proof; recovery now uses a separate 8 MiB
sparse fixture. Post-Trash pending records persist actual receipts/free/bin metadata before native
emptying authorization, including an explicit incomplete phase when counts differ.

`core.multi_scan.scan_roots` assembles up to 256 sequential normal crawler results under an empty-
named pathless virtual Node (no extra per-node field). Exact duplicate/ordinary overlaps collapse,
while native mount boundaries or different-device subfolders preserve explicit independent scopes.
Each physical child keeps its full absolute name; descendants retain actual paths. Live callbacks
attach the real roots, join normal workers and aggregate totals without reordering pending slots.
Failed roots retain errors, cancellation retains active/pending coverage, and hard-link accounting
is applied once across the combined tree. Virtual capacity has observed allocation but no summed
OS total/free/remainder; source operations refuse virtual scope. JSON adds a validated virtual
marker and SavedScan.root=None, CSV/report leave the root path blank. History refuses a virtual
root before touching storage. ScanWorker captures either one path or an immutable root tuple and
saves per-source history after a combined scan. MainWindow offers a bounded literal folder dialog
and a welcome ready-drive action, owns cancellation/join/rescan for the captured roots, and keeps
combined views read-only. Display helpers translate only the pathless root; menus, cleanup,
duplicate linking, copying, compression and compaction never derive authority from that label.
All four charts, search, exports and saved comparison preserve actual child paths. CLI --also
routes through the same API and adds actual roots while leaving virtual root/OS capacity null.

`core.updates` validates only FileTree stable x.y.z metadata and makes one bounded verified-TLS
request to the fixed PyPI host; it follows no redirects and installs nothing. `gui.updates` owns
an opt-out hourly/startup timer, QLockFile daily claim around synced QSettings, UpdateWorker and
translated fixed-link notice. Only gui.app.main starts scheduling; constructors, tests, screenshots
and CLI remain passive. Attempts are persisted before networking, including failures; disabling
cancels publication and close joins the owned request through wait_for. No scan data is sent.

Private Windows validation records six sparse logical lengths after the actual recovery cases.
`windows_sparse_trash_probe` separates Qt success, source disappearance, native-bin retention,
read-only observed preferences and OS free changes; missing inventory grants no emptying authority.
`validate_windows_sparse_trash` repeats only that diagnostic on a fresh larger VHDX. Owned creation
and the fixed PowerShell RAW/no-host formatter whitelist exactly 512 MiB/2 GiB and check the selected
capacity. CI runs each command separately and always retains partial JSON. Existing user bins,
registry settings and backing images are never selected or modified by this diagnostic.

Read-only virtual-disk matching canonicalizes extended Windows UNC/drive registrations while
retaining the original captured row. Unknown device/volume-GUID prefixes remain explicit; no
network path is queried again when a registration matches a recorded file, and no authority changes.

TrashWorker routes every source move through move_batch's optional boundary veto. The Windows
gate reads only a fixed local NTFS/GUID scope, per-volume recycling preferences and disabling
policy, refuses unknown/incomplete/full scopes and repeats the observation before dispatch.
Core source/ancestor identity and cancellation are checked again after the veto; skipped rows
retain ordinary durable audit and parent rescan. Passing observations grant no new authority
and do not lock OS preferences or guarantee retention. Native private diagnostics additionally
run the real worker for refused rows, preserve full hashes/IDs and inspect its durable audit;
raw Qt size-boundary probing remains confined to fresh owned disposable fixtures.

`tools/macos_owned_image.py` creates one UUID-named APFS sparse image in a fresh private directory;
it accepts no image/device/volume selector. Native partition-map entries identify the image disk,
separately from the synthesized APFS container. Before each phase/detach it checks image and scratch
identities, native image mapping, exact private mountpoint/name and volume UUID. No forced detach is
used; uncertain attachments are retained and never recursively cleaned up. `validate_macos_volume.py`
compares statvfs-bracketed capacity, ordinary file st_blocks, sparse/compressed/native clone fixtures,
one/last/all hard-link recovery estimates and private current-uid bin logical versus allocated bytes.
Actual free-space deltas retain deferred reclamation/metadata uncertainty; unknown shared/reserved
bytes stay null. It additionally exercises production cross-volume fcopyfile/resource-fork verification
between its own host scratch and image. No Finder automation, real user bin or cloud provider is used.
Each completed phase/failure and verified cleanup are atomically retained by native macOS CI; local
refusal tests alone do not establish native APFS behavior. macOS savings explicitly retain uncertainty.
Recovery retains each completed case before the next one. An all-name hard-link batch rechecks full
payload/identity metadata and subtracts only its own preceding removals from expected link counts.
The APFS diagnostic runs after the existing cocoa/background probes so its failure preserves their
independent native evidence. The first native image confirmed bin/capacity/sparse/compression/clone
metadata with successful detach/cleanup, including a null remainder when clone allocation exceeded
OS used bytes; complete recovery/cross-volume evidence remains required by #75/#76.
Native run 37738787491 subsequently completed all seven APFS recovery cases and cross-volume
fcopyfile/resource-fork/source-preservation proof with verified detach/cleanup. The first clone
released zero bytes, its final peer 8 MiB: distinct inode allocation cannot determine shared recovery.
It also completed the native cocoa wrapped-summary check and its screenshot was inspected.
`tools/macos_apfs_peer.py` derives a container only from this image's native checked physical store,
checks installed diskutil options and adds one fresh private peer with 16 MiB reserve/64 MiB quota.
Native volume-list UUID/name/device and configured byte values must match before accepting evidence.
Its statvfs/ledger samples retain raw shared-container effects and null independent reservation bytes;
capacity rows are never summed. The image holder recognizes only its registered fresh mountpoints
and normally detaches the complete owned image. Reviewed apfs-20261009-native.json confirms
the native 16 MiB reserve/64 MiB quota and complete detach/cleanup at 85490ec. The peer remains
unmounted with null capacity/ledger; shared extents and independent reserved bytes remain unknown.
Native diskutil rejected the initial custom mountpoint because it requires root. The peer is now
created with -nomount: its configured reserve/quota are cross-checked through the owned container's
UUID/device list, while peer statvfs/ledger remain null. Only the existing primary's actual capacity
and ledger are sampled; no privilege helper or default host mountpoint is used.

`core/darwin_mounts.py` implements the modern 2168-byte Darwin INODE64 statfs ABI from Apple's XNU
mount header. A private getfsstat array is bounded to 4096 entries and checked against a subsequent
count, refusing truncation/changing counts and malformed/unterminated paths. Intel uses explicit
INODE64/64 symbols; arm64 alone permits the modern unsuffixed symbols. No legacy layout is guessed.
MountSurvey now opens Darwin directories no-follow, verifies captured inode/device and fstatfs IDs,
and reads through the held descriptor. Exact mountpoint boundaries and final relevant scope/root
checks refuse changed scans without history publication; no filesystem transaction is implied.
Core remains stdlib-only, with no mount command or mutation. Buffer/refusal tests do not prove native
same-device mounts; native CI must establish the new ABI and traversal behavior. APFS failure phase
JSON additionally retains at most 64 KiB per native command stdout/stderr for actionable diagnostics.

`core/freebsd_mounts.py` adds the 2344-byte FreeBSD 12+ 64-bit statfs ABI with version 0x20140518,
bounded private getfsstat buffers and pinned fstatfs IDs. MountSurvey dispatches FreeBSD alongside
Linux/Darwin; unknown layouts and mount changes fail closed. Core remains stdlib-only.
The disposable FreeBSD 14.3 CI guest runs `tools/validate_freebsd_mounts.py`, accepting only explicit
CI/guest flags and fresh private source/target directories. Native nullfs source/target/type/FSID
are checked before normal unmount; uncertain mounts retain scratch. Static scans use one/four
workers; live mounts before opening refuse traversal, after opening retain the original descriptor
and refuse completion. Reviewed mounts-20261009-freebsd.json confirms all three cases,
source/underlying preservation and completed unmount/cleanup in native run 37808218838.
FreeBSD's null_stat rewrites st_dev to its own mount FSID: the diagnostic records actual IDs and
does not claim same-device evidence. This extends §6's mount contract without changing public
scan signatures or importing GUI/Qt.

The fresh APFS sparse image is 1 GiB so the container permits the primary volume and its
unmounted reservation peer. Apple documents `nx_max_file_systems` as container bytes divided
by 512 MiB, rounded up; the former 512 MiB fixture allowed only one volume. No existing image
is resized, and native ownership/detach checks remain mandatory.

FreeBSD phase evidence uses the existing `_atomic_file(..., encoding="utf-8")` contract.
The initial evidence write is inside the owned cleanup lifetime, so a write error before the first
mount still attempts verified scratch cleanup. Regression tests exercise the real atomic writer
and the initial-write failure path without asserting native mount equivalence.

SonarCloud automatic analysis reads `.sonarcloud.properties`: application code, tooling, workflows,
versioned documentation metadata and root launcher/project metadata are main sources; the dedicated
test directory is test code. No exclusion, suppression or reduced quality gate is configured.
The source/test paths are disjoint and include all currently tracked Python/PowerShell/JSON/YAML/shell
and TOML files. Adding another source root requires extending this explicit source list.
Sonar's [automatic analysis configuration](https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/automatic-analysis)
documents default-branch activation; placing the file on dev alone does not prove the service used it.
Its [initial scope contract](https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/project-analysis/setting-analysis-scope/setting-initial-scope)
distinguishes test analysis from source metrics and billed LOC. The current rejected analysis must
be replaced by observed fresh API evidence before claiming quota or gate recovery. This configuration
neither changes an account/plan nor triggers a release, default-branch merge or paid action.
Observed PR analysis at d138131 subsequently reported 36,803 lines (Python 34,951), down from 53,297,
but task AaEccZ39tYWSxWQdgf3A still refused the organization's 50,000-line allowance with current
organization usage 38,415. The reduced Python count is consistent with test classification; scanner
context was unavailable and analysis never completed. Retained sonar-20261009-classification.json
distinguishes this observation from a successful fresh gate. Quota resolution remains an owner/admin
decision; source scope and quality gates stay intact.

Native background validation atomically persists each phase before workspace/tray/service creation,
scheduled work, recurring review, optional notification, capture and quit/join calls. A failure retains
the last phase and completed fields; complete/owned cleanup are published only after session and
scratch cleanup finish. A repeating 60-second faulthandler traceback identifies synchronous Qt/native
blocking that an event-pump deadline cannot interrupt. The macOS CI step is bounded to five minutes;
its always-run artifact upload retains partial evidence rather than declaring a native pass.
The macOS step repeats four fresh native processes with separate `background/attempt-N` phase,
capture and `probe.log` artifacts. Bash pipefail preserves each Python failure through tee; the
five-minute step bound includes all attempts, and a blocked attempt cannot be counted as a pass.
Retained Cocoa stacks at `7ca3a2c` locate blocked recurring review in `MainWindow.move_to_trash`'s
`QMessageBox.question`: three attempts completed, the fourth did not return. The owned review probe
sets AA_DontUseNativeDialogs before creating its dialogs so its Qt controls are available to the
button driver, then restores the previous process attribute even on failure. It still exercises the
actual production question and real No click, source-policy guards, queue ownership and source hashes.
Evidence explicitly names `confirmation_backend=qt_widget` and `os_native_alert_verified=false`;
OS-native alert interaction needs owner desktop validation. Production dialog defaults remain intact.
Notification opt-in and source/permission/lifetime checks stay intact; registration/dispatch never
prove real login or display permission. Reviewed `b3159ca` push/PR artifacts each completed all four
fresh Cocoa widget-review attempts with real No, unchanged sources, joined workers and owned cleanup;
both APFS validators also completed verified cleanup. The two Tests runs passed all 14 jobs.
`docs/updates/background-20261009-native-widget.json` retains run/job/artifact/JSON hashes and
the scoped confirmation result; OS-native alert interaction and owner login/display remain #38.

Release signing: build-exe alone has OIDC id-token permission under the windows-signing environment.
check_signing validates explicit azure-artifact configuration without echoing IDs; absent mode stays
unsigned, invalid enabled configuration fails. The pinned local signing composite checks exact
nonlinked one-file/standalone/MSI paths, uses Azure CLI OIDC only with pinned Azure actions, SHA-256
and RFC 3161 timestamps, and refuses invalid native trust/timestamp/expected-subject verification.
Executable signing precedes ZIP/MSI construction; MSI signing precedes upload and store hashes.
Third-party runtimes are not resigned. No keys/accounts/settings or native signing evidence exist.

Native macOS arm64 Desktop build 37788683269 at 763182a compiled the actual bundle,
preserved all 167 source entries and verified canonical FileTree.app extraction. Reviewed proof
CRC/size is retained in docs/updates/desktop-20261008-macos.json. The app was not launched/published;
Finder consent, signing/notarization and the POSIX release gate remain external requirements.
Owned MFT tree parity failures report the first differing Node field or bounded coverage/count
detail without weakening comparisons; native candidate success alone is not parity evidence.

Ordinary Windows os.DirEntry metadata always passes through no-follow os.lstat even when a cached
ID is valid, because enumeration can omit NTFS internal attributes. Full attributes remain in
NodeSnapshot for later native path validation; denied paths retain ordinary errors.
Non-DirEntry audited adapters retain their already checked metadata. POSIX caching/missing-ID
fallback remain unchanged. Owned 10k-file/1k-folder one-worker measurements retain baseline and
path-authority medians in docs/updates/scan-20261008-path-authority.json; no speed claim is made.

Native tree parity compares all fields/coverage and normalizes only the known internal NTFS
DIRECTORY representation between independently confirmed ordinary nonlinked directory snapshots.
Both original snapshots are preserved. Unknown/other attributes, cloud/reparse flags, identities,
links, sizes and exact optional date bytes remain strict; linked/mount-boundary nodes do not receive
this equivalence. Native run 37795477143 proved the only remaining snapshot difference was
attributes 16 versus 268435472 before this explicitly bounded comparison rule.

Scan integration contract: `MainWindow.start_scan` returns after dispatch or queues the latest replacement;
folder errors are delivered asynchronously. `WelcomePage.drives_changed` publishes availability; the
ready-drive action uses `drive_rows` snapshots, while every scan revalidates its actual root independently.
`ThreadFence` invokes its continuation once on the GUI thread only after captured workers join; it grants
no source-operation approval and never starts a canceled replacement.

Owned worker-dialog contract: WorkerDialog.defer_done first requests subclass shutdown(wait=False),
invalidates late replies and retains the first result. ThreadFence keeps the GUI loop live until every
descendant QThread joins. The existing done/reporting path then runs with joined workers, reports
retained outcomes and releases the modal source-operation guard. shutdown(wait=True) remains the
explicit destruction contract. queue_worker serializes replaced previews and approved execution behind
retained workers, with a captured current-plan/request/cancellation predicate before starting. Replaced
workers use retire_worker instead of synchronous GUI joins; stale volume replies check worker identity.

Source handoff contract: MainWindow.pending_source_workers cancels gentle scans and native change
readers across its operation-group tabs without a blocking join, and returns retained threads.
WorkerDialog forwards this dependency
provider to its owner; queue_worker waits for captured source readers and prior child workers before
checking the current request. Main-window branch scans, Trash, Undo and approved bin work use this
same gate. A discarded queued branch/Trash/Undo request clears its controller through a terminal
continuation without starting native execution or writing an approval journal. Native operation results
pass through after_threads before reporting and releasing their source-operation ownership.

Normal FollowChanges.stop/configure/adopt calls retire readers without blocking; queued rearming
checks the current reader and cancellation state after old readers join. Explicit shutdown uses
stop(wait=True). History and comparison ready/failure callbacks are identity-guarded join continuations;
they enable comparisons and publish captured saved scans only after termination. Recurring foreground
scan delivery/review validation and virtual-disk query completion use the same nonblocking join gate.

Folder-entry contract: drag/drop negotiation copies only local path strings and acknowledges Copy;
FolderDrops/FolderWorker select the first existing folder off the GUI thread. Requests coalesce,
new foreground scans cancel pending drops, and late validation cannot replace a newer scan. The owned
multi-folder WorkerDialog reserves pending slots under MAX_ROOTS, deduplicates normalized paths and
inserts successful checks in original selection order. Acceptance freezes only validated rows; its modal
operation guard is released before dispatching the combined scan. All query threads remain owned until
full join, including canceled queries. Background capacity/scheduled-scan completion uses the same
after_threads continuation before reporting or publishing attempt receipts.
