# FileTree core Python API

Import functions from `je_file_tree.core`'s modules. The core uses the standard library and does not
import Qt, create a window or require a display. The package installation still includes PySide6 for
the desktop application. Work on a completed scan; running scans publish a mutable tree whose totals
and children are still changing. Run long operations on your own worker when embedding the core in an
interactive application.

## Supported interface

The import paths, argument names and result attributes listed here are the supported public API.
Call optional arguments by keyword and consume results by attribute; new fields may be added.
Breaking changes must be documented in release notes. Leading-underscore helpers, worker classes,
packed identity snapshots, GUI internals and tree mutation helpers are implementation details.
Capacity and recovery estimates are experimental measurements with the limits described below.

| Module | Public entry points | Result and meaning |
|---|---|---|
| `scanner` | `scan(path, *, options=None, progress=None, cancel=None, progress_interval=0.1, on_root=None, pause=None)`; `ScanOptions(include_hidden=True, workers=..., exclude=(), gentle=False, file_times=False, windows_owners=False, exact_windows_allocation=False, count_hard_links=False)` | `ScanResult.root`, `.errors` as `(path, reason)` pairs, `.warnings` for priority failures, `.elapsed` in seconds, including pauses |
| `node` | `Node.path`, `.iter_nodes()`, `.iter_files()` | Nodes are returned by scans; `name`, `is_dir`, `is_link`, `size`, `allocated`, `file_count`, `dir_count`, `modified`, `error`, `children`, `parent` describe the snapshot; optional `accessed`/`created` return timestamps or None; `owner` is a file's POSIX uid, captured Windows SID bytes or None |
| `analysis` | `summarise(root, limit=1000, *, now=None)`, `largest_files`, `extension_stats`, `category_stats`, `age_stats` | `Summary.largest`, `.extensions`, `.ages`, `.now` retain named totals; optional `.counted_categories` supplies counted chart bytes with named counts, or None when accounting is off |
| `hard_links` | `account_hard_links(root, *, cancel=None)`; `ScanOptions(count_hard_links=False)` | Optional `ScanResult.hard_links` describes `.aliases`, `.logical_overcount`, `.allocation_overcount`, `.unknown`; worker-only recorded-stat accounting without OS/payload queries; `Node.accounted_size/accounted_allocated` preserve named size/allocation; lexical first observed name contributes, proven aliases count zero; inconsistent/unknown groups stay named; reapply after tree mutation; canceled surveys retain previous accounting |
| `similar_photos` | `group_similar(signatures, distance=4, *, cancel=None)` | `PhotoSignature(node, value)` holds a 64-bit hash; groups expose `.files` and `.distances` relative to the first representative, not pairwise/equal-content proofs; 0..16-bit threshold, iterative indexed grouping, `PhotoSearchCancelledError` on Stop |
| `archives` | `read_archive(node, *, reader=zip_members, cancel=None)` | Worker-only guarded ZIP metadata by default; injected readers yield `ArchiveMember`; `ArchiveInventory.children` contains display-only `VirtualEntry` trees, `.files`/`.size` declared totals and `.rejected` omissions; real children/totals unchanged, no extraction; `ArchiveCancelledError` on Stop, OSError on changed/unavailable/unsafe metadata |
| `search` | `search(root, query, limit=1000, cancel=None, *, now=None)`; `Query` | `SearchResult.matches` contains the largest matches, `.count` counts all matches, `.size` counts overlapping matching paths once |
| `duplicates` | `find_duplicates(root, *, min_size=..., workers=4, progress=None, cancel=None)` | `DuplicateResult.groups`, `.files_read`, `.bytes_read`, `.skipped`; each `DuplicateGroup` has `.size`, `.files`, `.extra` (logical extra-copy size) |
| `compare` | `load_saved(path)`, `compare(root, saved)` | `SavedScan.root`, `.saved`, `.folders`, `.size`; `FolderChange.path`, `.node`, `.before`, `.after`, `.change` |
| `history` | `ScanHistory(directory, *, max_bytes=DEFAULT_LIMIT)`, `.save(root, *, cancel=None)`, `.read(root_path, *, limit=1000, cancel=None)`, `load_history(entry, *, cancel=None)` | Application-owned folder metadata only; atomic saved JSON, global oldest-first retention, bounded listing and iterative deep-tree loading; caller keeps the tree stable and excludes stopped scans |
| `programs` | `registered_programs(*, cancel=None)`, `installed_programs(root, *, partial=False, cancel=None)` | Read-only Windows registrations and bounded game metadata; `Programs.rows`, `.count`, `.issues`; exact recorded-folder matches, separate reported estimates, unknown/unreadable coverage; `None` on cancellation |
| `file_times` | `files_older_than(root, days, *, clock="accessed", now=None, cancel=None, policy=None)`, `access_policy()` | Bounded recorded-file date query, complete counts/unknowns and NTFS configuration limits; `None` on cancellation |
| `owners` | `owner_stats(root, *, cancel=None)` | `OwnerInventory.rows` (largest 1,000 owner groups), `.count`, `.files`, `.size`, `.unknown_files`, `.unknown_size`, `.incomplete`; `OwnerStat` includes raw identity/name, logical/named allocation/file totals and logical share; `None` on cancellation |
| `compression` | `compression_plan(root, *, cancel=None, include_compressed=False)` | Read-only `CompressionPlan.rows` (largest 1,000 type candidates; all safe recorded types for restoration), full `.count`, `.logical`, `.allocated`, `.total_files`, `.unknown_files`, `.incomplete`, Windows `.filesystem`/`.unit` and positively identified `.ntfs`; potential saving only 0..recorded candidate allocation; `None` on cancellation |
| `compression_ops` | `compress_files(root, files, mode, *, cancel=None, progress=None)` | Caller confirms ≤1,000 exact recorded files; `ntfs`, `xpress8k`, `uncompress`; local Windows NTFS only, current snapshots and ancestor pins; refuses links/cloud/sparse/protected/hard-linked files; no recursive commands; `CompressionResult` retains partial counts, matched before/after allocation, unknowns, failures and cancellation |
| `owner_id` | `owner_identifier(owner)`, `owner_name(owner)` | Stable uid/SID text and read-only name lookup with raw-identity fallback; None remains unavailable, never inferred from the process account |
| `allocation` | `allocation_for(root, *, exact_windows=False)`, `blocks_allocation()`, `windows_allocation(cluster, *, exact=False)`, `cluster_size(path)`, `compressed_size(path)` | A file-allocation callable takes `(DirEntry, stat_result)`; optional per-file Windows handle measurements include unflagged WOF, with estimates on failure; Windows-only helpers must be called on Windows |
| `export` | `export_folders_csv(root, target, max_depth=None)`, `export_files_csv(files, target)`, `export_json(root, target, max_depth=None)` | CSV exports return the row count and append `accounted_size_bytes`, `accounted_allocated_bytes`, `hard_link_accounting` (0/1); JSON returns `None`, adds counted folder fields and a top-level mode flag, retaining named `size` and `file-tree/1`; all write atomically to an existing destination directory |

`Query` accepts `text`, `min_size`, `max_size`, `changed_within`, `unchanged_for`, `category` and `kind`
(`"any"`, `"files"` or `"folders"`). Sizes are bytes; age spans are seconds. Conditions combine with AND.
Names match without case sensitivity: plain text is a substring, wildcards match the whole name and
`;` separates alternative patterns. An empty query has no matches. Search excludes the root itself.

The accounted root's `accounting` tuple marks active mode even without aliases. Its counted properties
fall back to named bytes when accounting is absent. Layouts use counted weights; file/type/age/owner
lists and saved-scan comparisons retain named totals. After mutation, callers must reapply accounting
on a stable tree in a worker. GUI branch refresh and Trash completion instead rescan the whole root,
so removing the contributing name transfers its bytes to a surviving name.

CLI `scan --count-hard-links` adds `accounted_logical_bytes`, `accounted_allocated_estimate_bytes` and
`hard_link_accounting` metadata without changing existing named totals. GUI report labels include
`accounted_bytes` and `accounted_allocated` to append counted columns and summary rows; older label
mappings retain the original report columns. Counts and capacity recovery remain distinct estimates:
once-per-observed-identity accounting does not measure shared extents or directory metadata.

## Runnable example

The non-core `je_file_tree.photo_reader.find_similar_photos(root, *, min_size=1048576, distance=4,
cancel=None, progress=None)` uses [Pillow image decoding](https://pillow.readthedocs.io/en/stable/reference/Image.html)
on guarded recorded sources. `SimilarPhotoResult` has `.groups`, `.files_read`, `.skipped`, `.distance`,
`.thumbnails` (Node-to-PNG bytes) and `.limited`. Successful signatures cap at 100,000, each source at
128 MiB/40 million pixels, thumbnails at 1,000; unsupported/changed/cloud/link/oversize images are
skipped, and cancellation waits through the current decoder call. These are heuristic review hints;
they cannot be supplied to exact duplicate keeper/savings/rehash decisions. Thumbnails stay in memory.

Archive adapters outside the core use [py7zr's metadata list API](https://py7zr.readthedocs.io/en/latest/api.html)
and [rarfile's header inventory API](https://rarfile.readthedocs.io/api.html). They never call extraction
or test member CRCs. `MetadataReader` limits cumulative physical reads to 32 MiB; inventories cap
100,000 entries, 1,024-character names and 128 levels. These are inventory limits, not a guarantee of
decoder peak memory or header validity; cancellation waits through the decoder's current call.
Virtual entries must never authorize filesystem actions or be inserted into real scan children.

This example creates its own temporary fixture and reports, then cleans up that fixture. Replace the
fixture creation with your own existing path to inspect real data; keep report files outside the scan.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from je_file_tree.core.analysis import summarise
from je_file_tree.core.compare import compare, load_saved
from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.duplicates import find_duplicates
from je_file_tree.core.export import export_files_csv, export_folders_csv, export_json
from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.core.search import Query, search

with TemporaryDirectory() as scratch:
    reports = Path(scratch)
    folder = reports / "data"
    folder.mkdir()
    (folder / "first.bin").write_bytes(b"example" * 1000)
    (folder / "copy.bin").write_bytes(b"example" * 1000)

    result = scan(folder, options=ScanOptions(workers=2, exclude=(".git",)))
    coverage = coverage_of(result.root)
    summary = summarise(result.root, limit=10)
    found = search(result.root, Query(text="*.bin", min_size=1024), limit=10)
    duplicates = find_duplicates(result.root, min_size=1024, workers=2)

    export_folders_csv(result.root, reports / "folders.csv")
    export_files_csv(summary.largest, reports / "largest.csv")
    export_json(result.root, reports / "before.json")
    saved = load_saved(reports / "before.json")
    (folder / "new.bin").write_bytes(b"more data")
    changes = compare(scan(folder).root, saved)

    print("logical bytes:", result.root.size, "complete:", coverage.complete)
    print("matches:", found.count, "duplicate groups:", len(duplicates.groups))
    print("folder changes:", [(entry.path, entry.change) for entry in changes])
```

## Cancellation, errors and ownership

Pass a `threading.Event` as `cancel`, then set it from another thread or a signal handler.
`scanner.ScanCancelledError.partial` holds a `ScanResult` when available; its unread folders carry an
error and must not be interpreted as empty. `search` returns `None` on cancellation;
`duplicates.DuplicateSearchCancelledError` aborts duplicate hashing without a result.
Scan progress callbacks run on the calling thread; duplicate progress callbacks run on hashing threads,
so dispatch them to your application's UI and synchronize shared state. Root and progress callbacks
must not mutate the scan tree.

An invalid scan root raises `NotADirectoryError`; root access or metadata failures may raise `OSError`.
Unreadable descendants are recorded and scanning continues. Use `coverage.coverage_of(root).complete`
as well as `ScanResult.errors` to distinguish a complete traversal from excluded, hidden, unreadable
or pending data. `compare.SavedScanError` is a `ValueError` for unreadable or invalid saved scans.
Exports propagate `OSError`; their temporary sibling is removed and a pre-existing target is preserved
if writing fails. Separate exports are independently atomic. Returned nodes reference the original
tree; do not detach, replace or change them while an analysis is running.

`ScanOptions(file_times=True)` retains optional regular-file access/creation dates from the stat already
read. `Node.accessed`/`created` return timestamps or None, with no new Node slots; directory/link dates
and unavailable birthtime are unknown. POSIX ctime is never creation time. `files_older_than(root, days,
clock="accessed"|"created", cancel=event)` returns up to 1,000 largest matching nodes with full counts,
known matched bytes and unknown/future-date counts. It does not read scanned payloads or modify entries.
NTFS disabled/unknown update configurations refuse access-age matching; timestamps never prove use.
File CSV adds accessed/created ISO dates, empty if absent; folder JSON/history remains folder-only.

Regular-file POSIX uid is captured from the existing scan stat. `ScanOptions(windows_owners=True)`
opts into per-file Windows security queries and a no-follow metadata recheck; defaults false because
the calls are costly. Links/cloud/offline/failed/changed queries have owner None. Owner metadata uses
one shared immutable key slot, separate from operation snapshots. `owners.owner_stats` groups recorded
non-link files by owner, never by an ancestor directory's owner. It runs account-name lookups only for
the largest displayed groups; run on your worker and keep the tree stable. Names may require network
account lookup and cancellation waits through the current OS call. Unknown owners form a separate
group; traversal omissions remain unknown. Named hard-link allocation is not counted once, ownership
does not establish actual use or cleanup permission, and folder-only exports/history omit file owners.
Windows capture follows the documented buffer ownership of
[GetNamedSecurityInfoW](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getnamedsecurityinfow);
raw identities follow the [SID structure](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-sid).

## Size and snapshot semantics

`Node.size` is logical size; folder totals count each file name, including hard-link names. `allocated`
uses POSIX `st_blocks * 512`; ordinary Windows files are estimated by cluster rounding, with system
allocation queried for compressed/sparse files. Online-only cloud data is counted without downloading
it during scanning. Directory metadata, shared extents and filesystem snapshots are not measured.
`ScanOptions(exact_windows_allocation=True)` opts into no-follow per-file FILE_STANDARD_INFO queries,
checking 64-bit volume/128-bit file identity (legacy stat identity on Python before 3.12), size/mtime
and known link/cloud state. It also measures
XPRESS/WOF files with no ordinary compression flag. Failed/unsupported/changed queries retain the
ordinary documented estimate; POSIX stat-block behavior is unchanged. Native per-file allocation does
not deduplicate hard-link names or shared extents. GetCompressedFileSizeW alone is not a general
allocation query: for ordinary files it can return logical length rather than allocated clusters.
The handle path follows [FILE_STANDARD_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_standard_info)
and [FILE_ID_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info).
Symbolic links, Windows junctions and different-device directory mounts are listed without traversal;
Linux mount surveys also omit same-device directory binds and ancestor aliases; pinned directory
descriptors reject live mount changes and incomplete mount-ID queries. Other POSIX same-device native
validation remains pending. The scan is a sequence of observations, not a
transactional filesystem snapshot.

`allocation.estimate_savings(nodes, *, root=None, cancel=None)` returns `Savings` (or `None` if canceled):
`.logical`, `.allocated`, `.recoverable_min`, `.recoverable_max`, `.free_now`, `.uncertain`. Overlapping
paths collapse; hard-linked allocation counts once and other surviving names can make recoverable data
zero. Recovery has no positive guaranteed lower bound; an unknown maximum is `None`, not zero.
Windows and macOS mark `.uncertain` explicitly: cluster estimates or APFS shared extents/snapshots
cannot be resolved from ordinary scan metadata. Native OS free changes are a separate observation.
`duplicates.estimate_duplicate_savings` applies this estimate to each group's explicit `kept` Node;
use `dataclasses.replace(group, kept=chosen_member)` to make a choice. Undecided groups have an unknown
recovery maximum, not an implicit oldest keeper. `DuplicateGroup.digest` and `.proofs` record the
verified search snapshot; `duplicate_decisions.check_group(..., rehash=True)` validates every member
and rehashes the whole group without changing files. Failed checks require rescanning/searching.
`DuplicateResult.folders` lists matching nonempty folder trees derived from those hashes, without extra
content reads. Each group has `.folders`, `.size` and `.files`; missing hashes/errors/links prevent a
match. Names and empty-folder structure are compared exactly. These are read-only snapshot results.
`capacity.capacity_ledger(root, *, partial=False)` reports OS capacity, coverage and an estimated
remainder only for compatible complete whole-volume scans. Both estimates still need isolated-volume
validation and neither authorizes removing files. Duplicate hashing checks snapshots around each read
and skips known offline/recall placeholders; unrecognized provider states may still trigger retrieval.

`bin_empty.prepare_bin_empty(root, *, cancel=None)` returns a frozen `BinEmptyPlan`, or `None` on
cancellation. Linux only: root must be a canonical mounted volume, scopes are derived current-user
freedesktop Trash directories, and `.usage.complete` is required. Linked/private-permission/owner/mount
failures and unrecognized/orphan receipts make approval incomplete. Inventories are capped at 100,000
entries, 128 levels and 64 KiB per receipt; logical payload bytes exclude directory/receipt allocation.
`empty_posix_bin(plan)` is a permanent-delete exception solely for these reviewed OS-bin scopes,
requiring the GUI's two questions naming exact files/info paths, bytes/items and irreversibility.
It rechecks the full plan, pins no-follow descriptors and validates current mount/ancestor identities;
original receipt paths and payload link targets are never followed. OS-bin containers remain.
`BinEmptyResult.removed` counts removed top-level payloads; `.failures` retains at most 20 errors.
Concurrent mutation can cause partial completion; no cancellation is offered after deletion starts.
This API does not authorize arbitrary source removal or report guaranteed recoverable bytes.

`finder_bin.prepare_finder_empty(provider, *, cancel=None)` is macOS-only and returns a frozen
`FinderEmptyPlan`, or `None` on cancellation. `provider()` must return every native mounted root
without omitted/unavailable scopes; the GUI uses `QStorageInfo` and rejects such omissions/errors.
Recognized private current-uid home/volume Trash is surveyed without payload reads, physical scopes
deduplicated and metadata bounded globally to 100k entries/128 levels. Incomplete scopes disable
approval. The unelevated process uid must match `SCDynamicStoreCopyConsoleUser`, never root or another
switched user; pwd supplies the account home, independent of HOME. Unknown identity disables approval.
`empty_finder_bin(plan, provider)` requires two explicit Finder-wide questions listing all
current-user scopes, mounted roots, logical bytes/items and permanent consequences. It rechecks the
whole plan, calls only fixed Finder osascript without path arguments/direct deletion, and surveys
remaining contents. Changed plans, OS/automation errors and remaining/inaccessible data raise visible
errors. Active execution is awaited; Finder can remove new arrivals and may continue after an error.
Returned `TrashUsage` is a fresh logical observation, never guaranteed recovery. Native macOS remains
unverified; POSIX fixture and mocked command checks establish only portable approval/control behavior.

Saved JSON (`file-tree/1`) stores folders and aggregate logical sizes, not a restorable file inventory or
removal authorization. `compare` matches relative folder paths, normalizing case on Windows; it compares
sizes, not contents. Missing values are `None`; `.change` treats a missing side as zero. Partial or
depth-limited reports only describe recorded coverage. CSV is UTF-8 with a BOM and byte-valued size
columns; JSON is UTF-8. Formatting, whitespace and object field order are not an API contract.

`namespace_moves.prepare_namespace(root, nodes, *, directory=None, pattern=None, collision="skip",
cancel=None)` returns a frozen `NamespacePlan` or None on cancellation. Choose exactly one existing
move directory or rename pattern; raw selections are bounded to 1,000 and collapse to outermost rows.
Only `{name}`, `{stem}`, `{ext}`, `{n}` are literal tokens; destination names cannot escape their
directory. `collision="rename"` previews available numbered suffixes, never chooses new names during
execution. `NamespaceItem.reason` is empty only for eligible rows; all other rows remain reviewable.
`execute_namespace(plan, *, cancel=None, progress=None)` requires explicit user approval of the plan.
It revalidates full source coverage, refuses protected/unavailable/special/link/incomplete/changed
sources and protected/descendant/colliding/cross-volume targets, and anchors captured parent identities.
Native exclusive rename has no overwrite/copy fallback. Results expose moved/skipped/failed rows,
canceled and both affected parent paths, including failures for conservative refresh. Stop between
entries retains completed moves. Verified post-rename receipts update only trusted inode expectations
for later hard-link names, never Node snapshots. A changed receipt attempts exclusive rollback; failure
reports the retained destination path for manual inspection. Native failures preserve sources;
concurrent filesystem mutation is not transactional. Native macOS remains unverified.
POSIX semantics: [Linux exclusive rename](https://www.man7.org/linux/man-pages/man2/rename.2.html),
[Apple rename flags/signature](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/stdio.h).
Windows behavior: [os.rename](https://docs.python.org/3/library/os.html#os.rename).

`verified_copy.prepare_copy(root, nodes, directory, *, collision="skip", cancel=None)` returns a
frozen NamespacePlan or None on cancellation. Ordinary folders only; raw selections are bounded to
1,000, outermost pairs retain eligibility reasons and literal reviewed destinations. Protected
ordinary sources may be read, but their later Trash approval remains the existing protected flow.
Linked/special/cloud/reparse/incomplete/changed/mounted sources and protected/descendant/colliding
destinations are refused. Explicit suffix choices never change during execution.
`copy_folders(plan, *, cancel=None, progress=None)` exclusively creates folders/files and compares full
child topology, counts, lengths and every main file/Windows ADS smaller than 64 MiB via SHA-256.
At/above the threshold, contents are length-only. Empty folders remain; hard-link names become separate
copies. Native Windows CopyFileExW preserves file metadata/ADS and PROGRESS_STOP retains partial data.
Failed/unsupported ADS enumeration prevents verification; directory streams are unsupported.
POSIX xattrs copy/compare strictly. Native macOS fcopyfile copies metadata/resource forks; native attrs
below 64 MiB compare values, larger values compare length only, with a 64 KiB attribute-name inventory.
Windows directory security inherits the destination; POSIX setuid/setgid/sticky bits are omitted.
Parent descriptors/Windows handles and path/descriptor snapshots reject links/replacements. Checked
Linux descriptor mount IDs reject same-device destination binds; other POSIX same-device validation
remains unknown. Failure stops the batch and preserves every original; partial paths remain visible.
`CopyResult` exposes verified CopyProofs, skipped/failed rows, partial paths and canceled.
`verify_copy(proof, *, cancel=None)` rechecks source coverage, captured destination root/volume and all
comparisons. Proofs are observations, never deletion permission or future-stability guarantees: repeat
verification immediately before the existing separately approved MainWindow.move_to_trash worker.
The copy functions never Trash/delete/redirect originals. Concurrent mutation remains nontransactional;
native macOS same-volume copy metadata is verified on owned CI fixtures; cross-volume and later
Trash/redirect remain unverified. The GUI routes separate original Trash approval through MainWindow.
Native references: [Windows CopyFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-copyfileexw),
[Apple fcopyfile](https://github.com/apple-oss-distributions/copyfile/blob/main/copyfile.3).

`copy_approval.CopyApproval(proofs, redirect=False)` freezes proofs selected for separate Trash
approval. `matches(root, nodes)` refuses unrelated trees, duplicate proofs and changed source paths.
`redirect_copy(proof)` is only for a successful approved Trash after immediate copy re-verification.
It anchors source parents/copied destination and captured volume, then exclusively creates a native
Windows junction or POSIX descriptor-relative symlink at the vacated original path. No overwrite
or deletion fallback exists; native junction failure may leave an empty original-path directory.
The caller retains successful Trash receipts and reports redirect errors separately; never claim
an original was preserved after an already successful Trash. MoveResult.copy_errors holds
source, copied destination, verify/redirect phase and literal error details.


`trash_restore.capture_origin(path, snapshot)` checks an existing scanned entry against its recorded
stable snapshot and captures no-follow parent identities **before** the OS Trash call. After successful
Trash, `prepare_restore(origin, trashed, volume, *, cancel=None)` requires its actual current-user
private recognized freedesktop files/info destination on the mounted Linux volume. No other bin
payload is enumerated. Top-level identity/size/mtime/type/attributes/link count must match the original;
only the OS move's ctime change is allowed. Entire payload/receipt observations are bounded to 100k
entries/128 levels. `receipt_destination(contents, *, topdir=None)` strictly decodes Path/DeletionDate,
refusing malformed escapes/NUL/dot traversal/duplicates/missing dates/oversized metadata; relative
paths require a mounted topdir and home-Trash paths remain absolute. Parsed paths never grant action
authority; they must exactly match the captured original.

`restore(plan, *, cancel=None)` is an explicit caller-approved native exclusive same-volume restore,
with no copy/overwrite/deletion fallback. Current uid, recognized scope, original/files/info identities,
mount IDs, exact receipt and every no-follow payload snapshot are rechecked. Occupied/arriving original
paths are refused. Unexpected post-rename observations attempt exclusive rollback; errors identify
actual original/Trash locations. RestoreResult exposes restored, source, trashed, error and
receipt_retained. Only a successful restoration permits removal of its unchanged recognized receipt;
cleanup failure is restored=True with an error and retained metadata. Cancellation stops before native
rename; native rename/rollback/receipt cleanup is joined rather than interrupted. Concurrency remains
observational. The GUI wraps these captured plans in an expiring explicit offer.
Specification: [freedesktop Trash](https://specifications.freedesktop.org/trash/1.0/).

Cancellation before native restoration returns restored=False, receipt_retained=True and a nonempty
error detail, including exceptions without a message.


`windows_restore.prepare_windows_restore(origin, *, actual=None, cancel=None)` captures a frozen
WindowsRestorePlan using only the current-user Recycle Bin Shell namespace. The native original-name
and deleted-from properties and payload identity must exactly match TrashOrigin. An actual Qt
receipt restricts lookup; without one, the bounded 100k-item enumeration must yield a unique match.
Payload snapshots are complete and bounded to 100k entries/128 levels; parent anchors, ordinary
nonlinked/noncloud types and a bounded actual `$I` receipt snapshot are required. Receipt contents
are never parsed into action authority.

`restore_windows(plan, *, window=0, cancel=None)` rechecks all observations and vacant original path,
then invokes only the matched Shell item's canonical `undelete` in an owned STA. Interfaces,
strings and context-menu resources are released on every exit. The native call requests synchronous
execution; a bounded 15s observation verifies actual identity/location and receipt cleanup. Receipt
waiting does not repeatedly traverse a restored payload. Native collision/error dialogs are left to
the user; no answer or suppression is automated. Return fields use RestoreResult: observed restored
payloads remain restored=True even if receipt cleanup or payload verification reports an error.
Unconfirmed returns explicitly warn that native work may still be active. No manual Windows payload
rename, receipt deletion, overwrite, copy or rollback fallback exists. Native validation of a freshly
owned CJK folder confirmed identity, hash and empty-directory preservation; this Shell retained its
receipt, truthfully reported with an error. Portable tests cover delayed cleanup and retained-receipt
timeouts, collisions, changed observations, cancellation and native resource lifetimes.

Reference: [canonical Shell restore](https://devblogs.microsoft.com/oldnewthing/20110901-00/?p=9753),
[invocation flags](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/ns-shobjidl_core-cminvokecommandinfo).


The GUI captures TrashOrigin before each actual approved Trash call, prepares frozen native plans
on its TrashWorker after successful receipts and offers them for 8 seconds. Failed optional capture
does not reverse or block the original approved Trash; reasons remain visible. GUI-only UndoEntry
retains the original immutable audit record and affected parent node; native plans never depend on
a detached Node.path. Expiry/root changes/new accepted actions/close discard offer authority.
UndoWorker checks expiry again before durable new inverse approvals and mutation, serializes native
restoration with scans/Trash/path dialogs and retains UndoBatch before queued delivery. Cancellation
skips unstarted entries; close joins native calls and reports late observed results. Automatic source
parent rescans wait for offer expiry or inverse completion; a replaced tree never receives a late
rescan. Parent references avoid a GUI-thread tree walk.

Operation-journal status `restored` is additive to `approved`, `moved`, `skipped`, `failed`; an explicit
inverse operation has new id/batch/reason `undo` and leaves original Trash records unchanged. Failed
inverse approval writes prevent restoration; failed outcome writes preserve observed success and
cancel remaining entries. An approved-only inverse remains unknown after interruption. Recorded
history is metadata, never authority to restore an arbitrary path. Occupied original-path redirects
are refused without unlinking them; successful copies remain intact.

Native Linux GUI CI verified the normal capture/preparation/native-restore/receipt cleanup/container preservation/
parent-rescan path on newly owned private fixtures. Windows GUI native proof and both nine-job CI runs
passed; no existing user bin was emptied.


`duplicate_links.prepare_links(root, groups, *, cancel=None)` returns a frozen LinkPlan of at most
1,000 exact extra-copy rows, or None on cancellation. Each DuplicateGroup needs an explicit kept
member, digest and handle proofs. Protected/changed/unknown/special/linked/cloud/already hard-linked
members refuse the whole decision; other-device or same-device Linux mount-boundary extras remain
refused rows. Repeated members across decisions are rejected. Groups/proof maps and paths/snapshots
are copied before future checks; original inputs remain untouched. Preview reads metadata only.

`verify_link_pair(plan, pair, *, cancel=None)` checks membership, exact frozen paths, current scan
containment, every scan/handle/parent/device/mount observation and then compares complete main data
with SHA-256 and the recorded BLAKE2 duplicate digest. Every Windows named data stream is fully
hashed, irrespective of length; names/lengths are checked before/after. POSIX attributes must exactly
match, including native macOS resource forks below 64 MiB; aggregate native attribute payload is
capped at 64 MiB before allocation. Larger native attributes are refused, not
accepted from length alone. LinkVerification exposes pair, digest and bytes_read (both payloads and
Windows ADS). Unknown/unavailable/changed metadata, content mismatches and cancellation raise
OSError/ValueError while leaving payloads untouched. This is read-only evidence, never authorization
for later replacement/deletion/linking; a mutation executor must recheck at its operation boundary.
Native macOS owned CI verified complete resource-fork/xattr hashes and ordinary core linking;
protected GUI approval remains unverified.

`duplicate_link_ops.execute_links(plan, *, cancel=None, progress=None, completed=None)` executes only an explicitly
reviewed plan while the caller keeps its scan tree stable. It fully rechecks each original group and
each pair before linking; subsequent extras accept only the keeper's observed own link-count/ctime
changes. Same-volume native hard links and native exclusive renames retain the old extra under a
unique sibling backup and publish without overwriting arrivals. Complete main data, every Windows
ADS and supported attribute payload are compared again before retiring only that captured backup.
Windows retirement uses an identity-checked DELETE handle and FileDispositionInfo (one BOOLEAN),
with DELETE-sharing ADS readers; POSIX uses the anchored parent descriptor. There is no copy,
overwrite, directory-removal or arbitrary original-path deletion fallback. These native contracts
follow [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle)
and [FILE_DISPOSITION_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_disposition_info).

LinkResult exposes outcomes, affected keeper/extra parents and canceled. LinkOutcome exposes pair,
linked, error and retained paths. A published alias remains linked=True on later verification or
retirement failure. Cancellation stops unstarted work; rollback is exclusive, and collisions preserve
arrivals and report actual retained backup/temporary paths. Cleanup refuses a temporary alias that
could be the last name. An error stops remaining extras in its group. Old copies are not kept in
Trash; edits and metadata/security changes through one linked name affect every name. Callers must
obtain explicit approval and refresh affected scan observations; no freed-space amount is guaranteed.
Concurrency remains observational. Native owned Windows fixtures verified multiple aliases, full
ADS retirement, cancellation, rollback, arrivals and partial publication. The optional completed
callback observes every stored outcome before the next row; callbacks should not raise and may set
cancel after an audit write failure. Unsupported native link APIs are explicit refusals.

The Duplicates panel offers *Link the extra copies* only for idle exact-file searches with explicit
keepers. `gui.duplicate_link_dialog` owns a frozen metadata-preview worker, lists every exact pair/
refusal and requires default-No plain-text approval with complete Details and shared-future-edits/no
Trash/no automatic Undo warnings. `gui.duplicate_link_worker` writes separate operation approvals
before execution and per-outcome audits with original identities, additive linked status and reason
duplicate_links. Approval failure prevents execution; result-audit failure retains actual success
and stops later rows. Workers retain outcomes before signals; stop/close joins native work and shows
late partial/retained paths in plain text. MainWindow serializes path dialogs with scan/Trash/Undo,
expires old Undo offers, then fully rescans the unchanged current root after any attempted batch.
Both keeper and extra snapshots, capacity and duplicate observations refresh; replaced roots cannot
receive an old refresh. Native Windows CJK/ADS GUI evidence verified three aliases, original audit
identities and full-root refresh. Native Linux CI passed the same fresh owned GUI/native workflow,
audits and full-root refresh.

`virtual_disks.find_virtual_disks(root, *, registrations=None, partial=False, cancel=None)` returns
VirtualDisks(rows, count, issues, incomplete), or None on cancellation. It walks recorded folders
iteratively with per-folder pacing; extension candidates include VHD/VHDX/VMDK/VDI/QCOW2. It keeps a
heap of at most 1,000 largest backing-file rows, while counting all discovered entries and recording
unknown rows, omissions/provider errors and incomplete scan coverage. Registrations may explicitly
override provider discovery with at most 1,000 DiskRegistration entries. Exact normalized paths merge
provider labels into scan rows without copying/modifying the scan tree. Scanned observations remain
recorded estimates; outside provider paths use final-file no-follow metadata and guarded Windows
allocation queries. Missing/linked/cloud/changed external entries remain visible with unknown sizes.

VirtualDisk exposes path, kind, source, name, node (None outside the scan), size, allocated, snapshot,
issue, distro, guest_used and virtual_size. The last two remain None: file length/provider allocation
never proves used guest bytes or virtual capacity. Discovery opens no disk headers/guest payload,
starts no command/VM, and grants no compaction authority. Provider labels do not prove format,
ownership or stopped state; future operations must independently recheck every native observation.
`virtual_disk_sources.registered_disks(*, cancel=None)` returns DiskRegistrations(rows, issues), or
None on cancellation. It reads at most 256 HKCU WSL registrations, requires a known WSL2 version,
literal name/absolute BasePath/literal VHDX basename, and preserves registry failures/omissions.
It adds only existing inferred default Docker disk paths; custom paths require scanning their folder.
Non-Windows supplies no implicit provider paths. These locations follow Microsoft's
[WSL disk-location guidance](https://learn.microsoft.com/en-us/windows/wsl/disk-space)
and Docker's [default WSL storage location](https://docs.docker.com/desktop/features/wsl/).

Native read-only Windows discovery observed two existing WSL/Docker backing files with no guest
launches/commands. A 100,000-candidate in-memory fixture retained 1,000 rows in 2.853 seconds with
544,072 additional peak traced bytes; no filesystem or guest was accessed.

`virtual_disk_info.inspect_virtual_disk(disk, *, cancel=None)` explicitly queries native Windows
VHD/VHDX header observations separately from automatic discovery. It requires a captured ordinary
record without an issue, anchors every nonlinked parent, pins the backing file against rename/delete
and checks the complete snapshot before opening a native header. System32-only virtdisk.dll uses
OpenVirtualDisk Version2 GetInfoOnly/ReadOnly, access NONE and NO_PARENTS, never write/attach/detach
permissions or a fallback. Fixed ABI sizes/offsets are tested independently. Every successful native
handle closes on success/failure/cancellation. Query sizes/version, Microsoft vendor/device, subtype,
loaded BOOL and nonzero capacity must be valid; final snapshot/cancellation checks prevent stale replies.
It returns frozen VirtualDiskInfo(disk, parents, virtual_size, physical_size, subtype, loaded, identifier),
with dynamic true only for subtype 3 (2 fixed, 4 differencing). A zero identifier becomes None.
Physical bytes describe the provider, not guest usage or guaranteed reclaimable allocation. Inspection
permits fixed/differencing/loaded observations but grants no operation approval or stopped-machine
proof. It launches no guest, command or elevation and never attaches a disk. Fresh owned fixed/dynamic
VHD/VHDX tests passed natively on Windows without elevation, exact UUIDs and complete unchanged hashes.
The native structures and flags follow the [Windows SDK header](https://github.com/microsoft/win32metadata/blob/main/generation/WinSDK/RecompiledIdlHeaders/um/virtdisk.h)
and [read-only open parameters](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/ns-virtdisk-open_virtual_disk_parameters).
`gui.virtual_disks` opens from View on a completed/partial recorded result. Its bounded numeric,
sortable/copyable read-only table separates backing length/allocation, native capacity/provider bytes
and unknown guest usage. Original scanned nodes may activate the tree; external providers cannot.
Inventory reads no headers; the explicit selected-header button owns a separate Windows query worker.
Unknown/unsupported/error/omitted coverage stays visible. Plain-text status includes literal paths.
Stop/close cancels replies and joins current calls; MainWindow tracks the owned modal dialog and
serializes scans/file operations. Six GUI tests cover no automatic queries, separated observations,
external/error behavior, both worker lifetimes and routing/serialization. Native fresh owned CJK VHDX
GUI evidence verified its UUID and unchanged complete file hash/snapshot without attachment/elevation.
`virtual_disk_compaction.prepare_compaction(disk, *, cancel=None)` adds a read-only frozen
CompactionPlan(info, runtime) for a detached dynamic VHD/VHDX with an exact UUID. It refuses
fixed/differencing/unsupported, changed/linked/cloud/protected/system/read-only/compressed/encrypted
files and nonlocal/non-NTFS backing volumes. Extended local drive paths are pinned; UNC/device
paths never grant local authority. `virtual_disk_runtime.stopped_runtime` uses bounded native
Toolhelp process snapshots and, when current-user WSL registrations exist, fixed System32 wsl.exe
--list --running --quiet with bounded output/timeout. Incomplete registrations, known guest/Docker
workers, running WSL guests or failed metadata queries refuse execution. It never launches/stops a
guest. Conservative observations are not a lock against a machine starting; the user must confirm
the owning machine remains stopped. Docker backend/service processes must be absent even for
custom files found by scanning. Runtime registration signatures must remain unchanged.

`execute_compaction(plan, *, machine_stopped, cancel=None)` requires literal True after explicit
default-No review and durable approval audit by the caller. It rechecks captured nonlinked parent
identities, complete backing snapshot, runtime and read-only native observations before writable
Version2 access NONE/NO_PARENTS opening. Parent timestamps may change with unrelated sibling
arrivals; identities remain anchored. The same writable handle freshly verifies native format,
exact UUID, dynamic subtype, detachment and capacity, then invokes synchronous CompactVirtualDisk
with flags 0/Version1 reserved 0. No shell, arbitrary program, UAC, attachment, shutdown or fallback.
The caller joins active calls. Returns CompactionOutcome(attempted, compacted, before, after, error):
native success remains true even after a failed later observation; unknown allocation remains None.
A writable open may repair metadata before later failure; every attempted outcome needs a rescan.
Zero-block compaction may reclaim nothing. Allocation observations do not measure guest usage or
guarantee free-space recovery. Native fresh blank VHDX execution proved zero-saving success, exact
UUID/dynamic capacity/detachment and unchanged identity; unrelated sibling arrivals were preserved.
The owned fixture's runtime was isolated from unrelated host guests; this does not prove privileged
populated-disk compaction or replace runtime refusal tests.
View → Virtual disks → Compact selected VHD owns a separate read-only preview and explicit
default-No stopped-machine approval showing the complete literal path, UUID/capacity and native
zero-block backend. Its operation worker durably records original frozen path/identity approval
before invoking the core executor, then stores actual completion/allocation/error before queued
delivery. Approval write failure blocks execution; later audit failure cannot hide native success.
The journal supports compacted outcomes and an explicit virtual_disk_compaction reason; Recent
actions translates both, retaining unknown crash outcomes. Stop/close joins preparation/execution,
suppresses stale reviews and reports unobserved actual results before dismissal. The inventory owns
the child dialog, so MainWindow close joins it too. Every attempted writable operation clears stale
native information and disables another header/compaction review until a full captured-root rescan
after closing. Source mutations remain serialized; prior Trash Undo expires on execution request.
Permission errors use the existing explicit administrator restart only after closing; plans are not
transferred and require a new scan/review. Seven GUI cases cover approval/audit barriers,
late success/unknown observations, joined preview/native closure, stale authority and full-root
refresh. Native CJK GUI proof used a fresh known unassigned blank VHDX, isolated unrelated host
runtimes only for that owned fixture, and verified default-No review, zero-saving completion, durable
compacted audit, exact UUID/capacity and detachment without attachment/elevation. Populated owned
privileged guest-data preservation remains #59.
The fixed native backend follows [CompactVirtualDisk requirements](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-compactvirtualdisk).
DiskPart and Optimize-VHD apply to supported VHD formats,
not VMDK/VDI/QCOW2:
[DiskPart requirements](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/compact-vdisk),
[Optimize-VHD requirements](https://learn.microsoft.com/en-us/powershell/module/hyper-v/optimize-vhd).

Validation tooling is separate from the supported library API. An already elevated disposable Windows
runner can run `py -3 tools/validate_windows_volume.py --output windows-volume.json`; its native result
passed on the administrator Windows CI runner. It accepts no image/disk/bin selector, creates only a new owned VHDX/UUID, validates the
live native physical mapping and formats only an empty RAW nonboot/non-system virtual disk through
a fixed script. The OS assigns its drive letter; device and volume GUID are rechecked before fixture
mutations. It compares OS capacity, FILE_STANDARD_INFO allocation, hard-link/sparse/compressed savings
and the private-bin allocation subset. The native bin proof confines surveys and explicit fixture
responses to that drive while actual Shell query/Trash/emptying, approval recheck and GUI worker
lifetime/refresh remain native. No real user bin is queried or emptied. Detachment failure retains
the scratch image; successful cleanup checks captured directory/image identities. Actual provider
placeholders, shared extents, independent reserved bytes and APFS remain unmeasured. Phase JSON is
saved before later native checks; only complete evidence confirms detachment/cleanup. Fixture Trash
uses the application's bool/tuple-compatible Qt receipt adapter.
Validation ledger JSON retains scalar coverage counts and the unsafe-folder count, preserving unknown
buckets without deep-copying or serializing Node authorization graphs.
Native evidence confirmed exact OS capacity, one/all hard-link bounds, compressed/sparse allocation,
No preservation, refusal of an arrival between approvals, two literal drive questions, one scoped
Shell empty call, active close refusal, joined refresh and confirmed owned detach/cleanup. An access
denied System Volume Information branch correctly retained incomplete coverage/null remainder.
Bin payload/metadata is a subset of allocation, not an extra total; after emptying, 136 observed
metadata bytes remained with zero OS items. Actual per-case hard-link/compression/sparse free recovery,
cloud providers, independently reserved/shared bytes and APFS remain separate validation scope.

`validate_windows_volume.py --kind vhd --output windows-volume-vhd.json` selects only a fresh owned
VHD fixture; the default remains VHDX and no existing image/device/drive selector is accepted. The
populated compaction stage passed native CI for both VHD and VHDX with complete guest data and
confirmed cleanup; observed backing allocation reductions were 31,518,720 bytes and zero. After
owned setup, the original pinned stopped backing file is queried read-only for its fresh review UUID.
Creation/review UUIDs are separately retained; production execution checks remain unchanged. It captures complete main/ADS hashes and
guest namespace/identities/lengths/link counts for fresh files, including a hard link and written then
zeroed blocks. After successful body/detachment/handle-close, an owned callback rechecks and pins the
original scratch/image identities before production preview/runtime/native compaction and durable
approval/outcome. Only the exact owned UUID is reattached read-only/NO_DRIVE_LETTER without formatting,
and every guest record is compared through the recorded volume GUID root. Guest usage stays unknown.
Hook or read-only detach failure retains the image; failed bodies never enter the hook. A created
handle now closes even if initial image stat fails. Phase JSON precedes later native stages; confirmed
cleanup is written only after successful callback/detach and captured cleanup. The Windows CI job
runs both fresh formats and preserves their separate JSON evidence for seven days.

`windows_recovery_probe` adds per-case one/last/all hard-link names, compressed and sparse private
NTFS measurements through production savings, native Trash and reviewed native bin emptying.
It records OS free before Trash, after Trash and after emptying, exact remaining alias identity/full
hash/link counts, and per-case phase evidence. Raw free deltas include unmeasured directory/bin
metadata and are not a guaranteed file-data recovery bound. Native one/last/all hard-link, compressed and 8 MiB sparse recovery passed on both fresh formats
with confirmed cleanup; observed sparse net/empty recovery was 65,536 bytes.

The 64 MiB sparse fixture reported successful Qt Trash but no native bin item; its emptying was
not approved or claimed. It remains in the allocation proof; recovery now uses a separate 8 MiB
sparse fixture. Post-Trash pending records persist actual receipts/free/bin metadata before native
emptying authorization, including an explicit incomplete phase when counts differ.

`je_file_tree.core.multi_scan.scan_roots(paths, *, options=None, progress=None, cancel=None,
on_root=None, pause=None)` accepts a bounded sequence of 1–256 explicit roots and returns ScanResult.
It uses joined normal crawlers sequentially, collapses duplicate/overlapping ordinary paths and
keeps explicitly selected native mount scopes independent. Its virtual root has name="", path=None,
no snapshot and absolute-named physical children. Ordinary Node.path values remain strings. This
root is display/accounting scope only and is refused by source mutation revalidation.
Failed roots remain error children; cancellation raises ScanCancelledError with active/previous/
pending roots. Global hard-link accounting runs once across all captured roots when requested.
CapacityLedger.status="multiple_roots" has no OS total/used/free/remainder but preserves observed
allocation and coverage. JSON adds virtual:true only at the pathless root; load_saved validates the
marker/name and returns SavedScan.root=None. CSV/report root paths are blank. ScanHistory.save
rejects this root before creating history storage; save physical roots individually.

CLI `scan ROOT --also ROOT` accepts repeatable additional roots and uses the same bounded API.
Single-root scan records retain the actual `root`; every scan record adds an actual `roots` list.
Combined records use `root: null`, capacity status `multiple_roots` and null OS capacity fields;
missing/incomplete roots still produce exit 1. Atomic folder/file/JSON exports and saved comparison
support the virtual tree. GUI workers capture root tuples, preserve joined cancellation/close,
rescan those sources and save only individual physical roots with captured snapshots to history.
Combined GUI results are read-only; translated virtual display labels never become OS paths.

`core.updates.check_due(last_attempt, now)` uses elapsed 24-hour intervals, treating malformed
stored values as no previous attempt and refusing invalid current times; backward clocks do not
accelerate checks. `newer_release(payload, current)` validates bounded UTF-8 PyPI project metadata,
refuses foreign/malformed projects and compares only FileTree stable x.y.z releases, ignoring
prereleases/local forms and yanked versions. `fetch_release(current, cancel)` makes one fixed
verified-TLS metadata request, refuses redirects/encoding changes and bounds response bytes/read
time. It returns a newer version or None; OSError/ValueError/HTTP protocol failures are observable.
No paths, file content, package downloads or installation are involved. Importing invokes no network.

`tools.windows_sparse_trash_probe` compares fresh sparse logical lengths of 8/16/32/48/64/96 MiB
on only the verified private NTFS volume. It captures complete source SHA-256/snapshots, Qt receipts,
native bin counts/bytes, bounded read-only private-bin inventory, OS free deltas and observed
per-volume registry preferences. Missing native items stay unknown and never authorize emptying;
only the single expected native item gets the existing two-question owned-bin workflow. Pending
JSON precedes approval, and settings are never interpreted as effective quota or changed.
The normal validator retains 512 MiB VHD/VHDX fixtures; validate_windows_sparse_trash.py adds only
a fresh fixed 2 GiB VHDX for comparison. Creation and RAW/private formatting accept exactly these
two capacities and prove the selected size; no existing disk/image/drive selector is available.
Native size-boundary conclusions require CI artifacts; mocked tests do not establish OS behavior.

Read-only virtual-disk provider matching normalizes extended Windows UNC and drive forms to the
corresponding ordinary path, preserving the original captured row/node/snapshot. Volume-GUID
and other device prefixes remain explicit. This lexical match never grants mutation authority;
actual UNC allocation, permission and disconnect behavior remains unverified without a share.

`core.windows_trash.recycle_reason(node, cancel=None)` returns an additional Windows Trash veto
or None on other platforms/passing observations. Only a current fixed drive-letter NTFS scope,
volume GUID, typed current-user MaxCapacity/NukeOnDelete and non-disabling user/machine policy
qualify for further checks. Missing/unsupported preferences, incomplete source sizes or native
bin metadata are refused. Named source bytes plus existing native bin logical bytes and 1 MiB
headroom must fit the observed preference. Volume/preferences are freshly checked twice. These
are conservative refusal observations, never authoritative effective quota or retention guarantees;
concurrent OS policy/bin changes are not transactionally locked. Nothing changes registry settings.
`move_batch(..., before_move=None)` adds an optional Node veto after source validation, then
rechecks source/ancestor identity and cancellation. It never replaces normal source approval.
TrashWorker supplies this gate for ordinary, duplicate and copy-then-Trash source moves; refused
rows remain attached, are audited as skipped and receive normal parent refresh/translated reasons.
The private sparse diagnostic runs the actual production worker for each observed veto, verifies
durable skipped status and full source preservation, then independently probes raw Qt only on
its newly owned disposable payload. Native Windows 10.0.26100 / Qt 6.11.2 CI verified production
capacity vetoes at 64/96 MiB on both private 512 MiB formats: source snapshot/full SHA-256 preserved,
durable skipped receipts, and no Qt dispatch. All six sizes passed the guard on the private 2 GiB
volume. Separate raw-Qt diagnostics retain no-bin outcomes as unknown; preferences are not effective quota.

GUI integration `app.create_workspace(settings, folder=None)` adds a ScanWorkspace with independent
result-tab MainWindow instances. `add_tab(folder=None)` returns a new owner or None at the sixteen-tab
limit/close; `current` is the active owner, `close_tab(index)` joins that owner, and closing the last tab
exits. Workspace close joins all owners. These factories schedule no network requests; the GUI entry
point invokes start_services after showing the workspace. Existing create_window retains its return
type and behavior. Shared OperationGroup exclusion is additional to exact source revalidation and
never authorizes filesystem operations. Combined scan roots remain one read-only tab.

`tools/validate_macos_sources.py --evidence DIRECTORY` requires native macOS and a non-overridden
cocoa Qt platform. It accepts no source, image, volume or bin selector: every source is a newly owned
temporary fixture. Production copy_folders/verify_copy and prepare_links/execute_links must preserve
complete main/resource-fork/xattr bytes and expected native identities. Length-only attributes fail
the proof. A separate GUI scan renders zh-TW/all chart modes and must leave the source proof unchanged.
Phase JSON is written even after failure; only complete plus owned_fixture_cleanup=true confirms the
scoped native proof. No Trash/Finder operations, cross-volume proof or APFS recovery is implied.

Native macOS 15.7.9 arm64 / Qt 6.11.2 cocoa CI evidence confirms the production same-volume
copy and duplicate-link APIs on owned fixtures, including complete resource-fork/xattr hashes,
keeper identity, empty folders and unchanged GUI sources across zh-TW/all four chart modes.
Cross-volume copies, Finder interaction/Trash and protected GUI link approval remain unverified.

`change_watch.watch(root, on_change, cancel, *, ready=None)` is a blocking, joinable metadata feed
for complete physical Windows/Linux scan roots. Run it on a worker; callbacks run there too.
`ChangeBatch.folders` contains captured folder paths, never untrusted event targets; `full=True`
requires a new full scan after overflow, cursor loss or uncertainty. `captured_scope` refuses
virtual/incomplete roots and bounds scopes at one million folders and 65,536 shared inodes.
Windows reads an existing NTFS USN journal without creating/deleting one; unavailable journals
fall back to one recursive ReadDirectoryChangesW handle. Partial roots with captured shared files
require readable USN, because recursive directory notifications cannot cover outside aliases.
Linux uses one inotify descriptor, anchored folder watches and captured shared-inode watches;
kernel resource limits are visible failures. Unsupported/corrupt records raise OSError/ValueError.
Cancellation closes native resources; Windows cancels and joins outstanding kernel I/O before
releasing its buffers. Setup/rearm races remain observational, and notifications confer no source
operation authority. This core API remains independent of the GUI.

`tools/validate_change_watch.py --output PATH` accepts only an evidence destination and creates
fresh owned sources. It records the actual backend, native notification, cancellation/join and
unchanged keeper identity/SHA-256. Linux/readable-USN additionally write through an owned outside hard-link
alias. Complete JSON plus owned_fixture_cleanup=true is required for success; failed native lifetime
checks retain fixtures. Reviewed CI JSON confirms ordinary/external-alias events on both Windows
existing USN and Linux inotify, with source preservation and joined cancellation. Local Windows evidence used
recursive directory notifications. No journals are created.

GUI Options → Follow changes is default off and persisted with `follow_changes`. Each tab owns a
ChangeWorker with worker-built captured folder/Node maps and one lock-protected bounded batch;
events never accumulate as Qt signals. The controller polls/coalesces for one second, defers scans
during source reviews/operations, scan/analysis, modal questions and live Undo offers, and invokes
the existing rescan_folder/branch replacement only for captured nodes. Unrelated dirty folders survive
the first refresh. Unknown maps, lost events or hard-link accounting require a full-root scan.
Source-operation gaps and a five-minute periodic reconciliation also require full scans; branch
rearming does not postpone that deadline. Ordinary notifications continue during branch scanning,
then cancel/join before tree replacement/rearming. New roots discard old events; opt-out/tab close
cancel and join through wait_for. Unsupported/incomplete scopes and native errors stay visible in
plain-text status, with no automatic error retry loop. Notifications never grant mutation approval.

`background.MonitorConfig(enabled=False, threshold=10, interval_hours=24, roots=())` validates
up to 32 explicitly chosen absolute roots, a 1–50% threshold and 1–720-hour schedule. `dumps` /
`load_config` use strict bounded versioned JSON; duplicate/unknown keys, paths and invalid options
fail closed. `schedule_id` fingerprints roots/interval independently of the warning threshold.
`claim_scan(config, root, now)` prepares a ScanAttempt before dispatch; callers must persist and
serialize it first. Key the attempts map by each `ScanAttempt.key` canonical metadata path.
`due_roots(config, attempts, now)` returns each due selected root once, including after missed periods,
without replaying a backlog. Claimed/failed/canceled attempts suppress repeated
same-period work; clock rollback postpones dispatch, and changed schedules invalidate old receipts.
`SpaceWarnings.observe(rows, threshold=10)` consumes at most 256 validated CapacityObservation rows
and returns informational below-threshold crossings. Unknown capacity never means zero or resets a
low-space latch; actual recovery permits a new crossing warning. Invalid batches leave latches intact.
These core APIs perform no scans, notification dispatch, startup installation or source mutation;
the separate GUI service supplies scans/notifications. Opt-in removable autostart remains #38.

`background.dump_attempts` / `load_attempts` strictly serialize at most 32 scalar claim receipts,
bounded at 128 KiB. Unknown action fields and duplicate normalized roots are refused. Timestamp
validation rejects non-finite/oversized values without overflowing display or schedule arithmetic.
`gui.background_monitor.BackgroundMonitor` belongs to ScanWorkspace. Factories are passive;
start_services starts monitoring only when persisted background_config explicitly enables it and
a system tray is available. Options → Background monitor reviews selected folders, threshold and
interval and a separate opt-in current-user login entry; no automatic clean-up follows acceptance. CapacityWorker copies
at most 256 OS capacity rows on its thread, without bin queries. Informational crossing warnings
appear as supported system notifications and plain-text status/tray tooltips; OS preferences may
suppress notifications. Unknown capacity never triggers a warning or falsely clears its latch.
QLockFile serializes QSettings claims before dispatch across processes. Failed/canceled attempts
remain throttled; bad/locked/unpersistable receipts never dispatch a source scan. ScheduledWorker
captures the current options but forces gentle=True/workers=1, refuses linked roots and saves only
normal bounded ScanHistory. A captured durable claim/interval and strict effective policy also prepare
bounded recurring observations from the last bound history on that worker; saving includes the new
baseline. Optional preparation errors retain normal saved history plus visible errors. Finished unread scopes retain incomplete history; cancellation keeps
a canceled receipt/partial result without publishing incomplete saved data. Results never replace
foreground tabs and never invoke source operations. Foreground scans/reviews cancel/join the gentle
worker; explicit Quit joins capacity and scans. Close-to-tray requires explicit opt-in and an actual
available tray; losing a tray restores a hidden workspace. Disabling restores the window and joins.
The GUI entry accepts --background, skips elevation and hides only when enabled/native tray is ready;
disabled/unavailable monitoring stays visible. The flag alone never enables monitoring or startup.

File → Scheduled scan proposals opens a metadata-only current-session view of at most 32 selected roots,
with new/current candidates and logical folder growth capped at 100 rows per list. Dates/expiry, omitted
rows, coverage and unknown comparisons remain visible. Literal full-path tooltips and Ctrl+C copy never
open recorded sources. OperationGroup guards the modal view across tabs. Status refresh checks bounded
settings/receipts only. Explicit review scans the same root in a new foreground tab and compares captured
fingerprints, coverage and the whole actual no-follow tree on a joinable guarded worker. Current effective
rules resolve displayed scalar rows to current actual scan Nodes only. Cancel/failure/replacement/owner
close discards the intent. The ordinary CleanupReview queue and protected/Trash questions remain required.
Metadata changes during review refuse dispatch; the operation worker rechecks the whole native tree
before a proposal batch and date/rules/schedule/receipt per item with thread-local QSettings instances.
Scalar settings capture preserves explicit backend/group and namespace fallback contracts, rejecting a
different reopened location. Observational validation never grants a filesystem transaction. Baselines persist under
normal history retention; reports appear after a scheduled scan in the current session.

`gui.autostart.registration()` reads native registration without creating metadata; `set_enabled(bool)`
applies only an explicit dialog choice. Windows uses one fixed HKCU Run value and a separate strict
durable ownership receipt before publication. POSIX uses descriptor-anchored no-follow private user
directories, canonical desktop/plist metadata and exclusive link publication; changed/foreign/linked/
shared entries are refused. Removal rechecks the captured content/identity; concurrency is observational.
Absolute literal launcher arguments avoid shell/working-directory dependency. Moving an installed
program requires explicit removal before registering a different program. Registration affects future
logins; no immediate launchctl/bootstrap, process launch or kill, KeepAlive, elevation or global startup
entry is used. Inspection reports metadata presence, not OS startup-policy approval or successful login.

`tools/validate_background.py` requires actual windows/cocoa/xcb/wayland rendering and owns fresh
literal CJK sources plus private settings/history. Phase evidence retains native capacity, completed
history, unchanged source identity/hash and foreground tabs, close/restore/explicit-Quit joins, or the
visible paused unavailable-tray state. Notification opt-in is explicit in the probe; Linux's isolated
XEmbed desktop additionally requires a visible native QBalloonTip screenshot. Dispatch alone never
claims notification permission or successful user login. No startup registration or bin/source action
is invoked by this proof. Windows/macOS artifacts retain unavailable states without claiming support.

`recurring.capture(root, policy, now, cancel=...)` records bounded Candidate rows, explicit five-field
coverage and an order-independent SHA-256 digest of every captured path/snapshot/size/error. It performs
no filesystem reads or mutations, adds no Node fields and checks cancellation/pacing on the worker.
Missing identities leave its signature unknown; the recorded root device/inode must also match before
historical comparisons can describe the same physical scope. Baselines contain at most 100 largest observed rows /
48 KiB; omitted paths still count and cannot prove absence. Strict `load_baseline` refuses unknown
fields, duplicate keys/paths, outside roots, invalid totals/dates/rules and action/approval fields.

`recurring.prepare(root, policy, ProposalContext, previous=..., saved=..., cancel=...)` derives new
candidate paths/rules and up to 100 largest logical folder growth rows only when both complete candidate
inventories and effective policy match the saved baseline's exact root/date. Legacy/partial/mismatched/
truncated histories keep comparison unknown. Rule fingerprints include built-in recognizers/details,
effective disabled/empty-folder settings and exclusions. No historical absence grants cleanup authority.
`proposal_status(proposal, root, policy, config, attempt, now, cancel=...)` rejects next-period expiry,
clock rollback, changed/disabled schedules, any replaced or non-complete receipt, changed rules,
incomplete/missing identity or changed captured descendants. None means current observations only.
`binding_status(proposal, policy, config, attempt, now)` performs the small settings/date/receipt part
without a tree walk; a caller still needs worker-side captured-tree validation and ordinary source review.

`ScanHistory.save(root, baseline=...)` optionally binds observations to the owned header's actual
root/size/date; their bytes share the existing cap and retention. `load_recurring(entry)` rejects a
changed entry or mismatched root/size/date/coverage. Existing `load_history` and export compatibility
remain unchanged; file-only errors now also flag incomplete history. ProposalCancelledError never
publishes a partial proposal. These APIs neither dispatch scans nor invoke source operations.

`operations.validate_tree(root, cancel=...)` compares no-follow snapshots and complete directory names
for an ordinary physical captured root, returning a refusal key or None. It belongs on a worker and
does not authorize mutations or replace `revalidate` immediately before each selected source move.
