"""Every text the window shows, per language (see ``je_file_tree.gui.i18n``)."""

from __future__ import annotations


def _cjk(html: str) -> str:
    """Join the source lines of Chinese HTML: a line break there would show up as a space between characters."""
    return "".join(line.strip() for line in html.splitlines())


EN: dict[str, str] = {
    "namespace_source_name": "Source name",
    "namespace_destination_name": "Destination name",
    "namespace_closed_errors": ("The stopped/closed operation reported errors. "
                                "Inspect the source/destination paths in Details."),
    "namespace_refreshed": "Refreshed {path}: {files} files; {errors} scan errors.",
    "namespace_refresh_failed": "Refresh failed at {path}: {reason}",
    "namespace_refreshing": "Refreshing affected destination: {path}",
    'menu_move_folder': 'Move to folder…',
    'menu_rename': 'Rename…',
    'namespace_source': 'Source',
    'namespace_destination': 'Destination',
    'namespace_status': 'Status',
    'namespace_pattern': 'Filename pattern',
    'namespace_rename_hint': ('Review every source and destination. Literal tokens: {name}, {stem}, {ext}, {n}. Same '
     'volume only; no overwriting. Up to 1,000 selected entries.'),
    'namespace_move_hint': ('Choose an existing destination folder and review every pair. Same volume only; no '
     'overwriting. Protected/link/unavailable/incomplete entries are refused. Up to 1,000 '
     'selected entries.'),
    'namespace_collision_skip': 'Existing name: skip',
    'namespace_collision_rename': 'Existing name: preview a numbered suffix',
    'namespace_preview': 'Preview paths',
    'namespace_apply': 'Apply reviewed paths…',
    'namespace_reading': 'Checking source and destination metadata…',
    'namespace_preview_needed': 'Options changed; preview paths again before applying.',
    'namespace_summary': '{total} outermost pairs; {ready} ready; {skipped} refused/unchanged.',
    'namespace_confirm': ('Apply the {count} eligible source/destination pairs from the preview? {skipped} other '
     'pairs will be skipped. Details list every eligible pair. No existing name will be '
     'overwritten. Stop/close waits through the current rename and keeps completed changes.'),
    'namespace_progress': 'Processed {done} / {total} pairs',
    'namespace_done': 'Moved/renamed: {moved}; skipped: {skipped}; failed: {failed}. Close to refresh the scan.',
    'namespace_failed': 'Operation failed: {reason}',
    'namespace_reason_ready': 'Ready',
    'namespace_reason_unverified': 'Unknown identity',
    'namespace_reason_link': 'Link refused',
    'namespace_reason_special': 'Special entry refused',
    'namespace_reason_unavailable': 'Unavailable/cloud entry',
    'namespace_reason_cancelled': 'Stopped',
    'namespace_reason_outside': 'Outside current scan/root',
    'namespace_reason_missing': 'Source missing',
    'namespace_reason_kind': 'Entry type changed',
    'namespace_reason_identity': 'Source replaced',
    'namespace_reason_changed': 'Source changed',
    'namespace_reason_incomplete': 'Incomplete source coverage',
    'namespace_reason_unreadable': 'Unreadable source',
    'namespace_reason_system_managed': 'System-managed source',
    'namespace_reason_protected': 'Protected source',
    'namespace_reason_unchanged': 'Name unchanged',
    'namespace_reason_descendant': 'Destination inside selected source',
    'namespace_reason_protected_destination': 'Protected destination',
    'namespace_reason_volume': 'Different volume; verified copy required',
    'namespace_reason_collision': 'Name already exists',
    "photos_exact": "Exact duplicates",
    "photos_find": "Find similar photos",
    "photos_similar": "Similar photos",
    "photos_distance": "Hash distance (0–16):",
    "photos_hint": ("Visual candidates only: compare thumbnails and originals. Hash collisions are possible; "
                    "no automatic keeper, extra-copy selection or recovery estimate. First animation frame."),
    "photos_group": "{count} images; within {distance} bits of the first image",
    "photos_running": "Reading images: {read}; skipped/failed: {skipped}",
    "photos_summary": "{groups} similar-image groups; {read} images read; {skipped} skipped/failed.",
    "photos_limited": "Limited inventory or display; up to {count} image rows/thumbnails shown.",
    "archive_loading": "Reading archive metadata…",
    "archive_virtual_name": "{name} [virtual]",
    "archive_virtual_hint": ("Archive member: declared uncompressed size, outside disk totals. "
                             "No file actions or extraction."),
    "archive_failed": "Preview unavailable: {reason}",
    "archive_rejected": "Omitted {count} unsafe, linked or conflicting members",
    "archive_empty": "No previewable members",
    "archive_stopped": "Archive preview stopped; inventory incomplete",
    "archive_busy": "Two archive reads are already running; rescan to retry",
    "archive_stop": "Stop reading this archive",
    "action_count_hard_links": (
        "Count observed hard links once"
    ),
    "action_count_hard_links_tip": (
        "Off by default; future scans keep named sizes and add counted totals. "
        "Branch/Trash rescans rebuild the full root."
    ),
    "column_accounted_size": (
        "Counted size"
    ),
    "column_accounted_allocated": (
        "Counted disk size"
    ),
    "hard_links_hint": (
        "With hard-link accounting enabled, the lexical first observed name con"
        "tributes bytes; aliases count zero here. Named sizes remain real file "
        "lengths. Unknown/inconsistent records stay estimated; shared extents a"
        "re unknown."
    ),
    "hard_links_summary": (
        "Counted: {size} (disk estimate {allocated}); {aliases} observed aliase"
        "s; {unknown} unknown records. Charts use counted totals; file/type/age"
        " lists keep named sizes."
    ),
    "compression_mode_ntfs": "NTFS compression",
    "compression_mode_xpress8k": "XPRESS8K compression (rarely modified files)",
    "compression_mode_uncompress": "Uncompress (NTFS and executable modes)",
    "compression_apply": "Process listed files…",
    "compression_restore_summary": (
        "{count}/{total} recorded files eligible for review; showing {shown}. Compression state may be "
        "unknown."
    ),
    "compression_confirm": (
        "Scope: {path}\nMode: {mode}\nOnly the {count} listed files ({size} logical), out of {total} "
        "candidates, will be processed.\n\nCurrent NTFS scope and unchanged files are checked again. Links, "
        "cloud/offline, sparse, hidden/system, hard-linked and protected files are refused. Directory "
        "defaults and unlisted files are untouched. Compression can slow writes; XPRESS is for rarely "
        "modified data. Uncompression needs free disk space. Stop/failure can leave partial "
        "changes.\n\nClosing this window cancels any current command, waits for it and rescans this folder "
        "with per-file allocation. Continue?"
    ),
    "compression_progress": "Processing {done}/{total} listed files…",
    "compression_done": (
        "{done}/{attempted} commands completed; {failures} failures. Known matched file allocation: "
        "{before} → {after}; {unknown} measurements unknown. Close to rescan; totals are not guaranteed "
        "freed space. First 20 errors are shown."
    ),
    "compression_canceled": "Stopped; earlier or current files may have changed. Close to rescan.",
    "compression_failed": "Operation failed: {reason}. Partial changes are possible; close to rescan.",
    "action_exact_allocation": "Measure Windows per-file allocation",
    "action_exact_allocation_tip": (
        "Off by default; extra metadata calls for future scans, including XPRESS/WOF files. "
        "Enable and rescan. Known cloud/offline files stay unqueried; failed queries remain estimates."
    ),
    "menu_compression": "NTFS compression…",
    "compression_reading": "Reviewing recorded compression candidates…",
    "compression_summary": (
        "{count}/{total} files are type candidates; showing {shown}; logical {logical}, named allocation {allocated}. "
        "Potential saving: 0–{allocated}; no fixed compression rate is predicted. "
        "{unknown} files have unknown metadata."
    ),
    "compression_volume": "Filesystem: {filesystem}; allocation unit: {unit}",
    "compression_unknown": "Unknown",
    "compression_ntfs_only": "NTFS was not confirmed; native compression is unavailable for this scope.",
    "compression_partial": "Incomplete scan: omitted/unreadable data is outside this estimate.",
    "compression_hint": (
        "Read-only type estimate: logs, text, code and possibly uncompressed image formats. "
        "Extensions do not prove compressibility. Hidden/system, compressed/sparse, reparse/cloud/offline and unknown "
        "records are omitted. Named allocation can be estimated or shared by hard links, so it is not guaranteed "
        "recoverable space. No payload is read. Double-click selects the recorded file; Ctrl+C copies rows."
    ),
    "action_capture_owners": "Capture Windows file owners",
    "action_capture_owners_tip": "Off by default; adds owner metadata queries to future scans; enable and rescan",
    "tab_users": "Users",
    "column_owner": "Owner",
    "column_owner_id": "Owner identity",
    "owner_unknown": "Unknown owner",
    "owners_refresh": "Refresh recorded totals",
    "owners_reading": "Adding recorded owner totals and resolving account names…",
    "owners_unqueried": "Open Users after scanning to query recorded owner totals.",
    "owners_partial": "Incomplete scan: omitted/unreadable bytes and their owners remain unknown.",
    "owners_summary": (
        "{count} owner groups; showing {shown}; {files} files, {size}. "
        "Unknown owners: {unknown_files} files, {unknown_size}."
    ),
    "owners_hint": (
        "Whole scan, file owners only; directory ownership does not assign descendants. "
        "POSIX uid comes from the scan's stat. On Windows enable Options → Capture Windows file owners and rescan. "
        "Disabled, failed, changed or cloud/offline queries stay unknown. Names can fall back to uid/SID. "
        "Named allocation remains estimated and hard links count per name. Ownership does not prove actual use "
        "or removal permission. No cleanup actions are prepared."
    ),
    "bin_labels_refresh": "Refresh bin totals",
    "bin_labels_hint": (
        "Read-only snapshot for up to 256 ready drives, prioritizing the scanned drive. "
        "POSIX totals are logical payload bytes; unavailable or partial totals never mean zero. "
        "Scopes can overlap; do not sum them. Refresh to query; this does not prepare cleanup actions."
    ),
    "bin_label_scope_unknown": "Recycle Bin for this scan's drive: scope not queried",
    "bin_label_unqueried": "{root} Recycle Bin: not queried",
    "bin_label_total": "{root} Recycle Bin: {size}, {count} items",
    "bin_label_partial": "{root} Recycle Bin: total unknown; known {size}, {count} items",
    "action_file_times": "File times…",
    "action_file_times_tip": "Filter recorded access and creation dates in this scan",
    "action_capture_file_times": "Capture file access/creation times",
    "action_capture_file_times_tip": (
        "Off by default; adds 16 bytes per regular file to future scans; rescan after ena"
        "bling"
    ),
    "column_accessed": "Recorded access",
    "column_created": "Created",
    "file_times_hint": (
        "Enable Options → Capture file access/creation times, then rescan. Regular files"
        " only; directory/link and unavailable creation dates remain unknown. Access date"
        "s can be disabled, delayed or updated by background tools; they never prove actu"
        "al use. POSIX ctime is not creation time. This view does not prepare cleanup act"
        "ions."
    ),
    "file_times_accessed": "Not opened since… (recorded access date)",
    "file_times_created": "Created at least… ago",
    "file_times_mode": "Recorded age mode",
    "file_times_days": "Days",
    "file_times_reading": "Filtering recorded file dates…",
    "file_times_summary": (
        "{count} matches, {size}; showing {shown}. {unknown}/{total} files have unavailab"
        "le or future dates."
    ),
    "file_times_policy_disabled": (
        "NTFS reports access updates disabled. Access-age matching is unavailable; creati"
        "on filtering remains available. Registry settings may require a restart and do n"
        "ot describe every filesystem."
    ),
    "file_times_policy_unknown": (
        "NTFS access-update configuration is unknown. Access-age matching is unavailable;"
        " creation filtering remains available."
    ),
    "file_times_policy_enabled": (
        "NTFS registry reports access updates enabled; pending restart, filesystem/provid"
        "er settings and deferred updates may still affect dates."
    ),
    "file_times_policy_platform": (
        "Filesystem/provider settings may defer or suppress access updates. Treat these d"
        "ates as recorded metadata."
    ),
    "action_programs": "Installed programs…",
    "action_programs_tip": "Compare installer/game metadata with installation folders in this scan",
    "program_name": "Program / game",
    "program_source": "Metadata source",
    "program_version": "Version / build",
    "program_publisher": "Publisher",
    "program_reported": "Reported estimate",
    "program_scanned": "Scanned logical bytes",
    "program_allocated": "Scanned named allocation",
    "program_coverage": "Recorded folder coverage",
    "program_location": "Installation folder",
    "program_registry": "Windows registry",
    "program_steam": "Steam manifest",
    "program_epic": "Epic manifest",
    "program_outside": "No exact scanned folder",
    "program_hint": "Windows uninstall registrations and recognized Steam/Epic manifests, matched only to exact "
                    "folders in this scan. Epic's fixed ProgramData manifest folder is also read. Reported sizes "
                    "are estimates; missing metadata stays unknown. Shared/nested folders can overlap: do not sum "
                    "rows or treat them as recoverable space. Portable/packaged apps may be absent. Double-click "
                    "selects a recorded folder; Ctrl+C copies rows. Uninstall only through Windows or the launcher.",
    "program_reading": "Reading installation metadata…",
    "program_summary": "Showing {shown} of {count} installations; "
                       "{issues} unavailable/malformed/omitted metadata items",
    "program_failed": "Cannot read installations: {reason}",
    "program_uninstall_page": "Open Windows installed-app settings",
    "program_open_failed": "Windows could not open the installed-app settings page",
    "action_history": "Scan history…",
    "action_history_tip": "Review this root's size over time and compare with an earlier scan",
    "action_history_settings": "Scan history settings…",
    "action_history_settings_tip": "Enable local scan metadata and set its global retention limit",
    "history_enable": "Keep completed full scans locally",
    "history_settings_hint": "History stores folder names, paths, totals and coverage, never file contents. "
                             "Default: enabled, 1 GiB total across all roots. Only recognized history metadata "
                             "is removed, oldest first. Disabling keeps existing history readable. Changes apply "
                             "to future full scans; a lower limit takes effect on the next save.",
    "history_limit": "Total history limit",
    "history_time": "Scan time",
    "history_logical": "Logical bytes",
    "history_allocated": "Allocated named bytes",
    "history_coverage": "Coverage",
    "history_incomplete": "Incomplete; known data only",
    "history_complete": "Complete recorded coverage",
    "history_chart": "Logical folder size over time",
    "history_chart_range": "{first}: {before}; {last}: {after}",
    "history_empty": "No retained scans for this root",
    "history_compare": "Compare selected scan with current results",
    "history_reading": "Reading local scan history…",
    "history_hint": "The latest 1,000 retained full scans for this root. Stopped scans and branch rescans are "
                    "not saved. Incomplete scans describe known data only: missing folders do not prove deletion. "
                    "Totals count hard-link names separately; differences are metadata, not content verification.",
    "history_summary": "Showing {shown} of {count} scans; {invalid} invalid/unavailable metadata files",
    "history_failed": "Cannot read history: {reason}",
    "history_save_failed": "The scan completed, but history could not be saved: {reason}",
    "action_scan_workers": "Scan workers…",
    "action_scan_workers_tip": "Choose concurrency for new scans; higher is not always faster",
    "workers_prompt": "Workers for new scans (1–32). The default is {default}. Slow network shares may benefit "
                      "from more workers; excessive concurrency can overload a disk/server. Running scans retain "
                      "their existing workers. Real UNC performance depends on your share.",
    "action_bins": "Recycle Bins…",
    "action_bins_tip": "Review bin totals and explicit scoped OS emptying",
    "bin_finder_empty": "Empty Finder Trash on all mounted volumes…",
    "bin_finder_all": "all mounted volumes (Finder-wide Trash)",
    "bin_finder_scopes": "Current-user Trash scopes:\n{scopes}\n\nMounted volumes:\n{roots}",
    "bin_finder_first": "Empty the current user's Finder Trash across ALL mounted volumes?\n\n{root}\n\n"
                        "Logical payload: {size}\nItems: {count}",
    "bin_finder_irreversible": "Permanently empty the current user's Finder Trash on ALL mounted volumes?\n\n"
                               "{root}\n\nLogical payload: {size}\nItems: {count}\n\nThis cannot be undone. Finder can "
                               "also remove items arriving during its operation. This affects every mounted bin, "
                               "regardless of the selected row. The OS operation cannot be canceled. Automation or "
                               "permission failures can leave partial results, and Finder may still be working.",
    "bin_preparing": "Reviewing exact Trash scopes on {root}…",
    "bin_no_approval": "No complete nonempty Trash approval; refresh and review again.",
    "bin_scope_first": "Empty these current-user Trash payload/receipt scopes?\n\n{root}\n\n"
                       "Logical payload: {size}\nItems: {count}",
    "bin_scope_irreversible": "Permanently remove the reviewed contents of these exact scopes?\n\n{root}\n\n"
                              "Logical payload: {size}\nItems: {count}\n\nThis cannot be undone. "
                              "Payload links are removed without following their targets. Changed entries are refused; "
                              "failures can leave partial results. Emptying cannot be canceled once started.",
    "bin_partial": "Removed {count} reviewed items; remaining failures: {reason}",
    "bin_empty": "Empty selected drive's Recycle Bin…",
    "bin_first": "Empty the Recycle Bin on {root}?\n\nReported size: {size}\nItems: {count}",
    "bin_irreversible": "Permanently remove all items currently in the Recycle Bin on {root}?\n\n"
                        "Reported size: {size}\nItems: {count}\n\nThis cannot be undone. New items arriving during "
                        "the OS operation may also be removed. The native operation cannot be canceled once started.",
    "bin_running": "Emptying the Recycle Bin on {root}; waiting for the OS operation…",
    "bin_failed": "Emptying did not complete: {reason}",
    "bin_hint": "Select one mounted volume. Windows empties its current-user OS bin; Linux inventories recognized "
                "files/info scopes. Two questions show exact scope and totals before permanent removal. "
                "Stop cancels surveys; active emptying must finish. macOS empties ALL mounted Finder Trash after "
                "global review (native validation pending). Capacity/bin "
                "values refresh afterwards; rescan to update the main tree.",
    "action_volumes": "Drive overview…",
    "action_volumes_tip": "Inspect mounted volumes, capacity, allocation units and Recycle Bin totals",
    "volume_root": "Mounted root",
    "volume_name": "Volume name",
    "volume_fs": "Filesystem",
    "volume_total": "Total",
    "volume_used": "Used",
    "volume_free": "Available to you",
    "volume_cluster": "Allocation unit",
    "volume_trash": "Recycle Bin bytes",
    "volume_trash_count": "Bin items",
    "volume_reading": "Reading mounted volumes and Recycle Bin totals…",
    "volume_summary": "Showing {shown} mounted volumes out of {count}. Double-click to scan.",
    "volume_trash_partial": "Unknown total ({known} known)",
    "volume_hint": "OS capacity snapshot; available space may exclude reservations or quotas. "
                   "Repeated mounts can share capacity: do not sum rows. Windows allocation units are clusters; "
                   "POSIX units are filesystem fragments, not optimal transfer sizes. Trash shows OS-reported "
                   "Windows totals or known POSIX logical payload bytes, not reclaimable space; directory/receipt "
                   "metadata and shared allocation are excluded. Errors remain unknown. Stop waits for current OS "
                   "calls; canceled surveys are discarded. Ctrl+C copies rows. No emptying action is provided here.",
    "action_export_report_html": "Scan report (HTML)…",
    "action_export_report_html_tip": "Save a self-contained report with three embedded chart images",
    "action_export_report_xlsx": "Scan report (Excel)…",
    "action_export_report_xlsx_tip": "Save the report lists on separate Excel worksheets",
    "html_filter": "HTML reports (*.html)",
    "xlsx_filter": "Excel workbooks (*.xlsx)",
    "report_title": "FileTree scan report",
    "report_note": "Known recorded scope only; allocation is an estimate. Counts in headings show displayed / total. "
                   "Top folders overlap: do not add their rows. Largest files and folders are limited to 1,000; "
                   "file types to 10,000. Sizes are bytes. Ages use recorded modification times, not last access; "
                   "unavailable dates belong to the oldest existing age group. HTML charts show the whole scan root "
                   "with bounded geometry. Excel text is escaped, control characters shown as hex, cells limited "
                   "to 32,767 characters and integers of 16 digits or more stored as exact text.",
    "report_bytes": "Logical bytes",
    "report_allocated": "Allocated bytes (estimate)",
    "report_created": "Report created",
    "report_reference": "Age reference",
    "report_skipped": "Skipped folders",
    "report_denied": "Unreadable folders",
    "report_pending": "Pending folders",
    "report_summary": "Summary",
    "report_notes": "Notes",
    "report_field": "Field",
    "report_value": "Value",
    "report_top_folders": "Largest folders (overlapping)",
    "report_categories": "Categories",
    "action_projects": "Projects and rebuildable data…",
    "action_projects_tip": "Inspect recorded project, Git and generated data sizes",
    "project_path": "Project / managed store",
    "project_kind": "Detected kind",
    "project_other": "Source / other",
    "project_git": ".git",
    "project_generated": "Rebuildable data",
    "project_coverage": "Coverage",
    "project_partial": "Incomplete",
    "project_recorded": "Recorded scope",
    "project_hint": "Known logical bytes only. Nested projects overlap. Git pointer files omit external metadata. "
                    "Generated data may contain custom files: review before moving. Maven, global Gradle and Docker "
                    "stores are shown separately; their contents are not presumed disposable.",
    "project_reading": "Inspecting recorded project data…",
    "project_summary": "Showing {shown} largest projects / stores out of {count} detected.",
    "project_review": "Review eligible rebuildable entries…",
    "project_review_count": "Review up to {shown} entries out of {count} eligible under the current age, coverage "
                            "and clean-up policy. Stopped scans cannot propose entries.",
    "project_git_kind": "Git",
    "project_python": "Python",
    "project_node": "Node.js",
    "project_rust": "Rust",
    "project_jvm": "JVM",
    "project_conda": "Conda project",
    "project_python_environment": "Python environment",
    "project_conda_environment": "Conda environment",
    "project_maven_store": "Maven store",
    "project_gradle_store": "Global Gradle store",
    "project_docker_store": "Docker data",
    "action_git_history": "Git history…",
    "action_git_history_tip": "Inspect the largest objects reachable from all Git references",
    "git_oid": "Object ID",
    "git_kind": "Object type",
    "git_length": "Uncompressed length",
    "git_type_blob": "File contents (blob)",
    "git_type_tree": "Directory listing (tree)",
    "git_type_commit": "Commit",
    "git_type_tag": "Annotated tag",
    "git_hint": ("Read-only Git plumbing inspects all refs, keeping the largest 1,000 objects. Sizes are "
                 "uncompressed lengths, not disk allocation or recoverable space. Names are omitted because "
                 "Git's object-name hints can be ambiguous. Ctrl+C copies object IDs/rows. Optional locks, "
                 "automatic maintenance and lazy network fetching are disabled; Git must support --no-lazy-fetch. "
                 "Repository ownership errors are not bypassed. Stop cancels; gc is never run here."),
    "git_reading": "Inspecting Git history…",
    "git_summary": "Showing {shown} of {count} reachable objects; uncompressed total {size}.",
    "git_gc_loose": ("Git gc may consolidate {count} loose objects, but these largest objects remain reachable "
                     "from refs and will not be removed. "
                     "Actual savings and other unreachable/reflog data are unknown."),
    "git_gc_packed": ("No loose objects to consolidate. Git gc will not remove these objects while refs retain "
                      "them; other unreachable/reflog data and actual savings were not measured."),
    "git_failed": "Git inspection failed: {reason}",
    "tree_filter_placeholder": "Filter expanded folders…",
    "tree_filter_hint": ("Match names (case-insensitive) only inside already expanded folders; ancestors stay visible. "
                         "Collapsed contents are not searched. Clear the filter to restore the tree. "
                         "Choosing a hidden entry in a chart/list clears the filter. "
                         "Scan totals and exports stay unchanged."),
    "action_live_compare": "Compare two folders…",
    "action_live_compare_tip": "Compare fresh relative paths and verify only requested file pairs",
    "compare_choose_left": "Choose the left folder",
    "compare_choose_right": "Choose the right folder",
    "compare_relative": "Relative path",
    "compare_state": "Comparison",
    "compare_left_size": "Left size",
    "compare_right_size": "Right size",
    "compare_left_time": "Left modified",
    "compare_right_time": "Right modified",
    "compare_roots": "Left: {left}\nRight: {right}",
    "compare_hint": ("Read-only: exact Unicode/case names are matched; links are not followed. Equal size/time "
                     "does not prove equal contents. Select file pairs and verify their full hashes with Stop "
                     "available; changed, unreadable and known cloud files remain unavailable. Results refer "
                     "to this scan/verification time. No copy, move or synchronization is performed. "
                     "Ctrl+C copies rows; CSV exports only the displayed rows, up to 10,000."),
    "compare_reading": "Scanning both folders…",
    "compare_error": "Comparison or export failed: {reason}",
    "compare_hashing": "Verifying selected file pairs…",
    "compare_verify": "Verify selected contents",
    "compare_summary": "Showing {shown} of {count} relative paths (limit 10,000).",
    "compare_incomplete": "Coverage is incomplete; missing paths in unreadable scopes remain unknown.",
    "compare_unavailable": "Unavailable or changed",
    "compare_link": "Link; contents not read",
    "compare_only_left": "Only on the left",
    "compare_only_right": "Only on the right",
    "compare_different_kind": "Different entry types",
    "compare_folder": "Folder on both sides",
    "compare_different_size": "Different sizes",
    "compare_different_time": "Different times; contents unchecked",
    "compare_unchecked": "Contents not verified",
    "compare_identical": "Matching full hashes",
    "compare_different_bytes": "Different contents",
    "problem_mount_boundary": "Mount boundary: contents not scanned",
    "action_special_files": "Cloud and special files…",
    "action_special_files_tip": "Inspect recorded recall, offline, compressed and sparse file states",
    "special_states": "Recorded state",
    "special_content_size": "Full content size",
    "special_recall": "May recall on access",
    "special_offline": "Offline",
    "special_compressed": "Compressed",
    "special_sparse": "Sparse",
    "special_allocation_low": "Lower allocation; cause unknown",
    "special_reading": "Reading recorded file metadata…",
    "special_hint": ("This list uses scan metadata only: no files are opened or downloaded. Recall/offline flags can "
                     "describe OneDrive, Dropbox or other providers; the provider and how much is already local cannot "
                     "be inferred. Full content size is the logical length, including online content; allocation after "
                     "downloading is unknown. Sparse holes, compression and resident data can reduce allocation. "
                     "Zero on disk for recall/offline entries is an estimate, not measured cloud allocation. "
                     "Double-click selects the scanned entry; Ctrl+C copies selected rows."),
    "special_summary": ("Showing {shown} of {count} matching files. Full content {size}; recorded allocation "
                        "{allocated}. Unavailable file metadata: {unknown}. Largest 1,000 are retained."),
    "special_partial": "Scan coverage is incomplete; unseen files remain unknown.",
    "action_shell_integration": "Explorer integration…",
    "action_shell_integration_tip": "Add or remove Scan with FileTree in your Explorer folder menu",
    "shell_enabled": "Add Scan with FileTree to Explorer's folder menu",
    "shell_scan": "Scan with FileTree",
    "shell_hint": ("Save changes only your account's folder menu; no administrator rights are needed. "
                   "On Windows 11, look under Show more options. Turn this off here to remove the entry. "
                   "Register again after moving the executable or source checkout."),
    "shell_failed": "Explorer integration could not be changed.\n{reason}",
    "menu_properties": "Properties",
    "properties_failed": "Windows could not open Properties for:\n{path}",
    "menu_theme": "Theme",
    "theme_system": "System",
    "theme_light": "Light",
    "theme_dark": "Dark",

    "chart_access_keys": ("Arrow keys select rendered entries. Enter opens a folder; Backspace goes up. "
                          "Use the folder tree for grouped or hidden entries."),
    "chart_access_tree_keys": ("Up/Down selects cards; Right/Left expands/collapses folders. "
                               "Enter opens a folder; Backspace goes up."),
    "chart_access_folder": "Showing folder: {path}",
    "chart_access_selected": "Selected: {path}. Size {size}; on disk {allocated}; {files} files, {folders} folders.",

    "system_file_hibernate": ("Hibernation and Fast Startup state. Windows manages this file. An "
                              "administrator can disable hibernation with powercfg /hibernate off, which "
                              "also removes Hibernate and may affect Fast Startup. FileTree only opens "
                              "power settings."),
    "system_file_pagefile": ("Virtual memory backing file. Windows can manage its size automatically. "
                             "Review Virtual memory under Performance settings on the Advanced tab; "
                             "reducing it can affect applications and crash dumps."),
    "system_file_swapfile": ("Windows swap backing file, including suspended app data. Windows manages "
                             "it together with virtual memory. Review system memory settings instead of "
                             "removing it."),
    "system_file_old": ("Previous Windows installation. Review Previous Windows installation(s) in "
                        "Disk Cleanup → Clean up system files. Removing it prevents going back to th"
                        "at installation."),
    "system_file_recycle": ("Deleted entries still take disk space until the Recycle Bin is emptied. "
                            "Review the Recycle Bin or Storage Sense; emptying is permanent."),
    "system_file_restore": ("System metadata, restore points and shadow copies. Review System "
                            "Protection → Configure to set the restore-point limit. Backup-owned shadow "
                            "copies may need their own backup tools; unread bytes remain unknown."),
    "system_file_winsxs": ("Windows component store. Many entries share hard links with Windows files, "
                           "so per-name totals can overstate distinct storage. Use Windows Update "
                           "Cleanup in Disk Cleanup → Clean up system files; do not remove components m"
                           "anually."),
    "system_file_updates": ("Windows Update download data. Review Windows Update and temporary files "
                            "using Disk Cleanup → Clean up system files. Leave update services to manage"
                            " active downloads."),
    "system_file_delivery": ("Delivery Optimization download cache for Windows updates and apps. Review "
                             "Delivery Optimization Files in Disk Cleanup; Windows manages active "
                             "transfers."),
    "system_tool_power": "Open power settings…",
    "system_tool_memory": "Open advanced system settings…",
    "system_tool_cleanup": "Open Disk Cleanup…",
    "system_tool_storage": "Open Storage Sense…",
    "system_tool_restore": "Open System Protection…",
    "system_tool_failed": "The Windows tool could not be opened.",
    "trash_skip_system_managed": "Windows manages this entry; use its system tool in Details instead",

    "type_locations_title": "Containing folders (up to 1,000)",
    "type_location_size": "Matching size",
    "type_locations_tip": ("Totals include matching files directly in each folder; "
                           "subfolders are separate, without overlap."),

    "action_export_list": "Current list (CSV)…",
    "action_export_list_tip": "Save every row of the active list in its displayed filter and sort order",
    "list_changed": "The list changed during capture. Try exporting or copying again.",

    "details_title": "Details",
    "details_empty": "Select an entry to see its details",
    "details_live": "Distribution is available when scanning finishes.",
    "details_loading": "Calculating type and age distribution…",
    "details_recorded": ("Recorded file totals only; unread entries are outside these distributions. "
                         "Folder modification is the newest recorded date."),
    "details_bucket": "{label}: {size} · {count} files",

    "breadcrumbs_back": "Back (Alt+Left)",
    "breadcrumbs_forward": "Forward (Alt+Right)",
    "breadcrumbs_more": "…",
    "breadcrumbs_more_tip": "Show earlier ancestors",

    "action_print_view": "Print current view…",
    "action_print_view_tip": "Print the visible results on one page through the system print dialog",
    "action_export_view_pdf": "Current view (PDF)…",
    "action_export_view_pdf_tip": "Save the visible results on one fitted PDF page",
    "pdf_filter": "PDF document (*.pdf)",
    "view_pdf_exported": "Saved current view: {path}",
    "print_failed": "Could not print the view: {reason}",
    "print_submitted": "View submitted to the printer",
    "action_export_chart_png": "Chart on screen (PNG)…",
    "action_export_chart_png_tip": "Save the visible chart, including its current viewport",
    "action_export_chart_svg": "Bars or sunburst (SVG)…",
    "action_export_chart_svg_tip": "Save full bounded bars or rings as vector shapes and text",
    "png_filter": "PNG image (*.png)",
    "svg_filter": "SVG image (*.svg)",
    "graphic_exported": "Saved chart: {path}",
    "treemap_colours_age": "By modified age",
    "age_colour_unknown": "Date unknown",
    "age_colour_tip": ("Time since modification. "
                        "Folder colour uses its newest recorded modification; grey means no usable date. "
                        "Grouped tiles stay grey."),
    "action_gentle": "Gentle scanning",
    "action_gentle_tip": "Lower CPU and I/O priority for new scans; may take longer",
    "scan_priority_warning": "Some scan priority settings could not be applied: {reason}",
    "scan_pause": "Pause",
    "scan_resume": "Resume",
    "scan_pause_tip": "Pause new folder reads; current reads finish. Stop works while paused.",
    "scan_paused": "Paused — {progress}",
    "scan_analysing": "Folder reads finished; analysing results…",
    "column_drive_share": "% of drive",
    "columns_reset": "Reset columns",
    "drive_share_tip": ("Logical bytes divided by total volume capacity. Hard-link names count separately; "
                        "this is not allocated or recoverable space. Unknown while capacity is unavailable or stale."),
    "action_recent_actions": "Recent actions…",
    "action_recent_actions_tip": "Inspect retained operation metadata and export a redacted audit report",
    "journal_time": "Time (UTC)",
    "journal_source": "Original path",
    "journal_identity": "Device / file identity",
    "journal_result": "Result",
    "journal_detail": "Detail",
    "journal_destination": "Trash destination",
    "journal_reason_duplicates": "Explicit duplicate decision",
    "journal_status_approved": "Unknown outcome (approved only)",
    "journal_status_moved": "Moved to Trash",
    "journal_status_skipped": "Skipped",
    "journal_status_failed": "Platform move failed",
    "journal_reading": "Reading retained actions…",
    "journal_hint": ("Latest 500 actions; metadata only, retained for 90 days / 50 MB. An approved-only event "
                     "has an unknown final outcome. A recorded Trash path does not guarantee restoration."),
    "journal_summary": "{count} actions shown; {invalid} damaged records and {unavailable} unavailable segments.",
    "journal_read_failed": "The operation journal could not be read: {reason}",
    "journal_write_failed": ("Journal writing or retention failed. Remaining moves were stopped where possible; "
                             "recent actions may be incomplete.\n\n{reason}"),
    "trash_skip_journal": "the approved action could not be recorded; nothing was moved",
    "journal_export": "Export redacted CSV…",
    "journal_exported": "Audit report saved with home-directory prefixes redacted.",
    "duplicate_folder_match": "{copy} = {original} ({size}, {files} files; matching search snapshot)",
    "duplicate_folder_tip": ("Matching names, sizes, verified hashes and empty-folder structure. "
                             "Read-only; not a clean-up approval."),
    "duplicates_keep_selected": "Keep selected copy",
    "duplicates_kept_name": "Kept: {name}",
    "duplicates_kept_path": "Kept copy: {path}.",
    "duplicates_choose_keeper": "Choose a kept copy in this group before selecting extras.",
    "duplicates_group_blocked": "Group left untouched; rescan required: {reason}",
    "trash_skip_duplicate_choose": "choose the kept copy, then review the group again",
    "trash_skip_duplicate_keep": "the kept copy was selected; the group was left untouched; rescan",
    "trash_skip_duplicate_unverified": "no verified hash for this group; rescan and search again",
    "trash_skip_duplicate_hard_links": "a copy has hard-link aliases; the group was left untouched; rescan",
    "trash_skip_duplicate_content": "group contents changed or could not be rehashed; rescan and search again",
    "menu_options": "Options",
    "action_cleanup_policy": "Clean-up policy…",
    "action_cleanup_policy_tip": "Enable rules, change minimum ages and exclude paths from clean-up suggestions",
    "policy_enabled": "Enabled",
    "policy_age": "Minimum age (days)",
    "policy_age_for": "Minimum age for {rule}",
    "policy_enabled_for": "Enable {rule}",
    "policy_hint": "Policy changes affect suggestions only. Manual-risk rules remain unchecked. Preview before saving.",
    "policy_exclusions": ("Never propose these paths or names (one per line; paths must be absolute). "
                          "Scanning is unchanged."),
    "policy_preview": "Preview changes",
    "policy_import": "Import policy JSON…",
    "policy_preview_needed": "Preview the current settings before saving.",
    "policy_preview_running": "Comparing candidate counts and logical sizes…",
    "policy_preview_result": ("Adds {added} candidates ({size}); removes {removed} candidates "
                              "({removed_size}). Nothing moved."),
    "policy_preview_partial": "The scan is incomplete; unseen candidates and bytes remain unknown.",
    "policy_no_scan": "No completed scan: effects cannot be measured. These settings apply to future proposals.",
    "policy_invalid": ("Invalid policy. Use supported rule keys, yes/no flags, ages 0–36500 "
                       "and absolute paths or name patterns."),
    "policy_saved": "Clean-up policy saved; suggestions are being refreshed.",
    "policy_saved_invalid": ("Saved clean-up policy is invalid. Suggestions are disabled until "
                             "the policy is reviewed in Options."),
    "cleanup_review_manual": "Review manually",
    "cleanup_evidence": ("Category: {category}; minimum age: {days} days; risk: {risk}. "
                         "Evidence: {evidence} Rebuild / consequence: {rebuild}"),
    "cleanup_category_temporary": "temporary files",
    "cleanup_category_cache": "downloaded / generated cache",
    "cleanup_category_application_state": "application state",
    "cleanup_category_build": "project build output",
    "cleanup_category_downloads": "user downloads",
    "cleanup_risk_low": "lower risk; verify before moving",
    "cleanup_risk_manual": "manual review; starts unchecked",
    "cleanup_rebuild_temp": "Close the owning application; temporary data cannot necessarily be recreated.",
    "cleanup_rebuild_browser_cache": ("Close the browser; it downloads cached pages again. "
                                      "Profiles and bookmarks are excluded."),
    "cleanup_rebuild_thumbnails": "Close the file manager; previews are generated again when needed.",
    "cleanup_rebuild_crash_dumps": "Keep needed crash evidence; a past crash dump cannot be recreated.",
    "cleanup_rebuild_package_caches": ("Use the package manager to download again; confirm network access. "
                                      "Package stores are excluded."),
    "cleanup_rebuild_build_output": ("Verify project contents and dependency locks, then rebuild using the "
                                    "project's documented commands. Keep authored files."),
    "cleanup_rebuild_old_installers": ("Keep offline or unavailable installers; download from the publisher "
                                      "if still available."),
    "cleanup_rebuild_empty_folders": "Empty folders may still be expected by applications; verify their purpose first.",
    "trash_holder": "{name} (PID {pid})",
    "trash_holders": "{path}: observed open in {programs}. Close the relevant program yourself and retry.",
    "trash_holders_limited": "{path}: process visibility is limited; other holders or causes may be unknown.",
    "duplicates_savings": ("Unique allocated estimate {allocated}; recoverable file data after emptying Trash "
                           "{recoverable}."),
    "duplicates_estimating": ('Estimating unique allocation and recover'
        'able file data…'),
    "duplicates_estimate_unavailable": ('Allocation estimate unavailable. Run the'
        ' search again before selecting extras.'),
    "duplicates_estimate_assumption": ("Estimates use your explicit kept-copy choices; undecided groups are unknown. "
                                      "Each group is checked and fully rehashed before moving. Hard-link aliases "
                                      "block a decision. Shared extents and directory metadata remain unknown; "
                                      "moving to Trash does not free space."),
    'capacity_details': 'Capacity details',
    'capacity_summary': 'OS used {used}; free {free}; unique allocated estimate {unique}. {status}',
    'capacity_estimated': 'Whole-volume estimate; unaccounted space is shown in Details.',
    'capacity_folder_only': 'Folder scan: cannot reconcile the volume.',
    'capacity_incomplete': 'Incomplete scan: cannot reconcile the volume.',
    'capacity_identity_unknown': 'Missing file identities: cannot reconcile the volume.',
    'capacity_capacity_unavailable': 'OS capacity is unavailable; cannot reconcile the volume.',
    'capacity_root_changed': 'Scanned root changed; rescan before reconciling.',
    'capacity_allocation_exceeds_used': 'Allocated estimate exceeds OS used space; cannot reconcile.',
    'capacity_coverage': 'Skipped {skipped}; unreadable {inaccessible}; pending {pending}',
    'capacity_bin_partial': 'The Recycle Bin was not fully identified or read; its shown amount is only data seen.',
    "capacity_explanation": ('Known file allocation includes the Recycle'
                             ' Bin data seen. Hard-link names count once'
                             '. Other mounted volumes are excluded. Omit'
                             'ted data and filesystem metadata are unkno'
                             'wn, not zero. Unaccounted may include inac'
                             'cessible data, metadata, snapshots, shared'
                             ' extents and allocation estimates. OS capa'
                             'city and files are measured at different i'
                             'nstants; the filesystem can change during '
                             'scanning. Unavailable free space is the di'
                             'fference between reported total, used and '
                             'available free, not a measured metadata to'
                             'tal. These are estimates pending NTFS, ext'
                             '4 and APFS volume validation.'),
    'capacity_row_total': 'OS total',
    'capacity_row_used': 'OS used',
    'capacity_row_free': 'OS available free',
    'capacity_row_unavailable_free': 'Unavailable free space',
    'capacity_row_named_allocated': 'Named allocated estimate',
    'capacity_row_unique_allocated': 'Unique allocated estimate',
    'capacity_row_hard_link_overcount': 'Hard-link overcount removed',
    'capacity_row_recycle_bin_seen': 'Recycle Bin allocation seen (included)',
    'capacity_row_foreign_allocated_seen': 'Other-volume file allocation seen (excluded)',
    'capacity_row_unaccounted': 'Unaccounted',
    'capacity_row_metadata_bytes': 'Filesystem metadata / reserved',
    'capacity_row_omitted_bytes': 'Omitted data',
    'capacity_row_other_volumes_bytes': 'Other mounted volumes',
    'capacity_row_mounts': 'Different-device mount boundaries',
    'capacity_row_coverage': 'Coverage',
    "review_title": "Review clean-up proposals",
    "review_details": "{path}\nRule: {rule}; protection: {protection}. {consequence}",
    "review_hint": "Review every path and consequence. Uncheck entries to keep them; Continue opens the confirmations.",
    "review_select": "Move",
    "review_rule": "Rule",
    "review_reason": "Reason",
    "review_protection": "Protection",
    "review_consequence": "Consequence",
    "review_manual": "Manual selection",
    "review_manual_reason": "User-selected entry; removing it may affect files or programs that depend on it.",
    "review_not_protected": "No protected-path match",
    "review_open_folder": "Open containing folder",
    "review_continue": "Continue to confirmation",
    "review_estimating": "{count} entries selected; estimating allocation…",
    "review_summary": ("{count} entries; logical {logical}; allocated estimate {allocated}; recoverable file data "
                       "after emptying the Recycle Bin: {recoverable}; free now {free}. "
                       "Shared extents and directory metadata remain unknown. Moving to Trash does not free space."),
    "size_unknown": "unknown",
    "trash_running": "Revalidating and moving approved entries… Stop cancels remaining entries.",
    "trash_batch_done": "Moved {moved}, skipped {skipped}, failed {failed}; {size} moved to the Recycle Bin.",
    "trash_skipped": "These entries were skipped. Rescan their folders before trying again:\n{names}",
    "trash_skip_outside": "outside the current scan",
    "trash_skip_unverified": "no verified scan identity",
    "trash_skip_incomplete": "incomplete scan coverage",
    "trash_skip_missing": "entry or parent is missing",
    "trash_skip_unreadable": "entry cannot be read",
    "trash_skip_link": "entry or parent became a link",
    "trash_skip_kind": "entry kind changed",
    "trash_skip_identity": "entry was replaced",
    "trash_skip_changed": "size, timestamps or folder contents changed",
    "trash_skip_protected": "resolved path has different protection",
    "trash_skip_cancelled": "operation cancelled",
    "coverage_complete": ("Coverage: {size} known in {known} folders; skipped {skipped}, "
                          "inaccessible {denied}, pending {pending}."),
    "coverage_partial": ("Incomplete coverage: {size} known in {known} folders; skipped {skipped}, inaccessible "
                         "{denied}, pending {pending}. Omitted bytes are unknown. "
                         "Rescan incomplete branches before cleanup; "
                         "Select all is disabled."),
    "problem_hidden_omitted": "Hidden entries were omitted; their size is unknown.",
    "problem_partial_folder": "Some entries could not be read; this folder is incomplete.",
    "app_title": "FileTree",
    "about_text": "<h3>FileTree {version}</h3><p>See where your disk space goes.</p>"
                  "<p>MIT License · © 2026 JE-Chen</p>",
    # menus and actions
    "menu_file": "&File",
    "menu_export": "&Export",
    "menu_view": "&View",
    "menu_unit": "Size &unit",
    "menu_language": "&Language",
    "menu_help": "&Help",
    "action_open": "Choose folder…",
    "action_open_tip": "Pick a folder or drive to scan",
    "action_rescan": "Rescan",
    "action_rescan_tip": "Scan the same folder again to pick up changes",
    "action_stop": "Stop",
    "action_stop_tip": "Stop the scan that is running",
    "action_export_folders": "Folder list (CSV)…",
    "action_export_folders_tip": "Save every folder with its size, for Excel or other spreadsheets",
    "action_export_largest": "Largest files (CSV)…",
    "action_export_largest_tip": "Save the list of the largest files",
    "action_export_json": "Folder tree (JSON)…",
    "action_export_json_tip": "Save the folder tree for scripts and other programs",
    "action_trash": "Move to Recycle Bin",
    "action_trash_tip": "Move the selected files and folders to the Recycle Bin (you are asked first)",
    "action_find": "Find…",
    "action_find_tip": "Find files and folders by name anywhere in the scan",
    "action_quit": "Quit",
    "action_quit_tip": "Close FileTree",
    "action_hidden": "Include hidden files",
    "action_exclusions": "Skip while scanning…",
    "action_exclusions_tip": "Folders and folder names that scans leave out, such as node_modules",
    "exclusions_title": "Skip while scanning",
    "exclusions_hint": ("Scans leave these folders out: they are listed, greyed out, with size 0. A name such as "
                        "node_modules or *.cache skips every folder of that name; a folder path skips that one "
                        "folder. The list applies from the next scan."),
    "exclusions_add_name": "Add a name…",
    "exclusions_add_folder": "Add a folder…",
    "exclusions_remove": "Remove",
    "exclusions_name_prompt": "Folder name, * and ? allowed:",
    "exclusions_saved": "{count} exclusions saved; they apply from the next scan.",
    "tooltip_excluded": "{path}\nSkipped: it is in View → Skip while scanning",
    "action_hidden_tip": "Count hidden files and folders (applies to the next scan)",
    "action_help": "How to use",
    "action_help_tip": "Short guide to FileTree",
    "action_about": "About FileTree",
    "action_about_tip": "Version and license",
    "app_title_admin": "FileTree (Administrator)",
    "action_elevate": "Restart as administrator",
    "action_elevate_tip": "Start FileTree again with administrator rights, so it can read every folder",
    "action_ask_admin": "Ask for administrator rights at start",
    "action_ask_admin_tip": "Windows asks for permission when FileTree starts, so protected folders can be read too",
    "problems_hint": "Some folders need administrator rights. Restart FileTree as administrator to read them too.",
    "elevate_declined": "FileTree is still running without administrator rights.",
    "unit_auto": "Automatic",
    "path_placeholder": "Type or paste a folder path and press Enter",
    "choose_folder_title": "Choose a folder to scan",
    # welcome page
    "welcome_title": "See where your disk space goes",
    "welcome_subtitle": "Pick a folder or a whole drive. FileTree adds up every file inside it and shows "
                        "you the biggest folders and files first.",
    "welcome_choose": "Choose a folder…",
    "welcome_drives": "Drives",
    "welcome_drive_tip": "Scan {path}",
    "welcome_drive_free": "{free} free of {total}",
    "welcome_recent": "Recently scanned",
    "welcome_tip": "Tip: you can also drag a folder from your file manager onto this window. Paste an absolute "
                   "UNC share path on Windows (\\\\server\\share); access uses your current account. Scan workers "
                   "can be adjusted in Options. Denied/disconnected branches remain incomplete, not empty.",
    # scanning
    "scan_starting": "Starting…",
    "scan_progress": "Scanning… {files} files in {folders} folders · {size} · {time}",
    "scan_stop": "Stop",
    "scan_stopping": "Stopping…",
    "scan_cancelled": "Scan stopped.",
    "scan_stopped_partial": "Scan stopped: the results show what was read so far.",
    "scan_failed_title": "Cannot scan",
    "scan_mount_changed": "Mount boundaries changed or could not be verified. Scan again before using these results.",
    "scan_failed": "FileTree could not read {path}.\n\nReason: {reason}",
    "not_a_folder": "{path} is not a folder that exists.",
    "duration_seconds": "{value} s",
    "duration_minutes": "{minutes} min {seconds} s",
    # results
    "summary": "<b>{path}</b> — {size} ({allocated} on disk) in {files} files and {folders} folders "
               "(scanned in {time})",
    "summary_live": "<b>{path}</b> — {size} ({allocated} on disk) in {files} files and {folders} folders so far",
    "summary_partial": "<b>{path}</b> — {size} ({allocated} on disk) in {files} files and {folders} folders · "
                       "<b>incomplete</b>: the scan was stopped after {time}",
    "tab_chart": "Chart",
    "chart_treemap": "Treemap",
    "treemap_levels": "Levels",
    "treemap_levels_all": "All",
    "treemap_colours": "Colours",
    "treemap_colours_type": "By file type",
    "treemap_colours_folder": "By folder",
    "chart_treemap_tip": "Every file as a rectangle sized by the space it takes",
    "chart_bars": "Bars",
    "chart_sunburst": "Sunburst",
    "chart_tree": "Tree",
    "chart_tree_tip": "Folder hierarchy: expand branches, Ctrl+wheel to zoom, double-click to focus",
    "tree_orientation": "Direction",
    "tree_orientation_horizontal": "Left to right",
    "tree_orientation_vertical": "Top to bottom",
    "tree_more": "{count} more folders · {size}",
    "tree_unavailable": "Not scanned",
    "chart_sunburst_tip": "The folder in the centre, each deeper level a ring; click the centre to go up",
    "chart_bars_tip": "One bar per entry of the folder, largest first, with its size and share",
    "bars_empty_folder": "This folder is empty.",
    "bars_more": "{count} more: {size}",
    "tab_largest": "Largest files",
    "scope_folder": "Selected folder only",
    "scope_folder_named": "Only in {name}",
    "scope_folder_tip": ("Show the largest files, types and ages of the folder selected in the tree instead of "
                         "the whole scan"),
    "tab_search": "Search",
    "tab_changes": "Changes",
    "action_compare": "Compare with a saved scan…",
    "action_compare_tip": "Open a scan saved with Export → Folder tree (JSON) and see what grew since",
    "compare_title": "Compare with a saved scan",
    "compare_failed": "This file is not a scan saved by FileTree:\n{reason}",
    "column_before": "Before",
    "column_now": "Now",
    "column_change": "Change",
    "changes_new": "new",
    "changes_gone": "gone",
    "changes_whole_scan": "(the scanned folder)",
    "changes_stop": "Stop comparing",
    "changes_running": "Comparing…",
    "changes_waiting": "The comparison follows when the scan is done.",
    "changes_unknown_time": "at an unknown time",
    "changes_summary": ("Compared with {path}, saved {when}: {before} then, {now} now ({change}); "
                        "{count} folders changed."),
    "tab_duplicates": "Duplicates",
    "tab_cleanup": "Clean up",
    "cleanup_suggestions": "Suggestions",
    "cleanup_select_all": "Select all",
    "cleanup_select_group": "Select this group",
    "cleanup_running": "Looking for things to clean up…",
    "cleanup_hint": "Places whose contents can usually go appear here after a scan.",
    "cleanup_none": "Nothing to suggest in this scan.",
    "cleanup_summary": ("{size} logical size in {groups} groups. Select entries to review paths and allocation "
                        "before moving to the Recycle Bin; moving does not free space immediately."),
    "cleanup_group": "{title} — {size} ({count})",
    "cleanup_temp": "Temporary files",
    "cleanup_temp_tip": "Files programs left behind for a while; a program that is still running may need some.",
    "cleanup_browser_cache": "Browser caches",
    "cleanup_browser_cache_tip": "Copies of web pages and pictures; browsers download them again as needed.",
    "cleanup_thumbnails": "Thumbnail caches",
    "cleanup_thumbnails_tip": "Small previews of pictures; they are made again when folders are opened.",
    "cleanup_crash_dumps": "Crash dumps",
    "cleanup_crash_dumps_tip": "Memory saved when a program crashed, only useful to report the crash.",
    "cleanup_package_caches": "Package download caches (pip, npm…)",
    "cleanup_package_caches_tip": ("Downloaded packages kept for the next install; they are downloaded again when "
                                   "needed."),
    "cleanup_build_output": "Build output (can be rebuilt)",
    "cleanup_build_output_tip": ("Installed dependencies and compiled files of projects; building the project again "
                                 "recreates them."),
    "cleanup_old_installers": "Installers in Downloads",
    "cleanup_old_installers_tip": ("Setup files that were most likely run long ago; keep the ones you install from "
                                   "again."),
    "cleanup_empty_folders": "Empty folders",
    "cleanup_empty_folders_tip": "Folders with nothing in them, or only other empty folders.",
    "duplicates_min_size": "Compare files from",
    "duplicates_any_size": "any size",
    "duplicates_find": "Find duplicates",
    "duplicates_stop": "Stop",
    "duplicates_select_extra": "Select extra copies",
    "duplicates_select_extra_tip": ("Select extras in groups with a chosen keeper and successful checks; "
                                    "then press Delete"),
    "duplicates_hint": ("Finds files with the same content anywhere in the scan. Only files of the same size are "
                        "read, but reading takes time, so small files are left out unless you choose a smaller size."),
    "duplicates_starting": "Looking for files of the same size…",
    "duplicates_running": "Read {files} of {total} files ({read} of {bytes})…",
    "duplicates_stopped": "The search was stopped.",
    "duplicates_none": "No duplicate files found.",
    "duplicates_summary": ('{groups} groups of duplicates: {extra} l'
        'ogical size in extra copies.'),
    "duplicates_limited": "The {shown} groups with the most extra space are listed.",
    "duplicates_skipped": "{count} files could not be read.",
    "duplicates_group": ('{count} copies × {size}: {extra} logical'
        ' extra-copy size.'),
    "search_placeholder": "Part of a name, or a pattern: backup, *.mp4, *.iso;*.zip",
    "search_hint": ("Type part of a name or a pattern with * and ?, choose conditions, or both, to find files "
                    "and folders anywhere in the scan."),
    "search_running": "Searching…",
    "search_larger": "Larger than",
    "search_smaller": "Smaller than",
    "search_no_limit": "no limit",
    "search_changed": "Changed",
    "search_changed_any": "any time",
    "search_changed_week": "in the last week",
    "search_changed_month": "in the last month",
    "search_changed_year": "in the last year",
    "search_changed_stale_year": "not for a year",
    "search_changed_stale_2y": "not for 2 years",
    "search_changed_stale_5y": "not for 5 years",
    "search_type": "Type",
    "search_type_any": "any type",
    "search_show": "Show",
    "search_kind_any": "files and folders",
    "search_kind_files": "files only",
    "search_kind_folders": "folders only",
    "search_saved": "Saved searches",
    "search_saved_none": "(none)",
    "search_save": "Save…",
    "search_delete": "Delete",
    "search_save_title": "Save this search",
    "search_save_prompt": "Name:",
    "search_none": "Nothing matches.",
    "search_summary": "{count} matches, {size} in total.",
    "search_limited": "The {shown} largest are listed.",
    "tab_types": "File types",
    "tab_age": "Age",
    "column_age": "Last changed",
    "age_month": "Within a month",
    "age_half_year": "1–6 months ago",
    "age_year": "6–12 months ago",
    "age_two_years": "1–2 years ago",
    "age_older": "Over 2 years ago",
    "largest_focus": "Showing only: {what}",
    "largest_show_all": "Show all",
    "list_files_tip": "Double-click a row to list its largest files",
    "tab_problems": "Problems",
    "tab_problems_count": "Problems ({count})",
    "column_name": "Name",
    "column_size": "Size",
    "column_allocated": "On disk",
    "column_share": "% of parent",
    "column_share_total": "% of total",
    "column_files": "Files",
    "column_folders": "Folders",
    "column_modified": "Modified",
    "column_folder": "Folder",
    "column_extension": "Extension",
    "column_type": "Type",
    "column_path": "Path",
    "column_problem": "Problem",
    "problem_access_denied": "Access denied",
    "problem_not_found": "No longer there",
    "problem_path_too_long": "Path too long",
    "problem_not_scanned": "Not scanned: the scan was stopped first",
    "no_extension": "(no extension)",
    "tooltip_unreadable": "{path}\nCould not be read: {reason}",
    "tooltip_link": "{path}\nLink: shown but not followed",
    "tooltip_not_scanned": "{path}\nNot scanned: the scan was stopped first",
    "treemap_empty": "Nothing to show",
    "treemap_up": "↑ Up",
    "treemap_up_tip": "Show the folder above",
    "treemap_tooltip": "<b>{name}</b><br>{size} ({share} of this view)<br>{path}",
    "treemap_more": "{count} more",
    "treemap_more_tooltip": "<b>{count} smaller entries</b> of {name}, each too small to draw<br>"
                            "{size} ({share} of this view)",
    "treemap_more_open": "Double-click to show this folder on its own",
    "largest_filter": "Filter by name or folder…",
    "types_all": "All types",
    "category_images": "Pictures",
    "category_video": "Videos",
    "category_audio": "Music and audio",
    "category_documents": "Documents",
    "category_archives": "Archives and disk images",
    "category_code": "Code and data",
    "category_programs": "Programs",
    "category_other": "Other",
    "status_selected": "{name}: {size} ({share} of its folder)",
    "status_selected_root": "{name}: {size}",
    # entry menu
    "menu_open_item": "Open",
    "menu_reveal": "Show in file manager",
    "menu_copy_path": "Copy path",
    "menu_show_chart": "Show in chart",
    "menu_scan_here": "Scan this folder",
    "menu_rescan_here": "Rescan this folder",
    "rescan_done": "Rescanned {name}: {before} → {after}",
    "trash_confirm_title": "Move to Recycle Bin",
    "protected_title": "System or program folder",
    "protected_question": ("{count} of the entries are system or program folders. Moving them can make the "
                           "system or programs stop working:\n\n{names}\n\nMove them anyway?"),
    "protected_system": "part of the operating system",
    "protected_programs": "installed programs",
    "protected_settings": "programs' settings and data",
    "protected_profile": "a user's profile folder",
    "trash_confirm": "Move “{name}” ({size}) to the Recycle Bin?\n\nYou can restore it from there.",
    "trash_failed": "“{name}” could not be moved to the Recycle Bin. It may be in use or read-only.",
    "trash_done": "Moved “{name}” to the Recycle Bin: {size} freed.",
    "action_trash_many": "Move {count} items to Recycle Bin",
    "trash_confirm_many": ("Move these {count} items ({size} in total) to the Recycle Bin?\n\n{names}\n\n"
                           "You can restore them from there."),
    "trash_more": "…and {count} more",
    "trash_failed_many": ("{count} items could not be moved to the Recycle Bin. "
                          "They may be in use or read-only:\n\n{names}"),
    "trash_done_many": "Moved {count} items to the Recycle Bin: {size} freed.",
    "status_selected_many": "{count} items selected: {size}",
    # export
    "export_title": "Export",
    "export_running": "Saving to {path}…",
    "csv_filter": "CSV files (*.csv)",
    "json_filter": "JSON files (*.json)",
    "export_done": "Saved {count} rows to {path}",
    "export_failed": "The file could not be saved.\n\nReason: {reason}",
    # help
    "help_title": "How to use FileTree",
    "help_html": """
<h2>FileTree in three steps</h2>
<ol>
<li><b>Choose what to scan.</b> Click <i>Choose a folder…</i> or one of the drives, drag a folder
onto the window, or type a path in the box at the top and press Enter.</li>
<li><b>Watch it fill in.</b> The tree appears right away and the biggest folders move to the top
while FileTree adds up every file; the largest files and file types follow when the scan ends. Press
<i>Stop</i> (or Esc) at any time: what was read so far stays on screen, marked as incomplete.</li>
<li><b>Find what takes the space.</b> The biggest folders are at the top of the tree. Click the arrow
next to a folder to look inside.</li>
</ol>
<h2>Reading the results</h2>
<ul>
<li><b>Folder tree</b> (left): the size of each folder or file, the space it takes <i>on disk</i> (whole
clusters, so usually a little more; less for compressed files, nothing for files kept only online), a
<i>% of parent</i> bar (how much of
the folder above it this entry takes), how many files and folders it holds, and when something in it
last changed. Click a column title to sort by it.</li>
<li><b>Chart</b>: switch between four views of the same folder in the corner of the tab (the treemap
comes first, and FileTree remembers the one you chose). The
<i>Treemap</i> draws every file as a rectangle, the bigger the file the bigger the rectangle; each folder
has a strip with its name and size, and the files of a folder too small to see share one grey, hatched
tile (<i>12 more</i>): double-click it to show that folder on its own. <i>Levels</i> sets how many levels
are drawn, <i>Colours</i> colours by file type (the legend is under it) or by top-level folder.
<i>Bars</i> gives each entry of the folder one bar, largest first, with its size and share, the easiest
to read exactly. The <i>Sunburst</i> puts the folder in the centre and each deeper level in a ring around
it; click the centre to go up. The <i>Tree</i> shows expandable folder cards; click + or an “other folders”
card to reveal more, choose the direction, Ctrl+wheel to zoom and scroll to pan. Click to find an entry in
the folder tree, double-click a folder to go into it,
and press <i>Up</i> to go back.</li>
<li><b>Largest files</b>: the 1,000 biggest files anywhere in the scan. Type in the filter box to
narrow the list; double-click a row to find the file in the tree.</li>
<li><b>Search</b> (Ctrl+F): files and folders whose name contains what you type, anywhere in the scan.
A pattern such as <code>*.mp4</code> must match the whole name; separate several with <code>;</code>
(<code>*.iso;*.zip</code>). The conditions under the box (size, when last changed, file type, files or
folders) narrow the search or make one on their own, and <i>Save…</i> keeps a search under a name. The
1,000 largest matches are listed, with the count and total size of all.</li>
<li><b>Clean up → Suggestions</b>: after every scan, the places whose contents can usually go, one group per
kind (temporary files, caches, crash dumps, build output that can be rebuilt, old installers in Downloads,
empty folders); hover over a group to see what deleting it does, then <i>Select this group</i> or
<i>Select all</i> and press Delete.</li>
<li><b>Clean up → Duplicates</b>: press <i>Find duplicates</i> to group files with the same content. Only files of the
same size are read; files under 1 MB are left out unless you choose a smaller size, because reading takes
time. Each group lists its copies oldest first; <i>Select extra copies</i> selects all but the oldest, and
Delete moves them to the Recycle Bin.</li>
<li><b>File types</b>: how much space each kind of file takes, per extension. Pick a type in the list
above the table to see only that kind; double-click a row to list the largest files of that type.</li>
<li><b>Age</b>: how much space was last changed within a month, 1–6 months ago, and so on up to over two
years ago. Old data is often what can be archived or deleted; double-click a row to list its largest
files.</li>
<li><b>Problems</b>: folders FileTree was not allowed to read. What is inside them is not counted.</li>
</ul>
<h2>Freeing space</h2>
<p>Right-click any entry to <i>Open</i> it, <i>Show in file manager</i>, <i>Copy path</i>,
<i>Show in treemap</i>, <i>Rescan this folder</i> (after changes made outside FileTree; the rest of the
results stay), <i>Scan this folder</i> on its own, or <i>Move to Recycle Bin</i>.
To move several entries at once, pick them with Ctrl+click or Shift+click in the folder tree, the
<i>Largest files</i> list or the <i>Search</i> results: FileTree asks once, listing them with their total size.
FileTree never deletes anything for good: it always asks first, and whatever it moves can be restored
from the Recycle Bin (the Trash on macOS and Linux). The numbers update right away, without a rescan.
System and program folders are asked about twice, with the reason; temporary folders and caches are not.</p>
<h2>Seeing what grew</h2>
<p>Save a scan with <i>File → Export → Folder tree (JSON)</i>. Later, after a new scan, choose
<i>File → Compare with a saved scan…</i> and open that file: the <b>Changes</b> tab lists every folder that
changed, with its size then and now, the biggest growth first (<i>new</i> and <i>gone</i> mark folders that
appeared or disappeared). It keeps comparing after each rescan until you press <i>Stop comparing</i>.</p>
<h2>Keyboard shortcuts</h2>
<table cellpadding="3">
<tr><td><b>Ctrl+O</b></td><td>Choose a folder</td></tr>
<tr><td><b>F5</b></td><td>Rescan</td></tr>
<tr><td><b>Esc</b></td><td>Stop the scan</td></tr>
<tr><td><b>Ctrl+F</b></td><td>Search by name</td></tr>
<tr><td><b>Delete</b></td><td>Move the selected entries to the Recycle Bin</td></tr>
<tr><td><b>F1</b></td><td>This guide</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>Quit</td></tr>
</table>
<p>On macOS use ⌘ instead of Ctrl (⌘R to rescan).</p>
<h2>Good to know</h2>
<ul>
<li>Sizes are the real file sizes in binary units (1 KB = 1,024 bytes), the same as Windows Explorer.
Choose a fixed unit under <i>View → Size unit</i>.</li>
<li>Shortcuts and links (symbolic links, junctions) are listed but never followed, so nothing is
counted twice.</li>
<li>On Windows, FileTree asks for administrator rights when it starts, like TreeSize, so it can read
protected folders too. Say no and it runs normally; folders it could not read are listed under
<i>Problems</i>, with a <i>Restart as administrator</i> button. Turn the question off under
<i>View → Ask for administrator rights at start</i>.</li>
<li><i>Largest files</i>, <i>File types</i> and <i>Age</i> cover the whole scan; <i>Selected folder only</i>,
at the top right of those tabs, makes them follow the folder selected in the tree.</li>
<li>Hidden files are counted. Turn off <i>View → Include hidden files</i> to leave them out of the
next scan.</li>
<li>To leave folders out of every scan, list them in <i>View → Skip while scanning</i>: a name such as
<code>node_modules</code> skips every folder of that name, a path skips one folder. Skipped folders are
listed greyed out, with size 0.</li>
<li>Save the results with <i>File → Export</i>: CSV opens in Excel, JSON is for scripts.</li>
</ul>
""",
}

ZH_TW: dict[str, str] = {
    "namespace_source_name": "來源名稱",
    "namespace_destination_name": "目的地名稱",
    "namespace_closed_errors": "已停止／關閉的作業回報錯誤。請檢查詳細資料中的來源／目的地路徑。",
    "namespace_refreshed": "已重掃 {path}：{files} 個檔案；{errors} 個掃描錯誤。",
    "namespace_refresh_failed": "重掃失敗，路徑 {path}：{reason}",
    "namespace_refreshing": "正在重掃受影響的目的地：{path}",
    'menu_move_folder': '移至資料夾…',
    'menu_rename': '重新命名…',
    'namespace_source': '來源',
    'namespace_destination': '目的地',
    'namespace_status': '狀態',
    'namespace_pattern': '檔名模式',
    'namespace_rename_hint': ('檢視每個來源與目的地。字面代換：{name}、{stem}、{ext}、{n}。'
                            '僅限同磁碟，不覆寫。最多選取 1,000 個項目。'),
    'namespace_move_hint': ('選擇現有目的地資料夾，檢視每組路徑。僅限同磁碟，不覆寫。'
                          '拒絕受保護、連結、無法取得或記錄不完整的項目。最多選取 1,000 個項目。'),
    'namespace_collision_skip': '名稱已存在：略過',
    'namespace_collision_rename': '名稱已存在：預覽編號尾碼',
    'namespace_preview': '預覽路徑',
    'namespace_apply': '套用已檢視的路徑…',
    'namespace_reading': '正在檢查來源與目的地中繼資料…',
    'namespace_preview_needed': '選項已變更；套用前請重新預覽路徑。',
    'namespace_summary': '{total} 組最外層路徑；{ready} 組可執行；{skipped} 組拒絕／未變更。',
    'namespace_confirm': ('要套用預覽中 {count} 組可執行的來源／目的地嗎？其餘 {skipped} '
     '組將略過。詳細資料列出每組可執行路徑。不覆寫現有名稱。停止／關閉須等目前重新命名完成，已完成的變更會保留。'),
    'namespace_progress': '已處理 {done}／{total} 組路徑',
    'namespace_done': '已移動／重新命名：{moved}；略過：{skipped}；失敗：{failed}。關閉後更新掃描。',
    'namespace_failed': '作業失敗：{reason}',
    'namespace_reason_ready': '可執行',
    'namespace_reason_unverified': '身分未知',
    'namespace_reason_link': '拒絕連結',
    'namespace_reason_special': '拒絕特殊項目',
    'namespace_reason_unavailable': '無法取得／雲端項目',
    'namespace_reason_cancelled': '已停止',
    'namespace_reason_outside': '目前掃描範圍外／根目錄',
    'namespace_reason_missing': '來源不存在',
    'namespace_reason_kind': '項目類型已變更',
    'namespace_reason_identity': '來源已被取代',
    'namespace_reason_changed': '來源已變更',
    'namespace_reason_incomplete': '來源記錄不完整',
    'namespace_reason_unreadable': '無法讀取來源',
    'namespace_reason_system_managed': '系統管理的來源',
    'namespace_reason_protected': '受保護的來源',
    'namespace_reason_unchanged': '名稱未變更',
    'namespace_reason_descendant': '目的地位於選取的來源內',
    'namespace_reason_protected_destination': '受保護的目的地',
    'namespace_reason_volume': '不同磁碟；須驗證複製',
    'namespace_reason_collision': '名稱已存在',
    "photos_exact": "精確重複檔案",
    "photos_find": "尋找相似照片",
    "photos_similar": "相似照片",
    "photos_distance": "雜湊距離（0–16）：",
    "photos_hint": ("僅為視覺候選：請比較縮圖與原圖。雜湊可能碰撞；"
                    "不自動選擇保留副本、多餘副本或估計回收量。動畫只看第一格。"),
    "photos_group": "{count} 張圖片；與第一張的距離在 {distance} 位元內",
    "photos_running": "正在讀取圖片：{read}；略過／失敗：{skipped}",
    "photos_summary": "{groups} 組相似圖片；已讀取 {read} 張；略過／失敗 {skipped} 張。",
    "photos_limited": "清單或顯示範圍受限；最多顯示 {count} 個圖片列／縮圖。",
    "archive_loading": "正在讀取壓縮檔中繼資料…",
    "archive_virtual_name": "{name}［虛擬］",
    "archive_virtual_hint": "壓縮檔內容：宣告的未壓縮大小，不計入磁碟總量。不提供檔案操作或解壓縮。",
    "archive_failed": "無法預覽：{reason}",
    "archive_rejected": "已略過 {count} 個不安全、連結或衝突的項目",
    "archive_empty": "沒有可預覽的項目",
    "archive_stopped": "壓縮檔預覽已停止；內容清單不完整",
    "archive_busy": "已有兩個壓縮檔讀取工作；重新掃描後可重試",
    "archive_stop": "停止讀取此壓縮檔",
    "action_count_hard_links": (
        "觀察到的硬連結只計一次"
    ),
    "action_count_hard_links_tip": (
        "預設關閉；後續掃描保留具名大小並新增計入總量。分支／資源回收筒移動後會重掃完整範圍。"
    ),
    "column_accounted_size": (
        "計入大小"
    ),
    "column_accounted_allocated": (
        "計入磁碟大小"
    ),
    "hard_links_hint": (
        "啟用硬連結計量時，觀察到的路徑排序第一個名稱計入位元組，其他名稱在此計為零。具名大小仍是實際檔案長度。未知／不一致記錄保留估計值，共用資料區"
        "段仍未知。"
    ),
    "hard_links_summary": (
        "計入：{size}（磁碟估計 {allocated}）；觀察到 {aliases} 個別名；未知記錄 {unknown} 個。圖表使用計入總"
        "量，檔案／類型／檔齡列表保留具名大小。"
    ),
    "compression_mode_ntfs": "NTFS 壓縮",
    "compression_mode_xpress8k": "XPRESS8K 壓縮（少修改的檔案）",
    "compression_mode_uncompress": "解壓縮（NTFS 及執行檔模式）",
    "compression_apply": "處理列表中的檔案…",
    "compression_restore_summary": "{count}/{total} 個已記錄檔案可供檢查；顯示 {shown} 個。壓縮狀態可能未知。",
    "compression_confirm": (
        "範圍：{path}\n模式：{mode}\n僅處理列表中的 {count} 個檔案（邏輯大小 {size}），"
        "候選項目共 {total} 個。\n\n會重新核對目前 NTFS "
        "範圍與未變更的檔案。拒絕連結、雲端／離線、稀疏、隱藏／系統、硬連結及受保護檔案。"
        "不變更資料夾預設值及列表外檔案。壓縮可能降低寫入速度；XPRESS "
        "適合少修改的資料。解壓縮需要足夠可用空間。停止或失敗可能留下部分變更。\n\n關閉此視窗會取消目前命令、等待結束，再以逐檔磁碟大小量測重新掃描此資料夾。是否繼續？"
    ),
    "compression_progress": "正在處理列表中的 {done}/{total} 個檔案…",
    "compression_done": (
        "{done}/{attempted} 個命令完成；失敗 {failures} 個。"
        "核對成功的已知檔案分配：{before} → {after}；未知量測 {unknown} "
        "個。關閉後重新掃描；總計不保證可釋出空間。顯示前 20 筆錯誤。"
    ),
    "compression_canceled": "已停止；先前或目前檔案可能已變更。關閉後重新掃描。",
    "compression_failed": "操作失敗：{reason}。可能有部分變更，關閉後重新掃描。",
    "action_exact_allocation": "量測 Windows 逐檔磁碟大小",
    "action_exact_allocation_tip": (
        "預設關閉，後續掃描增加中繼資料查詢，包含 XPRESS／WOF 檔案。啟用後請重新掃描。"
        "已知雲端／離線檔案不會查詢，失敗結果仍使用估計值。"
    ),
    "menu_compression": "NTFS 壓縮…",
    "compression_reading": "正在檢查已記錄的壓縮候選項目…",
    "compression_summary": (
        "{count}/{total} 個檔案為類型候選，顯示 {shown} 個；邏輯大小 {logical}，具名磁碟分配 {allocated}。"
        "可能節省 0–{allocated}，不預測固定壓縮率。{unknown} 個檔案的中繼資料未知。"
    ),
    "compression_volume": "檔案系統：{filesystem}；分配單位：{unit}",
    "compression_unknown": "未知",
    "compression_ntfs_only": "無法確認 NTFS，此範圍不能進行原生壓縮。",
    "compression_partial": "掃描不完整：略過／無法讀取的資料不在此估算範圍。",
    "compression_hint": (
        "唯讀類型估算：日誌、文字、程式碼與可能未壓縮的影像格式。副檔名不能證明可壓縮程度。"
        "不含隱藏／系統、壓縮／稀疏、重新解析／雲端／離線或中繼資料未知的項目。"
        "具名磁碟分配可能是估計值或由硬連結共用，不保證可回收空間；不讀取檔案內容。"
        "按兩下選取已記錄的檔案，Ctrl+C 複製列表。"
    ),
    "action_capture_owners": "記錄 Windows 檔案擁有者",
    "action_capture_owners_tip": "預設關閉；後續掃描增加擁有者中繼資料查詢，啟用後請重新掃描",
    "tab_users": "使用者",
    "column_owner": "擁有者",
    "column_owner_id": "擁有者識別碼",
    "owner_unknown": "擁有者未知",
    "owners_refresh": "更新記錄總計",
    "owners_reading": "正在加總擁有者記錄並查詢帳號名稱…",
    "owners_unqueried": "掃描完成後開啟「使用者」，即可查詢已記錄的擁有者總計。",
    "owners_partial": "掃描不完整：略過／無法讀取的大小與擁有者保持未知。",
    "owners_summary": (
        "{count} 組擁有者，顯示 {shown} 組；{files} 個檔案，{size}。"
        "擁有者未知：{unknown_files} 個檔案，{unknown_size}。"
    ),
    "owners_hint": (
        "使用整份掃描，僅按檔案擁有者加總；資料夾擁有者不會套用至內含檔案。"
        "POSIX uid 來自掃描已讀取的 stat；Windows 請啟用「選項 → 記錄 Windows 檔案擁有者」並重新掃描。"
        "未啟用、失敗、路徑已變或雲端／離線查詢保持未知，名稱可能改顯示 uid／SID。"
        "具名磁碟分配仍是估計值，硬連結按各名稱計算。擁有者不能證明實際使用或移除權限；此處不會準備清理操作。"
    ),
    "bin_labels_refresh": "更新回收筒大小",
    "bin_labels_hint": (
        "唯讀快照，最多查詢 256 個就緒磁碟，優先查詢掃描所在磁碟。"
        "POSIX 大小為內容的邏輯位元組；無法取得或不完整的總計不代表零。"
        "範圍可能重疊，請勿加總。按更新才會查詢，此處不會準備清理操作。"
    ),
    "bin_label_scope_unknown": "此掃描所在磁碟的資源回收筒：尚未查詢範圍",
    "bin_label_unqueried": "{root} 資源回收筒：尚未查詢",
    "bin_label_total": "{root} 資源回收筒：{size}，{count} 個項目",
    "bin_label_partial": "{root} 資源回收筒：總計未知；已知 {size}，{count} 個項目",
    "action_file_times": "檔案時間…",
    "action_file_times_tip": "依本次掃描記錄的存取與建立時間篩選",
    "action_capture_file_times": "記錄檔案存取／建立時間",
    "action_capture_file_times_tip": "預設關閉；之後掃描每個一般檔案增加 16 bytes；開啟後請重新掃描",
    "column_accessed": "記錄的存取時間",
    "column_created": "建立時間",
    "file_times_hint": (
        "請開啟「選項 → 記錄檔案存取／建立時間」後重新掃描。只記錄一般檔案；資料夾、連結"
        "及無法取得的建立時間保持未知。存取時間可能停用、延遲更新，或受背景工具影響，無法"
        "證明實際使用時間。POSIX ctime 不是建立時間。此檢視不會準備清理操作。"
    ),
    "file_times_accessed": "多久未開啟…（依記錄的存取日期）",
    "file_times_created": "建立至少多久…",
    "file_times_mode": "記錄時間的篩選模式",
    "file_times_days": "天數",
    "file_times_reading": "正在篩選已記錄的檔案時間…",
    "file_times_summary": (
        "符合 {count} 個檔案，共 {size}；顯示 {shown} 個。{total} 個檔案中有 {unknown} 個"
        "時間未知或在未來。"
    ),
    "file_times_policy_disabled": (
        "NTFS 回報已停用存取時間更新，無法依存取時間篩選；仍可依建立時間篩選。登錄設定可"
        "能需重新啟動，且不代表所有檔案系統。"
    ),
    "file_times_policy_unknown": "無法確認 NTFS 存取時間更新設定，無法依存取時間篩選；仍可依建立時間篩選。",
    "file_times_policy_enabled": (
        "NTFS 登錄設定回報已啟用存取時間更新；待重新啟動、檔案系統／提供者設定及延遲更新"
        "仍可能影響日期。"
    ),
    "file_times_policy_platform": "檔案系統／提供者設定可能延遲或停用存取時間更新，請將日期視為已記錄的中繼資料。",
    "action_programs": "已安裝程式…",
    "action_programs_tip": "核對安裝程式／遊戲中繼資料與此掃描中的安裝資料夾",
    "program_name": "程式／遊戲",
    "program_source": "中繼資料來源",
    "program_version": "版本／組建",
    "program_publisher": "發行者",
    "program_reported": "回報的估計大小",
    "program_scanned": "掃描的邏輯大小",
    "program_allocated": "掃描依名稱計算的配置量",
    "program_coverage": "記錄的資料夾涵蓋範圍",
    "program_location": "安裝資料夾",
    "program_registry": "Windows 登錄資料庫",
    "program_steam": "Steam 清單",
    "program_epic": "Epic 清單",
    "program_outside": "沒有完全相符的掃描資料夾",
    "program_hint": "Windows 解除安裝登錄項目與辨識到的 Steam／Epic 清單，僅核對此掃描中完全相符的資料夾，"
                    "也會讀取 Epic 在 ProgramData 的固定清單目錄。回報大小是估計，缺少資料保持未知。共用或巢狀"
                    "資料夾可能重疊，請勿加總列或視為可回收空間。可攜式／封裝應用程式可能未列出。按兩下選取"
                    "記錄的資料夾，Ctrl+C 複製列。請透過 Windows 或遊戲啟動器解除安裝。",
    "program_reading": "正在讀取安裝中繼資料…",
    "program_summary": "顯示 {shown}／{count} 個安裝項目；{issues} 個無法讀取、格式錯誤或略過的中繼資料項目",
    "program_failed": "無法讀取安裝項目：{reason}",
    "program_uninstall_page": "開啟 Windows 已安裝應用程式設定",
    "program_open_failed": "Windows 無法開啟已安裝應用程式設定頁面",
    "action_history": "掃描歷史…",
    "action_history_tip": "查看此根目錄大小隨時間的變化，並與先前掃描比較",
    "action_history_settings": "掃描歷史設定…",
    "action_history_settings_tip": "啟用本機掃描中繼資料並設定整體保留上限",
    "history_enable": "在本機保留已完成的整棵掃描",
    "history_settings_hint": "歷史保留資料夾名稱、路徑、容量與涵蓋範圍，不含檔案內容。預設啟用，所有根目錄合計 "
                             "1 GiB。只依時間移除辨識為歷史的中繼資料。關閉後仍可查看既有歷史。變更適用於未來的"
                             "整棵掃描；降低上限會在下次儲存時套用。",
    "history_limit": "歷史總容量上限",
    "history_time": "掃描時間",
    "history_logical": "邏輯大小",
    "history_allocated": "依名稱計算的配置量",
    "history_coverage": "涵蓋範圍",
    "history_incomplete": "不完整；僅含已知資料",
    "history_complete": "記錄範圍完整",
    "history_chart": "資料夾邏輯大小隨時間的變化",
    "history_chart_range": "{first}：{before}；{last}：{after}",
    "history_empty": "此根目錄沒有保留的掃描",
    "history_compare": "將所選掃描與目前結果比較",
    "history_reading": "正在讀取本機掃描歷史…",
    "history_hint": "顯示此根目錄最近 1,000 筆保留的整棵掃描，不儲存停止的掃描及局部重掃。不完整掃描僅描述"
                    "已知資料，缺少資料夾不代表已刪除。總量分別計入硬連結名稱；差異是中繼資料，不是內容驗證。",
    "history_summary": "顯示 {shown}／{count} 筆掃描；{invalid} 個無效或無法讀取的中繼資料檔",
    "history_failed": "無法讀取歷史：{reason}",
    "history_save_failed": "掃描已完成，但無法儲存歷史：{reason}",
    "action_scan_workers": "掃描執行緒數…",
    "action_scan_workers_tip": "選擇新掃描的並行數，較高不一定較快",
    "workers_prompt": "新掃描執行緒數（1–32），預設為 {default}。慢速網路共用可能受益於較多執行緒；"
                      "過高並行數可能使磁碟／伺服器負荷過重。進行中的掃描保留既有執行緒數，"
                      "UNC 效能取決於實際共用環境。",
    "action_bins": "資源回收筒…",
    "action_bins_tip": "審查回收筒總量與明確範圍的系統清空動作",
    "bin_finder_empty": "清空所有已掛載磁碟的 Finder 回收筒…",
    "bin_finder_all": "所有已掛載磁碟（Finder 全域回收筒）",
    "bin_finder_scopes": "目前使用者的回收筒範圍：\n{scopes}\n\n已掛載磁碟：\n{roots}",
    "bin_finder_first": "清空目前使用者在所有已掛載磁碟上的 Finder 回收筒？\n\n{root}\n\n"
                        "內容邏輯大小：{size}\n項目數：{count}",
    "bin_finder_irreversible": "永久清空目前使用者在所有已掛載磁碟上的 Finder 回收筒？\n\n{root}\n\n"
                               "內容邏輯大小：{size}\n項目數：{count}\n\n此動作無法復原。"
                               "Finder 也可能移除作業期間新增的項目。"
                               "此動作影響所有已掛載磁碟的回收筒，與選取哪一列無關，開始後不能取消。"
                               "自動化或權限錯誤可能導致僅完成一部分，Finder 也可能仍在執行。",
    "bin_preparing": "正在盤點 {root} 的確切回收筒範圍…",
    "bin_no_approval": "沒有完整且非空的回收筒盤點，請更新後重新檢視。",
    "bin_scope_first": "清空目前使用者的這些回收筒內容／收據範圍？\n\n{root}\n\n內容邏輯大小：{size}\n項目數：{count}",
    "bin_scope_irreversible": "永久移除這些確切範圍內已檢視的內容？\n\n{root}\n\n"
                              "內容邏輯大小：{size}\n項目數：{count}\n\n"
                              "此動作無法復原。內容中的連結只移除連結本身，不跟隨其目標。已變動項目會拒絕處理；"
                              "失敗時可能只完成一部分。開始清空後無法取消。",
    "bin_partial": "已移除 {count} 個已檢視項目；其餘失敗原因：{reason}",
    "bin_empty": "清空選取磁碟的資源回收筒…",
    "bin_first": "清空 {root} 的資源回收筒？\n\n回報大小：{size}\n項目數：{count}",
    "bin_irreversible": "永久移除 {root} 資源回收筒目前的全部項目？\n\n回報大小：{size}\n項目數：{count}\n\n"
                        "此動作無法復原。系統作業期間新增的項目也可能被移除；原生作業開始後不能取消。",
    "bin_running": "正在清空 {root} 的資源回收筒，等待系統作業完成…",
    "bin_failed": "未完成清空：{reason}",
    "bin_hint": "選取一個已掛載磁碟。Windows 清空目前使用者的系統回收筒；Linux 盤點已識別的 files／info 範圍。"
                "永久移除前以兩次詢問列出確切範圍與總量。停止可取消盤點；開始清空後必須等待完成。"
                "macOS 經全域檢視後清空所有已掛載磁碟的 Finder 回收筒，原生驗證待完成。"
                "完成後更新容量／回收筒數值；重新掃描可更新主樹狀圖。",
    "action_volumes": "磁碟總覽…",
    "action_volumes_tip": "查看已掛載磁碟、容量、配置單位與資源回收筒總量",
    "volume_root": "掛載根目錄",
    "volume_name": "磁碟名稱",
    "volume_fs": "檔案系統",
    "volume_total": "總量",
    "volume_used": "已用",
    "volume_free": "可用空間",
    "volume_cluster": "配置單位",
    "volume_trash": "資源回收筒大小",
    "volume_trash_count": "回收筒項目",
    "volume_reading": "正在讀取已掛載磁碟與資源回收筒總量…",
    "volume_summary": "共 {count} 個已掛載磁碟，顯示 {shown} 個。按兩下開始掃描。",
    "volume_trash_partial": "總量未知（已知 {known}）",
    "volume_hint": "作業系統容量快照；可用空間可能扣除保留量或配額。重複掛載可能共用容量，不要加總各列。"
                   "Windows 配置單位是叢集；POSIX 單位是檔案系統片段，不是最佳傳輸大小。"
                   "回收筒列出 Windows 回報總量或 POSIX 已知邏輯內容大小，非可回收空間，"
                   "不含資料夾／收據中繼資料與共用配置。"
                   "錯誤維持未知。停止會等待目前系統呼叫，取消時捨棄檢查結果。Ctrl+C 複製列；此處不提供清空動作。",
    "action_export_report_html": "掃描報告（HTML）…",
    "action_export_report_html_tip": "儲存內嵌三張圖表圖片的獨立報告",
    "action_export_report_xlsx": "掃描報告（Excel）…",
    "action_export_report_xlsx_tip": "將報告清單儲存在各自的 Excel 工作表",
    "html_filter": "HTML 報告 (*.html)",
    "xlsx_filter": "Excel 活頁簿 (*.xlsx)",
    "report_title": "FileTree 掃描報告",
    "report_note": "僅含已知記錄範圍；磁碟配置是估計值。標題數量為顯示／全部。最大資料夾範圍重疊，不要加總各列。"
                   "最大檔案與資料夾各限 1,000 筆，檔案類型限 10,000 筆。大小單位為位元組。檔齡依修改記錄，非最後存取；"
                   "無可用日期歸入既有的最舊檔齡群組。HTML 圖表顯示整份掃描根目錄，圖形範圍有限。"
                   "Excel 文字經逸出，控制字元顯示為十六進位，每格限 32,767 字元，16 位以上整數以精確文字儲存。",
    "report_bytes": "邏輯位元組",
    "report_allocated": "配置位元組（估計）",
    "report_created": "報告建立時間",
    "report_reference": "檔齡參照時間",
    "report_skipped": "略過資料夾",
    "report_denied": "無法讀取資料夾",
    "report_pending": "待讀取資料夾",
    "report_summary": "摘要",
    "report_notes": "說明",
    "report_field": "欄位",
    "report_value": "值",
    "report_top_folders": "最大資料夾（範圍重疊）",
    "report_categories": "分類",
    "action_projects": "專案與可重建資料…",
    "action_projects_tip": "查看已掃描的專案、Git 與產生資料大小",
    "project_path": "專案／管理儲存區",
    "project_kind": "辨識類型",
    "project_other": "來源／其他",
    "project_git": ".git",
    "project_generated": "可重建資料",
    "project_coverage": "掃描範圍",
    "project_partial": "不完整",
    "project_recorded": "已記錄範圍",
    "project_hint": "僅列已知邏輯大小；巢狀專案範圍重疊。Git 指標檔案不含外部中繼資料。產生資料可能含自訂檔案，"
                    "移動前請審查。Maven、全域 Gradle 與 Docker 儲存區分開顯示，不假定其內容可丟棄。",
    "project_reading": "正在查閱已掃描的專案資料…",
    "project_summary": "共辨識 {count} 個專案／儲存區，顯示最大的 {shown} 個。",
    "project_review": "審查符合條件的可重建項目…",
    "project_review_count": "依目前年齡、掃描範圍與清理設定，{count} 個符合條件的項目最多審查 {shown} 個。"
                            "已停止的掃描不提供清理提案。",
    "project_git_kind": "Git",
    "project_python": "Python",
    "project_node": "Node.js",
    "project_rust": "Rust",
    "project_jvm": "JVM",
    "project_conda": "Conda 專案",
    "project_python_environment": "Python 環境",
    "project_conda_environment": "Conda 環境",
    "project_maven_store": "Maven 儲存區",
    "project_gradle_store": "全域 Gradle 儲存區",
    "project_docker_store": "Docker 資料",
    "action_git_history": "Git 歷史…",
    "action_git_history_tip": "查看所有 Git 參照可達的最大物件",
    "git_oid": "物件識別碼",
    "git_kind": "物件類型",
    "git_length": "解壓後長度",
    "git_type_blob": "檔案內容（blob）",
    "git_type_tree": "資料夾清單（tree）",
    "git_type_commit": "提交",
    "git_type_tag": "註解標籤",
    "git_hint": ("唯讀 Git 底層命令查閱所有參照，保留最大的 1,000 個物件。大小是解壓後長度，並非磁碟配置或可回收空間。"
                 "Git 的物件名稱提示可能有歧義，因此不列名稱。Ctrl+C 複製識別碼／列。"
                 "停用選用鎖定、自動維護與延遲網路下載；"
                 "Git 必須支援 --no-lazy-fetch。不繞過存放庫擁有者檢查。可停止；不執行 gc。"),
    "git_reading": "正在查閱 Git 歷史…",
    "git_summary": "顯示 {count} 個可達物件中的 {shown} 個；解壓後總量 {size}。",
    "git_gc_loose": ("Git gc 可能整併 {count} 個鬆散物件，但這些最大物件仍可由參照到達，不會被移除。"
                     "實際節省量及其他不可達／參照日誌資料仍未知。"),
    "git_gc_packed": ("沒有可整併的鬆散物件。參照保留這些物件時，Git gc 不會移除它們；"
                      "其他不可達／參照日誌資料與實際節省量尚未量測。"),
    "git_failed": "Git 查閱失敗：{reason}",
    "tree_filter_placeholder": "篩選已展開的資料夾…",
    "tree_filter_hint": ("僅在已展開的資料夾比對名稱（不分大小寫），保留上層路徑。不搜尋摺疊的內容。"
                         "清除篩選即可恢復樹狀清單。從圖表／清單選取被隱藏的項目會清除篩選。掃描總量與匯出保持不變。"),
    "action_live_compare": "比較兩個資料夾…",
    "action_live_compare_tip": "比較即時相對路徑，僅驗證選取的檔案對",
    "compare_choose_left": "選擇左側資料夾",
    "compare_choose_right": "選擇右側資料夾",
    "compare_relative": "相對路徑",
    "compare_state": "比較結果",
    "compare_left_size": "左側大小",
    "compare_right_size": "右側大小",
    "compare_left_time": "左側修改時間",
    "compare_right_time": "右側修改時間",
    "compare_roots": "左側：{left}\n右側：{right}",
    "compare_hint": ("唯讀：依 Unicode 與大小寫完全相符的名稱配對，不跟隨連結。大小／時間相同不代表內容相同。"
                     "選取檔案對後可完整雜湊驗證，並可停止；變更、無法讀取與已知雲端檔案保持無法驗證。"
                     "結果對應此次掃描／驗證時間。不執行複製、移動或同步。Ctrl+C 複製列；"
                     "CSV 僅匯出顯示的列，最多 10,000 列。"),
    "compare_reading": "正在掃描兩個資料夾…",
    "compare_error": "比較或匯出失敗：{reason}",
    "compare_hashing": "正在驗證選取的檔案對…",
    "compare_verify": "驗證選取的內容",
    "compare_summary": "顯示 {count} 個相對路徑中的 {shown} 個（上限 10,000）。",
    "compare_incomplete": "掃描範圍不完整；無法讀取範圍中的缺少路徑仍為未知。",
    "compare_unavailable": "無法驗證或已變更",
    "compare_link": "連結；未讀取內容",
    "compare_only_left": "僅左側有",
    "compare_only_right": "僅右側有",
    "compare_different_kind": "項目類型不同",
    "compare_folder": "兩側皆為資料夾",
    "compare_different_size": "大小不同",
    "compare_different_time": "時間不同；尚未驗證內容",
    "compare_unchecked": "尚未驗證內容",
    "compare_identical": "完整雜湊相符",
    "compare_different_bytes": "內容不同",
    "problem_mount_boundary": "掛載邊界：未掃描內容",
    "action_special_files": "雲端與特殊檔案…",
    "action_special_files_tip": "查看已記錄的召回、離線、壓縮及稀疏檔案狀態",
    "special_states": "已記錄狀態",
    "special_content_size": "完整內容大小",
    "special_recall": "存取時可能召回",
    "special_offline": "離線",
    "special_compressed": "已壓縮",
    "special_sparse": "稀疏",
    "special_allocation_low": "配置較少，原因未知",
    "special_reading": "正在讀取已記錄的檔案中繼資料…",
    "special_hint": ("本清單只使用掃描中繼資料，不開啟或下載檔案。召回／離線屬性可能來自 OneDrive、Dropbox "
                     "或其他服務，無法據此判斷提供者及已在本機的比例。完整內容大小是含線上內容的邏輯長度；"
                     "下載後的磁碟配置未知。稀疏區段、壓縮及常駐資料都可能減少配置。召回／離線項目的磁碟大小 "
                     "0 是掃描估計，不是實測雲端配置。按兩下可選取掃描項目；Ctrl+C 複製所選列。"),
    "special_summary": ("顯示 {count} 個符合檔案中的 {shown} 個。完整內容 {size}；已記錄配置 {allocated}。"
                        "無法取得檔案中繼資料：{unknown}。保留最大的 1,000 個。"),
    "special_partial": "掃描範圍不完整；未讀取的檔案仍未知。",
    "action_shell_integration": "檔案總管整合…",
    "action_shell_integration_tip": "在檔案總管的資料夾選單新增或移除「使用 FileTree 掃描」",
    "shell_enabled": "在檔案總管的資料夾選單加入「使用 FileTree 掃描」",
    "shell_scan": "使用 FileTree 掃描",
    "shell_hint": ("儲存只會變更您帳號的資料夾選單，不需要系統管理員權限。"
                   "Windows 11 請查看「顯示其他選項」。在此取消勾選即可移除。"
                   "移動執行檔或原始碼資料夾後，請重新登錄。"),
    "shell_failed": "無法變更檔案總管整合。\n{reason}",
    "menu_properties": "內容",
    "properties_failed": "Windows 無法開啟此項目的內容：\n{path}",
    "menu_theme": "主題",
    "theme_system": "系統",
    "theme_light": "淺色",
    "theme_dark": "深色",

    "chart_access_keys": ("方向鍵選取已繪製項目；Enter 開啟資料夾，Backspace 返回上層。"
                          "合併或未顯示的項目可使用資料夾樹查看。"),
    "chart_access_tree_keys": "上／下選取卡片，右／左展開或收合資料夾。Enter 開啟資料夾，Backspace 返回上層。",
    "chart_access_folder": "目前資料夾：{path}",
    "chart_access_selected": "已選取：{path}。大小 {size}；磁碟大小 {allocated}；{files} 個檔案，{folders} 個資料夾。",

    "system_file_hibernate": ("休眠與快速啟動狀態，由 Windows 管理。系統管理員可使用 powercfg /hibernate o"
                              "ff 關閉休眠，這也會移除休眠功能，並可能影響快速啟動。FileTree 僅開啟電源設"
                              "定。"),
    "system_file_pagefile": ("虛擬記憶體的分頁檔，Windows 可自動管理大小。在進階系統設定的效能設定中查看"
                             "虛擬記憶體；縮小可能影響應用程式與損毀傾印。"),
    "system_file_swapfile": ("Windows 的交換檔，包含暫停的應用程式資料，由系統與虛擬記憶體一併管理。請查"
                             "看系統記憶體設定，不要直接移除。"),
    "system_file_old": ("先前的 Windows 安裝。在磁碟清理的「清理系統檔」中審查先前的 Windows 安裝；"
                        "移除後將無法返回該安裝。"),
    "system_file_recycle": "已刪除項目在清空資源回收筒前仍占用空間。請查看資源回收筒或儲存空間感知；清空是永久刪除。",
    "system_file_restore": ("系統中繼資料、還原點與陰影複製。在系統保護的「設定」中調整還原點容量上限。"
                            "備份工具管理的陰影複製可能需要各自的備份工具；未讀取的大小仍未知。"),
    "system_file_winsxs": ("Windows 元件存放區。許多項目與 Windows 檔案共用硬式連結，因此逐名稱加總可能"
                           "高估實際儲存空間。請使用磁碟清理的「清理系統檔」與 Windows Update 清理，不"
                           "要手動移除元件。"),
    "system_file_updates": ("Windows Update 下載資料。在磁碟清理的「清理系統檔」中審查更新及暫存檔案，進"
                            "行中的下載交由更新服務管理。"),
    "system_file_delivery": ("Windows 更新與應用程式的傳遞最佳化下載快取。請在磁碟清理中審查傳遞最佳化檔"
                             "案，進行中的傳輸由 Windows 管理。"),
    "system_tool_power": "開啟電源設定…",
    "system_tool_memory": "開啟進階系統設定…",
    "system_tool_cleanup": "開啟磁碟清理…",
    "system_tool_storage": "開啟儲存空間感知…",
    "system_tool_restore": "開啟系統保護…",
    "system_tool_failed": "無法開啟 Windows 工具。",
    "trash_skip_system_managed": "此項目由 Windows 管理，請使用詳細資訊中的系統工具",

    "type_locations_title": "所在資料夾（最多 1,000 個）",
    "type_location_size": "符合類型的大小",
    "type_locations_tip": "統計各資料夾直接包含的符合類型檔案；子資料夾分開列出，不重複計算。",

    "action_export_list": "目前清單（CSV）…",
    "action_export_list_tip": "依目前的篩選與排序儲存作用中清單的所有列",
    "list_changed": "擷取期間清單已變更，請重新匯出或複製。",

    "details_title": "詳細資訊",
    "details_empty": "選取項目以顯示詳細資訊",
    "details_live": "掃描完成後可查看分布。",
    "details_loading": "正在計算類型與檔齡分布…",
    "details_recorded": "僅統計已讀取的檔案，未讀取項目不在分布內。資料夾修改時間為最新的已記錄日期。",
    "details_bucket": "{label}：{size} · {count} 個檔案",

    "breadcrumbs_back": "返回（Alt+Left）",
    "breadcrumbs_forward": "前進（Alt+Right）",
    "breadcrumbs_more": "…",
    "breadcrumbs_more_tip": "顯示上層資料夾",

    "action_print_view": "列印目前畫面…",
    "action_print_view_tip": "透過系統列印對話框將可見結果印在一頁上",
    "action_export_view_pdf": "目前畫面（PDF）…",
    "action_export_view_pdf_tip": "將可見結果調整為一頁 PDF 儲存",
    "pdf_filter": "PDF 文件 (*.pdf)",
    "view_pdf_exported": "已儲存目前畫面：{path}",
    "print_failed": "無法列印畫面：{reason}",
    "print_submitted": "已將畫面送到印表機",
    "action_export_chart_png": "畫面上的圖表（PNG）…",
    "action_export_chart_png_tip": "儲存目前可見的圖表範圍",
    "action_export_chart_svg": "長條圖或放射圖（SVG）…",
    "action_export_chart_svg_tip": "將有數量上限的完整長條或圓弧儲存為向量圖形與文字",
    "png_filter": "PNG 圖片 (*.png)",
    "svg_filter": "SVG 圖片 (*.svg)",
    "graphic_exported": "已儲存圖表：{path}",
    "treemap_colours_age": "依修改檔齡",
    "age_colour_unknown": "日期未知",
    "age_colour_tip": "距離修改的時間。資料夾依最新的修改記錄著色，無可用日期時為灰色；合併的小項目保持灰色。",
    "action_gentle": "低優先順序掃描",
    "action_gentle_tip": "降低新掃描的 CPU 與 I/O 優先順序，可能花較久時間",
    "scan_priority_warning": "部分掃描優先順序設定無法套用：{reason}",
    "scan_pause": "暫停",
    "scan_resume": "繼續",
    "scan_pause_tip": "暫停取得新資料夾；目前讀取會完成。暫停時仍可停止。",
    "scan_paused": "已暫停 — {progress}",
    "scan_analysing": "資料夾讀取完成，正在分析結果…",
    "column_drive_share": "占磁碟比例",
    "columns_reset": "重設欄位",
    "drive_share_tip": ("邏輯位元組除以磁碟總容量。硬連結名稱分別計算；不是配置或可回收空間。"
                        "容量未知或已過期時不顯示比例。"),
    "action_recent_actions": "最近操作…",
    "action_recent_actions_tip": "查看保留的操作中繼資料，並匯出隱去個人路徑的稽核報告",
    "journal_time": "時間（UTC）",
    "journal_source": "原始路徑",
    "journal_identity": "磁碟／檔案身分",
    "journal_result": "結果",
    "journal_detail": "明細",
    "journal_destination": "資源回收筒位置",
    "journal_reason_duplicates": "明確的重複檔案決策",
    "journal_status_approved": "結果未知（只有確認紀錄）",
    "journal_status_moved": "已移到資源回收筒",
    "journal_status_skipped": "已略過",
    "journal_status_failed": "系統移動失敗",
    "journal_reading": "正在讀取保留的操作…",
    "journal_hint": ("最近 500 個操作；僅中繼資料，保留 90 天／50 MB。"
                     "只有確認紀錄的操作，其最終結果未知。記錄資源回收筒位置不保證可還原。"),
    "journal_summary": "顯示 {count} 個操作；{invalid} 筆損壞紀錄，{unavailable} 個無法讀取的日誌區段。",
    "journal_read_failed": "無法讀取操作日誌：{reason}",
    "journal_write_failed": "日誌寫入或保留管理失敗，已盡可能停止剩餘移動；最近操作可能不完整。\n\n{reason}",
    "trash_skip_journal": "無法記錄已確認的操作，未移動任何項目",
    "journal_export": "匯出隱去個人路徑的 CSV…",
    "journal_exported": "稽核報告已儲存，家目錄前綴已隱去。",
    "duplicate_folder_match": "{copy} = {original}（{size}，{files} 個檔案；搜尋快照相符）",
    "duplicate_folder_tip": "名稱、大小、已驗證雜湊與空資料夾結構相同。僅供比對，不代表可清理。",
    "duplicates_keep_selected": "保留選取的副本",
    "duplicates_kept_name": "保留：{name}",
    "duplicates_kept_path": "保留副本：{path}。",
    "duplicates_choose_keeper": "選取多餘副本前，請先選擇這組要保留的副本。",
    "duplicates_group_blocked": "此組保持原樣，須重新掃描：{reason}",
    "trash_skip_duplicate_choose": "請選擇保留副本，再次審查此組",
    "trash_skip_duplicate_keep": "選到了保留副本，此組保持原樣；請重新掃描",
    "trash_skip_duplicate_unverified": "此組沒有已驗證的雜湊；請重新掃描並搜尋",
    "trash_skip_duplicate_hard_links": "副本還有硬連結名稱，此組保持原樣；請重新掃描",
    "trash_skip_duplicate_content": "此組內容變更或無法重新雜湊；請重新掃描並搜尋",
    "menu_options": "選項",
    "action_cleanup_policy": "清理政策…",
    "action_cleanup_policy_tip": "啟用規則、變更最低檔齡，或排除清理建議的路徑",
    "policy_enabled": "啟用",
    "policy_age": "最低檔齡（天）",
    "policy_age_for": "{rule} 的最低檔齡",
    "policy_enabled_for": "啟用 {rule}",
    "policy_hint": "政策只影響建議。須手動審查的規則仍預設不勾選。儲存前請先預覽。",
    "policy_exclusions": "不提出建議的路徑或名稱（每行一個；路徑須為絕對路徑）。不影響掃描。",
    "policy_preview": "預覽變更",
    "policy_import": "匯入政策 JSON…",
    "policy_preview_needed": "儲存前請先預覽目前設定。",
    "policy_preview_running": "正在比較候選數量與邏輯大小…",
    "policy_preview_result": "增加 {added} 個候選（{size}）；移除 {removed} 個候選（{removed_size}）。未移動任何項目。",
    "policy_preview_partial": "掃描不完整；未讀取的候選與容量仍未知。",
    "policy_no_scan": "尚無完成的掃描，無法量測影響。設定將套用到往後的建議。",
    "policy_invalid": "政策無效。請使用支援的規則、是／否開關、0–36500 天，以及絕對路徑或名稱樣式。",
    "policy_saved": "清理政策已儲存，正在更新建議。",
    "policy_saved_invalid": "已儲存的清理政策無效。請至「選項」審查政策；目前已停用清理建議。",
    "cleanup_review_manual": "手動審查",
    "cleanup_evidence": "分類：{category}；最低檔齡：{days} 天；風險：{risk}。依據：{evidence} 重建／後果：{rebuild}",
    "cleanup_category_temporary": "暫存檔案",
    "cleanup_category_cache": "下載／產生的快取",
    "cleanup_category_application_state": "應用程式狀態",
    "cleanup_category_build": "專案建置輸出",
    "cleanup_category_downloads": "使用者下載",
    "cleanup_risk_low": "較低風險；移動前仍須確認",
    "cleanup_risk_manual": "手動審查；預設不勾選",
    "cleanup_rebuild_temp": "先關閉使用它的應用程式；暫存資料不一定能重建。",
    "cleanup_rebuild_browser_cache": "先關閉瀏覽器；快取網頁會重新下載。個人設定與書籤不列入。",
    "cleanup_rebuild_thumbnails": "先關閉檔案總管；需要時會重新產生預覽。",
    "cleanup_rebuild_crash_dumps": "保留需要的當機證據；過去的當機傾印無法重建。",
    "cleanup_rebuild_package_caches": "以套件管理工具重新下載，先確認網路可用。套件儲存庫不列入。",
    "cleanup_rebuild_build_output": "核對專案內容與相依套件鎖定檔，再依專案文件重建。自行撰寫的檔案應保留。",
    "cleanup_rebuild_old_installers": "保留離線或已無法取得的安裝檔；仍可取得時向發行者重新下載。",
    "cleanup_rebuild_empty_folders": "應用程式可能仍需要空資料夾；先確認用途。",
    "trash_holder": "{name}（PID {pid}）",
    "trash_holders": "{path}：觀察到 {programs} 開啟此檔案。請自行關閉相關程式後重試。",
    "trash_holders_limited": "{path}：無法完整查詢行程；其他占用程式或失敗原因可能未知。",
    "duplicates_savings": ("不重複配置估計 {allocated}；清空資源回收筒後可回收的檔案資料 "
                           "{recoverable}。"),
    "duplicates_estimating": ('正在估計不重複配置空間與可回收的檔案資料…'),
    "duplicates_estimate_unavailable": ('配置估計無法取得。選取多餘副本前請重新搜尋。'),
    "duplicates_estimate_assumption": ("估計依您選擇的保留副本，未決定的群組保持未知。"
        "移動前會核對並完整重新雜湊整組檔案。有硬連結名稱時不執行決策。"
        "共用區塊與資料夾中繼資料仍未知，移到資源回收筒不會釋放空間。"),
    'capacity_details': '容量明細',
    'capacity_summary': '系統已用 {used}；可用 {free}；不重複配置估計 {unique}。{status}',
    'capacity_estimated': '整個磁碟的估計；未能歸帳的空間請見明細。',
    'capacity_folder_only': '僅掃描資料夾：無法核對整個磁碟。',
    'capacity_incomplete': '掃描不完整：無法核對整個磁碟。',
    'capacity_identity_unknown': '缺少檔案識別資訊：無法核對整個磁碟。',
    'capacity_capacity_unavailable': '無法取得系統容量：無法核對整個磁碟。',
    'capacity_root_changed': '掃描根目錄已變更，請重新掃描後核對。',
    'capacity_allocation_exceeds_used': '配置估計超過系統已用空間，無法核對。',
    'capacity_coverage': '略過 {skipped}；無法讀取 {inaccessible}；尚未讀取 {pending}',
    'capacity_bin_partial': '未完整識別或讀取資源回收筒，顯示的大小僅限已讀取的資料。',
    "capacity_explanation": ('已知檔案配置包含讀取到的資源回收筒資料，硬連結的多個名稱只算一次。其他掛載磁碟不列入'
                             '。略過的資料與檔案系統中繼資料是未知，而非 0。未能歸帳的空間可能包含無法讀取的資料'
                             '、中繼資料、快照、共用區塊及配置估計誤差。系統容量與檔案不是同時量測，掃描期間檔案系'
                             '統可能變動。不可用的剩餘空間是系統回報的總量、已用及可用量之差，不是量測得到的中繼資'
                             '料總量。這些數字是估計，仍待 NTFS、ext4 與 APFS 測試磁碟驗證。'),
    'capacity_row_total': '系統總容量',
    'capacity_row_used': '系統已用空間',
    'capacity_row_free': '系統可用空間',
    'capacity_row_unavailable_free': '不可用的剩餘空間',
    'capacity_row_named_allocated': '依名稱計算的配置估計',
    'capacity_row_unique_allocated': '不重複配置估計',
    'capacity_row_hard_link_overcount': '已扣除的硬連結重複量',
    'capacity_row_recycle_bin_seen': '已讀取的資源回收筒配置（已包含）',
    'capacity_row_foreign_allocated_seen': '已讀取的其他磁碟配置（不列入）',
    'capacity_row_unaccounted': '未能歸帳',
    'capacity_row_metadata_bytes': '檔案系統中繼資料／保留空間',
    'capacity_row_omitted_bytes': '略過的資料',
    'capacity_row_other_volumes_bytes': '其他掛載磁碟',
    'capacity_row_mounts': '跨磁碟掛載邊界',
    'capacity_row_coverage': '掃描涵蓋範圍',
    "review_title": "審查清理建議",
    "review_details": "{path}\n規則：{rule}；保護狀態：{protection}。{consequence}",
    "review_hint": "請檢查每條路徑與移除後果，取消勾選即可保留項目；繼續後才會顯示確認問題。",
    "review_select": "移動",
    "review_rule": "規則",
    "review_reason": "原因",
    "review_protection": "保護狀態",
    "review_consequence": "移除後果",
    "review_manual": "手動選取",
    "review_manual_reason": "使用者選取的項目，移除可能影響相依的檔案或程式。",
    "review_not_protected": "未符合受保護路徑",
    "review_open_folder": "開啟所在資料夾",
    "review_continue": "繼續到確認步驟",
    "review_estimating": "已選取 {count} 項，正在估計配置空間…",
    "review_summary": ("{count} 項；邏輯大小 {logical}；配置空間估計 {allocated}；清空資源回收筒後可回收的檔案資料 "
                       "{recoverable}；目前可用 {free}。共用區塊與資料夾中繼資料仍未知，"
                       "移到資源回收筒不會立刻釋出空間。"),
    "size_unknown": "未知",
    "trash_running": "正在重新核對並移動已核准的項目…按停止可取消剩餘項目。",
    "trash_batch_done": "已移動 {moved}、略過 {skipped}、失敗 {failed}；共 {size} 移到資源回收筒。",
    "trash_skipped": "已略過下列項目，請重新掃描資料夾後再試：\n{names}",
    "trash_skip_outside": "不在目前的掃描範圍",
    "trash_skip_unverified": "沒有經核對的掃描身分",
    "trash_skip_incomplete": "掃描涵蓋範圍不完整",
    "trash_skip_missing": "項目或上層資料夾已不存在",
    "trash_skip_unreadable": "無法讀取項目",
    "trash_skip_link": "項目或上層資料夾變成連結",
    "trash_skip_kind": "項目種類已變更",
    "trash_skip_identity": "項目已被替換",
    "trash_skip_changed": "大小、時間或資料夾內容已變更",
    "trash_skip_protected": "解析後路徑的保護狀態不同",
    "trash_skip_cancelled": "操作已取消",
    "coverage_complete": ("涵蓋範圍：{known} 個資料夾，已知 {size}；"
                          "略過 {skipped}、無法讀取 {denied}、未掃描 {pending}。"),
    "coverage_partial": ("涵蓋範圍不完整：{known} 個資料夾，已知 {size}；略過 {skipped}、無法讀取 {denied}、"
                         "未掃描 {pending}。略過的位元組數未知。清理前請重新掃描不完整的分支；已停用全部選取。"),
    "problem_hidden_omitted": "已略過隱藏項目，大小未知。",
    "problem_partial_folder": "部分項目無法讀取，資料夾內容不完整。",
    "app_title": "FileTree",
    "about_text": "<h3>FileTree {version}</h3><p>看看磁碟空間都用到哪裡去了。</p>"
                  "<p>MIT 授權 · © 2026 JE-Chen</p>",
    "menu_file": "檔案(&F)",
    "menu_export": "匯出(&E)",
    "menu_view": "檢視(&V)",
    "menu_unit": "大小單位(&U)",
    "menu_language": "語言(&L)",
    "menu_help": "說明(&H)",
    "action_open": "選擇資料夾…",
    "action_open_tip": "選一個資料夾或磁碟來掃描",
    "action_rescan": "重新掃描",
    "action_rescan_tip": "再掃描一次同一個資料夾，取得最新的變動",
    "action_stop": "停止",
    "action_stop_tip": "停止正在進行的掃描",
    "action_export_folders": "資料夾清單（CSV）…",
    "action_export_folders_tip": "把每個資料夾和它的大小存成試算表，可用 Excel 開啟",
    "action_export_largest": "最大的檔案（CSV）…",
    "action_export_largest_tip": "把最大的檔案清單存起來",
    "action_export_json": "資料夾樹（JSON）…",
    "action_export_json_tip": "把資料夾樹存起來，給程式或其他軟體使用",
    "action_trash": "移到資源回收筒",
    "action_trash_tip": "把選取的檔案和資料夾移到資源回收筒（會先詢問）",
    "action_find": "搜尋…",
    "action_find_tip": "在整個掃描結果裡依名稱找檔案和資料夾",
    "action_quit": "結束",
    "action_quit_tip": "關閉 FileTree",
    "action_hidden": "包含隱藏檔案",
    "action_exclusions": "掃描時略過…",
    "action_exclusions_tip": "掃描時要略過的資料夾與資料夾名稱，例如 node_modules",
    "exclusions_title": "掃描時略過",
    "exclusions_hint": ("掃描會略過這些資料夾：它們仍會列出來，以灰字顯示、大小為 0。"
                        "像 node_modules 或 *.cache 這樣的名稱會略過所有同名的資料夾；"
                        "資料夾路徑只略過那一個資料夾。下一次掃描開始生效。"),
    "exclusions_add_name": "新增名稱…",
    "exclusions_add_folder": "新增資料夾…",
    "exclusions_remove": "移除",
    "exclusions_name_prompt": "資料夾名稱，可用 * 和 ?：",
    "exclusions_saved": "已儲存 {count} 項排除；下一次掃描開始生效。",
    "tooltip_excluded": "{path}\n已略過：它在「檢視 → 掃描時略過」的清單中",
    "action_hidden_tip": "把隱藏的檔案和資料夾也算進去（下次掃描時生效）",
    "action_help": "使用說明",
    "action_help_tip": "FileTree 的簡短使用說明",
    "action_about": "關於 FileTree",
    "action_about_tip": "版本與授權",
    "app_title_admin": "FileTree（系統管理員）",
    "action_elevate": "以系統管理員身分重新啟動",
    "action_elevate_tip": "用系統管理員權限重新啟動 FileTree，才能讀取每一個資料夾",
    "action_ask_admin": "啟動時要求系統管理員權限",
    "action_ask_admin_tip": "FileTree 啟動時由 Windows 詢問權限，受保護的資料夾也能讀取",
    "problems_hint": "有些資料夾需要系統管理員權限。以系統管理員身分重新啟動 FileTree 就能一起讀取。",
    "elevate_declined": "FileTree 仍以一般權限執行。",
    "unit_auto": "自動",
    "path_placeholder": "輸入或貼上資料夾路徑，按 Enter 開始掃描",
    "choose_folder_title": "選擇要掃描的資料夾",
    "welcome_title": "看看磁碟空間都用到哪裡去了",
    "welcome_subtitle": "選一個資料夾或整顆磁碟，FileTree 會把裡面每個檔案的大小加總，"
                        "先列出最大的資料夾和檔案。",
    "welcome_choose": "選擇資料夾…",
    "welcome_drives": "磁碟",
    "welcome_drive_tip": "掃描 {path}",
    "welcome_drive_free": "可用 {free}，共 {total}",
    "welcome_recent": "最近掃描過",
    "welcome_tip": "小技巧：也可以把資料夾從檔案總管拖曳到這個視窗。Windows 可貼上絕對 UNC 共用路徑"
                   "（\\\\server\\share），使用目前帳戶存取。掃描執行緒數可在選項調整；權限不足／斷線的分支維持不完整，非空資料夾。",
    "scan_starting": "準備中…",
    "scan_progress": "正在掃描… {folders} 個資料夾中的 {files} 個檔案 · {size} · {time}",
    "scan_stop": "停止",
    "scan_stopping": "正在停止…",
    "scan_cancelled": "已停止掃描。",
    "scan_stopped_partial": "已停止掃描：結果只包含停止前讀到的部分。",
    "scan_failed_title": "無法掃描",
    "scan_mount_changed": "掛載邊界已變更或無法確認。請重新掃描，再使用掃描結果。",
    "scan_failed": "FileTree 無法讀取 {path}。\n\n原因：{reason}",
    "not_a_folder": "{path} 不是存在的資料夾。",
    "duration_seconds": "{value} 秒",
    "duration_minutes": "{minutes} 分 {seconds} 秒",
    "summary": ("<b>{path}</b> — {size}（磁碟大小 {allocated}），共 {files} 個檔案、{folders} 個資料夾"
                "（掃描耗時 {time}）"),
    "summary_live": "<b>{path}</b> — 目前 {size}（磁碟大小 {allocated}），{files} 個檔案、{folders} 個資料夾",
    "summary_partial": "<b>{path}</b> — {size}（磁碟大小 {allocated}），{files} 個檔案、{folders} 個資料夾 · "
                       "<b>不完整</b>：掃描在 {time} 後停止",
    "tab_chart": "圖表",
    "chart_treemap": "方塊圖",
    "treemap_levels": "層數",
    "treemap_levels_all": "全部",
    "treemap_colours": "顏色",
    "treemap_colours_type": "依檔案類型",
    "treemap_colours_folder": "依資料夾",
    "chart_treemap_tip": "每個檔案都是一個方塊，大小代表佔用的空間",
    "chart_bars": "長條圖",
    "chart_sunburst": "放射圖",
    "chart_tree": "樹狀圖",
    "chart_tree_tip": "資料夾階層：展開分支、Ctrl＋滾輪縮放、連按兩下聚焦",
    "tree_orientation": "方向",
    "tree_orientation_horizontal": "由左到右",
    "tree_orientation_vertical": "由上到下",
    "tree_more": "其餘 {count} 個資料夾 · {size}",
    "tree_unavailable": "未掃描",
    "chart_sunburst_tip": "目前資料夾在中心，每深一層就是外面一圈；按中心回上一層",
    "chart_bars_tip": "資料夾裡每個項目一條長條，由大到小，附大小與比例",
    "bars_empty_folder": "這個資料夾是空的。",
    "bars_more": "其餘 {count} 個：{size}",
    "tab_largest": "最大的檔案",
    "scope_folder": "只看選取的資料夾",
    "scope_folder_named": "只看 {name}",
    "scope_folder_tip": "改為列出資料夾樹中選取的資料夾（而不是整個掃描範圍）的最大檔案、類型與新舊",
    "tab_search": "搜尋",
    "tab_changes": "變化",
    "action_compare": "與先前儲存的掃描比較…",
    "action_compare_tip": "開啟用「匯出 → 資料夾樹（JSON）」儲存的掃描，看看之後哪裡變大了",
    "compare_title": "與先前儲存的掃描比較",
    "compare_failed": "這個檔案不是 FileTree 儲存的掃描：\n{reason}",
    "column_before": "之前",
    "column_now": "現在",
    "column_change": "變化",
    "changes_new": "新增",
    "changes_gone": "已不存在",
    "changes_whole_scan": "（掃描的資料夾）",
    "changes_stop": "結束比較",
    "changes_running": "比較中…",
    "changes_waiting": "掃描結束後會再比較。",
    "changes_unknown_time": "時間不明",
    "changes_summary": ("與 {path}（儲存於 {when}）比較：之前 {before}，現在 {now}（{change}）；"
                        "{count} 個資料夾有變化。"),
    "tab_duplicates": "重複檔案",
    "tab_cleanup": "清理",
    "cleanup_suggestions": "建議",
    "cleanup_select_all": "全部選取",
    "cleanup_select_group": "選取這一組",
    "cleanup_running": "正在找可以清理的東西…",
    "cleanup_hint": "掃描完成後，這裡會列出內容通常可以刪掉的位置。",
    "cleanup_none": "這次掃描沒有可以建議清理的東西。",
    "cleanup_summary": ("共 {groups} 組，邏輯大小 {size}。移到資源回收筒前請先審查路徑與配置空間；"
                        "移動不會立刻釋出空間。"),
    "cleanup_group": "{title}：{count} 項，共 {size}",
    "cleanup_temp": "暫存檔",
    "cleanup_temp_tip": "程式暫時留下的檔案；仍在執行的程式可能還在使用其中一些。",
    "cleanup_browser_cache": "瀏覽器快取",
    "cleanup_browser_cache_tip": "網頁與圖片的副本；瀏覽器需要時會重新下載。",
    "cleanup_thumbnails": "縮圖快取",
    "cleanup_thumbnails_tip": "圖片的小型預覽；開啟資料夾時會重新產生。",
    "cleanup_crash_dumps": "當機傾印檔",
    "cleanup_crash_dumps_tip": "程式當機時存下的記憶體內容，只有回報當機時才用得到。",
    "cleanup_package_caches": "套件下載快取（pip、npm…）",
    "cleanup_package_caches_tip": "為下次安裝保留的已下載套件；需要時會重新下載。",
    "cleanup_build_output": "編譯產物（可以重新建置）",
    "cleanup_build_output_tip": "專案安裝的相依套件與編譯出來的檔案；重新建置專案就會再產生。",
    "cleanup_old_installers": "下載資料夾裡的安裝檔",
    "cleanup_old_installers_tip": "多半很久以前就執行過的安裝程式；之後還要拿來安裝的請留著。",
    "cleanup_empty_folders": "空資料夾",
    "cleanup_empty_folders_tip": "裡面什麼都沒有，或只有其他空資料夾的資料夾。",
    "duplicates_min_size": "比對的最小檔案",
    "duplicates_any_size": "任何大小",
    "duplicates_find": "尋找重複檔案",
    "duplicates_stop": "停止",
    "duplicates_select_extra": "選取多餘的副本",
    "duplicates_select_extra_tip": "選取已決定保留副本且核對成功群組的多餘副本，再按 Delete",
    "duplicates_hint": ("在整個掃描範圍內找內容相同的檔案。只會讀取大小相同的檔案，"
                        "但讀取需要時間，所以除非選了較小的大小，否則會略過小檔案。"),
    "duplicates_starting": "正在找大小相同的檔案…",
    "duplicates_running": "已讀取 {files} / {total} 個檔案（{read} / {bytes}）…",
    "duplicates_stopped": "搜尋已停止。",
    "duplicates_none": "沒有找到重複的檔案。",
    "duplicates_summary": ('{groups} 組重複檔案：多餘副本的邏輯大小共 {extra}。'),
    "duplicates_limited": "只列出多餘空間最大的 {shown} 組。",
    "duplicates_skipped": "有 {count} 個檔案無法讀取。",
    "duplicates_group": ('{count} 份 × {size}：多餘副本的邏輯大小 {extra}。'),
    "search_placeholder": "名稱的一部分，或樣式：backup、*.mp4、*.iso;*.zip",
    "search_hint": "輸入名稱的一部分或含 * 和 ? 的樣式、選擇條件，或兩者一起，在整個掃描結果裡找檔案和資料夾。",
    "search_running": "搜尋中…",
    "search_larger": "大於",
    "search_smaller": "小於",
    "search_no_limit": "不限",
    "search_changed": "修改時間",
    "search_changed_any": "不限",
    "search_changed_week": "最近一週內",
    "search_changed_month": "最近一個月內",
    "search_changed_year": "最近一年內",
    "search_changed_stale_year": "超過一年沒動",
    "search_changed_stale_2y": "超過兩年沒動",
    "search_changed_stale_5y": "超過五年沒動",
    "search_type": "類型",
    "search_type_any": "不限類型",
    "search_show": "顯示",
    "search_kind_any": "檔案和資料夾",
    "search_kind_files": "只有檔案",
    "search_kind_folders": "只有資料夾",
    "search_saved": "已存的搜尋",
    "search_saved_none": "（無）",
    "search_save": "儲存…",
    "search_delete": "刪除",
    "search_save_title": "儲存這個搜尋",
    "search_save_prompt": "名稱：",
    "search_none": "沒有符合的項目。",
    "search_summary": "{count} 個符合，共 {size}。",
    "search_limited": "只列出最大的 {shown} 個。",
    "tab_types": "檔案類型",
    "tab_age": "檔案新舊",
    "column_age": "最後修改",
    "age_month": "一個月內",
    "age_half_year": "1–6 個月前",
    "age_year": "6–12 個月前",
    "age_two_years": "1–2 年前",
    "age_older": "超過 2 年",
    "largest_focus": "只顯示：{what}",
    "largest_show_all": "顯示全部",
    "list_files_tip": "按兩下一列，列出它最大的檔案",
    "tab_problems": "無法讀取",
    "tab_problems_count": "無法讀取（{count}）",
    "column_name": "名稱",
    "column_size": "大小",
    "column_allocated": "磁碟大小",
    "column_share": "佔上層比例",
    "column_share_total": "佔總量比例",
    "column_files": "檔案數",
    "column_folders": "資料夾數",
    "column_modified": "修改時間",
    "column_folder": "所在資料夾",
    "column_extension": "副檔名",
    "column_type": "類型",
    "column_path": "路徑",
    "column_problem": "原因",
    "problem_access_denied": "拒絕存取",
    "problem_not_found": "已經不存在",
    "problem_path_too_long": "路徑太長",
    "problem_not_scanned": "沒有掃描到：掃描在讀到這裡之前就停止了",
    "no_extension": "（沒有副檔名）",
    "tooltip_unreadable": "{path}\n無法讀取：{reason}",
    "tooltip_link": "{path}\n連結：只列出，不會跟進去計算",
    "tooltip_not_scanned": "{path}\n沒有掃描到：掃描在讀到這裡之前就停止了",
    "treemap_empty": "沒有可以顯示的內容",
    "treemap_up": "↑ 上一層",
    "treemap_up_tip": "顯示上一層資料夾",
    "treemap_tooltip": "<b>{name}</b><br>{size}（佔目前畫面的 {share}）<br>{path}",
    "treemap_more": "其餘 {count} 個",
    "treemap_more_tooltip": "<b>{name} 裡其餘 {count} 個較小的項目</b>，每個都小到畫不出來<br>"
                            "{size}（佔目前畫面的 {share}）",
    "treemap_more_open": "按兩下可以單獨顯示這個資料夾",
    "largest_filter": "依名稱或資料夾篩選…",
    "types_all": "所有類型",
    "category_images": "圖片",
    "category_video": "影片",
    "category_audio": "音樂與音訊",
    "category_documents": "文件",
    "category_archives": "壓縮檔與映像檔",
    "category_code": "程式碼與資料",
    "category_programs": "應用程式",
    "category_other": "其他",
    "status_selected": "{name}：{size}（佔所在資料夾的 {share}）",
    "status_selected_root": "{name}：{size}",
    "menu_open_item": "開啟",
    "menu_reveal": "在檔案總管中顯示",
    "menu_copy_path": "複製路徑",
    "menu_show_chart": "在圖表中顯示",
    "menu_scan_here": "只掃描這個資料夾",
    "menu_rescan_here": "重新掃描這個資料夾",
    "rescan_done": "已重新掃描 {name}：{before} → {after}",
    "trash_confirm_title": "移到資源回收筒",
    "protected_title": "系統或程式資料夾",
    "protected_question": ("其中 {count} 個是系統或程式的資料夾，移走可能讓系統或程式無法正常運作："
                           "\n\n{names}\n\n仍要移走嗎？"),
    "protected_system": "作業系統的一部分",
    "protected_programs": "已安裝的程式",
    "protected_settings": "程式的設定與資料",
    "protected_profile": "使用者的個人資料夾",
    "trash_confirm": "要把「{name}」（{size}）移到資源回收筒嗎？\n\n之後仍可以從資源回收筒還原。",
    "trash_failed": "無法把「{name}」移到資源回收筒，可能正在使用中或是唯讀。",
    "trash_done": "已把「{name}」移到資源回收筒，釋出 {size}。",
    "action_trash_many": "把 {count} 個項目移到資源回收筒",
    "trash_confirm_many": ("要把這 {count} 個項目（共 {size}）移到資源回收筒嗎？\n\n{names}\n\n"
                           "之後仍可以從資源回收筒還原。"),
    "trash_more": "……還有 {count} 個",
    "trash_failed_many": "有 {count} 個項目無法移到資源回收筒，可能正在使用中或是唯讀：\n\n{names}",
    "trash_done_many": "已把 {count} 個項目移到資源回收筒，釋出 {size}。",
    "status_selected_many": "已選取 {count} 個項目：{size}",
    "export_title": "匯出",
    "export_running": "正在儲存到 {path}…",
    "csv_filter": "CSV 檔案 (*.csv)",
    "json_filter": "JSON 檔案 (*.json)",
    "export_done": "已把 {count} 列存到 {path}",
    "export_failed": "無法儲存檔案。\n\n原因：{reason}",
    "help_title": "FileTree 使用說明",
    "help_html": _cjk("""
<h2>三個步驟就會用</h2>
<ol>
<li><b>選擇要掃描的地方。</b>按<i>選擇資料夾…</i>或其中一顆磁碟，把資料夾拖曳到視窗上，
或在上方的方框輸入路徑後按 Enter。</li>
<li><b>邊掃邊看。</b>資料夾樹會立刻出現，FileTree 一邊加總，最大的資料夾一邊往上排；
最大的檔案與檔案類型在掃描結束時補上。
隨時可以按<i>停止</i>（或 Esc）：已經讀到的部分會留在畫面上，並標示為不完整。</li>
<li><b>找出佔空間的東西。</b>最大的資料夾排在最上面，按資料夾旁的箭頭就能看裡面的內容。</li>
</ol>
<h2>看懂結果</h2>
<ul>
<li><b>資料夾樹</b>（左邊）：每個資料夾或檔案的大小、<i>磁碟大小</i>（實際佔用的磁碟空間：以整個叢集計算，
通常比大小多一點；壓縮檔案較少，只存在雲端的檔案是 0）、<i>佔上層比例</i>長條（它佔上一層資料夾多少空間）、
裡面有幾個檔案和資料夾，以及裡面最近一次變動的時間。按欄位標題可以依該欄排序。</li>
<li><b>圖表</b>：在分頁角落切換同一個資料夾的四種圖（一開始是方塊圖，之後會記住你選的）。<i>方塊圖</i>把每個檔案畫成一個方塊，檔案越大、方塊越大，
每個資料夾頂端有寫著名稱和大小的標題列；
資料夾裡小到看不見的檔案會合成一個灰色斜線方塊（<i>其餘 12 個</i>），按兩下它可以單獨顯示那個資料夾。
<i>層數</i>決定要畫幾層，<i>顏色</i>可以依檔案類型（圖例在下方）或依最上層的資料夾上色。
<i>長條圖</i>替資料夾裡每個項目畫一條長條，由大到小，附大小與比例。
<i>放射圖</i>把目前資料夾放在中心，每深一層就是外面一圈，按中心回上一層。
<i>樹狀圖</i>畫出可展開的資料夾卡片，按加號或「其餘資料夾」顯示更多；可切換方向、
按 Ctrl＋滾輪縮放並用捲軸移動。
按一下可以在資料夾樹中找到它，按兩下資料夾可以進入，按<i>上一層</i>回去。</li>
<li><b>最大的檔案</b>：整個掃描範圍內最大的 1,000 個檔案。在篩選框輸入文字可以縮小清單，
按兩下某一列就會在資料夾樹中找到那個檔案。</li>
<li><b>搜尋</b>（Ctrl+F）：整個掃描範圍內，名稱含有輸入文字的檔案和資料夾。
<code>*.mp4</code> 這類樣式要符合完整名稱；好幾個樣式用 <code>;</code> 分開（<code>*.iso;*.zip</code>）。
搜尋框下方的條件（大小、修改時間、檔案類型、檔案或資料夾）可以縮小範圍，也可以單獨搜尋；
<i>儲存…</i>可以把搜尋取名存起來。會列出最大的 1,000 個符合項目，並顯示全部符合項目的數量和總大小。</li>
<li><b>清理 → 建議</b>：每次掃描後列出內容通常可以刪掉的位置，每種一組
（暫存檔、快取、當機傾印檔、可以重新建置的編譯產物、下載資料夾裡的舊安裝檔、空資料夾）；
滑鼠停在組名上可以看刪掉它的影響，再按<i>選取這一組</i>或<i>全部選取</i>，然後按 Delete。</li>
<li><b>清理 → 重複檔案</b>：按<i>尋找重複檔案</i>，把內容相同的檔案分組。只會讀取大小相同的檔案；因為讀取需要時間，
除非選了較小的大小，否則會略過 1 MB 以下的檔案。每一組由舊到新列出副本；<i>選取多餘的副本</i>會選取最舊那份以外的全部，
再按 Delete 就會移到資源回收筒。</li>
<li><b>檔案類型</b>：各種檔案依副檔名各佔多少空間；在表格上方的清單選一種類型，就只顯示那一類；
按兩下一列，會列出那種檔案裡最大的幾個。</li>
<li><b>檔案新舊</b>：一個月內、1–6 個月前……一直到超過 2 年前最後修改的檔案各佔多少空間。
舊資料常常就是可以封存或刪除的東西；按兩下一列，會列出那一段裡最大的檔案。</li>
<li><b>無法讀取</b>：FileTree 沒有權限讀取的資料夾，裡面的內容不會算進去。</li>
</ul>
<h2>釋出空間</h2>
<p>在任何項目上按右鍵，可以<i>開啟</i>、<i>在檔案總管中顯示</i>、<i>複製路徑</i>、<i>在方塊圖中顯示</i>、
<i>重新掃描這個資料夾</i>（在 FileTree 以外改過東西之後用，其餘結果不變）、
<i>只掃描這個資料夾</i>，或<i>移到資源回收筒</i>。
要一次移走好幾個項目，在資料夾樹、<i>最大的檔案</i>或<i>搜尋</i>清單裡用 Ctrl+按一下或 Shift+按一下選取，
只會詢問一次，並列出它們和總大小。
FileTree 不會永久刪除任何東西：每次都會先詢問，
移走的東西都能從資源回收筒（macOS 與 Linux 是「垃圾桶」）還原。數字會立刻更新，不必重新掃描。
系統與程式的資料夾會說明原因並多問一次；暫存資料夾與快取不會。</p>
<h2>看看哪裡變大了</h2>
<p>用<i>檔案 → 匯出 → 資料夾樹（JSON）</i>把掃描存起來。之後重新掃描，選<i>檔案 → 與先前儲存的掃描比較…</i>
開啟那個檔案，<b>變化</b>分頁就會列出每個有變化的資料夾之前和現在的大小，變大最多的排在最前面
（<i>新增</i>與<i>已不存在</i>標示新出現或消失的資料夾）。在按<i>結束比較</i>之前，每次重新掃描都會繼續比較。</p>
<h2>鍵盤快速鍵</h2>
<table cellpadding="3">
<tr><td><b>Ctrl+O</b></td><td>選擇資料夾</td></tr>
<tr><td><b>F5</b></td><td>重新掃描</td></tr>
<tr><td><b>Esc</b></td><td>停止掃描</td></tr>
<tr><td><b>Ctrl+F</b></td><td>依名稱搜尋</td></tr>
<tr><td><b>Delete</b></td><td>把選取的項目（可以好幾個）移到資源回收筒</td></tr>
<tr><td><b>F1</b></td><td>這份說明</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>結束</td></tr>
</table>
<p>在 macOS 上請用 ⌘ 取代 Ctrl（⌘R 是重新掃描）。</p>
<h2>小知識</h2>
<ul>
<li>大小是檔案的實際大小，以二進位單位計算（1 KB = 1,024 位元組），和 Windows 檔案總管相同；
可以在<i>檢視 → 大小單位</i>改用固定的單位。</li>
<li>捷徑與連結（符號連結、目錄連接）會列出來，但不會跟進去計算，所以不會重複計算。</li>
<li>在 Windows 上，FileTree 啟動時會像 TreeSize 一樣要求系統管理員權限，受保護的資料夾也能讀取。
拒絕的話它照常以一般權限執行，讀不到的資料夾列在<i>無法讀取</i>分頁，那裡有<i>以系統管理員身分重新啟動</i>按鈕。
不想每次被問，可以關掉<i>檢視 → 啟動時要求系統管理員權限</i>。</li>
<li><i>最大的檔案</i>、<i>檔案類型</i>與<i>檔案新舊</i>預設統計整個掃描範圍；
按這幾個分頁右上角的<i>只看選取的資料夾</i>，就會改為跟著資料夾樹中選取的資料夾。</li>
<li>預設會計算隱藏檔案；關掉<i>檢視 → 包含隱藏檔案</i>，下次掃描就不會算進去。</li>
<li>要讓某些資料夾每次都不掃描，把它們加進<i>檢視 → 掃描時略過</i>：
像 <code>node_modules</code> 這樣的名稱會略過所有同名的資料夾，路徑只略過那一個資料夾。
略過的資料夾會以灰字列出，大小為 0。</li>
<li>用<i>檔案 → 匯出</i>儲存結果：CSV 可用 Excel 開啟，JSON 給程式使用。</li>
</ul>
"""),
}

ZH_CN: dict[str, str] = {
    "namespace_source_name": "源名称",
    "namespace_destination_name": "目标名称",
    "namespace_closed_errors": "已停止／关闭的操作报告错误。请检查详细信息中的源／目标路径。",
    "namespace_refreshed": "已重扫 {path}：{files} 个文件；{errors} 个扫描错误。",
    "namespace_refresh_failed": "重扫失败，路径 {path}：{reason}",
    "namespace_refreshing": "正在重扫受影响的目标：{path}",
    'menu_move_folder': '移动到文件夹…',
    'menu_rename': '重命名…',
    'namespace_source': '源',
    'namespace_destination': '目标',
    'namespace_status': '状态',
    'namespace_pattern': '文件名模式',
    'namespace_rename_hint': ('查看每个源与目标。字面替换：{name}、{stem}、{ext}、{n}。'
                            '仅限同磁盘，不覆盖。最多选中 1,000 个项目。'),
    'namespace_move_hint': ('选择现有目标文件夹，查看每组路径。仅限同磁盘，不覆盖。'
                          '拒绝受保护、链接、不可用或记录不完整的项目。最多选中 1,000 个项目。'),
    'namespace_collision_skip': '名称已存在：跳过',
    'namespace_collision_rename': '名称已存在：预览编号后缀',
    'namespace_preview': '预览路径',
    'namespace_apply': '应用已查看的路径…',
    'namespace_reading': '正在检查源与目标元数据…',
    'namespace_preview_needed': '选项已变化；应用前请重新预览路径。',
    'namespace_summary': '{total} 组最外层路径；{ready} 组可执行；{skipped} 组拒绝／未变化。',
    'namespace_confirm': ('要应用预览中 {count} 组可执行的源／目标吗？其余 {skipped} '
     '组将跳过。详细信息列出每组可执行路径。不覆盖现有名称。停止／关闭须等待当前重命名完成，已完成的变化会保留。'),
    'namespace_progress': '已处理 {done}／{total} 组路径',
    'namespace_done': '已移动／重命名：{moved}；跳过：{skipped}；失败：{failed}。关闭后更新扫描。',
    'namespace_failed': '操作失败：{reason}',
    'namespace_reason_ready': '可执行',
    'namespace_reason_unverified': '标识未知',
    'namespace_reason_link': '拒绝链接',
    'namespace_reason_special': '拒绝特殊项目',
    'namespace_reason_unavailable': '不可用／云端项目',
    'namespace_reason_cancelled': '已停止',
    'namespace_reason_outside': '当前扫描范围外／根目录',
    'namespace_reason_missing': '源不存在',
    'namespace_reason_kind': '项目类型已变化',
    'namespace_reason_identity': '源已被替换',
    'namespace_reason_changed': '源已变化',
    'namespace_reason_incomplete': '源记录不完整',
    'namespace_reason_unreadable': '无法读取源',
    'namespace_reason_system_managed': '系统管理的源',
    'namespace_reason_protected': '受保护的源',
    'namespace_reason_unchanged': '名称未变化',
    'namespace_reason_descendant': '目标位于选中的源内',
    'namespace_reason_protected_destination': '受保护的目标',
    'namespace_reason_volume': '不同磁盘；须验证复制',
    'namespace_reason_collision': '名称已存在',
    "photos_exact": "精确重复文件",
    "photos_find": "查找相似照片",
    "photos_similar": "相似照片",
    "photos_distance": "哈希距离（0–16）：",
    "photos_hint": ("仅为视觉候选：请比较缩略图与原图。哈希可能碰撞；"
                    "不自动选择保留副本、多余副本或估计回收量。动画只看第一帧。"),
    "photos_group": "{count} 张图片；与第一张的距离在 {distance} 位内",
    "photos_running": "正在读取图片：{read}；跳过／失败：{skipped}",
    "photos_summary": "{groups} 组相似图片；已读取 {read} 张；跳过／失败 {skipped} 张。",
    "photos_limited": "列表或显示范围受限；最多显示 {count} 个图片行／缩略图。",
    "archive_loading": "正在读取压缩文件元数据…",
    "archive_virtual_name": "{name}［虚拟］",
    "archive_virtual_hint": "压缩文件内容：声明的未压缩大小，不计入磁盘总量。不提供文件操作或解压。",
    "archive_failed": "无法预览：{reason}",
    "archive_rejected": "已跳过 {count} 个不安全、链接或冲突的项目",
    "archive_empty": "没有可预览的项目",
    "archive_stopped": "压缩文件预览已停止；内容列表不完整",
    "archive_busy": "已有两个压缩文件读取任务；重新扫描后可重试",
    "archive_stop": "停止读取此压缩文件",
    "action_count_hard_links": (
        "观察到的硬链接只计一次"
    ),
    "action_count_hard_links_tip": (
        "默认关闭；后续扫描保留具名大小并增加计入总量。分支／回收站移动后会重扫完整范围。"
    ),
    "column_accounted_size": (
        "计入大小"
    ),
    "column_accounted_allocated": (
        "计入磁盘大小"
    ),
    "hard_links_hint": (
        "启用硬链接计量时，观察到的路径排序第一个名称计入字节，其他名称在此计为零。具名大小仍是实际文件长度。未知／不一致记录保留估计值，共享数据区段"
        "仍未知。"
    ),
    "hard_links_summary": (
        "计入：{size}（磁盘估计 {allocated}）；观察到 {aliases} 个别名；未知记录 {unknown} 个。图表使用计入总"
        "量，文件／类型／文件年龄列表保留具名大小。"
    ),
    "compression_mode_ntfs": "NTFS 压缩",
    "compression_mode_xpress8k": "XPRESS8K 压缩（很少修改的文件）",
    "compression_mode_uncompress": "解压缩（NTFS 及可执行文件模式）",
    "compression_apply": "处理列表中的文件…",
    "compression_restore_summary": "{count}/{total} 个已记录文件可供检查；显示 {shown} 个。压缩状态可能未知。",
    "compression_confirm": (
        "范围：{path}\n模式：{mode}\n仅处理列表中的 {count} 个文件（逻辑大小 {size}），"
        "候选项共 {total} 个。\n\n会重新核对当前 NTFS "
        "范围与未变化的文件。拒绝链接、云端／离线、稀疏、隐藏／系统、硬链接及受保护文件。"
        "不改变文件夹默认值及列表外文件。压缩可能降低写入速度；XPRESS "
        "适合很少修改的数据。解压缩需要足够可用空间。停止或失败可能留下部分更改。\n\n关闭此窗口会取消当前命令、等待结束，再以逐文件磁盘大小测量重新扫描此文件夹。是否继续？"
    ),
    "compression_progress": "正在处理列表中的 {done}/{total} 个文件…",
    "compression_done": (
        "{done}/{attempted} 个命令完成；失败 {failures} 个。"
        "核对成功的已知文件分配：{before} → {after}；未知测量 {unknown} "
        "个。关闭后重新扫描；总计不保证可释放空间。显示前 20 条错误。"
    ),
    "compression_canceled": "已停止；先前或当前文件可能已更改。关闭后重新扫描。",
    "compression_failed": "操作失败：{reason}。可能有部分更改，关闭后重新扫描。",
    "action_exact_allocation": "测量 Windows 逐文件磁盘大小",
    "action_exact_allocation_tip": (
        "默认关闭，后续扫描增加元数据查询，包含 XPRESS／WOF 文件。启用后请重新扫描。"
        "已知云端／离线文件不会查询，失败结果仍使用估计值。"
    ),
    "menu_compression": "NTFS 压缩…",
    "compression_reading": "正在检查已记录的压缩候选项…",
    "compression_summary": (
        "{count}/{total} 个文件为类型候选，显示 {shown} 个；逻辑大小 {logical}，具名磁盘分配 {allocated}。"
        "可能节省 0–{allocated}，不预测固定压缩率。{unknown} 个文件的元数据未知。"
    ),
    "compression_volume": "文件系统：{filesystem}；分配单位：{unit}",
    "compression_unknown": "未知",
    "compression_ntfs_only": "无法确认 NTFS，此范围不能进行原生压缩。",
    "compression_partial": "扫描不完整：跳过／无法读取的数据不在此估算范围。",
    "compression_hint": (
        "只读类型估算：日志、文本、代码与可能未压缩的图像格式。扩展名不能证明可压缩程度。"
        "不含隐藏／系统、压缩／稀疏、重解析／云端／离线或元数据未知的项。"
        "具名磁盘分配可能是估计值或由硬链接共享，不保证可回收空间；不读取文件内容。"
        "双击选择已记录的文件，Ctrl+C 复制列表。"
    ),
    "action_capture_owners": "记录 Windows 文件所有者",
    "action_capture_owners_tip": "默认关闭；后续扫描增加所有者元数据查询，启用后请重新扫描",
    "tab_users": "用户",
    "column_owner": "所有者",
    "column_owner_id": "所有者标识",
    "owner_unknown": "所有者未知",
    "owners_refresh": "刷新记录总计",
    "owners_reading": "正在累加所有者记录并查询账户名称…",
    "owners_unqueried": "扫描完成后打开“用户”，即可查询已记录的所有者总计。",
    "owners_partial": "扫描不完整：跳过／无法读取的大小与所有者保持未知。",
    "owners_summary": (
        "{count} 组所有者，显示 {shown} 组；{files} 个文件，{size}。"
        "所有者未知：{unknown_files} 个文件，{unknown_size}。"
    ),
    "owners_hint": (
        "使用整份扫描，仅按文件所有者累加；文件夹所有者不会应用到其中的文件。"
        "POSIX uid 来自扫描已读取的 stat；Windows 请启用“选项 → 记录 Windows 文件所有者”并重新扫描。"
        "未启用、失败、路径已变或云端／离线查询保持未知，名称可能改显示 uid／SID。"
        "具名磁盘分配仍是估计值，硬链接按各名称计算。所有者不能证明实际使用或移除权限；此处不会准备清理操作。"
    ),
    "bin_labels_refresh": "刷新回收站大小",
    "bin_labels_hint": (
        "只读快照，最多查询 256 个就绪磁盘，优先查询扫描所在磁盘。"
        "POSIX 大小为内容的逻辑字节；无法获取或不完整的总计不代表零。"
        "范围可能重叠，请勿累加。点击刷新才会查询，此处不会准备清理操作。"
    ),
    "bin_label_scope_unknown": "此扫描所在磁盘的回收站：尚未查询范围",
    "bin_label_unqueried": "{root} 回收站：尚未查询",
    "bin_label_total": "{root} 回收站：{size}，{count} 个项目",
    "bin_label_partial": "{root} 回收站：总计未知；已知 {size}，{count} 个项目",
    "action_file_times": "文件时间…",
    "action_file_times_tip": "按本次扫描记录的访问与创建时间筛选",
    "action_capture_file_times": "记录文件访问／创建时间",
    "action_capture_file_times_tip": "默认关闭；之后扫描每个普通文件增加 16 bytes；开启后请重新扫描",
    "column_accessed": "记录的访问时间",
    "column_created": "创建时间",
    "file_times_hint": (
        "请开启“选项 → 记录文件访问／创建时间”后重新扫描。只记录普通文件；文件夹、链接"
        "及无法获取的创建时间保持未知。访问时间可能停用、延迟更新，或受后台工具影响，无法"
        "证明实际使用时间。POSIX ctime 不是创建时间。此视图不会准备清理操作。"
    ),
    "file_times_accessed": "多久未打开…（按记录的访问日期）",
    "file_times_created": "创建至少多久…",
    "file_times_mode": "记录时间的筛选模式",
    "file_times_days": "天数",
    "file_times_reading": "正在筛选已记录的文件时间…",
    "file_times_summary": (
        "符合 {count} 个文件，共 {size}；显示 {shown} 个。{total} 个文件中有 {unknown} 个"
        "时间未知或在未来。"
    ),
    "file_times_policy_disabled": (
        "NTFS 报告已停用访问时间更新，无法按访问时间筛选；仍可按创建时间筛选。注册表设置"
        "可能需重启，且不代表所有文件系统。"
    ),
    "file_times_policy_unknown": "无法确认 NTFS 访问时间更新设置，无法按访问时间筛选；仍可按创建时间筛选。",
    "file_times_policy_enabled": (
        "NTFS 注册表设置报告已启用访问时间更新；待重启、文件系统／提供者设置及延迟更新仍"
        "可能影响日期。"
    ),
    "file_times_policy_platform": "文件系统／提供者设置可能延迟或停用访问时间更新，请将日期视为已记录的元数据。",
    "action_programs": "已安装程序…",
    "action_programs_tip": "核对安装程序／游戏元数据与此扫描中的安装文件夹",
    "program_name": "程序／游戏",
    "program_source": "元数据来源",
    "program_version": "版本／构建",
    "program_publisher": "发布者",
    "program_reported": "报告的估计大小",
    "program_scanned": "扫描的逻辑大小",
    "program_allocated": "扫描按名称计算的分配量",
    "program_coverage": "记录的文件夹覆盖范围",
    "program_location": "安装文件夹",
    "program_registry": "Windows 注册表",
    "program_steam": "Steam 清单",
    "program_epic": "Epic 清单",
    "program_outside": "没有完全匹配的扫描文件夹",
    "program_hint": "Windows 卸载注册项与识别到的 Steam／Epic 清单，仅核对此扫描中完全匹配的文件夹，"
                    "也会读取 Epic 在 ProgramData 的固定清单目录。报告大小是估计，缺少数据保持未知。共享或嵌套"
                    "文件夹可能重叠，请勿合计行或视为可回收空间。便携式／打包应用可能未列出。双击选中"
                    "记录的文件夹，Ctrl+C 复制行。请通过 Windows 或游戏启动器卸载。",
    "program_reading": "正在读取安装元数据…",
    "program_summary": "显示 {shown}／{count} 个安装条目；{issues} 个无法读取、格式错误或跳过的元数据条目",
    "program_failed": "无法读取安装条目：{reason}",
    "program_uninstall_page": "打开 Windows 已安装应用设置",
    "program_open_failed": "Windows 无法打开已安装应用设置页面",
    "action_history": "扫描历史…",
    "action_history_tip": "查看此根目录大小随时间的变化，并与先前扫描比较",
    "action_history_settings": "扫描历史设置…",
    "action_history_settings_tip": "启用本地扫描元数据并设置整体保留上限",
    "history_enable": "在本地保留已完成的整个扫描",
    "history_settings_hint": "历史保留文件夹名称、路径、容量与覆盖范围，不含文件内容。默认启用，所有根目录合计 "
                             "1 GiB。只按时间移除识别为历史的元数据。关闭后仍可查看已有历史。变化适用于未来的"
                             "整个扫描；降低上限会在下次保存时应用。",
    "history_limit": "历史总容量上限",
    "history_time": "扫描时间",
    "history_logical": "逻辑大小",
    "history_allocated": "按名称计算的分配量",
    "history_coverage": "覆盖范围",
    "history_incomplete": "不完整；仅含已知数据",
    "history_complete": "记录范围完整",
    "history_chart": "文件夹逻辑大小随时间的变化",
    "history_chart_range": "{first}：{before}；{last}：{after}",
    "history_empty": "此根目录没有保留的扫描",
    "history_compare": "将所选扫描与当前结果比较",
    "history_reading": "正在读取本地扫描历史…",
    "history_hint": "显示此根目录最近 1,000 条保留的整个扫描，不保存停止的扫描及局部重扫。不完整扫描仅描述"
                    "已知数据，缺少文件夹不代表已删除。总量分别计入硬链接名称；差异是元数据，而非内容验证。",
    "history_summary": "显示 {shown}／{count} 条扫描；{invalid} 个无效或无法读取的元数据文件",
    "history_failed": "无法读取历史：{reason}",
    "history_save_failed": "扫描已完成，但无法保存历史：{reason}",
    "action_scan_workers": "扫描线程数…",
    "action_scan_workers_tip": "选择新扫描的并行数，较高不一定较快",
    "workers_prompt": "新扫描线程数（1–32），默认值为 {default}。慢速网络共享可能受益于更多线程；"
                      "过高并行数可能使磁盘／服务器负荷过重。进行中的扫描保留现有线程数，UNC 性能取决于实际共享环境。",
    "action_bins": "回收站…",
    "action_bins_tip": "检查回收站总量与明确范围的系统清空操作",
    "bin_finder_empty": "清空所有已挂载磁盘的 Finder 回收站…",
    "bin_finder_all": "所有已挂载磁盘（Finder 全局回收站）",
    "bin_finder_scopes": "当前用户的回收站范围：\n{scopes}\n\n已挂载磁盘：\n{roots}",
    "bin_finder_first": "清空当前用户在所有已挂载磁盘上的 Finder 回收站？\n\n{root}\n\n"
                        "内容逻辑大小：{size}\n项数：{count}",
    "bin_finder_irreversible": "永久清空当前用户在所有已挂载磁盘上的 Finder 回收站？\n\n{root}\n\n"
                               "内容逻辑大小：{size}\n项数：{count}\n\n此操作无法恢复。"
                               "Finder 也可能移除操作期间新增的项。"
                               "此操作影响所有已挂载磁盘的回收站，与选中哪一行无关，开始后不能取消。"
                               "自动化或权限错误可能导致仅完成一部分，Finder 也可能仍在运行。",
    "bin_preparing": "正在清点 {root} 的确切回收站范围…",
    "bin_no_approval": "没有完整且非空的回收站清点，请刷新后重新检查。",
    "bin_scope_first": "清空当前用户的这些回收站内容／收据范围？\n\n{root}\n\n内容逻辑大小：{size}\n项数：{count}",
    "bin_scope_irreversible": "永久移除这些确切范围内已检查的内容？\n\n{root}\n\n"
                              "内容逻辑大小：{size}\n项数：{count}\n\n"
                              "此操作无法恢复。内容中的链接只移除链接本身，不跟随其目标。已变化的项会拒绝处理；"
                              "失败时可能只完成一部分。开始清空后无法取消。",
    "bin_partial": "已移除 {count} 个已检查项；其余失败原因：{reason}",
    "bin_empty": "清空选中磁盘的回收站…",
    "bin_first": "清空 {root} 的回收站？\n\n报告大小：{size}\n项数：{count}",
    "bin_irreversible": "永久移除 {root} 回收站当前的全部项？\n\n报告大小：{size}\n项数：{count}\n\n"
                        "此操作无法恢复。系统操作期间新增的项也可能被移除；原生操作开始后不能取消。",
    "bin_running": "正在清空 {root} 的回收站，等待系统操作完成…",
    "bin_failed": "未完成清空：{reason}",
    "bin_hint": "选中一个已挂载磁盘。Windows 清空当前用户的系统回收站；Linux 清点已识别的 files／info 范围。"
                "永久移除前以两次询问列出确切范围与总量。停止可取消清点；开始清空后必须等待完成。"
                "macOS 经全局检查后清空所有已挂载磁盘的 Finder 回收站，原生验证待完成。"
                "完成后更新容量／回收站数值；重新扫描可更新主树。",
    "action_volumes": "磁盘总览…",
    "action_volumes_tip": "查看已挂载磁盘、容量、分配单位与回收站总量",
    "volume_root": "挂载根目录",
    "volume_name": "磁盘名称",
    "volume_fs": "文件系统",
    "volume_total": "总量",
    "volume_used": "已用",
    "volume_free": "可用空间",
    "volume_cluster": "分配单位",
    "volume_trash": "回收站大小",
    "volume_trash_count": "回收站项数",
    "volume_reading": "正在读取已挂载磁盘与回收站总量…",
    "volume_summary": "共 {count} 个已挂载磁盘，显示 {shown} 个。双击开始扫描。",
    "volume_trash_partial": "总量未知（已知 {known}）",
    "volume_hint": "操作系统容量快照；可用空间可能扣除保留量或配额。重复挂载可能共用容量，不要汇总各行。"
                   "Windows 分配单位是簇；POSIX 单位是文件系统片段，不是最佳传输大小。"
                   "回收站列出 Windows 报告总量或 POSIX 已知逻辑内容大小，非可回收空间，"
                   "不含文件夹／回执元数据与共享分配。"
                   "错误保持未知。停止会等待当前系统调用，取消时丢弃检查结果。Ctrl+C 复制行；此处不提供清空操作。",
    "action_export_report_html": "扫描报告（HTML）…",
    "action_export_report_html_tip": "保存内嵌三张图表图片的独立报告",
    "action_export_report_xlsx": "扫描报告（Excel）…",
    "action_export_report_xlsx_tip": "将报告列表保存在各自的 Excel 工作表",
    "html_filter": "HTML 报告 (*.html)",
    "xlsx_filter": "Excel 工作簿 (*.xlsx)",
    "report_title": "FileTree 扫描报告",
    "report_note": "仅含已知记录范围；磁盘分配是估计值。标题数量为显示／全部。最大文件夹范围重叠，不要汇总各行。"
                   "最大文件与文件夹各限 1,000 条，文件类型限 10,000 条。大小单位为字节。"
                   "文件时间按修改记录，非最后访问；"
                   "无可用日期归入现有的最旧时间组。HTML 图表显示整份扫描根目录，图形范围有限。"
                   "Excel 文本经转义，控制字符显示为十六进制，每格限 32,767 字符，16 位以上整数以精确文本保存。",
    "report_bytes": "逻辑字节",
    "report_allocated": "分配字节（估计）",
    "report_created": "报告创建时间",
    "report_reference": "文件时间参考点",
    "report_skipped": "跳过文件夹",
    "report_denied": "不可读取文件夹",
    "report_pending": "待读取文件夹",
    "report_summary": "摘要",
    "report_notes": "说明",
    "report_field": "字段",
    "report_value": "值",
    "report_top_folders": "最大文件夹（范围重叠）",
    "report_categories": "分类",
    "action_projects": "项目与可重建数据…",
    "action_projects_tip": "查看已扫描的项目、Git 与生成数据大小",
    "project_path": "项目／管理存储区",
    "project_kind": "识别类型",
    "project_other": "源文件／其他",
    "project_git": ".git",
    "project_generated": "可重建数据",
    "project_coverage": "扫描范围",
    "project_partial": "不完整",
    "project_recorded": "已记录范围",
    "project_hint": "仅列已知逻辑大小；嵌套项目范围重叠。Git 指针文件不含外部元数据。生成数据可能含自定义文件，"
                    "移动前请检查。Maven、全局 Gradle 与 Docker 存储区分开显示，不假定其内容可丢弃。",
    "project_reading": "正在检查已扫描的项目数据…",
    "project_summary": "共识别 {count} 个项目／存储区，显示最大的 {shown} 个。",
    "project_review": "检查符合条件的可重建项…",
    "project_review_count": "按当前时间、扫描范围与清理设置，{count} 个符合条件的项最多检查 {shown} 个。"
                            "已停止的扫描不提供清理建议。",
    "project_git_kind": "Git",
    "project_python": "Python",
    "project_node": "Node.js",
    "project_rust": "Rust",
    "project_jvm": "JVM",
    "project_conda": "Conda 项目",
    "project_python_environment": "Python 环境",
    "project_conda_environment": "Conda 环境",
    "project_maven_store": "Maven 存储区",
    "project_gradle_store": "全局 Gradle 存储区",
    "project_docker_store": "Docker 数据",
    "action_git_history": "Git 历史…",
    "action_git_history_tip": "查看所有 Git 引用可达的最大对象",
    "git_oid": "对象标识",
    "git_kind": "对象类型",
    "git_length": "解压后长度",
    "git_type_blob": "文件内容（blob）",
    "git_type_tree": "文件夹列表（tree）",
    "git_type_commit": "提交",
    "git_type_tag": "附注标签",
    "git_hint": ("只读 Git 底层命令检查所有引用，保留最大的 1,000 个对象。大小是解压后长度，并非磁盘分配或可回收空间。"
                 "Git 的对象名称提示可能有歧义，因此不列名称。Ctrl+C 复制标识／行。"
                 "禁用可选锁定、自动维护与延迟网络下载；"
                 "Git 必须支持 --no-lazy-fetch。不绕过仓库所有者检查。可停止；不执行 gc。"),
    "git_reading": "正在检查 Git 历史…",
    "git_summary": "显示 {count} 个可达对象中的 {shown} 个；解压后总量 {size}。",
    "git_gc_loose": ("Git gc 可能合并 {count} 个松散对象，但这些最大对象仍可由引用到达，不会被移除。"
                     "实际节省量及其他不可达／引用日志数据仍未知。"),
    "git_gc_packed": ("没有可合并的松散对象。引用保留这些对象时，Git gc 不会移除它们；"
                      "其他不可达／引用日志数据与实际节省量尚未测量。"),
    "git_failed": "Git 检查失败：{reason}",
    "tree_filter_placeholder": "筛选已展开的文件夹…",
    "tree_filter_hint": ("仅在已展开的文件夹匹配名称（不区分大小写），保留上层路径。不搜索折叠的内容。"
                         "清除筛选即可恢复树状列表。从图表／列表选择被隐藏的项目会清除筛选。扫描总量与导出保持不变。"),
    "action_live_compare": "比较两个文件夹…",
    "action_live_compare_tip": "比较实时相对路径，仅验证选中的文件对",
    "compare_choose_left": "选择左侧文件夹",
    "compare_choose_right": "选择右侧文件夹",
    "compare_relative": "相对路径",
    "compare_state": "比较结果",
    "compare_left_size": "左侧大小",
    "compare_right_size": "右侧大小",
    "compare_left_time": "左侧修改时间",
    "compare_right_time": "右侧修改时间",
    "compare_roots": "左侧：{left}\n右侧：{right}",
    "compare_hint": ("只读：按 Unicode 与大小写完全匹配的名称配对，不跟随链接。大小／时间相同不代表内容相同。"
                     "选中文件对后可完整哈希验证，并可停止；更改、无法读取与已知云端文件保持无法验证。"
                     "结果对应此次扫描／验证时间。不执行复制、移动或同步。Ctrl+C 复制行；"
                     "CSV 仅导出显示的行，最多 10,000 行。"),
    "compare_reading": "正在扫描两个文件夹…",
    "compare_error": "比较或导出失败：{reason}",
    "compare_hashing": "正在验证选中的文件对…",
    "compare_verify": "验证选中的内容",
    "compare_summary": "显示 {count} 个相对路径中的 {shown} 个（上限 10,000）。",
    "compare_incomplete": "扫描范围不完整；无法读取范围中缺少的路径仍为未知。",
    "compare_unavailable": "无法验证或已更改",
    "compare_link": "链接；未读取内容",
    "compare_only_left": "仅左侧有",
    "compare_only_right": "仅右侧有",
    "compare_different_kind": "项目类型不同",
    "compare_folder": "两侧均为文件夹",
    "compare_different_size": "大小不同",
    "compare_different_time": "时间不同；尚未验证内容",
    "compare_unchecked": "尚未验证内容",
    "compare_identical": "完整哈希匹配",
    "compare_different_bytes": "内容不同",
    "problem_mount_boundary": "挂载边界：未扫描内容",
    "action_special_files": "云端与特殊文件…",
    "action_special_files_tip": "查看已记录的召回、脱机、压缩及稀疏文件状态",
    "special_states": "已记录状态",
    "special_content_size": "完整内容大小",
    "special_recall": "访问时可能召回",
    "special_offline": "脱机",
    "special_compressed": "已压缩",
    "special_sparse": "稀疏",
    "special_allocation_low": "分配较少，原因未知",
    "special_reading": "正在读取已记录的文件元数据…",
    "special_hint": ("本列表只使用扫描元数据，不打开或下载文件。召回／脱机属性可能来自 OneDrive、Dropbox "
                     "或其他服务，无法据此判断提供者及已在本机的比例。完整内容大小是含在线内容的逻辑长度；"
                     "下载后的磁盘分配未知。稀疏区域、压缩及驻留数据都可能减少分配。召回／脱机项目的磁盘大小 "
                     "0 是扫描估计，不是实测云端分配。双击可选择扫描项目；Ctrl+C 复制选中行。"),
    "special_summary": ("显示 {count} 个匹配文件中的 {shown} 个。完整内容 {size}；已记录分配 {allocated}。"
                        "无法获取文件元数据：{unknown}。保留最大的 1,000 个。"),
    "special_partial": "扫描范围不完整；未读取的文件仍未知。",
    "action_shell_integration": "资源管理器集成…",
    "action_shell_integration_tip": "在资源管理器的文件夹菜单添加或移除“使用 FileTree 扫描”",
    "shell_enabled": "在资源管理器的文件夹菜单添加“使用 FileTree 扫描”",
    "shell_scan": "使用 FileTree 扫描",
    "shell_hint": ("保存只会更改您账户的文件夹菜单，不需要管理员权限。"
                   "Windows 11 请查看“显示更多选项”。在此取消勾选即可移除。"
                   "移动可执行文件或源码文件夹后，请重新注册。"),
    "shell_failed": "无法更改资源管理器集成。\n{reason}",
    "menu_properties": "属性",
    "properties_failed": "Windows 无法打开此项目的属性：\n{path}",
    "menu_theme": "主题",
    "theme_system": "系统",
    "theme_light": "浅色",
    "theme_dark": "深色",

    "chart_access_keys": ("方向键选择已绘制条目；Enter 打开文件夹，Backspace 返回上级。"
                          "合并或未显示的条目可使用文件夹树查看。"),
    "chart_access_tree_keys": "上／下选择卡片，右／左展开或折叠文件夹。Enter 打开文件夹，Backspace 返回上级。",
    "chart_access_folder": "当前文件夹：{path}",
    "chart_access_selected": "已选择：{path}。大小 {size}；磁盘大小 {allocated}；{files} 个文件，{folders} 个文件夹。",

    "system_file_hibernate": ("休眠与快速启动状态，由 Windows 管理。管理员可使用 powercfg /hibernate off "
                              "关闭休眠，这也会移除休眠功能，并可能影响快速启动。FileTree 仅打开电源设置。"),
    "system_file_pagefile": ("虚拟内存的分页文件，Windows 可自动管理大小。在高级系统设置的性能设置中查看"
                             "虚拟内存；缩小可能影响应用程序与崩溃转储。"),
    "system_file_swapfile": ("Windows 的交换文件，包含暂停的应用数据，由系统与虚拟内存一并管理。请查看系"
                             "统内存设置，不要直接移除。"),
    "system_file_old": ("以前的 Windows 安装。在磁盘清理的“清理系统文件”中审查以前的 Windows 安装；"
                        "移除后将无法返回该安装。"),
    "system_file_recycle": "已删除条目在清空回收站前仍占用空间。请查看回收站或存储感知；清空是永久删除。",
    "system_file_restore": ("系统元数据、还原点与卷影副本。在系统保护的“配置”中调整还原点容量上限。备份"
                            "工具管理的卷影副本可能需要各自的备份工具；未读取的大小仍未知。"),
    "system_file_winsxs": ("Windows 组件存储。许多条目与 Windows 文件共用硬链接，因此逐名称汇总可能高估"
                           "实际存储空间。请使用磁盘清理的“清理系统文件”与 Windows 更新清理，不要手动移"
                           "除组件。"),
    "system_file_updates": ("Windows 更新下载数据。在磁盘清理的“清理系统文件”中审查更新及临时文件，进行"
                            "中的下载交由更新服务管理。"),
    "system_file_delivery": ("Windows 更新与应用的传递优化下载缓存。请在磁盘清理中审查传递优化文件，进行"
                             "中的传输由 Windows 管理。"),
    "system_tool_power": "打开电源设置…",
    "system_tool_memory": "打开高级系统设置…",
    "system_tool_cleanup": "打开磁盘清理…",
    "system_tool_storage": "打开存储感知…",
    "system_tool_restore": "打开系统保护…",
    "system_tool_failed": "无法打开 Windows 工具。",
    "trash_skip_system_managed": "此条目由 Windows 管理，请使用详细信息中的系统工具",

    "type_locations_title": "所在文件夹（最多 1,000 个）",
    "type_location_size": "匹配类型的大小",
    "type_locations_tip": "统计各文件夹直接包含的匹配类型文件；子文件夹单独列出，不重复计算。",

    "action_export_list": "当前列表（CSV）…",
    "action_export_list_tip": "按当前筛选与排序保存活动列表的所有行",
    "list_changed": "获取期间列表已变更，请重新导出或复制。",

    "details_title": "详细信息",
    "details_empty": "选择条目以显示详细信息",
    "details_live": "扫描完成后可查看分布。",
    "details_loading": "正在计算类型与文件年龄分布…",
    "details_recorded": "仅统计已读取的文件，未读取条目不在分布内。文件夹修改时间为最新的已记录日期。",
    "details_bucket": "{label}：{size} · {count} 个文件",

    "breadcrumbs_back": "返回（Alt+Left）",
    "breadcrumbs_forward": "前进（Alt+Right）",
    "breadcrumbs_more": "…",
    "breadcrumbs_more_tip": "显示上级文件夹",

    "action_print_view": "打印当前视图…",
    "action_print_view_tip": "通过系统打印对话框将可见结果打印在一页上",
    "action_export_view_pdf": "当前视图（PDF）…",
    "action_export_view_pdf_tip": "将可见结果调整为一页 PDF 保存",
    "pdf_filter": "PDF 文档 (*.pdf)",
    "view_pdf_exported": "已保存当前视图：{path}",
    "print_failed": "无法打印视图：{reason}",
    "print_submitted": "已将视图发送到打印机",
    "action_export_chart_png": "屏幕上的图表（PNG）…",
    "action_export_chart_png_tip": "保存当前可见的图表范围",
    "action_export_chart_svg": "条形图或旭日图（SVG）…",
    "action_export_chart_svg_tip": "将有数量上限的完整条形或圆弧保存为矢量图形与文字",
    "png_filter": "PNG 图片 (*.png)",
    "svg_filter": "SVG 图片 (*.svg)",
    "graphic_exported": "已保存图表：{path}",
    "treemap_colours_age": "按修改年龄",
    "age_colour_unknown": "日期未知",
    "age_colour_tip": "距离修改的时间。文件夹按最新修改记录着色，无可用日期时为灰色；合并的小项目保持灰色。",
    "action_gentle": "低优先级扫描",
    "action_gentle_tip": "降低新扫描的 CPU 与 I/O 优先级，可能花费较长时间",
    "scan_priority_warning": "部分扫描优先级设置无法应用：{reason}",
    "scan_pause": "暂停",
    "scan_resume": "继续",
    "scan_pause_tip": "暂停获取新文件夹；当前读取会完成。暂停时仍可停止。",
    "scan_paused": "已暂停 — {progress}",
    "scan_analysing": "文件夹读取完成，正在分析结果…",
    "column_drive_share": "占磁盘比例",
    "columns_reset": "重置列",
    "drive_share_tip": ("逻辑字节除以磁盘总容量。硬链接名称分别计算；不是分配或可回收空间。"
                        "容量未知或已过期时不显示比例。"),
    "action_recent_actions": "最近操作…",
    "action_recent_actions_tip": "查看保留的操作元数据，并导出隐藏个人路径的审计报告",
    "journal_time": "时间（UTC）",
    "journal_source": "原始路径",
    "journal_identity": "磁盘／文件标识",
    "journal_result": "结果",
    "journal_detail": "详情",
    "journal_destination": "回收站位置",
    "journal_reason_duplicates": "明确的重复文件决策",
    "journal_status_approved": "结果未知（只有确认记录）",
    "journal_status_moved": "已移到回收站",
    "journal_status_skipped": "已跳过",
    "journal_status_failed": "系统移动失败",
    "journal_reading": "正在读取保留的操作…",
    "journal_hint": ("最近 500 个操作；仅元数据，保留 90 天／50 MB。"
                     "只有确认记录的操作，其最终结果未知。记录回收站位置不保证可还原。"),
    "journal_summary": "显示 {count} 个操作；{invalid} 条损坏记录，{unavailable} 个无法读取的日志分段。",
    "journal_read_failed": "无法读取操作日志：{reason}",
    "journal_write_failed": "日志写入或保留管理失败，已尽可能停止剩余移动；最近操作可能不完整。\n\n{reason}",
    "trash_skip_journal": "无法记录已确认的操作，未移动任何项目",
    "journal_export": "导出隐藏个人路径的 CSV…",
    "journal_exported": "审计报告已保存，主目录前缀已隐藏。",
    "duplicate_folder_match": "{copy} = {original}（{size}，{files} 个文件；搜索快照相符）",
    "duplicate_folder_tip": "名称、大小、已验证哈希与空文件夹结构相同。仅供比较，不代表可清理。",
    "duplicates_keep_selected": "保留选中的副本",
    "duplicates_kept_name": "保留：{name}",
    "duplicates_kept_path": "保留副本：{path}。",
    "duplicates_choose_keeper": "选中多余副本前，请先选择这组要保留的副本。",
    "duplicates_group_blocked": "此组保持原样，须重新扫描：{reason}",
    "trash_skip_duplicate_choose": "请选择保留副本，再次审查此组",
    "trash_skip_duplicate_keep": "选到了保留副本，此组保持原样；请重新扫描",
    "trash_skip_duplicate_unverified": "此组没有已验证的哈希；请重新扫描并搜索",
    "trash_skip_duplicate_hard_links": "副本还有硬链接名称，此组保持原样；请重新扫描",
    "trash_skip_duplicate_content": "此组内容更改或无法重新哈希；请重新扫描并搜索",
    "menu_options": "选项",
    "action_cleanup_policy": "清理策略…",
    "action_cleanup_policy_tip": "启用规则、更改最低文件年龄，或排除清理建议的路径",
    "policy_enabled": "启用",
    "policy_age": "最低文件年龄（天）",
    "policy_age_for": "{rule} 的最低文件年龄",
    "policy_enabled_for": "启用 {rule}",
    "policy_hint": "策略只影响建议。须手动审查的规则仍默认不勾选。保存前请先预览。",
    "policy_exclusions": "不提出建议的路径或名称（每行一个；路径须为绝对路径）。不影响扫描。",
    "policy_preview": "预览更改",
    "policy_import": "导入策略 JSON…",
    "policy_preview_needed": "保存前请先预览当前设置。",
    "policy_preview_running": "正在比较候选数量与逻辑大小…",
    "policy_preview_result": "增加 {added} 个候选（{size}）；移除 {removed} 个候选（{removed_size}）。未移动任何项目。",
    "policy_preview_partial": "扫描不完整；未读取的候选与容量仍未知。",
    "policy_no_scan": "尚无完成的扫描，无法测量影响。设置将应用到以后的建议。",
    "policy_invalid": "策略无效。请使用支持的规则、是／否开关、0–36500 天，以及绝对路径或名称模式。",
    "policy_saved": "清理策略已保存，正在更新建议。",
    "policy_saved_invalid": "已保存的清理策略无效。请到“选项”审查策略；目前已停用清理建议。",
    "cleanup_review_manual": "手动审查",
    "cleanup_evidence": ("分类：{category}；最低文件年龄：{days} 天；风险：{risk}。"
                         "依据：{evidence} 重建／后果：{rebuild}"),
    "cleanup_category_temporary": "临时文件",
    "cleanup_category_cache": "下载／生成的缓存",
    "cleanup_category_application_state": "应用程序状态",
    "cleanup_category_build": "项目构建输出",
    "cleanup_category_downloads": "用户下载",
    "cleanup_risk_low": "较低风险；移动前仍须确认",
    "cleanup_risk_manual": "手动审查；默认不勾选",
    "cleanup_rebuild_temp": "先关闭使用它的应用程序；临时数据不一定能重建。",
    "cleanup_rebuild_browser_cache": "先关闭浏览器；缓存网页会重新下载。个人设置与书签不列入。",
    "cleanup_rebuild_thumbnails": "先关闭文件管理器；需要时会重新生成预览。",
    "cleanup_rebuild_crash_dumps": "保留需要的崩溃证据；过去的崩溃转储无法重建。",
    "cleanup_rebuild_package_caches": "用包管理工具重新下载，先确认网络可用。包存储库不列入。",
    "cleanup_rebuild_build_output": "核对项目内容与依赖锁定文件，再按项目文档重建。自行编写的文件应保留。",
    "cleanup_rebuild_old_installers": "保留离线或已无法获取的安装文件；仍可获取时向发布者重新下载。",
    "cleanup_rebuild_empty_folders": "应用程序可能仍需要空文件夹；先确认用途。",
    "trash_holder": "{name}（PID {pid}）",
    "trash_holders": "{path}：观察到 {programs} 打开此文件。请自行关闭相关程序后重试。",
    "trash_holders_limited": "{path}：无法完整查询进程；其他占用程序或失败原因可能未知。",
    "duplicates_savings": ("不重复分配估计 {allocated}；清空回收站后可回收的文件数据 "
                           "{recoverable}。"),
    "duplicates_estimating": ('正在估计不重复分配空间与可回收的文件数据…'),
    "duplicates_estimate_unavailable": ('无法获取分配估计。选择多余副本前请重新搜索。'),
    "duplicates_estimate_assumption": ("估计按您选择的保留副本，未决定的组保持未知。"
        "移动前会核对并完整重新哈希整组文件。有硬链接名称时不执行决策。"
        "共享区块与文件夹元数据仍未知，移到回收站不会释放空间。"),
    'capacity_details': '容量明细',
    'capacity_summary': '系统已用 {used}；可用 {free}；不重复分配估计 {unique}。{status}',
    'capacity_estimated': '整个磁盘的估计；无法归账的空间请见明细。',
    'capacity_folder_only': '仅扫描文件夹：无法核对整个磁盘。',
    'capacity_incomplete': '扫描不完整：无法核对整个磁盘。',
    'capacity_identity_unknown': '缺少文件标识信息：无法核对整个磁盘。',
    'capacity_capacity_unavailable': '无法获取系统容量：无法核对整个磁盘。',
    'capacity_root_changed': '扫描根目录已更改，请重新扫描后核对。',
    'capacity_allocation_exceeds_used': '分配估计超过系统已用空间，无法核对。',
    'capacity_coverage': '跳过 {skipped}；无法读取 {inaccessible}；尚未读取 {pending}',
    'capacity_bin_partial': '未完整识别或读取回收站，显示的大小仅限已读取的数据。',
    "capacity_explanation": ('已知文件分配包含读取到的回收站数据，硬链接的多个名称只算一次。其他挂载磁盘不计入。跳'
                             '过的数据与文件系统元数据是未知，而非 0。无法归账的空间可能包含无法读取的数据、元数'
                             '据、快照、共享区块及分配估计误差。系统容量与文件不是同时测量，扫描期间文件系统可能变'
                             '化。不可用的剩余空间是系统报告的总量、已用及可用量之差，不是测量得到的元数据总量。这'
                             '些数字是估计，仍待 NTFS、ext4 与 APFS 测试磁盘验证。'),
    'capacity_row_total': '系统总容量',
    'capacity_row_used': '系统已用空间',
    'capacity_row_free': '系统可用空间',
    'capacity_row_unavailable_free': '不可用的剩余空间',
    'capacity_row_named_allocated': '按名称计算的分配估计',
    'capacity_row_unique_allocated': '不重复分配估计',
    'capacity_row_hard_link_overcount': '已扣除的硬链接重复量',
    'capacity_row_recycle_bin_seen': '已读取的回收站分配（已包含）',
    'capacity_row_foreign_allocated_seen': '已读取的其他磁盘分配（不计入）',
    'capacity_row_unaccounted': '无法归账',
    'capacity_row_metadata_bytes': '文件系统元数据／保留空间',
    'capacity_row_omitted_bytes': '跳过的数据',
    'capacity_row_other_volumes_bytes': '其他挂载磁盘',
    'capacity_row_mounts': '跨磁盘挂载边界',
    'capacity_row_coverage': '扫描覆盖范围',
    "review_title": "审查清理建议",
    "review_details": "{path}\n规则：{rule}；保护状态：{protection}。{consequence}",
    "review_hint": "请检查每条路径与删除后果，取消勾选即可保留项目；继续后才会显示确认问题。",
    "review_select": "移动",
    "review_rule": "规则",
    "review_reason": "原因",
    "review_protection": "保护状态",
    "review_consequence": "删除后果",
    "review_manual": "手动选择",
    "review_manual_reason": "用户选择的项目，删除可能影响依赖的文件或程序。",
    "review_not_protected": "未匹配受保护路径",
    "review_open_folder": "打开所在文件夹",
    "review_continue": "继续到确认步骤",
    "review_estimating": "已选择 {count} 项，正在估计分配空间…",
    "review_summary": ("{count} 项；逻辑大小 {logical}；分配空间估计 {allocated}；清空回收站后可回收的文件数据 "
                       "{recoverable}；当前可用 {free}。共享区块与文件夹元数据仍未知，移到回收站不会立刻释放空间。"),
    "size_unknown": "未知",
    "trash_running": "正在重新核对并移动已批准的项目…点击停止可取消剩余项目。",
    "trash_batch_done": "已移动 {moved}、跳过 {skipped}、失败 {failed}；共 {size} 移到回收站。",
    "trash_skipped": "已跳过以下项目，请重新扫描文件夹后再试：\n{names}",
    "trash_skip_outside": "不在当前的扫描范围",
    "trash_skip_unverified": "没有经过核对的扫描身份",
    "trash_skip_incomplete": "扫描覆盖范围不完整",
    "trash_skip_missing": "项目或父文件夹已不存在",
    "trash_skip_unreadable": "无法读取项目",
    "trash_skip_link": "项目或父文件夹变成链接",
    "trash_skip_kind": "项目类型已变更",
    "trash_skip_identity": "项目已被替换",
    "trash_skip_changed": "大小、时间或文件夹内容已变更",
    "trash_skip_protected": "解析后路径的保护状态不同",
    "trash_skip_cancelled": "操作已取消",
    "coverage_complete": ("覆盖范围：{known} 个文件夹，已知 {size}；"
                          "跳过 {skipped}、无法读取 {denied}、未扫描 {pending}。"),
    "coverage_partial": ("覆盖范围不完整：{known} 个文件夹，已知 {size}；跳过 {skipped}、无法读取 {denied}、"
                         "未扫描 {pending}。跳过的字节数未知。清理前请重新扫描不完整的分支；已禁用全部选择。"),
    "problem_hidden_omitted": "已跳过隐藏项目，大小未知。",
    "problem_partial_folder": "部分项目无法读取，文件夹内容不完整。",
    "app_title": "FileTree",
    "about_text": "<h3>FileTree {version}</h3><p>看看磁盘空间都用到哪里去了。</p>"
                  "<p>MIT 许可证 · © 2026 JE-Chen</p>",
    "menu_file": "文件(&F)",
    "menu_export": "导出(&E)",
    "menu_view": "视图(&V)",
    "menu_unit": "大小单位(&U)",
    "menu_language": "语言(&L)",
    "menu_help": "帮助(&H)",
    "action_open": "选择文件夹…",
    "action_open_tip": "选一个文件夹或磁盘来扫描",
    "action_rescan": "重新扫描",
    "action_rescan_tip": "再扫描一次同一个文件夹，获取最新的变动",
    "action_stop": "停止",
    "action_stop_tip": "停止正在进行的扫描",
    "action_export_folders": "文件夹列表（CSV）…",
    "action_export_folders_tip": "把每个文件夹和它的大小保存为表格，可用 Excel 打开",
    "action_export_largest": "最大的文件（CSV）…",
    "action_export_largest_tip": "保存最大的文件列表",
    "action_export_json": "文件夹树（JSON）…",
    "action_export_json_tip": "保存文件夹树，供脚本或其他软件使用",
    "action_trash": "移到回收站",
    "action_trash_tip": "把选中的文件和文件夹移到回收站（会先询问）",
    "action_find": "搜索…",
    "action_find_tip": "在整个扫描结果里按名称找文件和文件夹",
    "action_quit": "退出",
    "action_quit_tip": "关闭 FileTree",
    "action_hidden": "包含隐藏文件",
    "action_exclusions": "扫描时跳过…",
    "action_exclusions_tip": "扫描时要跳过的文件夹与文件夹名称，例如 node_modules",
    "exclusions_title": "扫描时跳过",
    "exclusions_hint": ("扫描会跳过这些文件夹：它们仍会列出来，以灰字显示、大小为 0。"
                        "像 node_modules 或 *.cache 这样的名称会跳过所有同名的文件夹；"
                        "文件夹路径只跳过那一个文件夹。下一次扫描开始生效。"),
    "exclusions_add_name": "添加名称…",
    "exclusions_add_folder": "添加文件夹…",
    "exclusions_remove": "删除",
    "exclusions_name_prompt": "文件夹名称，可用 * 和 ?：",
    "exclusions_saved": "已保存 {count} 项排除；下一次扫描开始生效。",
    "tooltip_excluded": "{path}\n已跳过：它在“视图 → 扫描时跳过”的列表中",
    "action_hidden_tip": "把隐藏的文件和文件夹也算进去（下次扫描时生效）",
    "action_help": "使用说明",
    "action_help_tip": "FileTree 的简短使用说明",
    "action_about": "关于 FileTree",
    "action_about_tip": "版本与许可证",
    "app_title_admin": "FileTree（管理员）",
    "action_elevate": "以管理员身份重新启动",
    "action_elevate_tip": "用管理员权限重新启动 FileTree，才能读取每一个文件夹",
    "action_ask_admin": "启动时请求管理员权限",
    "action_ask_admin_tip": "FileTree 启动时由 Windows 询问权限，受保护的文件夹也能读取",
    "problems_hint": "有些文件夹需要管理员权限。以管理员身份重新启动 FileTree 就能一起读取。",
    "elevate_declined": "FileTree 仍以普通权限运行。",
    "unit_auto": "自动",
    "path_placeholder": "输入或粘贴文件夹路径，按 Enter 开始扫描",
    "choose_folder_title": "选择要扫描的文件夹",
    "welcome_title": "看看磁盘空间都用到哪里去了",
    "welcome_subtitle": "选一个文件夹或整个磁盘，FileTree 会把里面每个文件的大小加总，"
                        "先列出最大的文件夹和文件。",
    "welcome_choose": "选择文件夹…",
    "welcome_drives": "磁盘",
    "welcome_drive_tip": "扫描 {path}",
    "welcome_drive_free": "可用 {free}，共 {total}",
    "welcome_recent": "最近扫描过",
    "welcome_tip": "小技巧：也可以把文件夹从文件管理器拖到这个窗口。Windows 可粘贴绝对 UNC 共享路径"
                   "（\\\\server\\share），使用当前账户访问。扫描线程数可在选项调整；权限不足／断线的分支保持不完整，并非空文件夹。",
    "scan_starting": "准备中…",
    "scan_progress": "正在扫描… {folders} 个文件夹中的 {files} 个文件 · {size} · {time}",
    "scan_stop": "停止",
    "scan_stopping": "正在停止…",
    "scan_cancelled": "已停止扫描。",
    "scan_stopped_partial": "已停止扫描：结果只包含停止前读到的部分。",
    "scan_failed_title": "无法扫描",
    "scan_mount_changed": "挂载边界已变化或无法确认。请重新扫描后再使用扫描结果。",
    "scan_failed": "FileTree 无法读取 {path}。\n\n原因：{reason}",
    "not_a_folder": "{path} 不是存在的文件夹。",
    "duration_seconds": "{value} 秒",
    "duration_minutes": "{minutes} 分 {seconds} 秒",
    "summary": ("<b>{path}</b> — {size}（占用空间 {allocated}），共 {files} 个文件、{folders} 个文件夹"
                "（扫描用时 {time}）"),
    "summary_live": "<b>{path}</b> — 目前 {size}（占用空间 {allocated}），{files} 个文件、{folders} 个文件夹",
    "summary_partial": "<b>{path}</b> — {size}（占用空间 {allocated}），{files} 个文件、{folders} 个文件夹 · "
                       "<b>不完整</b>：扫描在 {time} 后停止",
    "tab_chart": "图表",
    "chart_treemap": "方块图",
    "treemap_levels": "层数",
    "treemap_levels_all": "全部",
    "treemap_colours": "颜色",
    "treemap_colours_type": "按文件类型",
    "treemap_colours_folder": "按文件夹",
    "chart_treemap_tip": "每个文件都是一个方块，大小代表占用的空间",
    "chart_bars": "条形图",
    "chart_sunburst": "旭日图",
    "chart_tree": "树状图",
    "chart_tree_tip": "文件夹层级：展开分支、Ctrl＋滚轮缩放、双击聚焦",
    "tree_orientation": "方向",
    "tree_orientation_horizontal": "从左到右",
    "tree_orientation_vertical": "从上到下",
    "tree_more": "其余 {count} 个文件夹 · {size}",
    "tree_unavailable": "未扫描",
    "chart_sunburst_tip": "当前文件夹在中心，每深一层就是外面一圈；点中心回上一级",
    "chart_bars_tip": "文件夹里每个项目一个条形，从大到小，附大小与比例",
    "bars_empty_folder": "这个文件夹是空的。",
    "bars_more": "其余 {count} 个：{size}",
    "tab_largest": "最大的文件",
    "scope_folder": "只看选中的文件夹",
    "scope_folder_named": "只看 {name}",
    "scope_folder_tip": "改为列出文件夹树中选中的文件夹（而不是整个扫描范围）的最大文件、类型与新旧",
    "tab_search": "搜索",
    "tab_changes": "变化",
    "action_compare": "与之前保存的扫描比较…",
    "action_compare_tip": "打开用“导出 → 文件夹树（JSON）”保存的扫描，看看之后哪里变大了",
    "compare_title": "与之前保存的扫描比较",
    "compare_failed": "这个文件不是 FileTree 保存的扫描：\n{reason}",
    "column_before": "之前",
    "column_now": "现在",
    "column_change": "变化",
    "changes_new": "新增",
    "changes_gone": "已不存在",
    "changes_whole_scan": "（扫描的文件夹）",
    "changes_stop": "结束比较",
    "changes_running": "比较中…",
    "changes_waiting": "扫描结束后会再比较。",
    "changes_unknown_time": "时间不明",
    "changes_summary": ("与 {path}（保存于 {when}）比较：之前 {before}，现在 {now}（{change}）；"
                        "{count} 个文件夹有变化。"),
    "tab_duplicates": "重复文件",
    "tab_cleanup": "清理",
    "cleanup_suggestions": "建议",
    "cleanup_select_all": "全部选中",
    "cleanup_select_group": "选中这一组",
    "cleanup_running": "正在查找可以清理的东西…",
    "cleanup_hint": "扫描完成后，这里会列出内容通常可以删掉的位置。",
    "cleanup_none": "这次扫描没有可以建议清理的东西。",
    "cleanup_summary": ("共 {groups} 组，逻辑大小 {size}。移到回收站前请先审查路径与分配空间；"
                        "移动不会立刻释放空间。"),
    "cleanup_group": "{title}：{count} 项，共 {size}",
    "cleanup_temp": "临时文件",
    "cleanup_temp_tip": "程序暂时留下的文件；仍在运行的程序可能还在使用其中一些。",
    "cleanup_browser_cache": "浏览器缓存",
    "cleanup_browser_cache_tip": "网页与图片的副本；浏览器需要时会重新下载。",
    "cleanup_thumbnails": "缩略图缓存",
    "cleanup_thumbnails_tip": "图片的小型预览；打开文件夹时会重新生成。",
    "cleanup_crash_dumps": "崩溃转储",
    "cleanup_crash_dumps_tip": "程序崩溃时保存的内存内容，只有报告崩溃时才用得到。",
    "cleanup_package_caches": "包下载缓存（pip、npm…）",
    "cleanup_package_caches_tip": "为下次安装保留的已下载包；需要时会重新下载。",
    "cleanup_build_output": "构建产物（可以重新构建）",
    "cleanup_build_output_tip": "项目安装的依赖与编译出来的文件；重新构建项目就会再生成。",
    "cleanup_old_installers": "下载文件夹里的安装包",
    "cleanup_old_installers_tip": "多半很久以前就运行过的安装程序；之后还要拿来安装的请留着。",
    "cleanup_empty_folders": "空文件夹",
    "cleanup_empty_folders_tip": "里面什么都没有，或只有其他空文件夹的文件夹。",
    "duplicates_min_size": "比较的最小文件",
    "duplicates_any_size": "任意大小",
    "duplicates_find": "查找重复文件",
    "duplicates_stop": "停止",
    "duplicates_select_extra": "选中多余的副本",
    "duplicates_select_extra_tip": "选中已决定保留副本且核对成功组的多余副本，再按 Delete",
    "duplicates_hint": ("在整个扫描范围内查找内容相同的文件。只会读取大小相同的文件，"
                        "但读取需要时间，所以除非选了较小的大小，否则会跳过小文件。"),
    "duplicates_starting": "正在查找大小相同的文件…",
    "duplicates_running": "已读取 {files} / {total} 个文件（{read} / {bytes}）…",
    "duplicates_stopped": "搜索已停止。",
    "duplicates_none": "没有找到重复的文件。",
    "duplicates_summary": ('{groups} 组重复文件：多余副本的逻辑大小共 {extra}。'),
    "duplicates_limited": "只列出多余空间最大的 {shown} 组。",
    "duplicates_skipped": "有 {count} 个文件无法读取。",
    "duplicates_group": ('{count} 份 × {size}：多余副本的逻辑大小 {extra}。'),
    "search_placeholder": "名称的一部分，或模式：backup、*.mp4、*.iso;*.zip",
    "search_hint": "输入名称的一部分或含 * 和 ? 的模式、选择条件，或两者一起，在整个扫描结果里找文件和文件夹。",
    "search_running": "搜索中…",
    "search_larger": "大于",
    "search_smaller": "小于",
    "search_no_limit": "不限",
    "search_changed": "修改时间",
    "search_changed_any": "不限",
    "search_changed_week": "最近一周内",
    "search_changed_month": "最近一个月内",
    "search_changed_year": "最近一年内",
    "search_changed_stale_year": "超过一年没动",
    "search_changed_stale_2y": "超过两年没动",
    "search_changed_stale_5y": "超过五年没动",
    "search_type": "类型",
    "search_type_any": "不限类型",
    "search_show": "显示",
    "search_kind_any": "文件和文件夹",
    "search_kind_files": "只有文件",
    "search_kind_folders": "只有文件夹",
    "search_saved": "已保存的搜索",
    "search_saved_none": "（无）",
    "search_save": "保存…",
    "search_delete": "删除",
    "search_save_title": "保存这个搜索",
    "search_save_prompt": "名称：",
    "search_none": "没有匹配的项目。",
    "search_summary": "{count} 个匹配，共 {size}。",
    "search_limited": "只列出最大的 {shown} 个。",
    "tab_types": "文件类型",
    "tab_age": "文件新旧",
    "column_age": "最后修改",
    "age_month": "一个月内",
    "age_half_year": "1–6 个月前",
    "age_year": "6–12 个月前",
    "age_two_years": "1–2 年前",
    "age_older": "超过 2 年",
    "largest_focus": "只显示：{what}",
    "largest_show_all": "显示全部",
    "list_files_tip": "双击一行，列出它最大的文件",
    "tab_problems": "无法读取",
    "tab_problems_count": "无法读取（{count}）",
    "column_name": "名称",
    "column_size": "大小",
    "column_allocated": "占用空间",
    "column_share": "占上级比例",
    "column_share_total": "占总量比例",
    "column_files": "文件数",
    "column_folders": "文件夹数",
    "column_modified": "修改时间",
    "column_folder": "所在文件夹",
    "column_extension": "扩展名",
    "column_type": "类型",
    "column_path": "路径",
    "column_problem": "原因",
    "problem_access_denied": "拒绝访问",
    "problem_not_found": "已经不存在",
    "problem_path_too_long": "路径太长",
    "problem_not_scanned": "没有扫描到：扫描在读到这里之前就停止了",
    "no_extension": "（没有扩展名）",
    "tooltip_unreadable": "{path}\n无法读取：{reason}",
    "tooltip_link": "{path}\n链接：只列出，不会进入计算",
    "tooltip_not_scanned": "{path}\n没有扫描到：扫描在读到这里之前就停止了",
    "treemap_empty": "没有可以显示的内容",
    "treemap_up": "↑ 上一级",
    "treemap_up_tip": "显示上一级文件夹",
    "treemap_tooltip": "<b>{name}</b><br>{size}（占当前画面的 {share}）<br>{path}",
    "treemap_more": "其余 {count} 个",
    "treemap_more_tooltip": "<b>{name} 里其余 {count} 个较小的项目</b>，每个都小到画不出来<br>"
                            "{size}（占当前画面的 {share}）",
    "treemap_more_open": "双击可以单独显示这个文件夹",
    "largest_filter": "按名称或文件夹筛选…",
    "types_all": "所有类型",
    "category_images": "图片",
    "category_video": "视频",
    "category_audio": "音乐与音频",
    "category_documents": "文档",
    "category_archives": "压缩包与镜像",
    "category_code": "代码与数据",
    "category_programs": "应用程序",
    "category_other": "其他",
    "status_selected": "{name}：{size}（占所在文件夹的 {share}）",
    "status_selected_root": "{name}：{size}",
    "menu_open_item": "打开",
    "menu_reveal": "在文件管理器中显示",
    "menu_copy_path": "复制路径",
    "menu_show_chart": "在图表中显示",
    "menu_scan_here": "只扫描这个文件夹",
    "menu_rescan_here": "重新扫描这个文件夹",
    "rescan_done": "已重新扫描 {name}：{before} → {after}",
    "trash_confirm_title": "移到回收站",
    "protected_title": "系统或程序文件夹",
    "protected_question": ("其中 {count} 个是系统或程序的文件夹，移走可能让系统或程序无法正常运行："
                           "\n\n{names}\n\n仍要移走吗？"),
    "protected_system": "操作系统的一部分",
    "protected_programs": "已安装的程序",
    "protected_settings": "程序的设置与数据",
    "protected_profile": "用户的个人文件夹",
    "trash_confirm": "要把“{name}”（{size}）移到回收站吗？\n\n之后仍可以从回收站还原。",
    "trash_failed": "无法把“{name}”移到回收站，可能正在使用或是只读。",
    "trash_done": "已把“{name}”移到回收站，释放 {size}。",
    "action_trash_many": "把 {count} 个项目移到回收站",
    "trash_confirm_many": ("要把这 {count} 个项目（共 {size}）移到回收站吗？\n\n{names}\n\n"
                           "之后仍可以从回收站还原。"),
    "trash_more": "……还有 {count} 个",
    "trash_failed_many": "有 {count} 个项目无法移到回收站，可能正在使用或是只读：\n\n{names}",
    "trash_done_many": "已把 {count} 个项目移到回收站，释放 {size}。",
    "status_selected_many": "已选中 {count} 个项目：{size}",
    "export_title": "导出",
    "export_running": "正在保存到 {path}…",
    "csv_filter": "CSV 文件 (*.csv)",
    "json_filter": "JSON 文件 (*.json)",
    "export_done": "已把 {count} 行保存到 {path}",
    "export_failed": "无法保存文件。\n\n原因：{reason}",
    "help_title": "FileTree 使用说明",
    "help_html": _cjk("""
<h2>三个步骤就会用</h2>
<ol>
<li><b>选择要扫描的地方。</b>点击<i>选择文件夹…</i>或其中一个磁盘，把文件夹拖到窗口上，
或在上方的输入框输入路径后按 Enter。</li>
<li><b>边扫边看。</b>文件夹树会立刻出现，FileTree 一边加总，最大的文件夹一边往上排；
最大的文件与文件类型在扫描结束时补上。
随时可以点<i>停止</i>（或按 Esc）：已经读到的部分会留在画面上，并标示为不完整。</li>
<li><b>找出占空间的东西。</b>最大的文件夹排在最上面，点文件夹旁的箭头就能看里面的内容。</li>
</ol>
<h2>看懂结果</h2>
<ul>
<li><b>文件夹树</b>（左边）：每个文件夹或文件的大小、<i>占用空间</i>（实际占用的磁盘空间：按整个簇计算，
通常比大小多一点；压缩文件较少，只在云端的文件是 0）、<i>占上级比例</i>条（它占上一级文件夹多少空间）、
里面有几个文件和文件夹，以及里面最近一次变动的时间。点列标题可以按该列排序。</li>
<li><b>图表</b>：在选项卡角落切换同一个文件夹的四种图（一开始是方块图，之后会记住你选的）。<i>方块图</i>把每个文件画成一个方块，文件越大、方块越大，
每个文件夹顶部有写着名称和大小的标题栏；
文件夹里小到看不见的文件会合成一个灰色斜线方块（<i>其余 12 个</i>），双击它可以单独显示那个文件夹。
<i>层数</i>决定要画几层，<i>颜色</i>可以按文件类型（图例在下方）或按最上层的文件夹上色。
<i>条形图</i>给文件夹里每个项目画一个条形，由大到小，附大小与比例。
<i>旭日图</i>把当前文件夹放在中心，每深一层就是外面一圈，点中心回上一级。
<i>树状图</i>画出可展开的文件夹卡片，点加号或“其余文件夹”显示更多；可切换方向、
按 Ctrl＋滚轮缩放并用滚动条移动。
单击可以在文件夹树中找到它，双击文件夹可以进入，点<i>上一级</i>回去。</li>
<li><b>最大的文件</b>：整个扫描范围内最大的 1,000 个文件。在筛选框输入文字可以缩小列表，
双击某一行就会在文件夹树中找到那个文件。</li>
<li><b>搜索</b>（Ctrl+F）：整个扫描范围内，名称含有输入文字的文件和文件夹。
<code>*.mp4</code> 这类模式要匹配完整名称；多个模式用 <code>;</code> 分开（<code>*.iso;*.zip</code>）。
搜索框下方的条件（大小、修改时间、文件类型、文件或文件夹）可以缩小范围，也可以单独搜索；
<i>保存…</i>可以把搜索取名保存起来。会列出最大的 1,000 个匹配项目，并显示全部匹配项目的数量和总大小。</li>
<li><b>清理 → 建议</b>：每次扫描后列出内容通常可以删掉的位置，每种一组
（临时文件、缓存、崩溃转储、可以重新构建的构建产物、下载文件夹里的旧安装包、空文件夹）；
鼠标停在组名上可以看删掉它的影响，再点<i>选中这一组</i>或<i>全部选中</i>，然后按 Delete。</li>
<li><b>清理 → 重复文件</b>：点<i>查找重复文件</i>，把内容相同的文件分组。只会读取大小相同的文件；因为读取需要时间，
除非选了较小的大小，否则会跳过 1 MB 以下的文件。每一组从旧到新列出副本；<i>选中多余的副本</i>会选中最旧那份以外的全部，
再按 Delete 就会移到回收站。</li>
<li><b>文件类型</b>：各种文件按扩展名各占多少空间；在表格上方的列表选一种类型，就只显示那一类；
双击一行，会列出那种文件里最大的几个。</li>
<li><b>文件新旧</b>：一个月内、1–6 个月前……一直到超过 2 年前最后修改的文件各占多少空间。
旧数据常常就是可以归档或删除的东西；双击一行，会列出那一段里最大的文件。</li>
<li><b>无法读取</b>：FileTree 没有权限读取的文件夹，里面的内容不会算进去。</li>
</ul>
<h2>释放空间</h2>
<p>在任何项目上点右键，可以<i>打开</i>、<i>在文件管理器中显示</i>、<i>复制路径</i>、<i>在方块图中显示</i>、
<i>重新扫描这个文件夹</i>（在 FileTree 以外改过东西之后用，其余结果不变）、
<i>只扫描这个文件夹</i>，或<i>移到回收站</i>。
要一次移走好几个项目，在文件夹树、<i>最大的文件</i>或<i>搜索</i>列表里用 Ctrl+单击或 Shift+单击选中，
只会询问一次，并列出它们和总大小。
FileTree 不会永久删除任何东西：每次都会先询问，
移走的东西都能从回收站（macOS 与 Linux 是“废纸篓”）还原。数字会立刻更新，不必重新扫描。
系统与程序的文件夹会说明原因并多问一次；临时文件夹与缓存不会。</p>
<h2>看看哪里变大了</h2>
<p>用<i>文件 → 导出 → 文件夹树（JSON）</i>把扫描保存起来。之后重新扫描，选<i>文件 → 与之前保存的扫描比较…</i>
打开那个文件，<b>变化</b>选项卡就会列出每个有变化的文件夹之前和现在的大小，变大最多的排在最前面
（<i>新增</i>与<i>已不存在</i>标示新出现或消失的文件夹）。在点<i>结束比较</i>之前，每次重新扫描都会继续比较。</p>
<h2>键盘快捷键</h2>
<table cellpadding="3">
<tr><td><b>Ctrl+O</b></td><td>选择文件夹</td></tr>
<tr><td><b>F5</b></td><td>重新扫描</td></tr>
<tr><td><b>Esc</b></td><td>停止扫描</td></tr>
<tr><td><b>Ctrl+F</b></td><td>按名称搜索</td></tr>
<tr><td><b>Delete</b></td><td>把选中的项目（可以好几个）移到回收站</td></tr>
<tr><td><b>F1</b></td><td>这份说明</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>退出</td></tr>
</table>
<p>在 macOS 上请用 ⌘ 代替 Ctrl（⌘R 是重新扫描）。</p>
<h2>小知识</h2>
<ul>
<li>大小是文件的实际大小，按二进制单位计算（1 KB = 1,024 字节），和 Windows 资源管理器相同；
可以在<i>视图 → 大小单位</i>改用固定的单位。</li>
<li>快捷方式与链接（符号链接、目录联接）会列出来，但不会进入计算，所以不会重复计算。</li>
<li>在 Windows 上，FileTree 启动时会像 TreeSize 一样请求管理员权限，受保护的文件夹也能读取。
拒绝的话它照常以普通权限运行，读不到的文件夹列在<i>无法读取</i>标签页，那里有<i>以管理员身份重新启动</i>按钮。
不想每次被问，可以关掉<i>视图 → 启动时请求管理员权限</i>。</li>
<li><i>最大的文件</i>、<i>文件类型</i>与<i>文件新旧</i>默认统计整个扫描范围；
点这几个选项卡右上角的<i>只看选中的文件夹</i>，就会改为跟着文件夹树中选中的文件夹。</li>
<li>默认会计算隐藏文件；关掉<i>视图 → 包含隐藏文件</i>，下次扫描就不会算进去。</li>
<li>要让某些文件夹每次都不扫描，把它们加进<i>视图 → 扫描时跳过</i>：
像 <code>node_modules</code> 这样的名称会跳过所有同名的文件夹，路径只跳过那一个文件夹。
跳过的文件夹会以灰字列出，大小为 0。</li>
<li>用<i>文件 → 导出</i>保存结果：CSV 可用 Excel 打开，JSON 供脚本使用。</li>
</ul>
"""),
}

STRINGS: dict[str, dict[str, str]] = {"en": EN, "zh-TW": ZH_TW, "zh-CN": ZH_CN}
