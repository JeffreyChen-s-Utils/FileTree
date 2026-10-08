# docs/updates: update log index

`progress.md` holds only work that is **not done yet**. Everything that *was* done (what changed, measured numbers, decisions, snapshots) is recorded here: **one batch file per month**, one entry per piece of work, each entry with a fixed-format ID and tags, and one row per entry in the index below.

> No TODOs here. If an entry mentions something still open, it only points to it (e.g. "open item: `progress.md` #3"); the item itself lives in `progress.md`.

## How to query

Run from the repository root:

| To find | Command |
|---|---|
| every entry, one line each | `rg -n "^## U-2" docs/updates` |
| entries of one type | `rg -n "^## U-2.*#done" docs/updates` |
| entries with a topic tag | `rg -n "^## U-2.*#<tag>" docs/updates` |
| one day or one month | `rg -n "^## U-202609" docs/updates` |
| the full text of one entry | `rg -n -A 60 "^## U-20260926-01" docs/updates` |
| any keyword | `rg -n "keyword" docs/updates` |

Without `rg`: `git grep -n "^## U-2" -- docs/updates`, or in PowerShell `Select-String -Path docs/updates/*.md -Pattern '^## U-2'`.

## Entry format

```markdown
## U-YYYYMMDD-NN · YYYY-MM-DD · one-line title · #type #topic

- **What**: ...
- **Result / numbers**: ...
- **Files**: `path` ...
- **Evidence**: commit, file:line, link ...
- **Open items**: none / see `progress.md` ...
```

- **ID**: `U-` + date + two-digit sequence for that day. IDs are never renumbered or reused, so code comments and other documents can cite them.
- **Type tag** (exactly one): `#done` finished `progress.md` item, `#snapshot` measurement or inventory, `#decision`, `#incident`, `#migration`, `#docs`, `#release`.
- Topic tags are free-form (`#scanner`, `#treemap`, ...).
- Keep conclusions, numbers, files and evidence; drop the reasoning trail and dead ends.

## Batch rules

1. One file per month: `docs/updates/YYYY-MM.md`. Append new entries at the end.
2. Over about 800 lines, continue in `YYYY-MM-b.md` (then `-c`) and list it in the batch table below.
3. **Claim the ID under a lock.** Several sessions may write this log at the same time, and without a lock two of them pick the same number:
   1. `mkdir docs/updates/.id-lock`. Creating a directory is atomic, so only one writer succeeds. If it already exists, someone else is claiming: wait a few seconds and retry. A lock older than 10 minutes is stale and may be removed.
   2. Find the day's last number with `rg -n "^## U-YYYYMMDD" docs/updates` and write the heading line and the index row.
   3. `rmdir docs/updates/.id-lock`, then fill in the body. Git never tracks the empty lock directory.
   4. Before committing, `rg -c "^## U-<your ID>" docs/updates` must report one match in total.
4. **One line per index row**: title only (about 60 characters), no summary.
5. Never rewrite a recorded entry. Correct it with a new `#decision` or `#incident` entry and add "→ corrected in U-..." to the old one.

## When a `progress.md` item is done

In the same commit: delete the item from `progress.md`, add a `#done` entry here that names it, and add its index row.

---

## Batches

| Batch | Covers |
|---|---|
| [2026-10-c](2026-10-c.md) | 2026-10 |
| [2026-10-b](2026-10-b.md) | 2026-10 |
| [2026-10](2026-10.md) | 2026-10 |
| [2026-09](2026-09.md) | 2026-09 |

## Index (newest first)

| ID | Date | Title | Tags | Batch |
|---|---|---|---|---|
| U-20261009-01 | 2026-10-09 | Validate strict whole-drive fallback and retain completed native phases | #ntfs #validation #fallback | [2026-10-c](2026-10-c.md) |
| U-20261008-93 | 2026-10-08 | Preserve native fixture DACL inheritance during exact restoration | #ntfs #validation #permissions | [2026-10-c](2026-10-c.md) |
| U-20261008-92 | 2026-10-08 | Retain exact owned ACL restoration evidence on failures | #ntfs #validation #permissions | [2026-10-c](2026-10-c.md) |
| U-20261008-91 | 2026-10-08 | Isolate native ACL modules and measure precise probe timings | #ntfs #validation #windows | [2026-10-c](2026-10-c.md) |
| U-20261008-90 | 2026-10-08 | Allow explicit full-suite native validation dispatch | #ci #validation #ntfs | [2026-10-c](2026-10-c.md) |
| U-20261008-89 | 2026-10-08 | Clarify signing gates and prior PyPI publication | #docs #signing #distribution | [2026-10-c](2026-10-c.md) |
| U-20261008-88 | 2026-10-08 | Compare proven NTFS directory snapshot representations | #snapshot #ntfs #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-87 | 2026-10-08 | Report exact differing snapshot fields in native tree validation | #snapshot #ntfs #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-86 | 2026-10-08 | Retain ordinary Windows no-follow path authority with cached identities | #snapshot #scanner #ntfs #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-85 | 2026-10-08 | Clarify Japanese and Korean recovery and approval wording | #snapshot #localization #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-84 | 2026-10-08 | Verify native five-language desktop bundles and retain exact tree mismatch diagnostics | #done #distribution #ntfs #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-83 | 2026-10-08 | Prepare opt-in OIDC release signing with native verification gates | #snapshot #signing #distribution #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-82 | 2026-10-08 | Normalize the proven native NTFS directory attribute representation | #snapshot #ntfs #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-81 | 2026-10-08 | Japanese and Korean interface and distribution catalogues | #done #localization #distribution #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-80 | 2026-10-08 | Retain bounded NTFS candidate refusal diagnostics for native parity review | #snapshot #mft #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-79 | 2026-10-08 | Package the actual compiler bundle into a verified canonical macOS app | #incident #packaging #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-78 | 2026-10-08 | Honor the native directory iterator keyword-only cancellation contract | #incident #mft #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-77 | 2026-10-08 | Compare native NTFS audit options ACL refusal cancellation and private-drive timings | #snapshot #mft #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-76 | 2026-10-08 | Generate native macOS ICNS and inspect complete Linux packaging proof | #snapshot #packaging #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-75 | 2026-10-08 | Stage an explicitly selected ACL-aware NTFS metadata audit with ordinary fallback | #snapshot #mft #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-74 | 2026-10-08 | Verify cross-platform compiler wheel hashes and correct native package publication | #snapshot #distribution #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-73 | 2026-10-08 | Package complete native Linux and macOS builds with gated release reuse | #snapshot #distribution #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-72 | 2026-10-08 | Prepare store review drafts from exact compiled artifacts and inspect native MSI evidence | #snapshot #distribution #validation | [2026-10-c](2026-10-c.md) |
| U-20261008-71 | 2026-10-08 | Isolate native GUI branch notification validation from volume-wide reconciliation | #incident #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-70 | 2026-10-08 | Check native Windows directory identity metadata before MFT tree construction | #snapshot #mft #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-69 | 2026-10-08 | Preserve live zero-link and formatted unused MFT segments | #snapshot #mft #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-68 | 2026-10-08 | Build actual compiled Windows installers with owned native validation | #snapshot #distribution #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-67 | 2026-10-08 | Accept known NTFS system and view-index FILE flags | #snapshot #mft #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-66 | 2026-10-08 | Identify refused raw MFT headers without exposing record payloads | #snapshot #mft #msi #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-65 | 2026-10-08 | Preserve named-stream paths throughout owned truncation fixture setup | #incident #mft #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-64 | 2026-10-08 | Verify owned MSI major upgrades before removing the upgraded product | #snapshot #msi #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-63 | 2026-10-08 | Retain padded resident value capacity without retaining DATA payloads | #snapshot #mft #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-62 | 2026-10-08 | Separate resident MFT clusters from native allocation and inspect native MSI evidence | #snapshot #mft #msi #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-61 | 2026-10-08 | Build a complete Windows MSI and validate owned installer fixtures in CI | #snapshot #distribution #msi #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-60 | 2026-10-08 | Retain owned fixture allocation values when native MFT parity refuses | #incident #mft #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-59 | 2026-10-08 | Add bounded read-only native NTFS metadata access and private-image evidence | #snapshot #mft #mounts #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-58 | 2026-10-08 | Preserve UTF-8 native phase evidence and bounded gentle-scan waits | #incident #validation #background | [2026-10-b](2026-10-b.md) |
| U-20261008-57 | 2026-10-08 | Parse bounded raw NTFS FILE and attribute metadata | #snapshot #scanner #ntfs #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-56 | 2026-10-08 | Guard FreeBSD native mounts and confirm APFS reservation evidence | #snapshot #scanner #capacity #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-55 | 2026-10-08 | Allow a second APFS fixture volume with a 1 GiB sparse image | #incident #capacity #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-54 | 2026-10-08 | Keep owned APFS reservation peers unmounted | #incident #apfs #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-53 | 2026-10-08 | Keep Linux descriptor fixtures on their intended backend | #incident #scanner #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-52 | 2026-10-08 | Guard Darwin scans with native mount metadata | #snapshot #scanner #mounts #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-51 | 2026-10-08 | Verify native APFS recovery and cocoa review summary | #done #apfs #review #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-50 | 2026-10-08 | Correct owned APFS hard-link recovery verification | #incident #apfs #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-49 | 2026-10-08 | Preserve wrapped recovery summary during review | #snapshot #review #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-48 | 2026-10-08 | Owned APFS capacity and recovery evidence tooling | #snapshot #apfs #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-47 | 2026-10-08 | Fresh recurring proposal validation and ordinary cleanup review | #done #recurring #safety #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-46 | 2026-10-08 | Scheduled recurring reports and read-only review viewer | #snapshot #background #recurring #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-45 | 2026-10-08 | Bounded recurring observations and history binding | #implementation #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-44 | 2026-10-08 | Native background desktop validation fixtures | #validation #implementation | [2026-10-b](2026-10-b.md) |
| U-20261008-43 | 2026-10-08 | Owned removable per-user login startup | #implementation #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-42 | 2026-10-08 | Background tray and scheduled history service | #implementation #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-41 | 2026-10-08 | Add opt-in schedule metadata and verify native follow lifecycle | #done #implementation #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-40 | 2026-10-08 | Follow native changes independently in result tabs | #implementation #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-39 | 2026-10-08 | Add bounded read-only native filesystem change feeds | #implementation #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-38 | 2026-10-08 | Exercise the intended Linux alias refusal on every POSIX runner | #fix #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-37 | 2026-10-08 | Add native macOS source metadata and cocoa validation | #implementation #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-36 | 2026-10-08 | Own concurrent result tabs and serialize source operations | #done #implementation #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-35 | 2026-10-08 | Refuse unsafe Windows Qt recycling before source dispatch | #implementation #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-34 | 2026-10-08 | Preserve extended UNC discovery paths and record sparse Trash boundaries | #fix #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-33 | 2026-10-08 | Add isolated sparse Trash size-boundary diagnostics | #implementation #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-32 | 2026-10-08 | Add opt-out daily PyPI update notices | #implementation #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-31 | 2026-10-08 | Complete multi-root GUI and CLI scanning | #implementation #validation #done | [2026-10-b](2026-10-b.md) |
| U-20261008-30 | 2026-10-08 | Add pathless multi-root core scans and verify native NTFS recovery | #implementation #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-29 | 2026-10-08 | Preserve incomplete Trash evidence and isolate sparse recovery fixture | #validation #implementation | [2026-10-b](2026-10-b.md) |
| U-20261008-28 | 2026-10-08 | Verify populated VHD compaction and add per-case NTFS recovery evidence | #implementation #validation #done | [2026-10-b](2026-10-b.md) |
| U-20261008-27 | 2026-10-08 | Review detached owned disk after setup and expose each CI failure | #implementation #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-26 | 2026-10-08 | Populated owned VHD compaction validation tooling | #implementation #validation #virtual-disks | [2026-10-b](2026-10-b.md) |
| U-20261008-25 | 2026-10-08 | Reviewed virtual disk compaction with durable outcomes | #implementation #virtual-disks #gui #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-24 | 2026-10-08 | Captured native virtual-disk compaction and private NTFS evidence | #implementation #virtual-disks #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-23 | 2026-10-08 | Read-only virtual disk review and explicit native information | #implementation #virtual-disks #gui #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-22 | 2026-10-08 | Preserve partial NTFS evidence and compatible Qt receipts | #incident #ntfs #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-21 | 2026-10-08 | Private Windows NTFS validation tooling | #implementation #ntfs #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-20 | 2026-10-08 | Read-only native VHD and VHDX information | #implementation #virtual-disks #native | [2026-10-b](2026-10-b.md) |
| U-20261008-19 | 2026-10-08 | Bounded read-only virtual-disk and WSL/Docker discovery | #implementation #virtual-disks #core | [2026-10-b](2026-10-b.md) |
| U-20261008-18 | 2026-10-08 | Duplicate hard-link workflow validated on Windows and Linux | #done #duplicates #verification | [2026-10-b](2026-10-b.md) |
| U-20261008-17 | 2026-10-08 | Reviewed duplicate-link GUI, durable audits and full-root refresh | #implementation #duplicates #gui | [2026-10-b](2026-10-b.md) |
| U-20261008-16 | 2026-10-08 | Exclusive duplicate-link executor and scoped native retirement | #implementation #duplicates #hard-links | [2026-10-b](2026-10-b.md) |
| U-20261008-15 | 2026-10-08 | Frozen duplicate-link previews and complete payload checks | #core #duplicates #hardlinks #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-14 | 2026-10-08 | Complete native audited Trash undo verification | #done #undo #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-13 | 2026-10-08 | Expiring audited Trash undo and joined GUI lifetime | #gui #undo #audit #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-12 | 2026-10-08 | Exact Windows Shell undo with observed native outcomes | #core #windows #undo #validation | [2026-10-b](2026-10-b.md) |
| U-20261008-11 | 2026-10-08 | 取消復原明確回報與 Linux 原生證據 | #52 #CI #Safety #Fix | [2026-10-b](2026-10-b.md) |
| U-20261008-10 | 2026-10-08 | freedesktop 復原核心、收據邊界與原生 Linux 驗證工作 | #52 #Safety #Core #CI | [2026-10-b](2026-10-b.md) |
| U-20261008-09 | 2026-10-08 | 跨磁碟複製介面、回收前驗證與選用原位置連結 | #22 #done #GUI #Safety #Copy | [2026-10-b](2026-10-b.md) |
| U-20261008-08 | 2026-10-08 | Verified exclusive folder-copy core | #22 #copy #files #safety | [2026-10-b](2026-10-b.md) |
| U-20261008-07 | 2026-10-08 | Reviewed same-volume move and rename GUI | #83 #done #gui #files #safety | [2026-10-b](2026-10-b.md) |
| U-20261008-06 | 2026-10-08 | Exclusive same-volume namespace core | #83 #files #safety | [2026-10-b](2026-10-b.md) |
| U-20261008-05 | 2026-10-08 | Finder-wide Trash approval and fixed OS emptying | #21 #macos #trash #safety | [2026-10-b](2026-10-b.md) |
| U-20261008-04 | 2026-10-08 | Scoped Linux Trash approval and emptying | #21 #linux #trash #safety | [2026-10-b](2026-10-b.md) |
| U-20261008-03 | 2026-10-08 | Add reviewable similar-photo groups and thumbnails | #done #photos #duplicates #performance #distribution | [2026-10](2026-10.md) |
| U-20261008-02 | 2026-10-08 | Fix archive symlink refusal fixture lookup | #fix #tests #ci | [2026-10](2026-10.md) |
| U-20261008-01 | 2026-10-08 | Add lazy virtual ZIP 7z and RAR inventories | #done #archives #gui #distribution | [2026-10](2026-10.md) |
| U-20261007-75 | 2026-10-07 | Complete optional hard-link accounting across results and exports | #done #hard-links #gui #cli #exports | [2026-10](2026-10.md) |
| U-20261007-74 | 2026-10-07 | Compression CI and native owned-file evidence across five Windows runtimes | #88 #done #windows #ci | [2026-10](2026-10.md) |
| U-20261007-73 | 2026-10-07 | Optional recorded hard-link accounting without changing named file sizes | #32 #snapshot #api #measurement | [2026-10](2026-10.md) |
| U-20261007-72 | 2026-10-07 | Canonical owned scratch paths for Windows short-name compression probes | #88 #incident #windows | [2026-10](2026-10.md) |
| U-20261007-71 | 2026-10-07 | Remote push rejection retained with explicit CI follow-up | #88 #incident #distribution | [2026-10](2026-10.md) |
| U-20261007-70 | 2026-10-07 | Confirmed exact-file NTFS and XPRESS compression with scoped native validation | #23 #done #windows #gui | [2026-10](2026-10.md) |
| U-20261007-69 | 2026-10-07 | Optional guarded Windows per-file allocation including unflagged XPRESS | #23 #measurement #windows | [2026-10](2026-10.md) |
| U-20261007-68 | 2026-10-07 | Read-only NTFS compression candidate estimates | #23 #gui #estimate | [2026-10](2026-10.md) |
| U-20261007-67 | 2026-10-07 | Recorded owner space with lazy Users tab and optional Windows capture | #28 #done #gui #measurement | [2026-10](2026-10.md) |
| U-20261007-66 | 2026-10-07 | Read-only per-drive bin labels on Welcome and Clean up | #21 #gui #snapshot | [2026-10](2026-10.md) |
| U-20261007-65 | 2026-10-07 | Native same-process mount-query timing evidence | #75 #measurement #validation | [2026-10](2026-10.md) |
| U-20261007-64 | 2026-10-07 | Compare mount ID backends within one native probe | #validation #75 #perf | [2026-10](2026-10.md) |
| U-20261007-63 | 2026-10-07 | Query Linux mount IDs through checked statx | #perf #75 #core #validation | [2026-10](2026-10.md) |
| U-20261007-62 | 2026-10-07 | Capture optional file dates and query recorded age | #done #27 #core #gui #perf | [2026-10](2026-10.md) |
| U-20261007-61 | 2026-10-07 | Verify native Linux live mount protections | #snapshot #75 #validation #perf | [2026-10](2026-10.md) |
| U-20261007-60 | 2026-10-07 | Exercise denied folders through both scan strategies | #fix #75 #tests | [2026-10](2026-10.md) |
| U-20261007-59 | 2026-10-07 | Guard Linux scans against live mount changes | #snapshot #75 #safety #core | [2026-10](2026-10.md) |
| U-20261007-58 | 2026-10-07 | Isolate installation-inventory platform tests | #fix #60 #tests | [2026-10](2026-10.md) |
| U-20261007-57 | 2026-10-07 | Installed programs and Steam/Epic library names | #done #60 #windows #gui | [2026-10](2026-10.md) |
| U-20261007-56 | 2026-10-07 | Retained scan history and size-over-time comparison | #done #37 #history #gui | [2026-10](2026-10.md) |
| U-20261007-55 | 2026-10-07 | Native ext4 capacity and recovery evidence | #snapshot #75 #76 #tests | [2026-10](2026-10.md) |
| U-20261007-54 | 2026-10-07 | Isolated ext4 capacity and recovery probe | #snapshot #75 #76 #ci | [2026-10](2026-10.md) |
| U-20261007-53 | 2026-10-07 | Configurable scan concurrency and UNC guidance | #snapshot #scanner #network #35 | [2026-10](2026-10.md) |
| U-20261007-52 | 2026-10-07 | Reviewed single-drive Windows bin emptying | #snapshot #trash #safety #21 | [2026-10](2026-10.md) |
| U-20261007-51 | 2026-10-07 | Mounted-drive overview and read-only bin totals | #done #volumes #trash #42 | [2026-10](2026-10.md) |
| U-20261007-50 | 2026-10-07 | Readable report summary labels | #incident #reports | [2026-10](2026-10.md) |
| U-20261007-49 | 2026-10-07 | Whole-scan HTML and Excel reports | #done #reports #exports #40 | [2026-10](2026-10.md) |
| U-20261007-48 | 2026-10-07 | Projects and conservative rebuildable-data review | #done #projects #cleanup #61 | [2026-10](2026-10.md) |
| U-20261007-47 | 2026-10-07 | Inspect largest all-ref Git objects without writes or lazy fetching | #done #git #performance | [2026-10](2026-10.md) |
| U-20261007-46 | 2026-10-07 | Filter expanded tree folders while preserving live model identities | #done #tree #navigation | [2026-10](2026-10.md) |
| U-20261007-45 | 2026-10-07 | Compare two live folders with explicit stable content verification | #done #comparison #exports | [2026-10](2026-10.md) |
| U-20261007-44 | 2026-10-07 | Verify native Linux desktop behavior with retained wire and drag evidence | #snapshot #linux #desktop | [2026-10](2026-10.md) |
| U-20261007-43 | 2026-10-07 | Target the owned Thunar row in client coordinates | #incident #linux #desktop | [2026-10](2026-10.md) |
| U-20261007-42 | 2026-10-07 | Verify native bus, Trash and fallback and correct Thunar startup | #incident #linux #desktop | [2026-10](2026-10.md) |
| U-20261007-41 | 2026-10-07 | Supply native desktop account identity and inspect retained artifacts | #incident #linux #desktop | [2026-10](2026-10.md) |
| U-20261007-40 | 2026-10-07 | Exercise external Thunar drag on the isolated X11 desktop | #snapshot #linux #desktop | [2026-10](2026-10.md) |
| U-20261007-39 | 2026-10-07 | Preserve dragged folders and probe the native folder fallback | #snapshot #desktop #safety | [2026-10](2026-10.md) |
| U-20261007-38 | 2026-10-07 | Reject masked native desktop failures and missing evidence | #incident #linux #ci | [2026-10](2026-10.md) |
| U-20261007-37 | 2026-10-07 | Restore isolated native Linux desktop checks and retained evidence | #snapshot #linux #desktop #ci | [2026-10](2026-10.md) |
| U-20261007-36 | 2026-10-07 | Observe native idle transitions in the Qt gate regression | #incident #tests #pacing | [2026-10](2026-10.md) |
| U-20261007-35 | 2026-10-07 | Detect Linux directory bind mounts from the process namespace | #snapshot #capacity #linux #scanning | [2026-10](2026-10.md) |
| U-20261007-34 | 2026-10-07 | Select explicit proposed files in review safety regressions | #incident #tests #safety | [2026-10](2026-10.md) |
| U-20261007-33 | 2026-10-07 | Explain cloud and special files using recorded scan metadata | #done #cloud #allocation | [2026-10](2026-10.md) |
| U-20261007-32 | 2026-10-07 | Measure named stream prevalence and per-entry cost | #done #performance #ntfs | [2026-10](2026-10.md) |
| U-20261007-31 | 2026-10-07 | Opt-in Explorer folder scanning and native Properties | #done #windows #shell | [2026-10](2026-10.md) |
| U-20261007-30 | 2026-10-07 | Use solid glyphs for exact theme foreground pixel checks | #incident #tests #themes | [2026-10](2026-10.md) |
| U-20261007-29 | 2026-10-07 | System, light and dark themes with readable chart labels | #done #themes #charts | [2026-10](2026-10.md) |
| U-20261007-28 | 2026-10-07 | Accessible chart descriptions and keyboard navigation | #done #accessibility #exports | [2026-10](2026-10.md) |
| U-20261007-27 | 2026-10-07 | Explain Windows-managed space and reject direct moves | #done #windows #safety | [2026-10](2026-10.md) |
| U-20261007-26 | 2026-10-07 | Locate extension bytes by containing folder off the UI thread | #done #file-types | [2026-10](2026-10.md) |
| U-20261007-25 | 2026-10-07 | Export every result list and copy selected rows | #done #exports | [2026-10](2026-10.md) |
| U-20261007-24 | 2026-10-07 | Collapsible selection details and background distributions | #done #details | [2026-10](2026-10.md) |
| U-20261007-23 | 2026-10-07 | Clickable chart breadcrumbs and navigation history | #done #navigation | [2026-10](2026-10.md) |
| U-20261007-22 | 2026-10-07 | Print and export the current view to PDF | #done #export #printing | [2026-10](2026-10.md) |
| U-20261007-21 | 2026-10-07 | Save chart pictures and vector graphics | #done #export #charts | [2026-10](2026-10.md) |
| U-20261007-20 | 2026-10-07 | Modified-age colours for treemap and sunburst | #done #charts #age | [2026-10](2026-10.md) |
| U-20261007-19 | 2026-10-07 | Gentle scan priorities and measured cost | #done #scanner #performance | [2026-10](2026-10.md) |
| U-20261007-18 | 2026-10-07 | Pause and resume folder scans | #done #scanner #gui | [2026-10](2026-10.md) |
| U-20261007-17 | 2026-10-07 | Remember tree columns and show share of drive | #done #gui #columns | [2026-10](2026-10.md) |
| U-20261007-16 | 2026-10-07 | Fix initial journal lock race and timestamp ties | #done #fix #journal | [2026-10](2026-10.md) |
| U-20261007-15 | 2026-10-07 | Durable operation journal and recent actions | #done #safety #journal | [2026-10](2026-10.md) |
| U-20261007-14 | 2026-10-07 | Find matching folder trees from existing duplicate hashes | #done #duplicates | [2026-10](2026-10.md) |
| U-20261007-13 | 2026-10-07 | Require explicit duplicate keepers and whole-group revalidation | #done #duplicates #safety | [2026-10](2026-10.md) |
| U-20261007-12 | 2026-10-07 | Preview and persist validated clean-up policy | #done #cleanup #settings | [2026-10](2026-10.md) |
| U-20261007-11 | 2026-10-07 | Require age and evidence for conservative clean-up rules | #done #cleanup #safety | [2026-10](2026-10.md) |
| U-20261007-10 | 2026-10-07 | Explain failed Trash moves with observed lock holders | #done #safety | [2026-10](2026-10.md) |
| U-20261007-09 | 2026-10-07 | Package the standalone Windows folder for releases | #done #build #release #windows | [2026-10](2026-10.md) |
| U-20261007-08 | 2026-10-07 | Document the supported headless core library API | #done #api #docs | [2026-10](2026-10.md) |
| U-20261007-07 | 2026-10-07 | Duplicate logical, allocated and recoverable estimates | #snapshot #duplicates #allocation #gui | [2026-10](2026-10.md) |
| U-20261007-06 | 2026-10-07 | Estimated capacity ledger and mount boundaries | #snapshot #capacity #scanning #gui #cli | [2026-10](2026-10.md) |
| U-20261007-05 | 2026-10-07 | Headless console scan exports and comparisons | #done #cli #core #export | [2026-10](2026-10.md) |
| U-20261007-04 | 2026-10-07 | Review every cleanup proposal before Trash confirmation | #done #safety #gui #allocation | [2026-10](2026-10.md) |
| U-20261007-03 | 2026-10-07 | Revalidate approved entries before background Trash moves | #done #safety #scanner #gui | [2026-10](2026-10.md) |
| U-20261007-02 | 2026-10-07 | Incomplete scans cannot propose whole branches for cleanup | #done #safety #scanner #gui | [2026-10](2026-10.md) |
| U-20261007-01 | 2026-10-07 | System-drive scale budgets and streaming exports | #done #scanner #performance #export | [2026-10](2026-10.md) |
| U-20261001-03 | 2026-10-01 | The release job builds with the locked setuptools | #done #ci #security #X-13 | [2026-10](2026-10.md) |
| U-20261001-02 | 2026-10-01 | The release job installs hash-locked build tooling | #done #ci #security #X-13 | [2026-10](2026-10.md) |
| U-20261001-01 | 2026-10-01 | The source distribution carries no tests | #done #packaging #X-13 | [2026-10](2026-10.md) |
| U-20260927-01 | 2026-09-27 | Expandable folder hierarchy in the Chart tab | #done #gui #core | [2026-09](2026-09.md) |
| U-20260926-35 | 2026-09-26 | The window stays responsive while background work runs | #fix #gui #core #performance | [2026-09](2026-09.md) |
| U-20260926-34 | 2026-09-26 | The treemap comes first again; a folder's specks share one group tile | #change #gui #core | [2026-09](2026-09.md) |
| U-20260926-33 | 2026-09-26 | Refactor: SonarCloud findings of pull request #8 | #refactor #core | [2026-09](2026-09.md) |
| U-20260926-32 | 2026-09-26 | Long paths no longer widen the window; the summary escapes the path | #fix #gui | [2026-09](2026-09.md) |
| U-20260926-31 | 2026-09-26 | Clean up tab: suggestions (temporary files, caches, build output, old installers, empty folders) | #done #core #gui | [2026-09](2026-09.md) |
| U-20260926-30 | 2026-09-26 | The Chart tab opens on the bar chart | #change #gui | [2026-09](2026-09.md) |
| U-20260926-29 | 2026-09-26 | Search conditions (size, age, type, kind) and saved searches | #done #gui #core | [2026-09](2026-09.md) |
| U-20260926-28 | 2026-09-26 | Taskbar: FileTree's own button and icon when run from Python | #fix #windows #gui | [2026-09](2026-09.md) |
| U-20260926-27 | 2026-09-26 | Largest files, types and ages for the selected folder | #done #gui | [2026-09](2026-09.md) |
| U-20260926-26 | 2026-09-26 | Skip folders while scanning (names or paths) | #done #scanner #gui | [2026-09](2026-09.md) |
| U-20260926-25 | 2026-09-26 | System and program folders are asked about twice before the Recycle Bin | #done #safety #gui | [2026-09](2026-09.md) |
| U-20260926-24 | 2026-09-26 | First release 0.1.1: je_file_tree on PyPI, FileTree.exe on GitHub | #done #release | [2026-09](2026-09.md) |
| U-20260926-23 | 2026-09-26 | Linux: ask the file manager to select the entry (D-Bus), else open its folder | #progress #linux #gui | [2026-09](2026-09.md) |
| U-20260926-22 | 2026-09-26 | Sunburst: the third view of the Chart tab | #done #core #gui | [2026-09](2026-09.md) |
| U-20260926-21 | 2026-09-26 | Treemap: folder name strips, sizes, levels and colours by folder | #done #gui #treemap | [2026-09](2026-09.md) |
| U-20260926-20 | 2026-09-26 | Chart tab: bars as a second view next to the treemap | #done #gui | [2026-09](2026-09.md) |
| U-20260926-19 | 2026-09-26 | Export on a worker thread | #done #gui #perf | [2026-09](2026-09.md) |
| U-20260926-18 | 2026-09-26 | Compare with a scan saved as JSON: a Changes tab | #done #core #gui | [2026-09](2026-09.md) |
| U-20260926-17 | 2026-09-26 | Find duplicate files and move the extra copies to the Recycle Bin | #done #core #gui #perf | [2026-09](2026-09.md) |
| U-20260926-16 | 2026-09-26 | Release workflow: PyPI and FileTree.exe on every merge into main | #progress #release #ci | [2026-09](2026-09.md) |
| U-20260926-15 | 2026-09-26 | Package renamed je_file_tree (PyPI name file_tree is taken) | #done #refactor #release | [2026-09](2026-09.md) |
| U-20260926-14 | 2026-09-26 | Size on disk for every entry | #done #core #gui #perf | [2026-09](2026-09.md) |
| U-20260926-13 | 2026-09-26 | Search the whole scan by name or pattern | #done #gui #core | [2026-09](2026-09.md) |
| U-20260926-12 | 2026-09-26 | Tests no longer bring up the real administrator prompt | #fix #test | [2026-09](2026-09.md) |
| U-20260926-11 | 2026-09-26 | Move several entries to the Recycle Bin with one question | #done #gui | [2026-09](2026-09.md) |
| U-20260926-10 | 2026-09-26 | Rescan one folder and swap it into the results | #done #scanner #gui | [2026-09](2026-09.md) |
| U-20260926-09 | 2026-09-26 | An application icon, drawn in code, also in the Nuitka build | #done #gui #build | [2026-09](2026-09.md) |
| U-20260926-08 | 2026-09-26 | Stop takes effect at once; live-scan tests no longer depend on timing | #incident #scanner #tests | [2026-09](2026-09.md) |
| U-20260926-07 | 2026-09-26 | Age tab; double-click a type or an age to list its largest files | #done #analysis #gui | [2026-09](2026-09.md) |
| U-20260926-06 | 2026-09-26 | Unreadable-folder reasons in the window's language | #done #scanner #i18n | [2026-09](2026-09.md) |
| U-20260926-05 | 2026-09-26 | Ask for administrator rights at start, like TreeSize (Windows) | #done #gui #windows | [2026-09](2026-09.md) |
| U-20260926-04 | 2026-09-26 | The tree fills in while the scan runs; Stop keeps what was read | #done #scanner #gui | [2026-09](2026-09.md) |
| U-20260926-03 | 2026-09-26 | The Nuitka script asks Qt where its translations are (Linux CI) | #incident #build #nuitka #ci | [2026-09](2026-09.md) |
| U-20260926-02 | 2026-09-26 | start_file_tree.py and a Nuitka build with Qt's translations | #release #build #nuitka #docs | [2026-09](2026-09.md) |
| U-20260926-01 | 2026-09-26 | FileTree 0.1.0: scanner, treemap and PySide6 window | #release #scanner #treemap #gui #i18n | [2026-09](2026-09.md) |
