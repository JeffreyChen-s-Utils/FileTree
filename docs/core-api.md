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
