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
| `scanner` | `scan(path, *, options=None, progress=None, cancel=None, progress_interval=0.1, on_root=None)`; `ScanOptions(include_hidden=True, workers=..., exclude=())` | `ScanResult.root`, `.errors` as `(path, reason)` pairs, `.elapsed` in seconds |
| `node` | `Node.path`, `.iter_nodes()`, `.iter_files()` | Nodes are returned by scans; `name`, `is_dir`, `is_link`, `size`, `allocated`, `file_count`, `dir_count`, `modified`, `error`, `children`, `parent` describe the snapshot |
| `analysis` | `summarise(root, limit=1000, *, now=None)`, `largest_files`, `extension_stats`, `category_stats`, `age_stats` | `Summary.largest`, `.extensions`, `.ages`, `.now`; extension/category/age records have logical `.size` and `.count` |
| `search` | `search(root, query, limit=1000, cancel=None, *, now=None)`; `Query` | `SearchResult.matches` contains the largest matches, `.count` counts all matches, `.size` counts overlapping matching paths once |
| `duplicates` | `find_duplicates(root, *, min_size=..., workers=4, progress=None, cancel=None)` | `DuplicateResult.groups`, `.files_read`, `.bytes_read`, `.skipped`; each `DuplicateGroup` has `.size`, `.files`, `.extra` (logical extra-copy size) |
| `compare` | `load_saved(path)`, `compare(root, saved)` | `SavedScan.root`, `.saved`, `.folders`, `.size`; `FolderChange.path`, `.node`, `.before`, `.after`, `.change` |
| `allocation` | `allocation_for(root)`, `blocks_allocation()`, `windows_allocation(cluster)`, `cluster_size(path)`, `compressed_size(path)` | A file-allocation callable takes `(DirEntry, stat_result)`; Windows-only helpers must be called on Windows |
| `export` | `export_folders_csv(root, target, max_depth=None)`, `export_files_csv(files, target)`, `export_json(root, target, max_depth=None)` | CSV exports return the row count; JSON returns `None`; all write atomically to an existing destination directory |

`Query` accepts `text`, `min_size`, `max_size`, `changed_within`, `unchanged_for`, `category` and `kind`
(`"any"`, `"files"` or `"folders"`). Sizes are bytes; age spans are seconds. Conditions combine with AND.
Names match without case sensitivity: plain text is a substring, wildcards match the whole name and
`;` separates alternative patterns. An empty query has no matches. Search excludes the root itself.

## Runnable example

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

## Size and snapshot semantics

`Node.size` is logical size; folder totals count each file name, including hard-link names. `allocated`
uses POSIX `st_blocks * 512`; ordinary Windows files are estimated by cluster rounding, with system
allocation queried for compressed/sparse files. Online-only cloud data is counted without downloading
it during scanning. Directory metadata, shared extents and filesystem snapshots are not measured.
Symbolic links, Windows junctions and different-device directory mounts are listed without traversal;
same-device POSIX bind-mount detection is pending. The scan is a sequence of observations, not a
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
`capacity.capacity_ledger(root, *, partial=False)` reports OS capacity, coverage and an estimated
remainder only for compatible complete whole-volume scans. Both estimates still need isolated-volume
validation and neither authorizes removing files. Duplicate hashing checks snapshots around each read
and skips known offline/recall placeholders; unrecognized provider states may still trigger retrieval.

Saved JSON (`file-tree/1`) stores folders and aggregate logical sizes, not a restorable file inventory or
removal authorization. `compare` matches relative folder paths, normalizing case on Windows; it compares
sizes, not contents. Missing values are `None`; `.change` treats a missing side as zero. Partial or
depth-limited reports only describe recorded coverage. CSV is UTF-8 with a BOM and byte-valued size
columns; JSON is UTF-8. Formatting, whitespace and object field order are not an API contract.
