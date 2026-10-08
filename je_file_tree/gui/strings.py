"""Every text the window shows, per language (see ``je_file_tree.gui.i18n``)."""

from __future__ import annotations


def _cjk(html: str) -> str:
    """Join the source lines of Chinese HTML: a line break there would show up as a space between characters."""
    return "".join(line.strip() for line in html.splitlines())


EN: dict[str, str] = {
    'recurring_review': 'Rescan and review current candidates…',
    'recurring_validating': 'Validating the dated proposal against the entire fresh scan and current source metadata…',
    'recurring_refused': ('Proposal cannot continue: {status}. '
                         'Run a new scheduled scan to prepare current observations.'),
    'recurring_tabs_full': 'All sixteen scan tabs are in use. Close a tab before reviewing a scheduled proposal.',
    'trash_skip_proposal_changed': ('Source paths or proposal settings/receipt changed or could not be verified; '
                                    'source kept.'),
    'trash_skip_proposal_expired': 'The scheduled proposal expired before this move; source kept.',
    'action_recurring': 'Scheduled scan proposals…',
    'action_recurring_tip': 'View dated scheduled observations and their coverage; no automatic clean-up.',
    'recurring_rule': 'Rule',
    'recurring_unknown': 'Unknown',
    'recurring_new': 'New junk since last scan',
    'recurring_current': 'Current candidates',
    'recurring_growth': 'Largest new growth',
    'recurring_empty': 'No scheduled report in this session. Enable background monitoring and select scan folders.',
    'recurring_hint': ('Observations only; nothing is moved automatically. Up to 100 rows per list. '
                       'Growth is logical bytes, not recoverable space. Unknown comparisons do not prove no new junk. '
                       'Reports appear after a scheduled scan in this session; baselines are kept in local history. '
                       'Review rescans in a new tab and uses the ordinary queue and confirmations.'),
    'recurring_summary': ('Prepared: {prepared}\nPrevious baseline: {previous}\nExpires: {expires}\n'
                          'Candidates shown: {retained} / {total}; coverage: {coverage}; comparison: {comparison}\n'
                          'Status: {status}'),
    'recurring_status_current': 'Observed; fresh source validation required before review',
    'recurring_status_expired': 'Expired (including a missed schedule or clock rollback)',
    'recurring_status_schedule_changed': 'Schedule changed or disabled',
    'recurring_status_stale_scan': 'Scan receipt changed or unavailable',
    'recurring_status_rule_changed': 'Clean-up rules changed',
    'recurring_status_incomplete': 'Incomplete coverage or unknown identity',
    'recurring_status_paths_changed': 'Source paths changed',
    'recurring_status_unavailable': 'Settings or receipt could not be verified',
    'recurring_prepare_failed': 'History saved; scheduled proposal unavailable: {detail}',
    'workspace_new': 'New scan tab',
    'workspace_new_tip': 'Open an independent scan tab (Ctrl+T); close the current tab with Ctrl+W.',
    'workspace_close': 'Close scan tab',
    'workspace_empty': 'Choose a folder',
    'trash_skip_recycle_unverified': (
        'Windows recycling settings, complete source size or native bin metadata could not be verified; source kept.'
    ),
    'trash_skip_recycle_disabled': (
        'Windows recycling is disabled for this scope; source kept.'
    ),
    'trash_skip_recycle_capacity': (
        'Selection and current bin contents exceed the observed recycling limit with headroom; source kept.'
    ),
    'action_check_updates': 'Check for updates daily',
    'action_background_monitor': 'Background monitor…',
    'action_background_monitor_tip': 'Opt in to tray notifications and gentle scheduled folder-history scans.',
    'background_enable': 'Enable background monitoring',
    'background_startup': 'Start this monitor when I sign in',
    'background_startup_hint': ('Separate opt-in for this user only. Uncheck to remove FileTree’s owned login entry. '
                                'Applies to future logins; does not start another copy or close this monitor.'),
    'background_startup_requires_monitor': 'Enable background monitoring before adding a login entry.',
    'background_startup_error': 'Login startup could not be changed: {detail}',
    'background_hint': ('Off by default. Closing keeps FileTree in the available system tray; Quit ends it. '
                        'Check OS available capacity each minute and scan only chosen folders gently. '
                        'Scheduled scans require enabled local history. '
                        'No automatic clean-up or startup registration.'),
    'background_threshold': 'Warn below available space',
    'background_interval': 'Scan interval (hours)',
    'background_roots': 'Scheduled scan folders',
    'background_add': 'Add scan folder…',
    'background_remove': 'Remove selected folders',
    'background_limit': 'Choose at most 32 scheduled folders.',
    'background_show': 'Show FileTree',
    'background_off': 'Background monitoring is off',
    'background_ready': 'Background monitoring is on',
    'background_no_tray': 'System tray unavailable; FileTree stays visible and background monitoring is paused.',
    'background_error': 'Background monitoring: {detail}',
    'background_history_disabled': 'Enable local scan history before scheduled scans can run.',
    'background_scanning': 'Scheduled scan: {detail}',
    'background_saved': 'Scheduled history saved: {detail}',
    'background_saved_partial': 'Scheduled history saved with unread scopes: {detail}',
    'background_canceled': 'Scheduled scan canceled; partial source coverage was not saved: {detail}',
    'background_warning': '{detail}',
    'background_low_space': 'Low available space on {root}: {free} ({percent}%)',
    'action_follow_changes': 'Follow changes',
    'action_follow_changes_tip': ('Off by default. Refresh changed folders on Windows/Linux; '
                                  'reconcile the root every five minutes.'),
    'follow_waiting': 'Follow changes: waiting for a scan',
    'follow_starting': 'Follow changes: starting…',
    'follow_active': 'Following changes ({detail})',
    'follow_failed': 'Follow changes stopped: {detail}',
    'follow_incomplete': 'Follow changes needs a complete physical scan',
    'follow_unsupported': 'Follow changes supports Windows and Linux',
    'follow_backend_usn': 'NTFS USN',
    'follow_backend_directory_changes': 'directory notifications',
    'follow_backend_inotify': 'inotify',
    'action_check_updates_tip': 'Ask PyPI over HTTPS at most once a day; notice only, with no installation.',
    'update_available': 'FileTree {version} is available',
    'multi_roots': 'Multiple roots',
    'action_multi_scan': 'Scan several folders…',
    'action_multi_scan_tip': 'Review explicit folders in one combined scan.',
    'multi_choose': 'Scan several folders',
    'multi_add': 'Add folder…',
    'multi_remove': 'Remove selected roots',
    'scan_all_drives': 'Scan all drives',
    'multi_hint': ('Combine up to 256 selected roots. Results are read-only; scan a source separately '
                   'for file operations. OS capacity stays per volume.'),
    'capacity_multiple_roots': 'Multiple roots: OS capacity is per volume.',
    'vc_title': (
        'Compact selected VHD…'
    ),
    'vc_apply': (
        'Review and compact…'
    ),
    'vc_hint': (
        'Only a detached dynamic VHD/VHDX on fixed local NTFS is eligible. Read-only pr'
        'eparation checks identity, headers and conservative WSL/Docker runtime state. '
        'Guest usage and guaranteed recovery stay unknown. Close this review before usi'
        'ng FileTree’s existing administrator restart for a permission error; a new sca'
        'n and approval are required.'
    ),
    'vc_preparing': (
        'Checking the captured disk and stopped runtime…'
    ),
    'vc_ready': (
        'Review the exact source and confirm its machine stays stopped.'
    ),
    'vc_details': (
        'Source: {path}\nName: {source}\nDisk UUID: {identifier}\nVirtual capacity: {capac'
        'ity}\nProvider bytes: {physical}\n\nBackend: Windows CompactVirtualDisk, detached'
        ' zero-block compaction. No guest attachment, launch or shutdown; guest-used by'
        'tes are unknown.'
    ),
    'vc_confirm': (
        'Compact this exact backing file?\n\n{path}\n\nChoosing Yes confirms that its ownin'
        'g machine is stopped and will stay stopped throughout the operation. Fresh run'
        'time and identity checks still apply. Native zero-block compaction may recover'
        ' nothing or change metadata before a later error. There is no automatic Undo. '
        'Guest usage/free-space recovery are unknown. Stop/close waits for an active na'
        'tive call and reports its actual outcome. Approval is recorded before any writ'
        'able open.'
    ),
    'vc_running': (
        'Rechecking and compacting the reviewed disk…'
    ),
    'vc_waiting': (
        'Waiting for the current native call; its actual result will be reported…'
    ),
    'vc_done': (
        '{status}\nObserved backing allocation: {before} → {after}. This is not guarante'
        'ed OS free recovery. Guest usage remains unknown; attempted writes require a f'
        'resh scan.'
    ),
    'vc_failed': (
        'Compaction: {reason}'
    ),
    'vc_not_compacted': (
        'Not compacted'
    ),
    'vc_stale': (
        'A writable operation was attempted. Recorded observations are stale; close thi'
        's window for a fresh scan before another review.'
    ),
    'vc_audit_refused': (
        'Approval could not be recorded; no native operation was started'
    ),
    'vc_audit_detail': (
        'Backing allocation before: {before}; after: {after}. Error: {error}'
    ),
    'journal_status_compacted': (
        'Native compaction completed'
    ),
    'journal_reason_compaction': (
        'Explicit virtual-disk compaction'
    ),
    'vd_hint': (
        'Read-only inventory; provider labels are location hints. Backing allocation, p'
        'rovider bytes and virtual capacity are separate; guest usage stays unknown. He'
        'ader queries and compaction reviews are explicit. Unsupported formats remain v'
        'isible; no guest starts, stops or mounts automatically.'
    ),
    "vd_name": 'Disk name',
    "vd_source": 'Source',
    'vd_issue_unverified': 'Unverified identity',
    'vd_issue_unavailable': 'Linked, cloud or unavailable',
    'vd_issue_changed': 'File changed',
    'vd_issue_duplicate_hard_links': 'Multiple hard-link names',
    "action_virtual_disks_tip": 'Review recorded virtual disks and explicitly query read-only native VHD information',
    'action_virtual_disks': 'Virtual disks…',
    'vd_kind': 'Format',
    'vd_length': 'Backing-file length',
    'vd_allocation': 'Recorded allocation',
    'vd_capacity': 'Virtual capacity',
    'vd_physical': 'Provider physical bytes',
    'vd_guest': 'Guest used',
    'vd_source_scan': 'Recorded scan',
    'vd_source_wsl': 'WSL registration',
    'vd_source_docker': 'Docker default (inferred)',
    'vd_unsupported': 'Native VHD tools unsupported',
    'vd_not_queried': 'Native header not queried',
    'vd_fixed': 'Fixed',
    'vd_dynamic': 'Dynamic',
    'vd_differencing': 'Differencing',
    'vd_loaded': 'Mounted/in use',
    'vd_detached': 'Not loaded (observation)',
    'vd_inspect': 'Query selected VHD header',
    'vd_select': 'Show recorded entry',
    'vd_reading': 'Discovering virtual backing files…',
    'vd_querying': 'Reading native header: {path}',
    'vd_summary': 'Showing {shown} of {count}; {issues} issues/omissions. Coverage: {coverage}.',
    'vd_failed': 'Virtual-disk information: {reason}',
    'vd_information_hint': (
        'Native observations do not authorize compaction or prove a stopped machine. Provider '
         'physical bytes are not guest-used bytes. Disk UUID is in the row tooltip.'
    ),
    "link_summary": "{total} extra copies: {ready} ready, {skipped} refused.",
    "link_title": "Link the extra copies…",
    "link_hint": (
        "Review exact duplicate files with explicitly kept copies (up to 1,000 extras). "
        "Protected, changed, cloud, linked and unsupported files are refused. No guaranteed freed-space amount."
    ),
    "link_copy": "Extra copy to replace",
    "link_keeper": "Kept file",
    "link_apply": "Link reviewed extra copies…",
    "link_confirm": (
        "Replace {count} extra copies with hard links? {skipped} refused rows will be skipped.\n\n"
        "Old data is not kept in Trash. Every linked name shares future content, metadata and "
        "security/permission changes. This has no automatic Undo. Failures or cancellation may retain "
        "published links and old-copy backups at the paths shown. Stop/close waits for the current native call. "
        "Complete data and named streams are rechecked; concurrent changes remain observational. "
        "Review every pair and refusal in Details."
    ),
    "link_progress": "Rechecking/linking: {path}",
    "link_done": (
        "Hard links: {linked} published, {other} not linked. "
        "Rescan to refresh observations; recovered capacity is unknown."
    ),
    "link_not_linked": "Not linked",
    "link_retained": "Retained paths:\n{paths}",
    "journal_status_linked": "Hard link published",
    "journal_reason_duplicate_links": "Explicit duplicate hard-link replacement",
    "undo_button": "Undo ({count})",
    "undo_running": "Restoring captured Trash items…",
    "undo_done": "Undo: {restored} restored, {failed} failed",
    "undo_title": "Trash restoration",
    "undo_result": "{status}\nOriginal: {source}\nTrash: {trashed}\n{reason}",
    "undo_unavailable": "Undo unavailable for some items: {reason}",
    "journal_status_restored": "Restored from Trash",
    "journal_reason_undo": "Explicit Trash undo",
    "menu_move_drive": "Move to another drive…",
    "copy_hint": ("Choose an existing folder on another drive. Originals stay until a separate Trash confirmation. "
                  "Verify file counts, lengths and SHA-256 below 64 MiB; larger payloads are length-only. "
                  "Failures/cancellation retain partial destinations. Up to 1,000 selected folders."),
    "copy_apply": "Copy and verify reviewed folders…",
    "copy_redirect": "After successful Trash, leave a junction/symbolic link at each original path",
    "copy_finish": "Move verified originals to Recycle Bin…",
    "copy_confirm": ("Copy and verify {count} reviewed folders? {skipped} other pairs will be skipped. "
                     "Existing names are never overwritten. Originals remain until a separate Trash approval; "
                     "partial destinations remain on errors or cancellation."),
    "copy_progress": "Copying/verifying {path}: {done} / {total} files in this folder",
    "copy_done": "Verified copies: {copied}; skipped: {skipped}; failed: {failed}. Originals retained.",
    "copy_partial": "Retained partial destination: {path}",
    "copy_trash_confirm": ("The copied folders will be verified again immediately before each original moves to "
                           "Trash. Counts/lengths are compared; payloads below 64 MiB are SHA-256 checked. "
                           "Larger payloads are length-only. A failed check stops the remaining batch. "
                           "Concurrent changes are not transactional."),
    "copy_errors": "Copy verification or original-path redirect failed. Review the actual paths in Details.",
    "copy_verify_failed": "Original retained: {source}\nCopy: {destination}\nVerification refused: {reason}",
    "copy_redirect_failed": ("Original moved to Trash: {source}\nVerified copy retained: {destination}\n"
                             "Redirect failed (an empty original-path directory may remain): {reason}"),
    "namespace_reason_same_volume": "Same volume; use Move to folder",
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
    'recurring_review': '重新掃描並審查目前候選…',
    'recurring_validating': '正在比對具日期建議、完整的新掃描與目前來源中繼資料…',
    'recurring_refused': '無法繼續此建議：{status}。請執行新的排程掃描，以產生目前的觀察資料。',
    'recurring_tabs_full': '十六個掃描分頁皆在使用中。請先關閉一個分頁，再審查排程建議。',
    'trash_skip_proposal_changed': '來源路徑、建議設定或掃描紀錄已變更或無法驗證；保留來源。',
    'trash_skip_proposal_expired': '移動前排程建議已到期；保留來源。',
    'action_recurring': '排程掃描建議…',
    'action_recurring_tip': '查看排程觀察的日期與涵蓋範圍；不會自動清理。',
    'recurring_rule': '規則',
    'recurring_unknown': '未知',
    'recurring_new': '上次掃描後新增的垃圾候選',
    'recurring_current': '目前的清理候選',
    'recurring_growth': '容量成長最多的資料夾',
    'recurring_empty': '本次執行尚無排程報告。請啟用背景監控並選擇掃描資料夾。',
    'recurring_hint': ('僅供查看，不會自動移動檔案。每份清單最多顯示 100 筆。'
                       '成長量是邏輯位元組，不代表可回收空間。比較未知不代表沒有新增垃圾。'
                       '報告會在本次執行的排程掃描後出現；基準資料儲存在本機掃描歷史。'
                       '審查會在新分頁重新掃描，再進入一般審查佇列與確認流程。'),
    'recurring_summary': ('產生時間：{prepared}\n上次基準：{previous}\n到期時間：{expires}\n'
                          '顯示候選：{retained} / {total}；涵蓋範圍：{coverage}；比較：{comparison}\n'
                          '狀態：{status}'),
    'recurring_status_current': '已觀察；審查前仍須重新驗證來源',
    'recurring_status_expired': '已到期（包含錯過排程或時鐘倒退）',
    'recurring_status_schedule_changed': '排程已變更或停用',
    'recurring_status_stale_scan': '掃描紀錄已變更或無法取得',
    'recurring_status_rule_changed': '清理規則已變更',
    'recurring_status_incomplete': '涵蓋範圍不完整或檔案識別未知',
    'recurring_status_paths_changed': '來源路徑已變更',
    'recurring_status_unavailable': '無法驗證設定或掃描紀錄',
    'recurring_prepare_failed': '歷史已儲存；無法產生排程建議：{detail}',
    'workspace_new': '新增掃描分頁',
    'workspace_new_tip': '開啟獨立的掃描分頁（Ctrl+T）；以 Ctrl+W 關閉目前分頁。',
    'workspace_close': '關閉掃描分頁',
    'workspace_empty': '選擇資料夾',
    'trash_skip_recycle_unverified': (
        '無法核對 Windows 回收設定、完整來源大小或原生回收筒資料；已保留來源。'
    ),
    'trash_skip_recycle_disabled': (
        '此範圍的 Windows 回收功能已停用；已保留來源。'
    ),
    'trash_skip_recycle_capacity': (
        '選取項目及目前回收筒內容超過觀察到的回收上限與預留空間；已保留來源。'
    ),
    'action_check_updates': '每天檢查更新',
    'action_background_monitor': '背景監視器…',
    'action_background_monitor_tip': '選擇啟用系統匣通知與低優先順序的排程資料夾歷史掃描。',
    'background_enable': '啟用背景監視',
    'background_startup': '登入時啟動此監視器',
    'background_startup_hint': ('需另外選擇啟用，僅適用目前使用者。取消勾選會移除 FileTree 擁有的登入項目。'
                                '適用下次登入，不會啟動另一個程式或結束目前監視器。'),
    'background_startup_requires_monitor': '請先啟用背景監視，再新增登入項目。',
    'background_startup_error': '無法變更登入啟動：{detail}',
    'background_hint': ('預設關閉。系統匣可用時，關閉視窗會保留 FileTree，選擇「結束」才退出。'
                        '每分鐘查詢系統可用容量，只低優先順序掃描明確選取的資料夾。'
                        '排程掃描需要啟用本機歷史記錄，不自動清理或註冊開機啟動。'),
    'background_threshold': '可用空間低於此值時通知',
    'background_interval': '掃描間隔（小時）',
    'background_roots': '排程掃描資料夾',
    'background_add': '新增掃描資料夾…',
    'background_remove': '移除選取資料夾',
    'background_limit': '最多選取 32 個排程資料夾。',
    'background_show': '顯示 FileTree',
    'background_off': '背景監視已關閉',
    'background_ready': '背景監視已啟用',
    'background_no_tray': '系統匣無法使用；FileTree 保持顯示，背景監視暫停。',
    'background_error': '背景監視：{detail}',
    'background_history_disabled': '請先啟用本機掃描歷史記錄，才能執行排程掃描。',
    'background_scanning': '排程掃描：{detail}',
    'background_saved': '已儲存排程歷史：{detail}',
    'background_saved_partial': '已儲存含未讀取範圍的排程歷史：{detail}',
    'background_canceled': '排程掃描已取消，未儲存部分來源記錄：{detail}',
    'background_warning': '{detail}',
    'background_low_space': '{root} 可用空間不足：{free}（{percent}%）',
    'action_follow_changes': '跟隨變更',
    'action_follow_changes_tip': '預設關閉。在 Windows／Linux 更新變動資料夾，每五分鐘完整核對根目錄。',
    'follow_waiting': '跟隨變更：等待掃描',
    'follow_starting': '跟隨變更：啟動中…',
    'follow_active': '跟隨變更（{detail}）',
    'follow_failed': '跟隨變更已停止：{detail}',
    'follow_incomplete': '跟隨變更需要完整的實際目錄掃描',
    'follow_unsupported': '跟隨變更支援 Windows 與 Linux',
    'follow_backend_usn': 'NTFS USN',
    'follow_backend_directory_changes': '目錄通知',
    'follow_backend_inotify': 'inotify',
    'action_check_updates_tip': '每天最多透過 HTTPS 向 PyPI 查詢一次；僅通知，不安裝更新。',
    'update_available': 'FileTree {version} 已推出',
    'multi_roots': '多個掃描來源',
    'action_multi_scan': '掃描多個資料夾…',
    'action_multi_scan_tip': '檢視明確選取的資料夾並合併掃描。',
    'multi_choose': '掃描多個資料夾',
    'multi_add': '加入資料夾…',
    'multi_remove': '移除選取的來源',
    'scan_all_drives': '掃描所有磁碟',
    'multi_hint': '合併最多 256 個選取來源。結果為唯讀；檔案操作請另掃描該來源。OS 容量仍依各磁碟呈現。',
    'capacity_multiple_roots': '多個來源：OS 容量依各磁碟呈現。',
    'vc_title': (
        '壓縮所選 VHD…'
    ),
    'vc_apply': (
        '檢視並壓縮…'
    ),
    'vc_hint': (
        '只接受固定本機 NTFS 上未載入的動態 VHD/VHDX。唯讀準備會核對身分、標頭'
        '及保守的 WSL／Docker 執行狀態。客體用量與保證回收量仍未知。權限錯誤時，先'
        '關閉此檢視，再使用 FileTree 既有的管理員重新啟動功能；必須重新掃描及核准。'
    ),
    'vc_preparing': (
        '正在核對記錄磁碟與停機狀態…'
    ),
    'vc_ready': (
        '請檢視確切來源，並確認所屬機器全程保持停機。'
    ),
    'vc_details': (
        '來源：{path}\n名稱：{source}\n磁碟識別碼：{identifier}\n虛'
        '擬容量：{capacity}\n提供者位元組：{physical}\n\n執行方式：Win'
        'dows CompactVirtualDisk，在未載入狀態壓縮全零區塊。不掛載、啟'
        '動或停止客體；客體已用量未知。'
    ),
    'vc_confirm': (
        '壓縮這個確切的磁碟檔案？\n\n{path}\n\n選擇「是」表示確認其所屬機器已停機，且操'
        '作期間全程保持停機。仍會重新核對執行狀態與身分。原生全零區塊壓縮可能不回收空間，也可'
        '能在後續錯誤前已變更中繼資料。沒有自動復原。客體用量／可用空間回收量未知。停止／關閉'
        '會等待目前原生呼叫，並回報實際結果。任何可寫入開啟前，會先持久記錄核准。'
    ),
    'vc_running': (
        '正在重新核對並壓縮核准的磁碟…'
    ),
    'vc_waiting': (
        '正在等待目前的原生呼叫，完成後會回報實際結果…'
    ),
    'vc_done': (
        '{status}\n觀察到的磁碟檔案配置：{before} → {after}。這不保'
        '證 OS 可用空間回收量。客體用量仍未知；嘗試寫入後必須重新掃描。'
    ),
    'vc_failed': (
        '壓縮：{reason}'
    ),
    'vc_not_compacted': (
        '未壓縮'
    ),
    'vc_stale': (
        '已嘗試可寫入操作。掃描觀察已過期；請關閉此視窗重新掃描，再次檢視核准。'
    ),
    'vc_audit_refused': (
        '無法記錄核准；未開始原生操作'
    ),
    'vc_audit_detail': (
        '磁碟檔案配置，操作前：{before}；操作後：{after}。錯誤：{error}'
    ),
    'journal_status_compacted': (
        '原生壓縮已完成'
    ),
    'journal_reason_compaction': (
        '明確核准的虛擬磁碟壓縮'
    ),
    'vd_hint': (
        '唯讀清單；來源標籤只是位置提示。磁碟檔案配置、提供者位元組與虛擬容量各自獨立，客體用'
        '量仍未知。標頭查詢與壓縮檢視須明確操作。不支援的格式仍會顯示；不自動啟動、停止或掛載'
        '客體。'
    ),
    "vd_name": '磁碟名稱',
    "vd_source": '來源',
    'vd_issue_unverified': '身分尚未核對',
    'vd_issue_unavailable': '連結、雲端或不可用',
    'vd_issue_changed': '檔案已變更',
    'vd_issue_duplicate_hard_links': '有多個硬連結名稱',
    "action_virtual_disks_tip": '檢視記錄的虛擬磁碟，並明確查詢唯讀原生 VHD 資訊',
    'action_virtual_disks': '虛擬磁碟…',
    'vd_kind': '格式',
    'vd_length': '磁碟檔案長度',
    'vd_allocation': '記錄的配置量',
    'vd_capacity': '虛擬容量',
    'vd_physical': '提供者實體位元組',
    'vd_guest': '客體已用量',
    'vd_source_scan': '掃描記錄',
    'vd_source_wsl': 'WSL 註冊',
    'vd_source_docker': 'Docker 預設（推定）',
    'vd_unsupported': '不支援原生 VHD 工具',
    'vd_not_queried': '尚未查詢原生標頭',
    'vd_fixed': '固定',
    'vd_dynamic': '動態',
    'vd_differencing': '差異',
    'vd_loaded': '已掛載／使用中',
    'vd_detached': '未載入（觀察值）',
    'vd_inspect': '查詢所選 VHD 標頭',
    'vd_select': '顯示掃描記錄項目',
    'vd_reading': '正在尋找虛擬磁碟檔案…',
    'vd_querying': '正在讀取原生標頭：{path}',
    'vd_summary': '顯示 {count} 筆中的 {shown} 筆；{issues} 個問題／略過項目。涵蓋範圍：{coverage}。',
    'vd_failed': '虛擬磁碟資訊：{reason}',
    'vd_information_hint': (
        '原生觀察不授予壓縮權限，也不證明機器已停機。提供者實體位元組不代表客體已用量。磁碟識別碼列於該列的工具提示。'
    ),
    "link_summary": "{total} 個多餘副本：{ready} 個可執行，{skipped} 個拒絕。",
    "link_title": "將多餘副本改為硬連結…",
    "link_hint": (
        "檢閱明確選定保留副本的精確重複檔案（最多 1,000 個多餘副本）。受保護、"
        "已變更、雲端、連結或不支援的檔案會拒絕。可回收容量無法保證。"
    ),
    "link_copy": "要替換的多餘副本",
    "link_keeper": "保留檔案",
    "link_apply": "將已檢閱的多餘副本改為硬連結…",
    "link_confirm": (
        "要將 {count} 個多餘副本替換為硬連結嗎？{skipped} 個拒絕列"
        "會略過。\n\n舊資料不保留在資源回收筒。全部連結名稱共用後續內容、中繼資料與安"
        "全性／權限變更。此操作沒有自動復原。失敗或取消可能保留已發布的連結及舊副本備"
        "份，確切路徑會顯示。停止／關閉會等待目前原生呼叫完成。完整內容及具名串流會重"
        "新核對；同時變更仍僅能觀察。請在詳細資料檢閱每個配對與拒絕原因。"
    ),
    "link_progress": "正在重新核對／建立硬連結：{path}",
    "link_done": (
        "硬連結：{linked} 個已發布，{other} 個未連結。請重新掃描以更"
        "新記錄；回收容量未知。"
    ),
    "link_not_linked": "未連結",
    "link_retained": "保留路徑：\n{paths}",
    "journal_status_linked": "已發布硬連結",
    "journal_reason_duplicate_links": "明確要求替換重複檔案為硬連結",
    "undo_button": "復原（{count}）",
    "undo_running": "正在復原已記錄的資源回收筒項目…",
    "undo_done": "復原：{restored} 個已復原，{failed} 個失敗",
    "undo_title": "資源回收筒復原",
    "undo_result": "{status}\n原位置：{source}\n資源回收筒：{trashed}\n{reason}",
    "undo_unavailable": "部分項目無法復原：{reason}",
    "journal_status_restored": "已從資源回收筒復原",
    "journal_reason_undo": "明確要求復原資源回收筒項目",
    "menu_move_drive": "移到另一個磁碟…",
    "copy_hint": ("選擇另一個磁碟上的現有資料夾。另行確認移入資源回收筒前，保留原始資料。"
                  "核對檔案數、長度及小於 64 MiB 內容的 SHA-256；較大內容僅核對長度。"
                  "失敗／取消會保留部分目的地。最多選取 1,000 個資料夾。"),
    "copy_apply": "複製並驗證已檢視的資料夾…",
    "copy_redirect": "成功移入資源回收筒後，在每個原始路徑留下 junction／符號連結",
    "copy_finish": "將已驗證的原始資料移到資源回收筒…",
    "copy_confirm": ("要複製並驗證已檢視的 {count} 個資料夾嗎？其餘 {skipped} 組將略過。"
                     "不覆寫現有名稱。另行確認移入資源回收筒前會保留原始資料；錯誤或取消會保留部分目的地。"),
    "copy_progress": "正在複製／驗證 {path}：此資料夾 {done}／{total} 個檔案",
    "copy_done": "已驗證副本：{copied}；略過：{skipped}；失敗：{failed}。原始資料已保留。",
    "copy_partial": "保留的部分目的地：{path}",
    "copy_trash_confirm": ("每個原始資料夾移入資源回收筒前，會再次驗證副本。核對數量及長度；"
                           "小於 64 MiB 的內容以 SHA-256 核對，較大內容僅核對長度。"
                           "驗證失敗會停止剩餘批次。並行變更不具交易保證。"),
    "copy_errors": "複製驗證或原始路徑連結失敗。請檢視詳細資料中的實際路徑。",
    "copy_verify_failed": "原始資料已保留：{source}\n副本：{destination}\n驗證遭拒：{reason}",
    "copy_redirect_failed": ("原始資料已移入資源回收筒：{source}\n已驗證副本已保留：{destination}\n"
                             "連結失敗（原始路徑可能留下空資料夾）：{reason}"),
    "namespace_reason_same_volume": "同一磁碟；請使用移到資料夾",
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
    'recurring_review': '重新扫描并审核当前候选…',
    'recurring_validating': '正在比对带日期建议、完整的新扫描与当前源元数据…',
    'recurring_refused': '无法继续此建议：{status}。请执行新的计划扫描，以生成当前的观察数据。',
    'recurring_tabs_full': '十六个扫描标签页均在使用中。请先关闭一个标签页，再审核计划建议。',
    'trash_skip_proposal_changed': '源路径、建议设置或扫描记录已更改或无法验证；保留来源。',
    'trash_skip_proposal_expired': '移动前计划建议已到期；保留来源。',
    'action_recurring': '计划扫描建议…',
    'action_recurring_tip': '查看计划观察的日期与覆盖范围；不会自动清理。',
    'recurring_rule': '规则',
    'recurring_unknown': '未知',
    'recurring_new': '上次扫描后新增的垃圾候选',
    'recurring_current': '当前的清理候选',
    'recurring_growth': '容量增长最多的文件夹',
    'recurring_empty': '本次运行尚无计划报告。请启用后台监控并选择扫描文件夹。',
    'recurring_hint': ('仅供查看，不会自动移动文件。每份列表最多显示 100 条。'
                       '增长量是逻辑字节，不代表可回收空间。比较未知不代表没有新增垃圾。'
                       '报告会在本次运行的计划扫描后出现；基准数据保存在本地扫描历史。'
                       '审核会在新标签页重新扫描，再进入普通审核队列与确认流程。'),
    'recurring_summary': ('生成时间：{prepared}\n上次基准：{previous}\n到期时间：{expires}\n'
                          '显示候选：{retained} / {total}；覆盖范围：{coverage}；比较：{comparison}\n'
                          '状态：{status}'),
    'recurring_status_current': '已观察；审核前仍须重新验证来源',
    'recurring_status_expired': '已到期（包括错过计划或时钟倒退）',
    'recurring_status_schedule_changed': '计划已更改或停用',
    'recurring_status_stale_scan': '扫描记录已更改或无法获取',
    'recurring_status_rule_changed': '清理规则已更改',
    'recurring_status_incomplete': '覆盖范围不完整或文件标识未知',
    'recurring_status_paths_changed': '源路径已更改',
    'recurring_status_unavailable': '无法验证设置或扫描记录',
    'recurring_prepare_failed': '历史已保存；无法生成计划建议：{detail}',
    'workspace_new': '新建扫描标签页',
    'workspace_new_tip': '打开独立的扫描标签页（Ctrl+T）；用 Ctrl+W 关闭当前标签页。',
    'workspace_close': '关闭扫描标签页',
    'workspace_empty': '选择文件夹',
    'trash_skip_recycle_unverified': (
        '无法核对 Windows 回收设置、完整来源大小或原生回收站数据；已保留来源。'
    ),
    'trash_skip_recycle_disabled': (
        '此范围的 Windows 回收功能已禁用；已保留来源。'
    ),
    'trash_skip_recycle_capacity': (
        '选中项目及当前回收站内容超过观察到的回收上限与预留空间；已保留来源。'
    ),
    'action_check_updates': '每天检查更新',
    'action_background_monitor': '后台监视器…',
    'action_background_monitor_tip': '选择启用托盘通知与低优先级的定期文件夹历史扫描。',
    'background_enable': '启用后台监视',
    'background_startup': '登录时启动此监视器',
    'background_startup_hint': ('需另外选择启用，仅适用当前用户。取消勾选会移除 FileTree 拥有的登录项目。'
                                '适用下次登录，不会启动另一个程序或结束当前监视器。'),
    'background_startup_requires_monitor': '请先启用后台监视，再添加登录项目。',
    'background_startup_error': '无法更改登录启动：{detail}',
    'background_hint': ('默认关闭。托盘可用时，关闭窗口会保留 FileTree，选择“退出”才结束。'
                        '每分钟查询系统可用容量，只低优先级扫描明确选择的文件夹。'
                        '定期扫描需要启用本地历史记录，不自动清理或注册开机启动。'),
    'background_threshold': '可用空间低于此值时通知',
    'background_interval': '扫描间隔（小时）',
    'background_roots': '定期扫描文件夹',
    'background_add': '添加扫描文件夹…',
    'background_remove': '移除选中文件夹',
    'background_limit': '最多选择 32 个定期文件夹。',
    'background_show': '显示 FileTree',
    'background_off': '后台监视已关闭',
    'background_ready': '后台监视已启用',
    'background_no_tray': '托盘不可用；FileTree 保持显示，后台监视暂停。',
    'background_error': '后台监视：{detail}',
    'background_history_disabled': '请先启用本地扫描历史记录，才能运行定期扫描。',
    'background_scanning': '定期扫描：{detail}',
    'background_saved': '已保存定期历史：{detail}',
    'background_saved_partial': '已保存包含未读取范围的定期历史：{detail}',
    'background_canceled': '定期扫描已取消，未保存部分来源记录：{detail}',
    'background_warning': '{detail}',
    'background_low_space': '{root} 可用空间不足：{free}（{percent}%）',
    'action_follow_changes': '跟随变更',
    'action_follow_changes_tip': '默认关闭。在 Windows／Linux 更新变化文件夹，每五分钟完整核对根目录。',
    'follow_waiting': '跟随变更：等待扫描',
    'follow_starting': '跟随变更：启动中…',
    'follow_active': '跟随变更（{detail}）',
    'follow_failed': '跟随变更已停止：{detail}',
    'follow_incomplete': '跟随变更需要完整的实际目录扫描',
    'follow_unsupported': '跟随变更支持 Windows 与 Linux',
    'follow_backend_usn': 'NTFS USN',
    'follow_backend_directory_changes': '目录通知',
    'follow_backend_inotify': 'inotify',
    'action_check_updates_tip': '每天最多通过 HTTPS 向 PyPI 查询一次；仅通知，不安装更新。',
    'update_available': 'FileTree {version} 已发布',
    'multi_roots': '多个扫描来源',
    'action_multi_scan': '扫描多个文件夹…',
    'action_multi_scan_tip': '检查明确选取的文件夹并合并扫描。',
    'multi_choose': '扫描多个文件夹',
    'multi_add': '添加文件夹…',
    'multi_remove': '移除选取的来源',
    'scan_all_drives': '扫描所有磁盘',
    'multi_hint': '合并最多 256 个选取来源。结果为只读；文件操作请另扫描该来源。OS 容量仍按各磁盘显示。',
    'capacity_multiple_roots': '多个来源：OS 容量按各磁盘显示。',
    'vc_title': (
        '压缩所选 VHD…'
    ),
    'vc_apply': (
        '检查并压缩…'
    ),
    'vc_hint': (
        '只接受固定本机 NTFS 上未加载的动态 VHD/VHDX。只读准备会核对身份、头部'
        '及保守的 WSL／Docker 运行状态。客户机用量与保证回收量仍未知。权限错误时，'
        '先关闭此检查，再使用 FileTree 现有的管理员重新启动功能；必须重新扫描及批准'
        '。'
    ),
    'vc_preparing': (
        '正在核对记录磁盘与停机状态…'
    ),
    'vc_ready': (
        '请检查确切来源，并确认所属机器全程保持停机。'
    ),
    'vc_details': (
        '来源：{path}\n名称：{source}\n磁盘标识符：{identifier}\n虚'
        '拟容量：{capacity}\n提供程序字节：{physical}\n\n执行方式：Win'
        'dows CompactVirtualDisk，在未加载状态压缩全零块。不挂载、启动'
        '或停止客户机；客户机已用量未知。'
    ),
    'vc_confirm': (
        '压缩这个确切的磁盘文件？\n\n{path}\n\n选择“是”表示确认其所属机器已停机，且操'
        '作期间全程保持停机。仍会重新核对运行状态与身份。原生全零块压缩可能不回收空间，也可能'
        '在后续错误前已更改元数据。没有自动撤销。客户机用量／可用空间回收量未知。停止／关闭会'
        '等待当前原生调用，并报告实际结果。任何可写入打开前，会先持久记录批准。'
    ),
    'vc_running': (
        '正在重新核对并压缩批准的磁盘…'
    ),
    'vc_waiting': (
        '正在等待当前的原生调用，完成后会报告实际结果…'
    ),
    'vc_done': (
        '{status}\n观察到的磁盘文件分配：{before} → {after}。这不保'
        '证 OS 可用空间回收量。客户机用量仍未知；尝试写入后必须重新扫描。'
    ),
    'vc_failed': (
        '压缩：{reason}'
    ),
    'vc_not_compacted': (
        '未压缩'
    ),
    'vc_stale': (
        '已尝试可写入操作。扫描观察已过期；请关闭此窗口重新扫描，再次检查批准。'
    ),
    'vc_audit_refused': (
        '无法记录批准；未开始原生操作'
    ),
    'vc_audit_detail': (
        '磁盘文件分配，操作前：{before}；操作后：{after}。错误：{error}'
    ),
    'journal_status_compacted': (
        '原生压缩已完成'
    ),
    'journal_reason_compaction': (
        '明确批准的虚拟磁盘压缩'
    ),
    'vd_hint': (
        '只读列表；来源标签只是位置提示。磁盘文件分配、提供程序字节与虚拟容量各自独立，客户机'
        '用量仍未知。头部查询与压缩检查须明确操作。不支持的格式仍会显示；不自动启动、停止或挂'
        '载客户机。'
    ),
    "vd_name": '磁盘名称',
    "vd_source": '来源',
    'vd_issue_unverified': '身份尚未核对',
    'vd_issue_unavailable': '链接、云端或不可用',
    'vd_issue_changed': '文件已变化',
    'vd_issue_duplicate_hard_links': '有多个硬链接名称',
    "action_virtual_disks_tip": '查看记录的虚拟磁盘，并显式查询只读原生 VHD 信息',
    'action_virtual_disks': '虚拟磁盘…',
    'vd_kind': '格式',
    'vd_length': '磁盘文件长度',
    'vd_allocation': '记录的分配量',
    'vd_capacity': '虚拟容量',
    'vd_physical': '提供程序物理字节',
    'vd_guest': '客户机已用量',
    'vd_source_scan': '扫描记录',
    'vd_source_wsl': 'WSL 注册',
    'vd_source_docker': 'Docker 默认（推定）',
    'vd_unsupported': '不支持原生 VHD 工具',
    'vd_not_queried': '尚未查询原生头部',
    'vd_fixed': '固定',
    'vd_dynamic': '动态',
    'vd_differencing': '差分',
    'vd_loaded': '已挂载／使用中',
    'vd_detached': '未加载（观察值）',
    'vd_inspect': '查询所选 VHD 头部',
    'vd_select': '显示扫描记录项目',
    'vd_reading': '正在查找虚拟磁盘文件…',
    'vd_querying': '正在读取原生头部：{path}',
    'vd_summary': '显示 {count} 行中的 {shown} 行；{issues} 个问题／跳过项目。覆盖范围：{coverage}。',
    'vd_failed': '虚拟磁盘信息：{reason}',
    'vd_information_hint': (
        '原生观察不授予压缩权限，也不证明机器已关机。提供程序物理字节不代表客户机已用量。磁盘标识符显示在该行的工具提示中。'
    ),
    "link_summary": "{total} 个多余副本：{ready} 个可执行，{skipped} 个拒绝。",
    "link_title": "将多余副本改为硬链接…",
    "link_hint": (
        "检查明确选定保留副本的精确重复文件（最多 1,000 个多余副本）。受保护、"
        "已变化、云端、链接或不支持的文件会拒绝。可回收容量无法保证。"
    ),
    "link_copy": "要替换的多余副本",
    "link_keeper": "保留文件",
    "link_apply": "将已检查的多余副本改为硬链接…",
    "link_confirm": (
        "要将 {count} 个多余副本替换为硬链接吗？{skipped} 个拒绝行"
        "会跳过。\n\n旧数据不保留在回收站。全部链接名称共享后续内容、元数据与安全性／"
        "权限变化。此操作没有自动恢复。失败或取消可能保留已发布的链接及旧副本备份，准"
        "确路径会显示。停止／关闭会等待当前原生调用完成。完整内容及命名流会重新核对；"
        "同时变化仍只能观察。请在详细信息检查每个配对与拒绝原因。"
    ),
    "link_progress": "正在重新核对／创建硬链接：{path}",
    "link_done": (
        "硬链接：{linked} 个已发布，{other} 个未链接。请重新扫描以更"
        "新记录；回收容量未知。"
    ),
    "link_not_linked": "未链接",
    "link_retained": "保留路径：\n{paths}",
    "journal_status_linked": "已发布硬链接",
    "journal_reason_duplicate_links": "明确要求替换重复文件为硬链接",
    "undo_button": "恢复（{count}）",
    "undo_running": "正在恢复已记录的回收站项目…",
    "undo_done": "恢复：{restored} 个已恢复，{failed} 个失败",
    "undo_title": "回收站恢复",
    "undo_result": "{status}\n原位置：{source}\n回收站：{trashed}\n{reason}",
    "undo_unavailable": "部分项目无法恢复：{reason}",
    "journal_status_restored": "已从回收站恢复",
    "journal_reason_undo": "明确要求恢复回收站项目",
    "menu_move_drive": "移动到另一个磁盘…",
    "copy_hint": ("选择另一个磁盘上的现有文件夹。另行确认移入回收站前，保留原始数据。"
                  "核对文件数、长度及小于 64 MiB 内容的 SHA-256；更大内容仅核对长度。"
                  "失败／取消会保留部分目标。最多选择 1,000 个文件夹。"),
    "copy_apply": "复制并验证已查看的文件夹…",
    "copy_redirect": "成功移入回收站后，在每个原始路径留下 junction／符号链接",
    "copy_finish": "将已验证的原始数据移到回收站…",
    "copy_confirm": ("要复制并验证已查看的 {count} 个文件夹吗？其余 {skipped} 组将跳过。"
                     "不覆盖现有名称。另行确认移入回收站前会保留原始数据；错误或取消会保留部分目标。"),
    "copy_progress": "正在复制／验证 {path}：此文件夹 {done}／{total} 个文件",
    "copy_done": "已验证副本：{copied}；跳过：{skipped}；失败：{failed}。原始数据已保留。",
    "copy_partial": "保留的部分目标：{path}",
    "copy_trash_confirm": ("每个原始文件夹移入回收站前，会再次验证副本。核对数量及长度；"
                           "小于 64 MiB 的内容以 SHA-256 核对，更大内容仅核对长度。"
                           "验证失败会停止剩余批次。并行变更不具事务保证。"),
    "copy_errors": "复制验证或原始路径链接失败。请查看详细信息中的实际路径。",
    "copy_verify_failed": "原始数据已保留：{source}\n副本：{destination}\n验证遭拒：{reason}",
    "copy_redirect_failed": ("原始数据已移入回收站：{source}\n已验证副本已保留：{destination}\n"
                             "链接失败（原始路径可能留下空文件夹）：{reason}"),
    "namespace_reason_same_volume": "同一磁盘；请使用移动到文件夹",
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











JA: dict[str, str] = {
    'recurring_review': '再スキャンして現在の候補を確認…',
    'recurring_validating': '日付の付いた提案を新しいスキャン全体と現在のソース メタデータと照合して検証しています…',
    'recurring_refused': (
        'プロポーザルを続行できません: {status}。新しいスケジュールされたスキャンを実行して、現在の観測を準備'
        'します。'
    ),
    'recurring_tabs_full': (
        '16 個のスキャン タブはすべて使用中です。スケジュールされたプロポーザルを確認する前にタブを閉じてくだ'
        'さい。'
    ),
    'trash_skip_proposal_changed': (
        '元のパス、候補レポートの設定または記録が変更されたか、確認できませんでした。元の項目を保持しました。'
    ),
    'trash_skip_proposal_expired': (
        '移動前に定期スキャンの候補レポートが期限切れになりました。元の項目を保持しました。'
    ),
    'action_recurring': 'スケジュールされたスキャンの提案…',
    'action_recurring_tip': '日付のスケジュールされた観測とその範囲を表示します。自動クリーンアップはありません。',
    'recurring_rule': 'ルール',
    'recurring_unknown': '不明',
    'recurring_new': '前回のスキャン以降の新しいジャンク',
    'recurring_current': '現在の候補',
    'recurring_growth': '最大の新規成長',
    'recurring_empty': (
        'このセッションにはスケジュールされたレポートはありません。バックグラウンド監視を有効にし、スキャンフ'
        'ォルダーを選択します。'
    ),
    'recurring_hint': (
        '観察のみ。何も自動的に移動されません。リストごとに最大 100 行。増加は論理バイトであり、回復可能なス'
        'ペースではありません。不明な比較は、新しいジャンクがないことを証明するものではありません。レポートは'
        '、このセッションのスケジュールされたスキャンの後に表示されます。ベースラインはローカル履歴に保存され'
        'ます。新しいタブで再スキャンを確認し、通常のキューと確認を使用します。'
    ),
    'recurring_summary': (
        '準備済み: {prepared}\n前のベースライン: {previous}\n有効期限: {expires}\n表示された候補: {retained} '
        '/ {total};カバレッジ: {coverage};比較: {comparison}\nステータス: {status}'
    ),
    'recurring_status_current': '観察されました。レビュー前に最新のソースの検証が必要',
    'recurring_status_expired': '期限切れ (スケジュールの欠如またはクロックのロールバックを含む)',
    'recurring_status_schedule_changed': 'スケジュールが変更または無効になった',
    'recurring_status_stale_scan': 'スキャン操作記録が変更されているか、使用不可になっています',
    'recurring_status_rule_changed': 'クリーンアップルールが変更されました',
    'recurring_status_incomplete': '不完全な報道または不明な身元',
    'recurring_status_paths_changed': 'ソースパスが変更されました',
    'recurring_status_unavailable': '設定または受信を確認できませんでした',
    'recurring_prepare_failed': '履歴が保存されました。スケジュールされたプロポーザルは利用できません: {detail}',
    'workspace_new': '新しいスキャンタブ',
    'workspace_new_tip': '独立したスキャン タブを開きます (Ctrl+T)。 Ctrl+W で現在のタブを閉じます。',
    'workspace_close': 'スキャンタブを閉じる',
    'workspace_empty': 'フォルダーを選択',
    'trash_skip_recycle_unverified': (
        'Windows リサイクル設定、完全なソース サイズ、またはネイティブ ビン メタデータを検証できませんでした'
        '。元の項目を保持しました。'
    ),
    'trash_skip_recycle_disabled': 'Windows このスコープではリサイクルが無効になっています。元の項目を保持しました。',
    'trash_skip_recycle_capacity': (
        '選択した内容と現在のビンの内容が、観察されたヘッドルームのあるリサイクル制限を超えています。元の項目'
        'を保持しました。'
    ),
    'action_check_updates': '毎日更新をチェックする',
    'action_background_monitor': 'バックグラウンドモニター…',
    'action_background_monitor_tip': (
        'トレイ通知と穏やかなスケジュールされたフォルダー履歴スキャンをオプトインします。'
    ),
    'background_enable': 'バックグラウンド監視を有効にする',
    'background_startup': 'サインイン時にこのモニターを開始します',
    'background_startup_hint': (
        'このユーザーのみに個別のオプトインを設定します。 FileTree が所有するログイン エントリを削除するには'
        '、チェックを外します。今後のログインに適用されます。別のコピーを開始したり、このモニターを閉じたりす'
        'ることはありません。'
    ),
    'background_startup_requires_monitor': 'ログインエントリを追加する前に、バックグラウンド監視を有効にします。',
    'background_startup_error': 'ログインの起動を変更できませんでした: {detail}',
    'background_hint': (
        'デフォルトではオフです。閉じると、FileTree が使用可能なシステム トレイに保持されます。終了すると終了'
        'します。 OSの利用可能な容量を1分ごとに確認し、選択したフォルダーのみを優しくスキャンします。スケジュ'
        'ールされたスキャンには、ローカル履歴が有効になっている必要があります。自動クリーンアップやスタートア'
        'ップ登録はありません。'
    ),
    'background_threshold': '利用可能なスペースを下回ると警告する',
    'background_interval': 'スキャン間隔 (時間)',
    'background_roots': 'スケジュールスキャンフォルダー',
    'background_add': 'スキャンフォルダーを追加…',
    'background_remove': '選択したフォルダーを削除します',
    'background_limit': '最大 32 個のスケジュールされたフォルダーを選択します。',
    'background_show': 'FileTree を表示',
    'background_off': 'バックグラウンド監視がオフになっています',
    'background_ready': 'バックグラウンド監視がオンになっています',
    'background_no_tray': (
        'システムトレイは使用できません。 FileTree は表示されたままになり、バックグラウンド監視は一時停止され'
        'ます。'
    ),
    'background_error': 'バックグラウンド監視: {detail}',
    'background_history_disabled': 'スケジュールされたスキャンを実行する前に、ローカル スキャン履歴を有効にします。',
    'background_scanning': 'スケジュールされたスキャン: {detail}',
    'background_saved': '保存されたスケジュールされた履歴: {detail}',
    'background_saved_partial': '未読スコープで保存されたスケジュールされた履歴: {detail}',
    'background_canceled': (
        'スケジュールされたスキャンがキャンセルされました。部分的なソース カバレッジは保存されませんでした: {'
        'detail}'
    ),
    'background_warning': '{detail}',
    'background_low_space': '{root} の空き容量が少ない: {free} ({percent}%)',
    'action_follow_changes': '変更を追跡する',
    'action_follow_changes_tip': (
        'デフォルトではオフです。 Windows/Linux で変更されたフォルダーを更新します。 5分ごとにルートを調整し'
        'ます。'
    ),
    'follow_waiting': '変更の追跡: スキャンを待機しています',
    'follow_starting': '変更を追跡: 開始中…',
    'follow_active': '次の変更点 ({detail})',
    'follow_failed': '変更の追跡が停止されました: {detail}',
    'follow_incomplete': '変更を追跡するには完全な物理スキャンが必要です',
    'follow_unsupported': '変更を追跡すると、Windows および Linux がサポートされます',
    'follow_backend_usn': 'NTFS USN',
    'follow_backend_directory_changes': 'ディレクトリ通知',
    'follow_backend_inotify': '通知する',
    'action_check_updates_tip': (
        '多くても 1 日に 1 回、HTTPS 経由で PyPI に問い合わせます。通知のみで、インストールはありません。'
    ),
    'update_available': 'FileTree {version} は利用可能です',
    'multi_roots': '複数のルート',
    'action_multi_scan': '複数のフォルダーをスキャンします…',
    'action_multi_scan_tip': '1 回の結合スキャンで明示的なフォルダーを確認します。',
    'multi_choose': '複数のフォルダーをスキャンする',
    'multi_add': 'フォルダを追加…',
    'multi_remove': '選択したルートを削除します',
    'scan_all_drives': 'すべてのドライブをスキャンする',
    'multi_hint': (
        '選択したルートを最大 256 個結合します。結果は読み取り専用です。ファイル操作のためにソースを個別にス'
        'キャンします。 OS の容量はボリュームごとに維持されます。'
    ),
    'capacity_multiple_roots': '複数のルート: OS の容量はボリュームごとです。',
    'vc_title': 'コンパクトな選択された VHD…',
    'vc_apply': 'レビューしてコンパクトに…',
    'vc_hint': (
        '固定ローカル NTFS 上の切り離されたダイナミック VHD/VHDX のみが対象となります。読み取り専用の準備では'
        '、ID、ヘッダー、保守的な WSL/Docker ランタイム状態がチェックされます。ゲストの使用状況と保証された回'
        '復は不明のままです。 FileTree の既存の管理者が権限エラーのために再起動する前に、このレビューを閉じて'
        'ください。新たなスキャンと承認が必要です。'
    ),
    'vc_preparing': 'キャプチャされたディスクと停止したランタイムを確認しています…',
    'vc_ready': '正確なソースを確認し、そのマシンが停止したままであることを確認します。',
    'vc_details': (
        'ソース: {path}\n名前: {source}\nディスク UUID: {identifier}\n仮想容量: {capacity}\nプロバイダー バイ'
        'ト: {physical}\n\nバックエンド: Windows CompactVirtualDisk、切り離されたゼロブロック圧縮。ゲストの接'
        '続、起動またはシャットダウンはありません。ゲストが使用するバイトは不明です。'
    ),
    'vc_confirm': (
        '次の正確な仮想ディスクファイルをコンパクト化しますか？\n\n{path}\n\n「はい」を選ぶと、このファイルを'
        '使用するマシンが停止しており、処理中も停止したままであることを確認したものとみなします。実行状態と識'
        '別情報を改めて確認します。OS のゼロブロック処理では容量が回復しない場合があり、後からエラーが発生し'
        'てもメタデータがすでに変更されている可能性があります。自動的に元に戻す機能はありません。ゲストの使用'
        '量と空き容量の回復量は不明です。停止または閉じる操作は、実行中の OS 呼び出しを待ち、実際の結果を報告'
        'します。書き込み可能な状態で開く前に承認を記録します。'
    ),
    'vc_running': 'レビューしたディスクを再チェックして圧縮しています…',
    'vc_waiting': '現在のネイティブ呼び出しを待機しています。実際の結果はまた報告します…',
    'vc_done': (
        '{status}\n観察されたバッキング割り当て: {before} → {after}。これは OS のフリーリカバリを保証するもの'
        'ではありません。ゲストの使用状況は不明のままです。書き込みを試行するには、新たなスキャンが必要です。'
    ),
    'vc_failed': '圧縮: {reason}',
    'vc_not_compacted': '圧縮されていない',
    'vc_stale': (
        '書き込み可能な操作が試行されました。記録された観察は古いものです。別のレビューを行う前に、このウィン'
        'ドウを閉じて新たにスキャンしてください。'
    ),
    'vc_audit_refused': '承認を記録できませんでした。ネイティブ操作は開始されていません',
    'vc_audit_detail': '以前のバッキング割り当て: {before};後: {after}。エラー: {error}',
    'journal_status_compacted': 'ネイティブ圧縮が完了しました',
    'journal_reason_compaction': '明示的な仮想ディスクの圧縮',
    'vd_hint': (
        '読み取り専用インベントリ。プロバイダー ラベルは場所のヒントです。バッキング割り当て、プロバイダーの'
        'バイト、および仮想容量は別個です。ゲストの使用状況は不明のままです。ヘッダー クエリと圧縮レビューは'
        '明示的です。サポートされていない形式は表示されたままになります。ゲストが自動的に起動、停止、マウント'
        'することはありません。'
    ),
    'vd_name': 'ディスク名',
    'vd_source': 'ソース',
    'vd_issue_unverified': '未確認の身元',
    'vd_issue_unavailable': 'リンクされているか、クラウドか、または利用できない',
    'vd_issue_changed': 'ファイルが変更されました',
    'vd_issue_duplicate_hard_links': '複数のハードリンク名',
    'action_virtual_disks_tip': (
        '記録された仮想ディスクを確認し、読み取り専用のネイティブ VHD 情報を明示的にクエリします'
    ),
    'action_virtual_disks': '仮想ディスク…',
    'vd_kind': 'フォーマット',
    'vd_length': 'バッキングファイルの長さ',
    'vd_allocation': '記録された割り当て',
    'vd_capacity': '仮想容量',
    'vd_physical': 'プロバイダーの物理バイト',
    'vd_guest': 'ゲストが利用した',
    'vd_source_scan': '記録されたスキャン',
    'vd_source_wsl': 'WSL登録',
    'vd_source_docker': 'Docker のデフォルト (推定)',
    'vd_unsupported': 'ネイティブ VHD ツールはサポートされていません',
    'vd_not_queried': 'ネイティブヘッダーはクエリされません',
    'vd_fixed': '修正済み',
    'vd_dynamic': 'ダイナミック',
    'vd_differencing': '差異化',
    'vd_loaded': '装着中・使用中',
    'vd_detached': '積まれていない（観察）',
    'vd_inspect': '選択した VHD ヘッダーをクエリします',
    'vd_select': '記録されたエントリを表示する',
    'vd_reading': '仮想バッキング ファイルを検出しています…',
    'vd_querying': 'ネイティブヘッダーを読み取り中: {path}',
    'vd_summary': '{count}中{shown}を表示しています。 {issues} の問題/欠落。対象範囲: {coverage}。',
    'vd_failed': '仮想ディスク情報: {reason}',
    'vd_information_hint': (
        'ネイティブの観察では、圧縮を許可したり、マシンが停止していることを証明したりすることはありません。プ'
        'ロバイダーの物理バイトはゲストが使用するバイトではありません。ディスク UUID は行のツールチップにあり'
        'ます。'
    ),
    'link_summary': '{total} 枚の追加コピー: {ready} 準備完了、{skipped} は拒否されました。',
    'link_title': '追加のコピーをリンクします…',
    'link_hint': (
        '明示的に保存されたコピー (最大 1,000 個の追加ファイル) を使用して、完全に重複したファイルを確認しま'
        'す。保護されたファイル、変更されたファイル、クラウド ファイル、リンクされたファイル、およびサポート'
        'されていないファイルは拒否されます。保証される空き領域量はありません。'
    ),
    'link_copy': '置き換える追加のコピー',
    'link_keeper': '保持されたファイル',
    'link_apply': 'リンクは追加コピーをレビューしました…',
    'link_confirm': (
        '{count} 個の重複コピーをハードリンクに置き換えますか？ 処理できない {skipped} 行はスキップします。\n'
        '\n元のデータはごみ箱に保存されません。リンクされたすべての名前は、以後の内容、メタデータおよびアクセ'
        'ス権の変更を共有します。自動的に元に戻す機能はありません。失敗やキャンセル時には、作成済みリンクと元'
        'のコピーのバックアップが表示されたパスに残る場合があります。停止または閉じる操作は、実行中の OS 呼び'
        '出しの終了を待ちます。すべてのデータと名前付きストリームを再確認します。同時変更に対する確認は観察に'
        '基づくものであり、トランザクションではありません。詳細で各ペアと拒否理由を確認してください。'
    ),
    'link_progress': '再チェック/リンク: {path}',
    'link_done': (
        'ハードリンク: {linked} が公開されていますが、{other} はリンクされていません。再スキャンして観察を更'
        '新します。回復容量は不明。'
    ),
    'link_not_linked': 'リンクされていません',
    'link_retained': '保持されるパス:\n{paths}',
    'journal_status_linked': 'ハードリンクが公開されました',
    'journal_reason_duplicate_links': '明示的な重複ハードリンクの置換',
    'undo_button': '元に戻す ({count})',
    'undo_running': 'キャプチャされたゴミ箱アイテムを復元しています…',
    'undo_done': '元に戻す: {restored} は復元されましたが、{failed} は失敗しました',
    'undo_title': 'ゴミ箱の修復',
    'undo_result': '{status}\nオリジナル: {source}\nゴミ箱: {trashed}\n{reason}',
    'undo_unavailable': '一部の項目では元に戻すことができません: {reason}',
    'journal_status_restored': 'ゴミ箱から復元',
    'journal_reason_undo': '明示的なゴミ箱の取り消し',
    'menu_move_drive': '別のドライブに移動します…',
    'copy_hint': (
        '別のドライブにある既存のフォルダーを選択します。オリジナルは、別のゴミ箱確認が行われるまで保持されま'
        'す。ファイル数、長さ、SHA-256 が 64 MiB 未満であることを確認します。より大きなペイロードは長さのみで'
        'す。失敗/キャンセルでは部分的な宛先が保持されます。最大 1,000 個のフォルダーを選択できます。'
    ),
    'copy_apply': 'レビュー済みフォルダーをコピーして確認します…',
    'copy_redirect': 'ゴミ箱に成功した後、元の各パスにジャンクション/シンボリック リンクを残します。',
    'copy_finish': '確認済みのオリジナルをごみ箱に移動します…',
    'copy_confirm': (
        '確認済みの {count} 組のフォルダーをコピーして検証しますか？ ほかの {skipped} 組はスキップします。既'
        '存の名前は上書きしません。元の項目は、ごみ箱への移動を別途承認するまで保持します。失敗やキャンセル時'
        'には、途中までコピーされた項目がコピー先に残ります。'
    ),
    'copy_progress': 'このフォルダー内の {path}: {done} / {total} ファイルをコピー/検証しています',
    'copy_done': (
        '検証済みのコピー: {copied};スキップされました: {skipped};失敗しました: {failed}。原本は保管されてい'
        'ます。'
    ),
    'copy_partial': '保持された部分的な宛先: {path}',
    'copy_trash_confirm': (
        '各項目をごみ箱へ移動する直前に、コピー先のフォルダーを再検証します。項目数と長さを比較します。64 MiB'
        ' 未満の内容は SHA-256 で照合し、それ以上の内容は長さだけを比較します。確認に失敗すると残りの処理を停'
        '止します。同時変更に対する確認はトランザクションではありません。'
    ),
    'copy_errors': (
        'コピーの検証または元のパスのリダイレクトに失敗しました。 「詳細」で実際のパスを確認してください。'
    ),
    'copy_verify_failed': '保持されたオリジナル: {source}\nコピー: {destination}\n検証が拒否されました: {reason}',
    'copy_redirect_failed': (
        'オリジナルはゴミ箱に移動されました: {source}\n確認されたコピーは保持されました: {destination}\nリダ'
        'イレクトに失敗しました (空のオリジナル パス ディレクトリが残る可能性があります): {reason}'
    ),
    'namespace_reason_same_volume': '同じボリューム。フォルダーに移動を使用する',
    'namespace_source_name': 'ソース名',
    'namespace_destination_name': '宛先名',
    'namespace_closed_errors': (
        '停止/クローズされた操作でエラーが報告されました。 「詳細」で送信元/宛先パスを検査します。'
    ),
    'namespace_refreshed': '{path}: {files} ファイルを更新しました。 {errors} スキャン エラー。',
    'namespace_refresh_failed': '{path} で更新に失敗しました: {reason}',
    'namespace_refreshing': '影響を受ける宛先を更新しています: {path}',
    'menu_move_folder': 'フォルダに移動…',
    'menu_rename': '名前を変更…',
    'namespace_source': 'ソース',
    'namespace_destination': '目的地',
    'namespace_status': 'ステータス',
    'namespace_pattern': 'ファイル名のパターン',
    'namespace_rename_hint': (
        'すべてのソースと宛先を確認します。リテラルトークン: {name}、{stem}、{ext}、{n}。同じボリュームのみ。'
        '上書きはありません。選択されたエントリは最大 1,000 件です。'
    ),
    'namespace_move_hint': (
        '既存の宛先フォルダーを選択し、すべてのペアを確認します。同じボリュームのみ。上書きはありません。保護'
        'されている/リンク/利用できない/不完全なエントリは拒否されます。選択されたエントリは最大 1,000 件です'
        '。'
    ),
    'namespace_collision_skip': '既存の名前: スキップ',
    'namespace_collision_rename': '既存の名前: 番号付きサフィックスをプレビューする',
    'namespace_preview': 'パスのプレビュー',
    'namespace_apply': 'レビューしたパスを適用します…',
    'namespace_reading': 'ソースと宛先のメタデータを確認しています…',
    'namespace_preview_needed': 'オプションが変更されました。適用する前にパスを再度プレビューしてください。',
    'namespace_summary': (
        '{total} 最も外側のペア。 {ready} 準備完了。 {skipped} は拒否されました/変更されませんでした。'
    ),
    'namespace_confirm': (
        'プレビューの処理可能な {count} 組の元のパス／移動先のペアを適用しますか？ ほかの {skipped} 組はスキ'
        'ップします。詳細には処理可能な全ペアを表示します。既存の名前は上書きしません。停止または閉じる操作は'
        '、実行中の名前変更の終了を待ち、完了した変更を保持します。'
    ),
    'namespace_progress': '{done} / {total} ペアを処理しました',
    'namespace_done': (
        '移動/名前変更: {moved};スキップされました: {skipped};失敗しました: {failed}。閉じてスキャンを更新し'
        'ます。'
    ),
    'namespace_failed': '操作が失敗しました: {reason}',
    'namespace_reason_ready': '準備完了',
    'namespace_reason_unverified': '不明な身元',
    'namespace_reason_link': 'リンクが拒否されました',
    'namespace_reason_special': '特別入場は拒否されました',
    'namespace_reason_unavailable': '利用不可/クラウドエントリー',
    'namespace_reason_cancelled': '停止しました',
    'namespace_reason_outside': '現在のスキャン/ルート以外',
    'namespace_reason_missing': 'ソースがありません',
    'namespace_reason_kind': 'エントリタイプが変更されました',
    'namespace_reason_identity': 'ソースを交換しました',
    'namespace_reason_changed': 'ソースが変更されました',
    'namespace_reason_incomplete': '不完全な情報源の網羅',
    'namespace_reason_unreadable': '読めないソース',
    'namespace_reason_system_managed': 'システム管理のソース',
    'namespace_reason_protected': '保護されたソース',
    'namespace_reason_unchanged': '名前は変更されていません',
    'namespace_reason_descendant': '選択したソース内の宛先',
    'namespace_reason_protected_destination': '保護された宛先',
    'namespace_reason_volume': 'ボリュームが異なります。確認済みのコピーが必要です',
    'namespace_reason_collision': '名前はすでに存在します',
    'photos_exact': '完全な重複',
    'photos_find': '似た写真を探す',
    'photos_similar': '類似の写真',
    'photos_distance': 'ハッシュ距離 (0 ～ 16):',
    'photos_hint': (
        '視覚的な候補のみ: サムネイルとオリジナルを比較します。ハッシュの衝突が発生する可能性があります。自動'
        '残すファイル、追加コピーの選択、または回復の見積もりはありません。最初のアニメーション フレーム。'
    ),
    'photos_group': '{count} 画像;最初の画像の {distance} ビット以内',
    'photos_running': '画像の読み取り: {read};スキップ/失敗: {skipped}',
    'photos_summary': (
        '{groups} 類似画像グループ。 {read} 画像が読み取られました。 {skipped} はスキップ/失敗しました。'
    ),
    'photos_limited': '在庫または展示が限られている。最大 {count} 件の画像行/サムネイルが表示されます。',
    'archive_loading': 'アーカイブ メタデータを読み取り中…',
    'archive_virtual_name': '{name} [仮想]',
    'archive_virtual_hint': (
        'アーカイブ メンバー: 宣言された非圧縮サイズ、ディスク合計外。ファイル操作や抽出はありません。'
    ),
    'archive_failed': 'プレビューは利用できません: {reason}',
    'archive_rejected': '{count} の安全でない、リンクされた、または競合するメンバーが省略されました',
    'archive_empty': 'プレビュー可能なメンバーがいません',
    'archive_stopped': 'アーカイブのプレビューが停止しました。在庫が不完全',
    'archive_busy': '2 つのアーカイブ読み取りがすでに実行されています。再スキャンして再試行する',
    'archive_stop': 'このアーカイブを読むのをやめる',
    'action_count_hard_links': '観察されたハードリンクを 1 回カウントする',
    'action_count_hard_links_tip': (
        'デフォルトではオフです。今後のスキャンでは名前付きサイズが保持され、カウントされた合計が追加されます'
        '。ブランチ/ゴミ箱の再スキャンにより、完全なルートが再構築されます。'
    ),
    'column_accounted_size': 'カウントサイズ',
    'column_accounted_allocated': 'カウントされたディスクサイズ',
    'hard_links_hint': (
        'ハードリンク アカウンティングを有効にすると、最初に検出された語彙名がバイト数に寄与します。ここでは'
        'エイリアスはゼロとカウントされます。名前付きサイズは実際のファイル長のままです。不明または矛盾した記'
        '録は推定のままです。共有エクステントは不明です。'
    ),
    'hard_links_summary': (
        'カウント: {size} (ディスク推定値 {allocated}); {aliases} 観察されたエイリアス。 {unknown} 不明なレコ'
        'ードです。グラフではカウントされた合計が使用されます。ファイル/タイプ/経過時間リストは名前付きサイズ'
        'を保持します。'
    ),
    'compression_mode_ntfs': 'NTFS 圧縮',
    'compression_mode_xpress8k': 'XPRESS8K 圧縮 (ほとんど変更されないファイル)',
    'compression_mode_uncompress': '解凍 (NTFS および実行可能モード)',
    'compression_apply': 'リストされたファイルを処理します…',
    'compression_restore_summary': (
        '{count}/{total} 件の記録ファイルはレビューの対象となります。 {shown} を表示しています。圧縮状態が不'
        '明な可能性があります。'
    ),
    'compression_confirm': (
        '範囲: {path}\nモード: {mode}\n候補 {total} 件のうち、一覧の {count} ファイル（論理サイズ {size}）だ'
        'けを処理します。\n\n現在の NTFS 範囲と、ファイルが変更されていないことを再確認します。リンク、クラウ'
        'ド／オフライン、スパース、隠し／システム、ハードリンクおよび保護されたファイルは処理しません。フォル'
        'ダーの既定設定と一覧にないファイルは変更しません。圧縮すると書き込みが遅くなる場合があります。XPRESS'
        ' は変更の少ないデータ向けです。圧縮解除には空き容量が必要です。停止や失敗時には一部の変更が残る場合'
        'があります。\n\nこの画面を閉じると実行中のコマンドをキャンセルし、その終了を待ってから、ファイルごと'
        'の割り当てを確認してこのフォルダーを再スキャンします。続行しますか？'
    ),
    'compression_progress': '{done}/{total} リストされたファイルを処理しています…',
    'compression_done': (
        '{done}/{attempted} コマンドが完了しました。 {failures} 回失敗しました。既知の一致するファイル割り当'
        'て: {before} → {after}; {unknown} 測定値は不明です。再スキャン間近です。合計は空き領域を保証するもの'
        'ではありません。最初の 20 個のエラーが表示されます。'
    ),
    'compression_canceled': (
        '止まった。以前のファイルまたは現在のファイルが変更されている可能性があります。再スキャン間近です。'
    ),
    'compression_failed': '操作が失敗しました: {reason}。部分的な変更は可能です。再スキャン間近です。',
    'action_exact_allocation': 'ファイルごとの割り当て Windows を測定します',
    'action_exact_allocation_tip': (
        'デフォルトではオフです。追加のメタデータは、XPRESS/WOF ファイルなど、今後のスキャンを必要とします。'
        '有効にして再スキャンします。既知のクラウド/オフライン ファイルは照会されません。失敗したクエリは推定'
        '値のままです。'
    ),
    'menu_compression': 'NTFS 圧縮…',
    'compression_reading': '記録された圧縮候補を確認しています…',
    'compression_summary': (
        '{count}/{total} ファイルはタイプの候補です。 {shown} を表示しています。論理 {logical}、名前付き割り'
        '当て {allocated}。節約の可能性: 0–{allocated};固定の圧縮率は予測されません。 {unknown} ファイルには'
        '不明なメタデータがあります。'
    ),
    'compression_volume': 'ファイルシステム: {filesystem};割り当て単位: {unit}',
    'compression_unknown': '不明',
    'compression_ntfs_only': 'NTFS は確認されませんでした。このスコープではネイティブ圧縮は使用できません。',
    'compression_partial': '不完全なスキャン: 省略された/読み取り不可能なデータはこの推定値の範囲外です。',
    'compression_hint': (
        '読み取り専用タイプの推定: ログ、テキスト、コード、および場合によっては非圧縮画像形式。拡張子は圧縮可'
        '能であることを証明しません。非表示/システム、圧縮/スパース、再解析/クラウド/オフライン、および不明な'
        'レコードは省略されます。名前付き割り当てはハード リンクによって推定または共有される可能性があるため'
        '、回復可能な領域が保証されているわけではありません。ペイロードは読み取られません。ダブルクリックする'
        'と、記録されたファイルが選択されます。 Ctrl+C で行をコピーします。'
    ),
    'action_capture_owners': 'Windows ファイル所有者をキャプチャする',
    'action_capture_owners_tip': (
        'デフォルトではオフです。今後のスキャンに所有者のメタデータ クエリを追加します。有効にして再スキャン'
        'する'
    ),
    'tab_users': 'ユーザー',
    'column_owner': '所有者',
    'column_owner_id': '所有者の身元',
    'owner_unknown': '不明な所有者',
    'owners_refresh': '記録された合計を更新する',
    'owners_reading': '記録された所有者の合計を追加し、アカウント名を解決しています...',
    'owners_unqueried': 'スキャン後に「ユーザー」を開き、記録された所有者の合計を照会します。',
    'owners_partial': '不完全なスキャン: 省略された/読み取り不可能なバイトとその所有者は不明のままです。',
    'owners_summary': (
        '{count} 所有者グループ。 {shown} を表示しています。 {files} ファイル、{size}。不明な所有者: {unknown'
        '_files} ファイル、{unknown_size}。'
    ),
    'owners_hint': (
        '全体スキャン、ファイル所有者のみ。ディレクトリの所有権は子孫を割り当てません。 POSIX uid はスキャン'
        'の統計から取得されます。 Windows で、[オプション] → [Windows ファイル所有者のキャプチャ] を有効にし'
        'て再スキャンします。無効、失敗、変更されたクエリ、またはクラウド/オフライン クエリは不明のままです。'
        '名前は uid/SID にフォールバックできます。名前付きの割り当ては推定されたままであり、名前ごとのハード '
        'リンクの数は変わりません。所有権は、実際の使用または削除の許可を証明するものではありません。クリーン'
        'アップアクションは用意されていません。'
    ),
    'bin_labels_refresh': 'ビンの合計を更新する',
    'bin_labels_hint': (
        '最大 256 個の準備完了ドライブの読み取り専用スナップショット。スキャンされたドライブが優先されます。 '
        'POSIX の合計は論理ペイロード バイトです。利用できない合計や一部の合計がゼロになることはありません。'
        'スコープは重複する可能性があります。合計しないでください。クエリを更新します。これはクリーンアップア'
        'クションを準備するものではありません。'
    ),
    'bin_label_scope_unknown': 'このスキャンのドライブのごみ箱: スコープは照会されません',
    'bin_label_unqueried': '{root} ごみ箱: クエリされませんでした',
    'bin_label_total': '{root} ごみ箱: {size}、{count} アイテム',
    'bin_label_partial': '{root} ごみ箱: 合計は不明です。既知の {size}、{count} アイテム',
    'action_file_times': 'ファイル時間…',
    'action_file_times_tip': 'このスキャンで記録されたアクセス日と作成日をフィルターします。',
    'action_capture_file_times': 'ファイルのアクセス/作成時間をキャプチャする',
    'action_capture_file_times_tip': (
        'デフォルトではオフです。今後のスキャンでは、通常のファイルごとに 16 バイトが追加されます。有効にした'
        '後に再スキャンする'
    ),
    'column_accessed': '記録されたアクセス',
    'column_created': '作成されました',
    'file_times_hint': (
        '[オプション] → [ファイルのアクセス/作成時間をキャプチャ] を有効にしてから、再スキャンします。通常の'
        'ファイルのみ。ディレクトリ/リンク、および利用できない作成日は不明のままです。アクセス日は、バックグ'
        'ラウンド ツールによって無効化、遅延、または更新される可能性があります。実際の使用を証明することは決'
        'してありません。 POSIX ctime は作成時間ではありません。このビューでは、クリーンアップ アクションは準'
        '備されません。'
    ),
    'file_times_accessed': '…以降開かれていません (アクセス日の記録)',
    'file_times_created': '少なくとも…前に作成されました',
    'file_times_mode': '記録年齢モード',
    'file_times_days': '日数',
    'file_times_reading': '記録されたファイルの日付をフィルタリングしています…',
    'file_times_summary': (
        '{count} は一致、{size}; {shown} を表示しています。 {unknown}/{total} ファイルの日付は使用できないか'
        '、将来の日付です。'
    ),
    'file_times_policy_disabled': (
        'NTFS は、アクセス更新が無効になっていると報告します。アクセス年齢の一致は利用できません。作成フィル'
        'タリングは引き続き利用可能です。レジストリ設定には再起動が必要な場合がありますが、すべてのファイルシ'
        'ステムが記述されているわけではありません。'
    ),
    'file_times_policy_unknown': (
        'NTFS アクセス更新構成が不明です。アクセス年齢の一致は利用できません。作成フィルタリングは引き続き利'
        '用可能です。'
    ),
    'file_times_policy_enabled': (
        'NTFS レジストリ レポートは更新へのアクセスが有効になっています。保留中の再起動、ファイルシステム/プ'
        'ロバイダーの設定、および延期された更新が日付に影響を与える可能性があります。'
    ),
    'file_times_policy_platform': (
        'ファイルシステム/プロバイダーの設定により、アクセスの更新が延期または抑制される場合があります。これ'
        'らの日付を記録されたメタデータとして扱います。'
    ),
    'action_programs': 'インストールされているプログラム…',
    'action_programs_tip': 'このスキャンでインストーラー/ゲームのメタデータとインストール フォルダーを比較します',
    'program_name': 'プログラム・ゲーム',
    'program_source': 'メタデータソース',
    'program_version': 'バージョン/ビルド',
    'program_publisher': '出版社',
    'program_reported': '報告された推定値',
    'program_scanned': 'スキャンされた論理バイト',
    'program_allocated': 'スキャンされた名前付き割り当て',
    'program_coverage': '録音フォルダーの範囲',
    'program_location': 'インストールフォルダ',
    'program_registry': 'Windows レジストリ',
    'program_steam': 'Steam マニフェスト',
    'program_epic': 'エピックマニフェスト',
    'program_outside': '正確にスキャンされたフォルダーがありません',
    'program_hint': (
        'Windows 登録と認識された Steam/Epic マニフェストをアンインストールします。このスキャンで正確なフォル'
        'ダーにのみ一致しました。 Epic の修正された ProgramData マニフェスト フォルダーも読み込まれます。報告'
        'されるサイズは推定値です。欠落しているメタデータは不明のままです。共有/ネストされたフォルダーは重複'
        'する可能性があります。行を合計したり、回復可能な領域として扱ったりしないでください。ポータブル/パッ'
        'ケージ化されたアプリが存在しない場合があります。ダブルクリックすると、録音されたフォルダーが選択され'
        'ます。 Ctrl+C で行をコピーします。アンインストールは、Windows またはランチャーを通じてのみ行ってくだ'
        'さい。'
    ),
    'program_reading': 'インストールメタデータを読み取り中…',
    'program_summary': (
        '{count} 件中 {shown} 件のインストールを表示しています。 {issues} メタデータ項目が使用不可/不正な形式'
        '/省略されています'
    ),
    'program_failed': 'インストールを読み取れません: {reason}',
    'program_uninstall_page': 'Windows インストール済みアプリの設定を開きます',
    'program_open_failed': 'Windows はインストール済みアプリの設定ページを開けませんでした',
    'action_history': 'スキャン履歴…',
    'action_history_tip': 'このルートのサイズを経時的に確認し、以前のスキャンと比較します',
    'action_history_settings': 'スキャン履歴の設定…',
    'action_history_settings_tip': 'ローカル スキャン メタデータを有効にし、そのグローバルな保存制限を設定します',
    'history_enable': '完了したフルスキャンをローカルに保存する',
    'history_settings_hint': (
        '履歴にはフォルダー名、パス、合計、カバレッジが保存されますが、ファイルの内容は保存されません。デフォ'
        'ルト: 有効、すべてのルートで合計 1 GiB。認識された履歴メタデータのみが古いものから順に削除されます。'
        '無効にすると、既存の履歴が読み取れる状態が維持されます。変更は今後のフル スキャンに適用されます。下'
        '限は次回の保存時に有効になります。'
    ),
    'history_limit': '合計履歴制限',
    'history_time': 'スキャン時間',
    'history_logical': '論理バイト',
    'history_allocated': '割り当てられた名前付きバイト',
    'history_coverage': '適用範囲',
    'history_incomplete': '不完全;既知のデータのみ',
    'history_complete': '完全な記録されたカバレッジ',
    'history_chart': '論理フォルダーのサイズの経時変化',
    'history_chart_range': '{first}: {before}; {last}: {after}',
    'history_empty': 'このルートのスキャンは保持されていません',
    'history_compare': '選択したスキャンと現在の結果を比較する',
    'history_reading': 'ローカルスキャン履歴を読み取っています…',
    'history_hint': (
        'このルートに対して保持されている最新の 1,000 件のフル スキャン。停止したスキャンとブランチの再スキャ'
        'ンは保存されません。不完全なスキャンでは、既知のデータのみが記述されます。フォルダーが見つからないか'
        'らといって、削除されたことは証明されません。合計ではハードリンク名を個別にカウントします。違いはメタ'
        'データであり、コンテンツの検証ではありません。'
    ),
    'history_summary': (
        '{count} 件中 {shown} 件のスキャンを表示しています。 {invalid} メタデータ ファイルが無効または使用で'
        'きません'
    ),
    'history_failed': '履歴を読み取れません: {reason}',
    'history_save_failed': 'スキャンは完了しましたが、履歴を保存できませんでした: {reason}',
    'action_scan_workers': 'スキャン作業者…',
    'action_scan_workers_tip': '新しいスキャンの同時実行性を選択します。高いほど速いとは限りません',
    'workers_prompt': (
        '新しいスキャンのワーカー (1 ～ 32)。デフォルトは {default} です。ネットワーク共有が遅い場合は、ワー'
        'カーを増やすことでメリットが得られる可能性があります。過剰な同時実行により、ディスク/サーバーに過負'
        '荷がかかる可能性があります。スキャンを実行すると、既存のワーカーが保持されます。実際の UNC のパフォ'
        'ーマンスはあなたのシェアに依存します。'
    ),
    'action_bins': 'ごみ箱…',
    'action_bins_tip': 'ビンの合計と明示的なスコープ指定された OS の空の確認',
    'bin_finder_empty': 'マウントされているすべてのボリュームの Finder ゴミ箱を空にします…',
    'bin_finder_all': 'マウントされているすべてのボリューム (Finder 規模のゴミ箱)',
    'bin_finder_scopes': '現在のユーザーのゴミ箱スコープ:\n{scopes}\n\nマウントされたボリューム:\n{roots}',
    'bin_finder_first': (
        '現在のユーザーの Finder マウントされているすべてのボリュームのゴミ箱を空にしますか?\n\n{root}\n\n論'
        '理ペイロード: {size}\nアイテム: {count}'
    ),
    'bin_finder_irreversible': (
        'マウントされているすべてのボリュームについて、現在のユーザーの Finder のごみ箱を完全に空にしますか？'
        '\n\n{root}\n\n内容の論理サイズ: {size}\n項目数: {count}\n\nこの操作は元に戻せません。Finder の処理中'
        'に新しく入った項目も削除される場合があります。選択した行にかかわらず、マウントされているすべてのごみ'
        '箱に作用します。OS の処理はキャンセルできません。自動操作の許可やアクセス権の問題で一部だけ処理され'
        'る場合があり、Finder の処理が続いている可能性もあります。'
    ),
    'bin_preparing': '{root} の正確なゴミ箱スコープを確認しています…',
    'bin_no_approval': '完全に空ではないゴミ箱の承認はありません。リフレッシュしてもう一度見直してください。',
    'bin_scope_first': (
        'これらの現在のユーザーのゴミ箱ペイロード/受信スコープを空にしますか?\n\n{root}\n\n論理ペイロード: {s'
        'ize}\nアイテム: {count}'
    ),
    'bin_scope_irreversible': (
        '確認した次の範囲の内容を完全に削除しますか？\n\n{root}\n\n内容の論理サイズ: {size}\n項目数: {count}'
        '\n\nこの操作は元に戻せません。リンク先をたどらず、リンク自体を削除します。変更された項目は処理しませ'
        'ん。失敗時には一部だけ処理される場合があります。開始後はごみ箱を空にする操作をキャンセルできません。'
    ),
    'bin_partial': '{count} 件のレビュー済みアイテムを削除しました。残りの失敗: {reason}',
    'bin_empty': '選択したドライブのごみ箱を空にする…',
    'bin_first': '{root}?\n\n報告されたサイズ: {size}\nアイテム: {count} のごみ箱を空にします',
    'bin_irreversible': (
        '{root} のごみ箱に現在あるすべての項目を完全に削除しますか？\n\n報告されたサイズ: {size}\n項目数: {co'
        'unt}\n\nこの操作は元に戻せません。OS の処理中に新しく入った項目も削除される場合があります。開始後は '
        'OS の処理をキャンセルできません。'
    ),
    'bin_running': '{root} のごみ箱を空にしています。 OSの操作を待っています…',
    'bin_failed': '空化が完了しませんでした: {reason}',
    'bin_hint': (
        'マウントされたボリュームを 1 つ選択します。 Windows は、現在のユーザーの OS ビンを空にします。 Linux'
        ' インベントリはファイル/情報スコープを認識しました。 2 つの質問は、永久削除前の正確な範囲と合計を示'
        'します。 「停止」はアンケートをキャンセルします。アクティブな空化が完了する必要があります。 macOS は'
        '、グローバル レビュー後にマウントされた Finder ゴミ箱をすべて空にします (ネイティブ検証保留中)。容量'
        '/ビンの値は後で更新されます。再スキャンしてメイン ツリーを更新します。'
    ),
    'action_volumes': 'ドライブの概要…',
    'action_volumes_tip': 'マウントされたボリューム、容量、割り当て単位、およびごみ箱の合計を検査する',
    'volume_root': 'マウントされたルート',
    'volume_name': 'ボリューム名',
    'volume_fs': 'ファイルシステム',
    'volume_total': '合計',
    'volume_used': '中古品',
    'volume_free': 'ご利用いただけます',
    'volume_cluster': '割り当て単位',
    'volume_trash': 'ごみ箱のバイト数',
    'volume_trash_count': 'アイテムをビンに入れる',
    'volume_reading': 'マウントされたボリュームとごみ箱の合計を読み取り中…',
    'volume_summary': (
        '{count} のうち、マウントされた {shown} 個のボリュームを表示しています。ダブルクリックしてスキャンし'
        'ます。'
    ),
    'volume_trash_partial': '合計は不明 ({known} は判明)',
    'volume_hint': (
        'OS 容量のスナップショット。利用可能なスペースには予約または割り当てが含まれない場合があります。マウ'
        'ントを繰り返すと容量を共有できるため、行を合計しないでください。 Windows アロケーション ユニットはク'
        'ラスターです。 POSIX ユニットはファイルシステムのフラグメントであり、最適な転送サイズではありません'
        '。ゴミ箱には、再利用可能な領域ではなく、OS によって報告された Windows 合計または既知の POSIX 論理ペ'
        'イロード バイトが表示されます。ディレクトリ/受信メタデータと共有割り当ては除外されます。エラーは不明'
        'のままです。 Stop は現在の OS 呼び出しを待ちます。キャンセルされたアンケートは破棄されます。 Ctrl+C '
        'で行をコピーします。ここでは空にするアクションは提供されません。'
    ),
    'action_export_report_html': 'スキャンレポート(HTML)…',
    'action_export_report_html_tip': '3 つのチャート画像が埋め込まれた自己完結型レポートを保存する',
    'action_export_report_xlsx': 'スキャンレポート（Excel）…',
    'action_export_report_xlsx_tip': 'レポート リストを別の Excel ワークシートに保存する',
    'html_filter': 'HTML レポート (*.html)',
    'xlsx_filter': 'Excel ワークブック (*.xlsx)',
    'report_title': 'FileTree スキャン レポート',
    'report_note': (
        '既知の記録された範囲のみ。配分は目安です。見出しのカウントは、表示/合計を示します。最上位のフォルダ'
        'ーが重なっています。行を追加しないでください。最大のファイルとフォルダーは 1,000 に制限されます。フ'
        'ァイルタイプは10,000まで。サイズはバイトです。年齢は、最終アクセスではなく、記録された変更時刻を使用'
        'します。利用できない日付は、既存の最も古い年齢グループに属します。 HTML チャートには、スキャン ルー'
        'ト全体が境界付きジオメトリで表示されます。 Excel テキストはエスケープされ、制御文字は 16 進数で表示'
        'され、セルは 32,767 文字に制限され、16 桁以上の整数は正確なテキストとして保存されます。'
    ),
    'report_bytes': '論理バイト',
    'report_allocated': '割り当てられたバイト数 (推定)',
    'report_created': 'レポートが作成されました',
    'report_reference': '年齢の目安',
    'report_skipped': 'スキップされたフォルダー',
    'report_denied': '読み取り不可能なフォルダー',
    'report_pending': '保留中のフォルダー',
    'report_summary': '概要',
    'report_notes': '注意事項',
    'report_field': 'フィールド',
    'report_value': '値',
    'report_top_folders': '最大のフォルダー (重複)',
    'report_categories': 'カテゴリー',
    'action_projects': 'プロジェクトと再構築可能なデータ…',
    'action_projects_tip': '記録されたプロジェクト、Git、生成されたデータのサイズを検査する',
    'project_path': '企画・運営店舗',
    'project_kind': '検出された種類',
    'project_other': 'ソース・その他',
    'project_git': '.git',
    'project_generated': '再構築可能なデータ',
    'project_coverage': '適用範囲',
    'project_partial': '不完全',
    'project_recorded': '記録範囲',
    'project_hint': (
        '既知の論理バイトのみ。ネストされたプロジェクトは重複します。 Git ポインター ファイルでは、外部メタデ'
        'ータが省略されます。生成されたデータにはカスタム ファイルが含まれる場合があります。移動する前に確認'
        'してください。 Maven、グローバル Gradle、Docker ストアは個別に表示されます。内容物は使い捨てではない'
        'と考えられます。'
    ),
    'project_reading': '記録されたプロジェクト データを検査しています…',
    'project_summary': '検出された {count} のうち最大のプロジェクト/ストア {shown} を表示しています。',
    'project_review': '適格な再構築可能なエントリを確認してください…',
    'project_review_count': (
        '現在の年齢、適用範囲、クリーンアップ ポリシーに基づいて対象となる {count} 件のうち、最大 {shown} 件'
        'のエントリを確認します。停止したスキャンではエントリを提案できません。'
    ),
    'project_git_kind': 'Git',
    'project_python': 'パイソン',
    'project_node': 'Node.js',
    'project_rust': 'さび',
    'project_jvm': 'JVM',
    'project_conda': 'コンダプロジェクト',
    'project_python_environment': 'Python環境',
    'project_conda_environment': 'Conda環境',
    'project_maven_store': 'メイブンストア',
    'project_gradle_store': 'グローバル Gradle ストア',
    'project_docker_store': 'Dockerデータ',
    'action_git_history': 'Gitの歴史…',
    'action_git_history_tip': 'すべての Git 参照から到達可能な最大のオブジェクトを検査する',
    'git_oid': 'オブジェクトID',
    'git_kind': 'オブジェクトの種類',
    'git_length': '非圧縮長さ',
    'git_type_blob': 'ファイルの内容 (BLOB)',
    'git_type_tree': 'ディレクトリリスト (ツリー)',
    'git_type_commit': 'コミット',
    'git_type_tag': '注釈付きタグ',
    'git_hint': (
        '読み取り専用の Git 配管はすべての参照を検査し、最大 1,000 個のオブジェクトを保持します。サイズは非圧'
        '縮の長さであり、ディスク割り当てや回復可能な領域ではありません。 Git のオブジェクト名のヒントがあい'
        'まいになる可能性があるため、名前は省略されています。 Ctrl+C はオブジェクト ID/行をコピーします。オプ'
        'ションのロック、自動メンテナンス、遅延ネットワーク取得は無効になっています。 Git は --no-lazy-fetch '
        'をサポートする必要があります。リポジトリ所有権エラーはバイパスされません。停止はキャンセルします。こ'
        'こでは gc が実行されることはありません。'
    ),
    'git_reading': 'Git 履歴を検査しています…',
    'git_summary': '{count} 件中 {shown} 件の到達可能なオブジェクトを表示しています。非圧縮合計 {size}。',
    'git_gc_loose': (
        'Git gc は {count} 個の孤立したオブジェクトを統合することがありますが、これらの最大のオブジェクトは参'
        '照から到達可能なままであり、削除されません。実際の節約量やその他の到達不能/reflog データは不明です。'
    ),
    'git_gc_packed': (
        '固定するためのばらばらの物体はありません。 Git gc は、refs がこれらのオブジェクトを保持している間、'
        'これらのオブジェクトを削除しません。その他の到達不能/reflog データと実際の節約量は測定されませんでし'
        'た。'
    ),
    'git_failed': 'Git インスペクションが失敗しました: {reason}',
    'tree_filter_placeholder': '展開済みフォルダーを絞り込み…',
    'tree_filter_hint': (
        'すでに展開されているフォルダー内でのみ名前を照合します (大文字と小文字は区別されません)。祖先は目に'
        '見えるままになります。折りたたまれたコンテンツは検索されません。フィルタをクリアしてツリーを復元しま'
        'す。チャート/リストで非表示のエントリを選択すると、フィルターがクリアされます。スキャンの合計とエク'
        'スポートは変更されません。'
    ),
    'action_live_compare': '2 つのフォルダーを比較してください…',
    'action_live_compare_tip': '新しい相対パスを比較し、要求されたファイルのペアのみを検証します',
    'compare_choose_left': '左側のフォルダーを選択してください',
    'compare_choose_right': '適切なフォルダーを選択してください',
    'compare_relative': '相対パス',
    'compare_state': '比較',
    'compare_left_size': '左のサイズ',
    'compare_right_size': '適切なサイズ',
    'compare_left_time': '左が変更されました',
    'compare_right_time': '右修正',
    'compare_roots': '左: {left}\n右: {right}',
    'compare_hint': (
        '読み取り専用: 正確な Unicode/大文字と小文字の名前が一致します。リンクはたどられません。サイズや時間'
        'が等しいことは、内容が等しいことを証明するものではありません。ファイル ペアを選択し、Stop が利用可能'
        'な状態で完全なハッシュを確認します。変更され、読み取り不能になり、既知のクラウド ファイルは利用でき'
        'ないままになります。結果は、このスキャン/検証時間を指します。コピー、移動、同期は実行されません。 Ct'
        'rl+C で行をコピーします。 CSV は、表示されている行のみ (最大 10,000 行) をエクスポートします。'
    ),
    'compare_reading': '両方のフォルダーをスキャンしています…',
    'compare_error': '比較またはエクスポートに失敗しました: {reason}',
    'compare_hashing': '選択したファイル ペアを確認しています…',
    'compare_verify': '選択した内容を確認する',
    'compare_summary': '{count} 件中 {shown} 件の相対パスを表示しています (制限 10,000)。',
    'compare_incomplete': '補償内容は不完全です。読み取り不可能なスコープ内で欠落しているパスは不明のままです。',
    'compare_unavailable': '利用できないか変更されました',
    'compare_link': 'リンク;内容が読まれていない',
    'compare_only_left': '左側のみ',
    'compare_only_right': '右側のみ',
    'compare_different_kind': 'さまざまなエントリータイプ',
    'compare_folder': '両面にフォルダーあり',
    'compare_different_size': 'さまざまなサイズ',
    'compare_different_time': 'さまざまな時代。内容未チェック',
    'compare_unchecked': '内容は未確認',
    'compare_identical': '完全なハッシュの一致',
    'compare_different_bytes': '異なる内容',
    'problem_mount_boundary': 'マウント境界: コンテンツはスキャンされません',
    'action_special_files': 'クラウドと特殊ファイル…',
    'action_special_files_tip': '記録されたリコール、オフライン、圧縮およびスパース ファイルの状態を検査する',
    'special_states': '記録状態',
    'special_content_size': 'コンテンツ全体のサイズ',
    'special_recall': 'アクセス時にリコールされる可能性があります',
    'special_offline': 'オフライン',
    'special_compressed': '圧縮された',
    'special_sparse': 'まばらな',
    'special_allocation_low': '割り当てが低くなります。原因不明',
    'special_reading': '記録されたファイルのメタデータを読み取り中…',
    'special_hint': (
        'このリストはスキャン メタデータのみを使用します。ファイルを開いたりダウンロードしたりすることはあり'
        'ません。リコール/オフライン フラグは、OneDrive、Dropbox、またはその他のプロバイダーを記述することが'
        'できます。プロバイダーと、すでにローカルにどれだけあるのかを推測することはできません。コンテンツ全体'
        'のサイズは、オンライン コンテンツを含む論理長です。ダウンロード後の割り当ては不明です。まばらなホー'
        'ル、圧縮、および常駐データにより、割り当てが削減される可能性があります。リコール/オフライン エントリ'
        'のディスク上のゼロは推定値であり、クラウド割り当ての測定値ではありません。ダブルクリックすると、スキ'
        'ャンされたエントリが選択されます。 Ctrl+C は選択した行をコピーします。'
    ),
    'special_summary': (
        '{count} 件中 {shown} 件の一致するファイルを表示しています。全コンテンツ {size};割り当て {allocated} '
        'を記録しました。利用できないファイル メタデータ: {unknown}。最大の 1,000 が保持されます。'
    ),
    'special_partial': 'スキャン範囲は不完全です。表示されていないファイルは不明のままです。',
    'action_shell_integration': 'エクスプローラーの統合…',
    'action_shell_integration_tip': (
        'エクスプローラーのフォルダー メニューで [FileTree でスキャン] を追加または削除します'
    ),
    'shell_enabled': 'エクスプローラーのフォルダー メニューに FileTree でスキャンを追加',
    'shell_scan': 'FileTree でスキャン',
    'shell_hint': (
        '変更を保存するのは、アカウントのフォルダー メニューのみです。管理者権限は必要ありません。 Windows 11'
        ' で、[その他のオプションを表示] を確認します。エントリを削除するには、ここでこれをオフにします。実行'
        '可能ファイルまたはソース チェックアウトを移動した後、再度登録します。'
    ),
    'shell_failed': 'Explorer の統合を変更できませんでした。\n{reason}',
    'menu_properties': 'プロパティ',
    'properties_failed': 'Windows は次のプロパティを開けませんでした:\n{path}',
    'menu_theme': 'テーマ',
    'theme_system': 'システム',
    'theme_light': 'ライト',
    'theme_dark': '暗い',
    'chart_access_keys': (
        '矢印キーでレンダリングされたエントリを選択します。 Enter を押すとフォルダーが開きます。バックスペー'
        'スが上がります。グループ化されたエントリまたは非表示のエントリにはフォルダ ツリーを使用します。'
    ),
    'chart_access_tree_keys': (
        'Up/Down でカードを選択します。右/左でフォルダーを展開/折りたたみます。 Enter を押すとフォルダーが開'
        'きます。バックスペースが上がります。'
    ),
    'chart_access_folder': '表示中のフォルダー: {path}',
    'chart_access_selected': (
        '選択済み: {path}。サイズ {size};ディスク {allocated} 上。 {files} ファイル、{folders} フォルダー。'
    ),
    'system_file_hibernate': (
        '休止状態と高速スタートアップ状態。 Windows がこのファイルを管理します。管理者は、powercfg /hibernate'
        ' off を使用して休止状態を無効にすることができます。これにより、休止状態も削除され、高速スタートアッ'
        'プに影響を与える可能性があります。 FileTree は電源設定のみを開きます。'
    ),
    'system_file_pagefile': (
        '仮想メモリのバッキング ファイル。 Windows はサイズを自動的に管理できます。 [詳細設定] タブの [パフォ'
        'ーマンス設定] で [仮想メモリ] を確認します。これを減らすと、アプリケーションやクラッシュ ダンプに影'
        '響を与える可能性があります。'
    ),
    'system_file_swapfile': (
        'Windows スワップ バッキング ファイル (一時停止されたアプリ データを含む)。 Windows は仮想メモリと合'
        'わせて管理します。システム メモリの設定を削除するのではなく、見直してください。'
    ),
    'system_file_old': (
        '以前の Windows インストール。 「ディスク クリーンアップ」→「システム ファイルのクリーンアップ」で以'
        '前の Windows インストールを確認します。これを削除すると、そのインストールに戻ることができなくなりま'
        'す。'
    ),
    'system_file_recycle': (
        '削除されたエントリは、ごみ箱が空になるまでディスク領域を占有します。ごみ箱またはストレージ センスを'
        '確認します。空にすることは永続的です。'
    ),
    'system_file_restore': (
        'システム メタデータ、復元ポイント、シャドウ コピー。 「システム保護」→「構成」を確認して、復元ポイン'
        'トの制限を設定します。バックアップ所有のシャドウ コピーには、独自のバックアップ ツールが必要な場合が'
        'あります。未読のバイトは不明のままです。'
    ),
    'system_file_winsxs': (
        'Windows コンポーネント ストア。多くのエントリは Windows ファイルとハード リンクを共有しているため、'
        '名前ごとの合計が個別のストレージを過大評価する可能性があります。 Windows [ディスク クリーンアップ] →'
        ' [システム ファイルのクリーンアップ] で [アップデート クリーンアップ] を使用します。コンポーネントを'
        '手動で削除しないでください。'
    ),
    'system_file_updates': (
        'Windows ダウンロードデータを更新します。 Windows を確認してください。 [ディスク クリーンアップ] → ['
        'システム ファイルのクリーンアップ] を使用して一時ファイルを更新します。アクティブなダウンロードの管'
        '理は更新サービスに任せてください。'
    ),
    'system_file_delivery': (
        'Windows アップデートとアプリの配信の最適化ダウンロード キャッシュ。ディスク クリーンアップで配信最適'
        '化ファイルを確認します。 Windows はアクティブな転送を管理します。'
    ),
    'system_tool_power': '電源設定を開きます…',
    'system_tool_memory': '詳細なシステム設定を開きます…',
    'system_tool_cleanup': 'ディスククリーンアップを開きます…',
    'system_tool_storage': 'ストレージセンスを開く…',
    'system_tool_restore': 'オープンシステム保護…',
    'system_tool_failed': 'Windows ツールを開けませんでした。',
    'trash_skip_system_managed': (
        'Windows はこのエントリを管理します。代わりに詳細でシステム ツールを使用してください'
    ),
    'type_locations_title': 'フォルダーを含む (最大 1,000)',
    'type_location_size': '適合サイズ',
    'type_locations_tip': (
        '合計には、各フォルダー内の直接一致するファイルが含まれます。サブフォルダーは重複せずに別々に作成され'
        'ます。'
    ),
    'action_export_list': '現在のリスト (CSV)…',
    'action_export_list_tip': 'アクティブなリストのすべての行を、表示されているフィルターと並べ替え順に保存します。',
    'list_changed': 'キャプチャ中にリストが変更されました。もう一度エクスポートまたはコピーしてみてください。',
    'details_title': '詳細',
    'details_empty': 'エントリを選択して詳細を表示します',
    'details_live': 'スキャンが終了すると配信可能になります。',
    'details_loading': 'タイプと年齢分布を計算しています…',
    'details_recorded': (
        '記録されたファイルの合計のみ。未読のエントリはこれらのディストリビューションの外にあります。フォルダ'
        'ーの変更は最も新しい記録日です。'
    ),
    'details_bucket': '{label}: {size} · {count} ファイル',
    'breadcrumbs_back': '戻る (Alt+左)',
    'breadcrumbs_forward': '進む (Alt+右)',
    'breadcrumbs_more': '…',
    'breadcrumbs_more_tip': '以前の先祖を表示する',
    'action_print_view': '現在のビューを印刷…',
    'action_print_view_tip': 'システムの印刷ダイアログを使用して、表示された結果を 1 ページに印刷します',
    'action_export_view_pdf': '現在のビュー (PDF)…',
    'action_export_view_pdf_tip': '表示された結果を 1 つの適合 PDF ページに保存します',
    'pdf_filter': 'PDFドキュメント(*.pdf)',
    'view_pdf_exported': '保存された現在のビュー: {path}',
    'print_failed': 'ビューを印刷できませんでした: {reason}',
    'print_submitted': 'プリンターに送信されたビュー',
    'action_export_chart_png': '画面上のグラフ (PNG)…',
    'action_export_chart_png_tip': '現在のビューポートを含む表示されているグラフを保存します。',
    'action_export_chart_svg': 'バーまたはサンバースト (SVG)…',
    'action_export_chart_svg_tip': '完全に囲まれたバーまたはリングをベクトル図形およびテキストとして保存',
    'png_filter': 'PNG画像(*.png)',
    'svg_filter': 'SVG画像(*.svg)',
    'graphic_exported': '保存されたチャート: {path}',
    'treemap_colours_age': '修正された年齢による',
    'age_colour_unknown': '日付不明',
    'age_colour_tip': (
        '変更されてからの経過時間。フォルダーの色には、記録された最新の変更が使用されます。灰色は使用可能な日'
        '付がないことを意味します。グループ化されたタイルは灰色のままです。'
    ),
    'action_gentle': '穏やかなスキャン',
    'action_gentle_tip': '新しいスキャンの CPU と I/O の優先順位が低くなります。もっと時間がかかるかもしれない',
    'scan_priority_warning': '一部のスキャン優先度設定を適用できませんでした: {reason}',
    'scan_pause': '一時停止',
    'scan_resume': '再開',
    'scan_pause_tip': (
        '新しいフォルダーの読み取りを一時停止します。現在の読み取りが終了します。一時停止中に動作を停止します'
        '。'
    ),
    'scan_paused': '一時停止 — {progress}',
    'scan_analysing': 'フォルダーの読み取りが完了しました。結果を分析中…',
    'column_drive_share': 'ドライブの%',
    'columns_reset': '列をリセット',
    'drive_share_tip': (
        '論理バイトをボリュームの合計容量で割った値。ハードリンク名は個別にカウントされます。これは割り当てら'
        'れたスペースでも回復可能なスペースでもありません。容量が利用できないか古い場合は不明です。'
    ),
    'action_recent_actions': '最近の行動…',
    'action_recent_actions_tip': '保持されている操作メタデータを検査し、編集された監査レポートをエクスポートします',
    'journal_time': '時間 (UTC)',
    'journal_source': '元のパス',
    'journal_identity': 'デバイス/ファイルのアイデンティティ',
    'journal_result': '結果',
    'journal_detail': '詳細',
    'journal_destination': 'ゴミ箱の送り先',
    'journal_reason_duplicates': '明示的な重複の決定',
    'journal_status_approved': '結果が不明 (承認済みのみ)',
    'journal_status_moved': 'ゴミ箱に移動しました',
    'journal_status_skipped': 'スキップされました',
    'journal_status_failed': 'プラットフォームの移動に失敗しました',
    'journal_reading': '保持されたアクションを読み取り中…',
    'journal_hint': (
        '最新の 500 件のアクション。メタデータのみ、90 日間 / 50 MB 保持されます。承認のみのイベントの最終結'
        '果は不明です。記録されたゴミ箱パスは復元を保証しません。'
    ),
    'journal_summary': (
        '{count} アクションが表示されました。 {invalid} レコードが破損しており、{unavailable} セグメントが使'
        '用できません。'
    ),
    'journal_read_failed': '操作ジャーナルを読み取れませんでした: {reason}',
    'journal_write_failed': (
        'ジャーナルの書き込みまたは保存に失敗しました。残りの動きは可能な限り停止されました。最近のアクション'
        'が不完全である可能性があります。\n\n{reason}'
    ),
    'trash_skip_journal': '承認されたアクションを記録できませんでした。何も動かなかった',
    'journal_export': '編集されたCSVをエクスポート…',
    'journal_exported': 'ホーム ディレクトリのプレフィックスを編集して保存された監査レポート。',
    'duplicate_folder_match': '{copy} = {original} ({size}、{files} ファイル; 一致する検索スナップショット)',
    'duplicate_folder_tip': (
        '一致する名前、サイズ、検証済みのハッシュ、および空のフォルダー構造。読み取り専用。クリーンアップの承'
        '認ではありません。'
    ),
    'duplicates_keep_selected': '選択したコピーを保持する',
    'duplicates_kept_name': '保持: {name}',
    'duplicates_kept_path': 'コピーを保持: {path}。',
    'duplicates_choose_keeper': 'エクストラを選択する前に、このグループで保持されているコピーを選択してください。',
    'duplicates_group_blocked': 'グループはそのまま残されました。再スキャンが必要です: {reason}',
    'trash_skip_duplicate_choose': '保存されたコピーを選択し、グループを再度確認します',
    'trash_skip_duplicate_keep': '保存されたコピーが選択されました。グループはそのまま残されました。再スキャン',
    'trash_skip_duplicate_unverified': 'このグループには検証済みのハッシュがありません。再スキャンして再度検索する',
    'trash_skip_duplicate_hard_links': (
        'コピーにはハードリンク エイリアスが含まれます。グループはそのまま残されました。再スキャン'
    ),
    'trash_skip_duplicate_content': (
        'グループの内容が変更されたか、再ハッシュできませんでした。再スキャンして再度検索する'
    ),
    'menu_options': 'オプション',
    'action_cleanup_policy': 'クリーンアップポリシー…',
    'action_cleanup_policy_tip': 'ルールを有効にし、最低年齢を変更し、クリーンアップ提案からパスを除外します。',
    'policy_enabled': '有効',
    'policy_age': '最低経過日数（日数）',
    'policy_age_for': '{rule} の最低年齢',
    'policy_enabled_for': '{rule} を有効にする',
    'policy_hint': (
        'ポリシーの変更は提案のみに影響します。手動リスク ルールはチェックされないままになります。保存する前'
        'にプレビューします。'
    ),
    'policy_exclusions': (
        'これらのパスまたは名前は決して提案しないでください (1 行に 1 つ、パスは絶対パスである必要があります)'
        '。スキャンは変更されません。'
    ),
    'policy_preview': '変更のプレビュー',
    'policy_import': 'インポートポリシー JSON…',
    'policy_preview_needed': '保存する前に現在の設定をプレビューします。',
    'policy_preview_running': '候補数と論理サイズを比較しています…',
    'policy_preview_result': (
        '{added} 候補を追加します ({size})。 {removed} 候補 ({removed_size}) を削除します。何も動かなかった。'
    ),
    'policy_preview_partial': 'スキャンは不完全です。表示されていない候補とバイトは不明のままです。',
    'policy_no_scan': 'スキャンが完了していません: 効果を測定できません。これらの設定は、今後の提案に適用されます。',
    'policy_invalid': (
        '無効なポリシーです。サポートされているルール キー、はい/いいえフラグ、年齢 0 ～ 36500、および絶対パ'
        'スまたは名前パターンを使用します。'
    ),
    'policy_saved': 'クリーンアップ ポリシーが保存されました。提案が更新されています。',
    'policy_saved_invalid': (
        '保存されたクリーンアップ ポリシーが無効です。オプションでポリシーが確認されるまで、提案は無効になり'
        'ます。'
    ),
    'cleanup_review_manual': '手動で確認する',
    'cleanup_evidence': (
        'カテゴリ: {category};最低有効期間: {days} 日。リスク: {risk}。証拠: {evidence} 再構築/結果: {rebuild'
        '}'
    ),
    'cleanup_category_temporary': '一時ファイル',
    'cleanup_category_cache': 'ダウンロード/生成されたキャッシュ',
    'cleanup_category_application_state': 'アプリケーションの状態',
    'cleanup_category_build': 'プロジェクトのビルド出力',
    'cleanup_category_downloads': 'ユーザーのダウンロード',
    'cleanup_risk_low': 'リスクが低い。移動前に確認する',
    'cleanup_risk_manual': '手動レビュー。チェックなしで開始します',
    'cleanup_rebuild_temp': (
        '所有しているアプリケーションを閉じます。一時データは必ずしも再作成できるわけではありません。'
    ),
    'cleanup_rebuild_browser_cache': (
        'ブラウザを閉じます。キャッシュされたページを再度ダウンロードします。プロフィールとブックマークは除外'
        'されます。'
    ),
    'cleanup_rebuild_thumbnails': 'ファイルマネージャーを閉じます。必要に応じてプレビューが再度生成されます。',
    'cleanup_rebuild_crash_dumps': (
        '必要な衝突証拠を保管してください。過去のクラッシュ ダンプを再作成することはできません。'
    ),
    'cleanup_rebuild_package_caches': (
        'パッケージ マネージャーを使用して再度ダウンロードします。ネットワークアクセスを確認します。パッケー'
        'ジストアは対象外となります。'
    ),
    'cleanup_rebuild_build_output': (
        'プロジェクトの内容と依存関係のロックを確認し、プロジェクトの文書化されたコマンドを使用して再構築しま'
        'す。作成したファイルを保存します。'
    ),
    'cleanup_rebuild_old_installers': (
        'オフラインまたは利用できないインストーラーを維持します。まだ利用可能な場合は、発行者からダウンロード'
        'します。'
    ),
    'cleanup_rebuild_empty_folders': (
        'アプリケーションは空のフォルダーを予期する場合があります。まずその目的を確認してください。'
    ),
    'trash_holder': '{name} (PID {pid})',
    'trash_holders': (
        '{path}: {programs} で開いていることが観察されました。関連するプログラムを自分で閉じて、再試行してく'
        'ださい。'
    ),
    'trash_holders_limited': (
        '{path}: プロセスの可視性は制限されています。他の所有者や原因は不明である可能性があります。'
    ),
    'duplicates_savings': (
        '一意に割り当てられた推定値 {allocated};ゴミ箱 {recoverable} を空にした後に回復可能なファイル データ'
        '。'
    ),
    'duplicates_estimating': '固有の割り当てと回復可能なファイル データを見積もっています…',
    'duplicates_estimate_unavailable': (
        '割り当ての見積もりは利用できません。エクストラを選択する前に、もう一度検索を実行してください。'
    ),
    'duplicates_estimate_assumption': (
        '推定では、明示的に保持されたコピーの選択が使用されます。未決定のグループは不明です。各グループは、移'
        '動前にチェックされ、完全に再ハッシュされます。ハードリンクのエイリアスは決定を妨げます。共有エクステ'
        'ントとディレクトリのメタデータは不明のままです。ゴミ箱に移動してもスペースは空きません。'
    ),
    'capacity_details': '容量の詳細',
    'capacity_summary': 'OS 使用量 {used}、空き容量 {free}、重複を除いた占有量の推定 {unique}。{status}',
    'capacity_estimated': 'ボリューム全体の推定です。内訳が不明な領域は詳細に表示します。',
    'capacity_folder_only': 'フォルダーのみのスキャンです。ボリューム全体の容量と照合できません。',
    'capacity_incomplete': 'スキャンが不完全です。ボリューム全体の容量と照合できません。',
    'capacity_identity_unknown': 'ファイル ID が不明です。ボリューム全体の容量と照合できません。',
    'capacity_capacity_unavailable': 'OS の容量を取得できません。ボリューム全体の容量と照合できません。',
    'capacity_root_changed': 'スキャン対象のルートが変更されています。容量の照合前に再スキャンしてください。',
    'capacity_allocation_exceeds_used': '占有量の推定が OS の使用量を超えているため、容量を照合できません。',
    'capacity_coverage': '{skipped} をスキップしました。 {inaccessible} を読み取れません。保留中 {pending}',
    'capacity_bin_partial': 'ごみ箱の識別または読み取りが不完全です。表示値には確認できたデータだけを含みます。',
    'capacity_explanation': (
        '既知のファイル割り当てには、表示されるごみ箱データが含まれます。ハードリンク名は 1 回カウントされま'
        'す。他のマウントされたボリュームは除外されます。省略されたデータとファイルシステムのメタデータは不明'
        'であり、ゼロではありません。説明されていないデータには、アクセスできないデータ、メタデータ、スナップ'
        'ショット、共有エクステント、および割り当て推定が含まれる場合があります。 OS の容量とファイルはさまざ'
        'まな時点で測定されます。ファイルシステムはスキャン中に変更される可能性があります。利用できない空き容'
        '量は、測定されたメタデータの合計ではなく、報告された合計、使用済みおよび利用可能な空き容量の差です。'
        'これらは、NTFS、ext4、APFS のボリューム検証が保留中の推定値です。'
    ),
    'capacity_row_total': 'OS合計',
    'capacity_row_used': 'OS 使用量',
    'capacity_row_free': 'OS 利用可能な空き容量',
    'capacity_row_unavailable_free': '利用できない空き領域',
    'capacity_row_named_allocated': '名前ごとの占有量の推定',
    'capacity_row_unique_allocated': '重複を除いた占有量の推定',
    'capacity_row_hard_link_overcount': '除外したハードリンクの重複集計',
    'capacity_row_recycle_bin_seen': 'ごみ箱の割り当てが確認されました (含まれています)',
    'capacity_row_foreign_allocated_seen': '他のボリュームのファイル割り当てが確認されました (除外)',
    'capacity_row_unaccounted': '内訳不明の使用量',
    'capacity_row_metadata_bytes': 'ファイルシステムメタデータ / 予約済み',
    'capacity_row_omitted_bytes': '省略されたデータ',
    'capacity_row_other_volumes_bytes': 'その他のマウントされたボリューム',
    'capacity_row_mounts': '別デバイスへのマウント境界',
    'capacity_row_coverage': '検査範囲',
    'review_title': 'クリーンアップ提案を検討する',
    'review_details': '{path}\nルール: {rule};保護: {protection}。 {consequence}',
    'review_hint': (
        'あらゆる道筋と結果を見直してください。エントリを保持するにはチェックを外します。 [続行] をクリックす'
        'ると確認が開きます。'
    ),
    'review_select': '移動',
    'review_rule': 'ルール',
    'review_reason': '理由',
    'review_protection': '保護',
    'review_consequence': '結果',
    'review_manual': '手動選択',
    'review_manual_reason': (
        'ユーザーが選択したエントリ。これを削除すると、それに依存するファイルやプログラムに影響が出る可能性が'
        'あります。'
    ),
    'review_not_protected': '保護されたパスが一致しない',
    'review_open_folder': '含まれているフォルダーを開く',
    'review_continue': '確認に進む',
    'review_estimating': '{count} エントリが選択されました。割り当てを見積もっています…',
    'review_summary': (
        '{count} エントリ;論理 {logical};割り当てられた見積もり {allocated};ごみ箱を空にした後に回復可能なフ'
        'ァイル データ: {recoverable};今なら無料 {free}。共有エクステントとディレクトリのメタデータは不明のま'
        'まです。ゴミ箱に移動してもスペースは空きません。'
    ),
    'size_unknown': '不明',
    'trash_running': (
        '承認されたエントリの再検証と移動… [停止] をクリックすると、残りのエントリがキャンセルされます。'
    ),
    'trash_batch_done': (
        '{moved} を移動、{skipped} をスキップ、{failed} に失敗しました。 {size} はごみ箱に移動されました。'
    ),
    'trash_skipped': (
        'これらのエントリはスキップされました。再試行する前にフォルダーを再スキャンしてください:\n{names}'
    ),
    'trash_skip_outside': '現在のスキャンの外側',
    'trash_skip_unverified': '検証されたスキャン ID がありません',
    'trash_skip_incomplete': '不完全なスキャン範囲',
    'trash_skip_missing': 'エントリまたは親がありません',
    'trash_skip_unreadable': 'エントリを読み取ることができません',
    'trash_skip_link': 'エントリまたは親がリンクになりました',
    'trash_skip_kind': 'エントリの種類が変更されました',
    'trash_skip_identity': 'エントリが置き換えられました',
    'trash_skip_changed': 'サイズ、タイムスタンプ、またはフォルダーの内容が変更されました',
    'trash_skip_protected': '解決されたパスには異なる保護があります',
    'trash_skip_cancelled': '操作がキャンセルされました',
    'coverage_complete': (
        'カバレッジ: {size} は {known} フォルダー内で認識されます。 {skipped} はスキップされました、{denied} '
        'はアクセス不能、保留中 {pending} です。'
    ),
    'coverage_partial': (
        '不完全なカバレッジ: {known} フォルダー内で {size} が認識されています。 {skipped} はスキップされまし'
        'た、{denied} はアクセス不能、保留中 {pending} です。省略されたバイトは不明です。クリーンアップの前に'
        '不完全なブランチを再スキャンします。 「すべて選択」は無効になっています。'
    ),
    'problem_hidden_omitted': '非表示のエントリは省略されました。それらの大きさは不明です。',
    'problem_partial_folder': '一部のエントリを読み取れませんでした。このフォルダは不完全です。',
    'app_title': 'FileTree',
    'about_text': (
        '<h3>FileTree {version}</h3><p>ディスク容量がどこにあるかを確認してください。</p><p>MIT ライセンス · '
        '© 2026 JE-Chen</p>'
    ),
    'menu_file': '&ファイル',
    'menu_export': '&エクスポート',
    'menu_view': '&表示',
    'menu_unit': 'サイズ&単位',
    'menu_language': '&言語',
    'menu_help': '&ヘルプ',
    'action_open': 'フォルダを選択してください…',
    'action_open_tip': 'スキャンするフォルダーまたはドライブを選択します',
    'action_rescan': '再スキャン',
    'action_rescan_tip': '同じフォルダを再度スキャンして変更を取得します',
    'action_stop': '停止',
    'action_stop_tip': '実行中のスキャンを停止します',
    'action_export_folders': 'フォルダーリスト (CSV)…',
    'action_export_folders_tip': (
        'Excel またはその他のスプレッドシート用に、すべてのフォルダーをそのサイズで保存します'
    ),
    'action_export_largest': '最大のファイル (CSV)…',
    'action_export_largest_tip': '最大のファイルのリストを保存する',
    'action_export_json': 'フォルダー ツリー (JSON)…',
    'action_export_json_tip': 'スクリプトやその他のプログラムのフォルダー ツリーを保存します。',
    'action_trash': 'ごみ箱に移動',
    'action_trash_tip': '選択したファイルとフォルダーをごみ箱に移動します (最初に尋ねられます)。',
    'action_find': '見つけてください…',
    'action_find_tip': 'スキャン内の任意の場所でファイルとフォルダーを名前で検索します',
    'action_quit': '終了',
    'action_quit_tip': '閉じる FileTree',
    'action_hidden': '隠しファイルを含める',
    'action_exclusions': 'スキャン中にスキップ…',
    'action_exclusions_tip': 'スキャンで除外されるフォルダーとフォルダー名 (node_modules など)',
    'exclusions_title': 'スキャン中にスキップする',
    'exclusions_hint': (
        'スキャンではこれらのフォルダーは除外されます。これらのフォルダーはリストされ、グレー表示され、サイズ'
        'は 0 になります。node_modules や *.cache などの名前は、その名前のすべてのフォルダーをスキップします'
        '。フォルダー パスはその 1 つのフォルダーをスキップします。リストは次回のスキャンから適用されます。'
    ),
    'exclusions_add_name': '名前を追加…',
    'exclusions_add_folder': 'フォルダーを追加…',
    'exclusions_remove': '削除',
    'exclusions_name_prompt': 'フォルダー名、*、?許可される:',
    'exclusions_saved': '{count} 件の除外が保存されました。次のスキャンから適用されます。',
    'tooltip_excluded': '{path}\nスキップ: 表示中です → スキャン中はスキップします',
    'action_hidden_tip': '隠しファイルと隠しフォルダーを数える (次回のスキャンに適用)',
    'action_help': '使用方法',
    'action_help_tip': 'FileTree への短いガイド',
    'action_about': 'FileTree について',
    'action_about_tip': 'バージョンとライセンス',
    'app_title_admin': 'FileTree (管理者)',
    'action_elevate': '管理者として再起動する',
    'action_elevate_tip': 'すべてのフォルダーを読み取ることができるように、管理者権限で FileTree を再度起動します。',
    'action_ask_admin': '開始時に管理者権限を要求する',
    'action_ask_admin_tip': (
        'Windows は FileTree の起動時に許可を求めるため、保護されたフォルダーも読み取ることができます'
    ),
    'problems_hint': (
        '一部のフォルダーには管理者権限が必要です。これらも読み取るには、管理者として FileTree を再起動します'
        '。'
    ),
    'elevate_declined': 'FileTree は管理者権限なしでまだ実行されています。',
    'unit_auto': '自動',
    'path_placeholder': 'フォルダーのパスを入力または貼り付けて Enter キーを押します',
    'choose_folder_title': 'スキャンするフォルダーを選択してください',
    'welcome_title': 'ディスク容量がどこに行くのかを確認する',
    'welcome_subtitle': (
        'フォルダーまたはドライブ全体を選択します。 FileTree は、その中のすべてのファイルを合計し、最大のフォ'
        'ルダーとファイルを最初に表示します。'
    ),
    'welcome_choose': 'フォルダーを選択してください…',
    'welcome_drives': 'ドライブ',
    'welcome_drive_tip': '{path} をスキャンします',
    'welcome_drive_free': '{free} から {total} まで無料',
    'welcome_recent': '最近スキャンした',
    'welcome_tip': (
        'ヒント: ファイル マネージャーからフォルダーをこのウィンドウにドラッグすることもできます。絶対 UNC 共'
        '有パスを Windows (\\\\server\\share) に貼り付けます。アクセスには現在のアカウントが使用されます。ス'
        'キャン ワーカーはオプションで調整できます。拒否/切断されたブランチは空ではなく、不完全なままになりま'
        'す。'
    ),
    'scan_starting': '開始中…',
    'scan_progress': 'スキャン中… {folders} フォルダー内の {files} ファイル · {size} · {time}',
    'scan_stop': '停止',
    'scan_stopping': '停止中…',
    'scan_cancelled': 'スキャンが停止されました。',
    'scan_stopped_partial': 'スキャンが停止しました: 結果には、これまでに読み取られた内容が表示されます。',
    'scan_failed_title': 'スキャンできません',
    'scan_mount_changed': (
        'マウント境界が変更されたか、検証できませんでした。これらの結果を使用する前に、再度スキャンしてくださ'
        'い。'
    ),
    'scan_failed': 'FileTree は {path} を読み取れませんでした。\n\n理由: {reason}',
    'not_a_folder': '{path} は存在するフォルダーではありません。',
    'duration_seconds': '{value} 秒',
    'duration_minutes': '{minutes} 分 {seconds} 秒',
    'summary': (
        '<b>{path}</b> — {files} ファイルおよび {folders} フォルダー ({time} でスキャン) 内の {size} (ディス'
        'ク上の {allocated})'
    ),
    'summary_live': (
        '<b>{path}</b> — これまでの {files} ファイルと {folders} フォルダー内の {size} (ディスク上の {allocat'
        'ed})'
    ),
    'summary_partial': (
        '<b>{path}</b> — {files} ファイルおよび {folders} フォルダー内の {size} (ディスク上の {allocated}) · '
        '<b>incomplete</b>: スキャンは次の時間に停止されました。 {time}'
    ),
    'tab_chart': 'チャート',
    'chart_treemap': 'ツリーマップ',
    'treemap_levels': 'レベル',
    'treemap_levels_all': 'すべて',
    'treemap_colours': '色',
    'treemap_colours_type': 'ファイルの種類別',
    'treemap_colours_folder': 'フォルダごと',
    'chart_treemap_tip': 'すべてのファイルは、必要なスペースに応じたサイズの長方形として表示されます',
    'chart_bars': '棒グラフ',
    'chart_sunburst': 'サンバースト',
    'chart_tree': 'ツリー',
    'chart_tree_tip': 'フォルダー階層: ブランチを展開、Ctrl+ホイールでズーム、ダブルクリックでフォーカス',
    'tree_orientation': '方向',
    'tree_orientation_horizontal': '左から右へ',
    'tree_orientation_vertical': '上から下へ',
    'tree_more': '{count} 個のフォルダー · {size}',
    'tree_unavailable': 'スキャンされていません',
    'chart_sunburst_tip': (
        '中央にフォルダーがあり、それぞれの深いレベルがリングになります。中央をクリックすると上に移動します'
    ),
    'chart_bars_tip': 'フォルダーのエントリごとに 1 つのバー (最大のものから順)、そのサイズとシェア',
    'bars_empty_folder': 'このフォルダーは空です。',
    'bars_more': '{count} 詳細: {size}',
    'tab_largest': '最大のファイル',
    'scope_folder': '選択したフォルダーのみ',
    'scope_folder_named': '{name} のみ',
    'scope_folder_tip': (
        'スキャン全体ではなく、ツリーで選択したフォルダーの最大のファイル、タイプ、経過時間を表示します'
    ),
    'tab_search': '検索',
    'tab_changes': '変更点',
    'action_compare': '保存したスキャンと比較してください…',
    'action_compare_tip': (
        '[エクスポート] → [フォルダー ツリー (JSON)] で保存したスキャンを開き、その後の成長を確認します。'
    ),
    'compare_title': '保存したスキャンと比較する',
    'compare_failed': 'このファイルは、FileTree:\n{reason} によって保存されたスキャンではありません。',
    'column_before': '以前',
    'column_now': '今',
    'column_change': '変更',
    'changes_new': '新しい',
    'changes_gone': '消えた',
    'changes_whole_scan': '(スキャンしたフォルダー)',
    'changes_stop': '比較するのをやめる',
    'changes_running': '比較中…',
    'changes_waiting': 'スキャンが完了すると、比較が行われます。',
    'changes_unknown_time': '未知の時間に',
    'changes_summary': (
        '{path} と比較すると、{when} が保存されました。その後、{before}、現在は {now} ({change})。 {count} フ'
        'ォルダーが変更されました。'
    ),
    'tab_duplicates': '重複',
    'tab_cleanup': 'クリーンアップ',
    'cleanup_suggestions': '提案',
    'cleanup_select_all': 'すべて選択',
    'cleanup_select_group': 'このグループを選択してください',
    'cleanup_running': '掃除するものを探しています…',
    'cleanup_hint': '通常、コンテンツが移動できる場所は、スキャン後にここに表示されます。',
    'cleanup_none': 'このスキャンでは何も示唆されません。',
    'cleanup_summary': (
        '{groups} グループ内の {size} 論理サイズ。エントリを選択して、ごみ箱に移動する前にパスと割り当てを確'
        '認します。移動してもすぐにスペースが解放されるわけではありません。'
    ),
    'cleanup_group': '{title} — {size} ({count})',
    'cleanup_temp': '一時ファイル',
    'cleanup_temp_tip': 'しばらく残されたファイルプログラム。まだ実行中のプログラムには必要な場合があります。',
    'cleanup_browser_cache': 'ブラウザのキャッシュ',
    'cleanup_browser_cache_tip': 'ウェブページと写真のコピー。ブラウザは必要に応じてそれらを再度ダウンロードします。',
    'cleanup_thumbnails': 'サムネイルキャッシュ',
    'cleanup_thumbnails_tip': '写真の小さなプレビュー。フォルダを開いたときに再度作成されます。',
    'cleanup_crash_dumps': 'クラッシュダンプ',
    'cleanup_crash_dumps_tip': (
        'プログラムがクラッシュしたときに保存されたメモリ。クラッシュを報告する場合にのみ役立ちます。'
    ),
    'cleanup_package_caches': 'パッケージのダウンロード キャッシュ (pip、npm…)',
    'cleanup_package_caches_tip': (
        'ダウンロードしたパッケージは次回のインストールのために保存されます。必要に応じて再度ダウンロードされ'
        'ます。'
    ),
    'cleanup_build_output': 'ビルド出力 (再ビルド可能)',
    'cleanup_build_output_tip': (
        'インストールされた依存関係とプロジェクトのコンパイルされたファイル。プロジェクトを再度ビルドすると、'
        'それらが再作成されます。'
    ),
    'cleanup_old_installers': 'ダウンロードのインストーラー',
    'cleanup_old_installers_tip': (
        'かなり前に実行された可能性が高いセットアップ ファイル。再度インストールしたものは保管しておいてくだ'
        'さい。'
    ),
    'cleanup_empty_folders': '空のフォルダー',
    'cleanup_empty_folders_tip': '何も入っていないフォルダー、または他の空のフォルダーのみ。',
    'duplicates_min_size': 'からのファイルを比較',
    'duplicates_any_size': '任意のサイズ',
    'duplicates_find': '重複の検索',
    'duplicates_stop': '停止',
    'duplicates_select_extra': '追加のコピーを選択してください',
    'duplicates_select_extra_tip': (
        '選択した残すファイルと成功したチェックでグループ内のエキストラを選択します。次に「削除」を押します'
    ),
    'duplicates_hint': (
        'スキャン内の任意の場所で同じ内容のファイルを検索します。同じサイズのファイルのみが読み取られますが、'
        '読み取りに時間がかかるため、より小さいサイズを選択しない限り、小さなファイルは無視されます。'
    ),
    'duplicates_starting': '同じサイズのファイルを探しています…',
    'duplicates_running': '{total} ファイルの {files} ({bytes} の {read}) を読み取ります…',
    'duplicates_stopped': '捜索は中止された。',
    'duplicates_none': '重複したファイルは見つかりませんでした。',
    'duplicates_summary': '{groups} の重複グループ: 追加コピーの {extra} 論理サイズ。',
    'duplicates_limited': '最も多くの追加スペースを持つ {shown} グループがリストされます。',
    'duplicates_skipped': '{count} ファイルを読み取れませんでした。',
    'duplicates_group': '{count} コピー × {size}: {extra} の論理追加コピー サイズ。',
    'search_placeholder': '名前の一部またはパターン:backup、*.mp4、*.iso;*.zip',
    'search_hint': (
        '* と ? を使用して名前の一部またはパターンを入力し、条件またはその両方を選択して、スキャン内の任意の'
        '場所にあるファイルとフォルダーを検索します。'
    ),
    'search_running': '検索中…',
    'search_larger': 'より大きい',
    'search_smaller': 'より小さい',
    'search_no_limit': '制限なし',
    'search_changed': '変更されました',
    'search_changed_any': 'いつでも',
    'search_changed_week': '先週に',
    'search_changed_month': '先月に',
    'search_changed_year': '昨年に',
    'search_changed_stale_year': '1年ではない',
    'search_changed_stale_2y': '2年間ではない',
    'search_changed_stale_5y': '5年間ではない',
    'search_type': '種類',
    'search_type_any': '任意のタイプ',
    'search_show': '表示する',
    'search_kind_any': 'ファイルとフォルダー',
    'search_kind_files': 'ファイルのみ',
    'search_kind_folders': 'フォルダのみ',
    'search_saved': '保存された検索条件',
    'search_saved_none': '(なし)',
    'search_save': '保存…',
    'search_delete': '削除',
    'search_save_title': 'この検索を保存します',
    'search_save_prompt': '名前:',
    'search_none': '何も一致しません。',
    'search_summary': '{count} 件一致、合計 {size} 件。',
    'search_limited': '最大の {shown} がリストされます。',
    'tab_types': 'ファイルの種類',
    'tab_age': '更新時期',
    'column_age': '最後に変更されました',
    'age_month': '1ヶ月以内',
    'age_half_year': '1～6 か月前',
    'age_year': '6 ～ 12 か月前',
    'age_two_years': '1 ～ 2 年前',
    'age_older': '2年以上前',
    'largest_focus': '表示のみ: {what}',
    'largest_show_all': 'すべて表示',
    'list_files_tip': '行をダブルクリックすると、その最大のファイルが一覧表示されます',
    'tab_problems': '問題点',
    'tab_problems_count': '問題 ({count})',
    'column_name': '名前',
    'column_size': 'サイズ',
    'column_allocated': 'ディスク上',
    'column_share': '親の%',
    'column_share_total': '全体の %',
    'column_files': 'ファイル',
    'column_folders': 'フォルダー',
    'column_modified': '修正済み',
    'column_folder': 'フォルダー',
    'column_extension': '延長',
    'column_type': '種類',
    'column_path': 'パス',
    'column_problem': '問題',
    'problem_access_denied': 'アクセスが拒否されました',
    'problem_not_found': 'もうそこにはいない',
    'problem_path_too_long': 'パスが長すぎます',
    'problem_not_scanned': '未スキャン: スキャンが最初に停止されました',
    'no_extension': '(延長なし)',
    'tooltip_unreadable': '{path}\n読み取れませんでした: {reason}',
    'tooltip_link': '{path}\nリンク: 表示されていますが、フォローされていません',
    'tooltip_not_scanned': '{path}\nスキャンされませんでした: スキャンが最初に停止されました',
    'treemap_empty': '何も見せられない',
    'treemap_up': '↑上へ',
    'treemap_up_tip': '上のフォルダーを表示',
    'treemap_tooltip': '<b>{name}</b><br>{size} (このビューの{share})<br>{path}',
    'treemap_more': '{count} 詳細',
    'treemap_more_tooltip': (
        '<b>{count} より小さいエントリ</b>/{name}、それぞれ小さすぎて描画できません<br>{size} (このビューの {'
        'share})'
    ),
    'treemap_more_open': 'ダブルクリックすると、このフォルダーが単独で表示されます',
    'largest_filter': '名前またはフォルダーでフィルター…',
    'types_all': '全種類',
    'category_images': '写真',
    'category_video': '動画',
    'category_audio': '音楽とオーディオ',
    'category_documents': '書類',
    'category_archives': 'アーカイブとディスクイメージ',
    'category_code': 'コードとデータ',
    'category_programs': 'プログラム',
    'category_other': 'その他',
    'status_selected': '{name}: {size} (そのフォルダーの {share})',
    'status_selected_root': '{name}: {size}',
    'menu_open_item': '開く',
    'menu_reveal': 'ファイルマネージャーで表示',
    'menu_copy_path': 'パスをコピーする',
    'menu_show_chart': 'チャートで表示',
    'menu_scan_here': 'このフォルダーをスキャンします',
    'menu_rescan_here': 'このフォルダーを再スキャンします',
    'rescan_done': '再スキャン {name}: {before} → {after}',
    'trash_confirm_title': 'ごみ箱に移動',
    'protected_title': 'システムまたはプログラムフォルダー',
    'protected_question': (
        'エントリのうち {count} はシステム フォルダーまたはプログラム フォルダーです。これらを移動すると、シ'
        'ステムまたはプログラムが動作しなくなる可能性があります:\n\n{names}\n\nそれでも移動しますか?'
    ),
    'protected_system': 'オペレーティングシステムの一部',
    'protected_programs': 'インストールされているプログラム',
    'protected_settings': 'プログラムの設定とデータ',
    'protected_profile': 'ユーザーのプロファイルフォルダー',
    'trash_confirm': '「{name}」({size}) をごみ箱に移動しますか?\n\nそこから復元できます。',
    'trash_failed': '「{name}」をごみ箱に移動できませんでした。使用中または読み取り専用である可能性があります。',
    'trash_done': '「{name}」をごみ箱に移動しました: {size} は解放されました。',
    'action_trash_many': '{count} アイテムをごみ箱に移動します',
    'trash_confirm_many': (
        'これらの {count} アイテム (合計 {size}) をごみ箱に移動しますか?\n\n{names}\n\nそこから復元できます。'
    ),
    'trash_more': '…その他 {count}',
    'trash_failed_many': (
        '{count} 個のアイテムをごみ箱に移動できませんでした。これらは使用中または読み取り専用である可能性があ'
        'ります:\n\n{names}'
    ),
    'trash_done_many': '{count} 個のアイテムをごみ箱に移動しました: {size} が解放されました。',
    'status_selected_many': '{count} 個のアイテムが選択されました: {size}',
    'export_title': 'エクスポート',
    'export_running': '{path} に保存中…',
    'csv_filter': 'CSV ファイル (*.csv)',
    'json_filter': 'JSON ファイル (*.json)',
    'export_done': '{count} 行を {path} に保存しました',
    'export_failed': 'ファイルを保存できませんでした。\n\n理由: {reason}',
    'help_title': 'FileTreeの使用方法',
    'help_html': (
        '\n<h2>FileTree 3 つのステップ</h2>\n<ol>\n<li><b>スキャン対象を選択してください。</b> をクリックしま'
        'す<i> フォルダーを選択してください…</i> またはドライブの 1 つを選択し、フォルダーをドラッグします\n'
        'ウィンドウにパスを入力するか、上部のボックスにパスを入力して Enter キーを押します。</li>\n<li><b>入'
        '力を見てください。</b> ツリーがすぐに表示され、最大のフォルダーが一番上に移動します\n一方、FileTree '
        'はすべてのファイルを合計します。スキャンが終了すると、最大のファイルとファイルの種類が続きます。 \n '
        'を押してください<i></i> をいつでも停止 (または Esc) できます。これまでに読み取られた内容は画面上に残'
        'り、不完全としてマークされます。</li>\n<li><b>スペースを占有しているものを見つけます。</b> 最大のフ'
        'ォルダーがツリーの最上部にあります。矢印をクリック\nフォルダの横にあるをクリックして中を確認します。'
        '</li>\n</ol>\n<h2>結果の読み取り</h2>\n<ul>\n<li><b>フォルダー ツリー</b> (左): 各フォルダーまたはフ'
        'ァイルのサイズ、ディスク上の<i></i> (全体\n)クラスターなので、通常はもう少し多くなります。圧縮ファイ'
        'ルの場合は少なく、オンラインのみに保存されているファイルの場合は何もありません)、a\n親</i> バーの<i>'
        '% (\n の量)その上のフォルダー (このエントリが必要とする)、保持するファイルとフォルダーの数、その中に'
        '何かがあるとき\n最後に変更されました。列タイトルをクリックして並べ替えます。</li>\n<li><b>Chart</b>:'
        ' タブの隅にある同じフォルダーの 4 つのビュー (ツリーマップ\n) を切り替えます。が最初に表示され、File'
        'Tree は選択したものを記憶します)。 \n<i>Treemap</i> は、すべてのファイルを長方形として描画します。フ'
        'ァイルが大きくなるほど、長方形も大きくなります。各フォルダー\n名前とサイズが記載されたストリップがあ'
        'り、フォルダーのファイルが小さすぎて見えない共有 1 つがあり、灰色のハッチングが施されています\nタイ'
        'ル (<i>12 more</i>): ダブルクリックすると、そのフォルダーが単独で表示されます。 <i>Levels</i> はレベ'
        'ル数を設定します\n<i>Colors</i> ファイル タイプ (凡例はその下にあります) または最上位フォルダーごと'
        'に色が描画されます。\n<i>Bars</i> では、フォルダーの各エントリに 1 つのバーが与えられ、最初に最大の'
        'バーが表示され、そのサイズとシェアが最も簡単です\n正確に読むこと。 <i>Sunburst</i> は、フォルダーを'
        '中央に配置し、\n の周囲のリングのさらに深いレベルに配置します。それ;中央をクリックすると上に移動しま'
        'す。 <i>Tree</i> には、展開可能なフォルダー カードが表示されます。 + または「その他のフォルダー」を'
        'クリックします\nカードをさらに表示するには、方向を選択し、Ctrl+ホイールでズームし、スクロールしてパ'
        'ンします。クリックして\nのエントリを見つけますフォルダー ツリーで、フォルダーをダブルクリックしてそ'
        'のフォルダーに移動します。\n<i>Up</i> を押して戻ります。</li>\n<li><b>最大のファイル</b>: スキャン内'
        'の任意の場所にある最大の 1,000 ファイル。フィルターボックスに「\n」と入力します。リストを絞り込みま'
        'す。行をダブルクリックしてツリー内でファイルを見つけます。</li>\n<li><b>Search</b> (Ctrl+F): スキャ'
        'ン内の任意の場所にある、入力した内容が名前に含まれるファイルとフォルダー。\n<code>*.mp4</code> のよ'
        'うなパターンは、名前全体と一致する必要があります。 <code>;</code>\n で複数を区切ります。(<code>*.iso'
        ';*.zip</code>)。ボックスの下の条件 (サイズ、最終変更日、ファイルタイプ、ファイルまたは\n)フォルダー)'
        ' で検索を絞り込むか、独自に検索を作成します。<i>Save...</i> は検索を名前で保持します。 \n最大の一致'
        'が 1,000 個、すべての数と合計サイズとともにリストされます。</li>\n<li><b>クリーンアップ → 提案</b>: '
        '各スキャン後、コンテンツが通常移動できる場所、\n ごとに 1 つのグループ種類 (一時ファイル、キャッシュ'
        '、クラッシュ ダンプ、再ビルド可能なビルド出力、ダウンロード内の古いインストーラー、\n)空のフォルダー'
        ');グループの上にマウスを移動して、削除の内容を確認してから、<i>このグループを選択</i> または\n<i>す'
        'べて</i>を選択し、[削除]を押します。</li>\n<li><b>クリーンアップ→重複</b>: <i>重複を検索</i>を押して'
        '、同じ内容のファイルをグループ化します。 \n のファイルのみ同じサイズが読み取られます。 1 MB 未満のフ'
        'ァイルは、読み取りに\n かかるため、より小さいサイズを選択しない限り除外されます。時間。各グループは'
        '、そのコピーを最も古いものから順にリストします。 <i>追加のコピーを選択</i>は最も古いコピーを除くすべ'
        'てを選択し、\n削除すると、それらはごみ箱に移動します。</li>\n<li><b>ファイル タイプ</b>: 各種類のフ'
        'ァイルが拡張子ごとに使用するスペース。リストからタイプを選択してください\nテーブルの上にあるとその種'
        '類だけが表示されます。行をダブルクリックすると、その種類の最大のファイルが一覧表示されます。</li>\n<'
        'li><b>Age</b>: 1 か月以内、1 ～ 6 か月前などに最後に変更されたスペースの量\n何年も前。多くの場合、古'
        'いデータはアーカイブまたは削除できるものです。行をダブルクリックすると、最大の\nがリストされます。フ'
        'ァイル。</li>\n<li><b>問題</b>: フォルダー FileTree は読み取りを許可されませんでした。中に何が入って'
        'いるかはカウントされません。</li>\n</ul>\n<h2>スペースを解放</h2>\n<p>任意のエントリを右クリックして'
        '<i>開く</i>、<i>ファイルマネージャーに表示</i>、<i>パスをコピー</i>、\n<i>ツリーマップに表示</i>、<i'
        '>このフォルダーを再スキャン</i> (FileTree の外側で行われた変更後、残りの部分は\n)結果は残ります)、<i'
        '>このフォルダーを単独でスキャン</i>、または<i>ごみ箱に移動</i>.\n複数のエントリを一度に移動するには'
        '、フォルダ ツリー (\n) で Ctrl キーを押しながらクリックするか、Shift キーを押しながらクリックしてエ'
        'ントリを選択します。<i>最大ファイル</i> リストまたは <i>Search</i> 結果: FileTree は 1 回質問し、合'
        '計サイズをリストします。\nFileTree は永久に何も削除しません。常に最初に要求し、移動したものはすべて'
        '復元できます\nごみ箱 (macOS および Linux のゴミ箱) から。番号は再スキャンせずにすぐに更新されます。'
        '\nシステム フォルダーとプログラム フォルダーについては、理由とともに 2 回ほど尋ねられます。一時フォ'
        'ルダーとキャッシュは対象外です。</p>\n<h2>成長したものを見る</h2>\n<p><i>ファイル → エクスポート → '
        'フォルダー ツリー (JSON)</i> を使用してスキャンを保存します。後で新しいスキャンを行った後、\n を選択'
        'します。<i>ファイル → 保存されたスキャンと比較…</i> し、そのファイルを開きます。 <b>Changes</b> タブ'
        'には、\n が含まれるすべてのフォルダーがリストされます。当時と現在のサイズを比較すると、最初に最大の'
        '増加が見られます (<i>new</i> および <i>gone</i> は、\n というフォルダーをマークします)現れたり消えた'
        'り）。 <i>比較を停止</i>.</p>\nを押すまで、再スキャンのたびに比較が継続されます。<h2>キーボード ショ'
        'ートカット</h2>\n<table cellpadding="3">\n<tr><td><b>Ctrl+O</b></td><td>フォルダーを選択</td></tr>\n'
        '<tr><td><b>F5</b></td><td>再スキャン</td></tr>\n<tr><td><b>Esc</b></td><td>スキャンを停止</td></tr>'
        '\n<tr><td><b>Ctrl+F</b></td><td>名前で検索</td></tr>\n<tr><td><b>削除</b></td><td>選択したエントリを'
        'ごみ箱に移動</td></tr>\n<tr><td><b>F1</b></td><td>このガイド</td></tr>\n<tr><td><b>Ctrl+Q</b></td><t'
        'd>終了</td></tr>\n</table>\n<p>macOS では、Ctrl の代わりに ⌘ を使用します (再スキャンするには ⌘R)。<'
        '/p>\n<h2>知っておきたい</h2>\n<ul>\n<li>サイズはバイナリ単位の実際のファイル サイズ (1 KB = 1,024 バ'
        'イト) であり、Windows Explorer と同じです。\n<i>View → サイズ単位</i>.</li>\n で固定単位を選択します'
        '。<li>ショートカットとリンク (シンボリック リンク、ジャンクション) はリストされていますが、たどられ'
        'ることはないため、何もありません\n2 回カウントされました。</li>\n<li>Windows では、FileTree は起動時'
        'に TreeSize などの管理者権限を要求するため、\n を読み取ることができます。保護されたフォルダーも。 「'
        'いいえ」と言えば、正常に実行されます。読み取れなかったフォルダーは\n の下にリストされます。<i>問題</'
        'i>、<i>管理者として再起動</i> ボタン。 \n の下の質問をオフにしてください<i>表示 → 開始時に管理者権限'
        'を要求</i>.</li>\n<li><i>最大のファイル</i>、<i>ファイル タイプ</i>、<i>Age</i> はスキャン全体をカバ'
        'ーします。 <i>選択したフォルダーのみ</i>、\nこれらのタブの右上にあるをクリックすると、ツリーで選択し'
        'たフォルダーをたどります。</li>\n<li>隠しファイルもカウントされます。 <i>View をオフにする → 隠しフ'
        'ァイル</i> を含めて、\n から除外します。次のスキャン。</li>\n<li>すべてのスキャンからフォルダーを除'
        '外するには、<i>表示→スキャン中にスキップ</i>:\n などの名前を付けます。<code>node_modules</code> はそ'
        'の名前のすべてのフォルダーをスキップし、パスは 1 つのフォルダーをスキップします。スキップされたフォ'
        'ルダーは\nですサイズは 0.</li>\n でグレー表示されます。<li><i>File → Export</i> で結果を保存します。'
        'CSV は Excel で開き、JSON はスクリプト用です。</li>\n</ul>\n'
    ),
}


KO: dict[str, str] = {
    'recurring_review': '다시 스캔하고 현재 후보 항목 검토…',
    'recurring_validating': '전체 신규 스캔 및 현재 소스 메타데이터에 대해 날짜가 지정된 제안을 검증하는 중…',
    'recurring_refused': '제안을 계속할 수 없습니다: {status}. 현재 관찰을 준비하려면 새로운 예약 검사를 실행하세요.',
    'recurring_tabs_full': '16개의 스캔 탭이 모두 사용 중입니다. 예정된 제안을 검토하기 전에 탭을 닫으세요.',
    'trash_skip_proposal_changed': (
        '원본 경로 또는 후보 보고서 설정·기록이 변경되었거나 확인할 수 없습니다. 원본을 유지했습니다.'
    ),
    'trash_skip_proposal_expired': '이동 전에 예약 스캔의 후보 보고서가 만료되었습니다. 원본을 유지했습니다.',
    'action_recurring': '예약된 스캔 제안…',
    'action_recurring_tip': '날짜가 지정된 예정된 관찰 및 해당 범위를 봅니다. 자동 정리가 되지 않습니다.',
    'recurring_rule': '규칙',
    'recurring_unknown': '알 수 없음',
    'recurring_new': '마지막 스캔 이후 새로운 정크',
    'recurring_current': '현재 후보 항목',
    'recurring_growth': '최대 신규 성장',
    'recurring_empty': (
        '이 세션에는 예약된 보고서가 없습니다. 백그라운드 모니터링을 활성화하고 스캔 폴더를 선택합니다.'
    ),
    'recurring_hint': (
        '관찰만; 아무것도 자동으로 이동되지 않습니다. 목록당 최대 100개 행. 증가는 복구 가능한 공간이 아닌 논'
        '리적 바이트입니다. 알려지지 않은 비교는 새로운 쓰레기가 없음을 증명하지 않습니다. 보고서는 이 세션에'
        '서 예약된 검사 후에 나타납니다. 기준선은 로컬 기록에 보관됩니다. 새 탭에서 재검색을 검토하고 일반 대'
        '기열과 확인을 사용합니다.'
    ),
    'recurring_summary': (
        '준비됨: {prepared}\n이전 기준: {previous}\n만료: {expires}\n표시된 후보: {retained} / {total}; 적용 '
        '범위: {coverage}; 비교: {comparison}\n상태: {status}'
    ),
    'recurring_status_current': '관찰됨; 검토 전 새로운 소스 검증 필요',
    'recurring_status_expired': '만료됨(일정 누락 또는 시계 롤백 포함)',
    'recurring_status_schedule_changed': '일정이 변경되거나 비활성화되었습니다.',
    'recurring_status_stale_scan': '스캔 작업 기록이 변경되었거나 사용할 수 없음',
    'recurring_status_rule_changed': '청소 규칙이 변경되었습니다.',
    'recurring_status_incomplete': '불완전한 적용 범위 또는 알 수 없는 신원',
    'recurring_status_paths_changed': '소스 경로가 변경됨',
    'recurring_status_unavailable': '설정 또는 작업 기록을 확인할 수 없습니다.',
    'recurring_prepare_failed': '기록이 저장되었습니다. 예약된 제안을 사용할 수 없음: {detail}',
    'workspace_new': '새 스캔 탭',
    'workspace_new_tip': '독립적인 스캔 탭을 엽니다(Ctrl+T). Ctrl+W로 현재 탭을 닫습니다.',
    'workspace_close': '스캔 탭 닫기',
    'workspace_empty': '폴더 선택',
    'trash_skip_recycle_unverified': (
        'Windows 재활용 설정, 전체 소스 크기 또는 기본 저장소 메타데이터를 확인할 수 없습니다. 소스가 유지됩'
        '니다.'
    ),
    'trash_skip_recycle_disabled': 'Windows 이 범위에서는 재활용이 비활성화됩니다. 소스가 유지됩니다.',
    'trash_skip_recycle_capacity': (
        '선택 항목 및 현재 쓰레기통 내용물이 여유 공간이 있는 관찰된 재활용 한도를 초과합니다. 소스가 유지됩'
        '니다.'
    ),
    'action_check_updates': '매일 업데이트를 확인하세요',
    'action_background_monitor': '백그라운드 모니터…',
    'action_background_monitor_tip': '트레이 알림 및 일정에 따른 폴더 기록 검색을 선택하세요.',
    'background_enable': '백그라운드 모니터링 활성화',
    'background_startup': '로그인할 때 이 모니터 시작',
    'background_startup_hint': (
        '이 사용자에 대해서만 별도의 선택이 가능합니다. FileTree 소유의 로그인 항목을 제거하려면 선택을 취소'
        '하세요. 향후 로그인에 적용됩니다. 다른 복사를 시작하거나 이 모니터를 닫지 않습니다.'
    ),
    'background_startup_requires_monitor': '로그인 항목을 추가하기 전에 백그라운드 모니터링을 활성화하십시오.',
    'background_startup_error': '로그인 시작을 변경할 수 없습니다: {detail}',
    'background_hint': (
        '기본적으로 꺼져 있습니다. 닫으면 사용 가능한 시스템 트레이에 FileTree이 유지됩니다. 그만둬 끝내세요.'
        ' 매분마다 OS의 사용 가능한 용량을 확인하고 선택한 폴더만 부드럽게 검사합니다. 예약된 검색에는 활성화'
        '된 로컬 기록이 필요합니다. 자동 정리 또는 시작 등록이 없습니다.'
    ),
    'background_threshold': '사용 가능한 공간 아래에 경고',
    'background_interval': '검사 간격(시간)',
    'background_roots': '예약된 검사 폴더',
    'background_add': '스캔 폴더 추가…',
    'background_remove': '선택한 폴더 제거',
    'background_limit': '최대 32개의 예약 폴더를 선택하세요.',
    'background_show': 'FileTree 표시',
    'background_off': '백그라운드 모니터링이 꺼져 있습니다',
    'background_ready': '백그라운드 모니터링이 켜져 있습니다.',
    'background_no_tray': (
        '시스템 트레이를 사용할 수 없습니다. FileTree은 계속 표시되고 배경 모니터링은 일시 중지됩니다.'
    ),
    'background_error': '백그라운드 모니터링: {detail}',
    'background_history_disabled': '예약된 검사를 실행하기 전에 로컬 검사 기록을 활성화하십시오.',
    'background_scanning': '예약된 검사: {detail}',
    'background_saved': '저장된 예약 내역: {detail}',
    'background_saved_partial': '읽지 않은 범위와 함께 저장된 예약 내역: {detail}',
    'background_canceled': '예약된 검사가 취소되었습니다. 부분 소스 범위가 저장되지 않았습니다: {detail}',
    'background_warning': '{detail}',
    'background_low_space': '{root}의 사용 가능한 공간 부족: {free} ({percent}%)',
    'action_follow_changes': '변경 사항 따르기',
    'action_follow_changes_tip': (
        '기본적으로 꺼져 있습니다. Windows/Linux에서 변경된 폴더를 새로 고칩니다. 5분마다 루트를 조정합니다.'
    ),
    'follow_waiting': '변경 사항 따르기: 스캔 대기 중',
    'follow_starting': '변경사항 따르기: 시작 중…',
    'follow_active': '다음 변경 사항({detail})',
    'follow_failed': '변경사항 팔로우가 중지되었습니다: {detail}',
    'follow_incomplete': '변경 사항을 따르려면 완전한 물리적 스캔이 필요합니다.',
    'follow_unsupported': '변경 사항에 따라 Windows 및 Linux을 지원합니다.',
    'follow_backend_usn': 'NTFS USN',
    'follow_backend_directory_changes': '디렉터리 알림',
    'follow_backend_inotify': 'inotify',
    'action_check_updates_tip': '최대 하루에 한 번 HTTPS를 통해 PyPI에 문의하세요. 설치 없이 참고만 가능합니다.',
    'update_available': 'FileTree {version} 사용 가능',
    'multi_roots': '여러 뿌리',
    'action_multi_scan': '여러 폴더를 스캔합니다…',
    'action_multi_scan_tip': '한 번의 결합 스캔으로 명시적 폴더를 검토합니다.',
    'multi_choose': '여러 폴더 스캔',
    'multi_add': '폴더 추가…',
    'multi_remove': '선택한 루트 제거',
    'scan_all_drives': '모든 드라이브 검사',
    'multi_hint': (
        '최대 256개의 선택된 뿌리를 결합합니다. 결과는 읽기 전용입니다. 파일 작업을 위해 소스를 별도로 스캔합'
        '니다. OS 용량은 볼륨별로 유지됩니다.'
    ),
    'capacity_multiple_roots': '다중 루트: OS 용량은 볼륨당입니다.',
    'vc_title': '컴팩트한 VHD 선택…',
    'vc_apply': '검토하고 컴팩트하게…',
    'vc_hint': (
        '고정 로컬 NTFS의 분리된 동적 VHD/VHDX만 적합합니다. 읽기 전용 준비는 ID, 헤더 및 보수적인 WSL/Docker'
        ' 런타임 상태를 확인합니다. 게스트 사용량 및 보장된 복구는 알 수 없습니다. 권한 오류로 인해 FileTree'
        '의 기존 관리자 재시작을 사용하기 전에 이 검토를 닫으십시오. 새로운 스캔과 승인이 필요합니다.'
    ),
    'vc_preparing': '캡처된 디스크 및 중지된 런타임을 확인하는 중…',
    'vc_ready': '정확한 소스를 검토하고 해당 기계가 계속 중지되어 있는지 확인하세요.',
    'vc_details': (
        '소스: {path}\n이름: {source}\n디스크 UUID: {identifier}\n가상 용량: {capacity}\n공급자 바이트: {phys'
        'ical}\n\n백엔드: Windows CompactVirtualDisk, 분리형 제로 블록 압축. 게스트 연결, 실행 또는 종료가 없'
        '습니다. 게스트가 사용하는 바이트는 알 수 없습니다.'
    ),
    'vc_confirm': (
        '다음 정확한 가상 디스크 파일을 압축 정리하시겠습니까?\n\n{path}\n\n예를 선택하면 이 파일을 사용하는 '
        '머신이 중지되었으며 작업 내내 중지 상태를 유지한다는 것을 확인한 것으로 간주합니다. 실행 상태와 식별'
        ' 정보를 새로 확인합니다. 운영체제의 제로 블록 작업으로 공간이 회복되지 않을 수 있으며, 나중에 오류가'
        ' 발생하더라도 메타데이터가 이미 변경되었을 수 있습니다. 자동으로 되돌리는 기능은 없습니다. 게스트의 '
        '사용량 및 여유 공간 회복량은 알 수 없습니다. 중지 또는 닫기는 진행 중인 운영체제 호출이 끝날 때까지 '
        '기다리고 실제 결과를 보고합니다. 쓰기 가능한 상태로 열기 전에 승인을 기록합니다.'
    ),
    'vc_running': '검토된 디스크를 다시 확인하고 압축하는 중…',
    'vc_waiting': '현재 운영체제 호출을 기다리는 중입니다. 실제 결과가 보고될 예정입니다…',
    'vc_done': (
        '{status}\n관찰된 지원 할당: {before} → {after}. 이는 OS 무료 복구를 보장하지 않습니다. 게스트 사용량'
        '은 아직 알려지지 않았습니다. 쓰기를 시도하려면 새로 검사해야 합니다.'
    ),
    'vc_failed': '압축: {reason}',
    'vc_not_compacted': '압축되지 않음',
    'vc_stale': (
        '쓰기 가능한 작업이 시도되었습니다. 기록된 관찰 내용은 오래되었습니다. 다른 검토 전에 새로 스캔하려면'
        ' 이 창을 닫으세요.'
    ),
    'vc_audit_refused': '승인을 기록할 수 없습니다. 운영체제 작업이 시작되지 않았습니다.',
    'vc_audit_detail': '이전 백업 할당: {before}; 이후: {after}. 오류: {error}',
    'journal_status_compacted': '네이티브 압축 완료',
    'journal_reason_compaction': '명시적 가상 디스크 압축',
    'vd_hint': (
        '읽기 전용 인벤토리 공급자 라벨은 위치 힌트입니다. 지원 할당, 공급자 바이트 및 가상 용량은 별개입니다'
        '. 게스트 사용량은 알 수 없습니다. 헤더 쿼리와 압축 검토는 명시적입니다. 지원되지 않는 형식은 계속 표'
        '시됩니다. 게스트가 자동으로 시작, 중지 또는 마운트되지 않습니다.'
    ),
    'vd_name': '디스크 이름',
    'vd_source': '소스',
    'vd_issue_unverified': '확인되지 않은 신원',
    'vd_issue_unavailable': '연결됨, 클라우드 또는 사용할 수 없음',
    'vd_issue_changed': '파일이 변경됨',
    'vd_issue_duplicate_hard_links': '여러 하드 링크 이름',
    'action_virtual_disks_tip': '기록된 가상 디스크를 검토하고 읽기 전용 기본 VHD 정보를 명시적으로 쿼리합니다.',
    'action_virtual_disks': '가상 디스크…',
    'vd_kind': '형식',
    'vd_length': '백업 파일 길이',
    'vd_allocation': '기록된 할당',
    'vd_capacity': '가상 용량',
    'vd_physical': '공급자 물리적 바이트',
    'vd_guest': '사용된 게스트',
    'vd_source_scan': '기록된 스캔',
    'vd_source_wsl': 'WSL 등록',
    'vd_source_docker': 'Docker 기본값(추론)',
    'vd_unsupported': '기본 VHD 도구는 지원되지 않습니다.',
    'vd_not_queried': '쿼리되지 않은 기본 헤더',
    'vd_fixed': '고정',
    'vd_dynamic': '동적',
    'vd_differencing': '차별화',
    'vd_loaded': '탑재/사용 중',
    'vd_detached': '로드되지 않음(관찰)',
    'vd_inspect': '선택한 VHD 헤더 쿼리',
    'vd_select': '기록된 항목 표시',
    'vd_reading': '가상 백업 파일 검색 중…',
    'vd_querying': '기본 헤더 읽기: {path}',
    'vd_summary': '{count} 중 {shown} 표시 중; {issues} 문제/누락. 적용 범위: {coverage}.',
    'vd_failed': '가상 디스크 정보: {reason}',
    'vd_information_hint': (
        '기본 관찰은 압축을 승인하거나 기계가 정지되었음을 증명하지 않습니다. 공급자 실제 바이트는 게스트 사'
        '용 바이트가 아닙니다. 디스크 UUID는 행 도구 설명에 있습니다.'
    ),
    'link_summary': '{total} 추가 사본: {ready} 준비됨, {skipped} 거부됨.',
    'link_title': '추가 사본을 연결하십시오…',
    'link_hint': (
        '명시적으로 보관된 복사본(최대 1,000개 추가)을 사용하여 정확한 중복 파일을 검토합니다. 보호된 파일, '
        '변경된 파일, 클라우드 파일, 링크된 파일, 지원되지 않는 파일은 거부됩니다. 여유 공간이 보장되지 않습'
        '니다.'
    ),
    'link_copy': '교체할 추가 사본',
    'link_keeper': '보관된 파일',
    'link_apply': '링크가 추가 사본을 검토했습니다…',
    'link_confirm': (
        '중복 복사본 {count}개를 하드 링크로 바꾸시겠습니까? 처리할 수 없는 {skipped}개 행은 건너뜁니다.\n\n'
        '기존 데이터는 휴지통에 보관하지 않습니다. 연결된 모든 이름은 이후의 내용, 메타데이터 및 접근 권한 변'
        '경을 공유합니다. 자동으로 되돌리는 기능은 없습니다. 실패하거나 취소하면 생성한 링크와 기존 복사본의 '
        '백업이 표시된 경로에 남을 수 있습니다. 중지 또는 닫기는 진행 중인 운영체제 호출이 끝날 때까지 기다립'
        '니다. 전체 데이터와 모든 명명된 스트림을 다시 확인합니다. 동시 변경에 대한 확인은 관찰에 기반하며 트'
        '랜잭션이 아닙니다. 상세 내용에서 모든 쌍과 거부 이유를 확인하세요.'
    ),
    'link_progress': '재확인/링크: {path}',
    'link_done': (
        '하드 링크: {linked} 게시됨, {other} 연결되지 않음. 관찰 내용을 새로 고치려면 다시 스캔하세요. 복구된'
        ' 용량은 알 수 없습니다.'
    ),
    'link_not_linked': '연결되지 않음',
    'link_retained': '유지된 경로:\n{paths}',
    'journal_status_linked': '하드 링크 게시됨',
    'journal_reason_duplicate_links': '명시적 중복 하드링크 교체',
    'undo_button': '실행 취소({count})',
    'undo_running': '캡처된 휴지통 항목을 복원하는 중…',
    'undo_done': '실행 취소: {restored} 복원, {failed} 실패',
    'undo_title': '쓰레기 복원',
    'undo_result': '{status}\n원본: {source}\n휴지통: {trashed}\n{reason}',
    'undo_unavailable': '일부 항목은 실행취소할 수 없습니다: {reason}',
    'journal_status_restored': '휴지통에서 복원됨',
    'journal_reason_undo': '명시적 휴지통 실행 취소',
    'menu_move_drive': '다른 드라이브로 이동…',
    'copy_hint': (
        '다른 드라이브에 있는 기존 폴더를 선택합니다. 원본은 별도의 휴지통 확인 전까지 보관됩니다. 64MiB 미만'
        '의 파일 수, 길이 및 SHA-256을 확인하세요. 더 큰 페이로드는 길이만 제한됩니다. 실패/취소 시 부분 대상'
        '이 유지됩니다. 최대 1,000개의 폴더를 선택할 수 있습니다.'
    ),
    'copy_apply': '검토된 폴더 복사 및 확인…',
    'copy_redirect': '휴지통을 성공적으로 삭제한 후 각 원래 경로에 교차점/기호 링크를 남겨두세요.',
    'copy_finish': '검증된 원본을 휴지통으로 이동…',
    'copy_confirm': (
        '검토한 폴더 {count}쌍을 복사하고 검증하시겠습니까? 나머지 {skipped}쌍은 건너뜁니다. 기존 이름을 덮어'
        '쓰지 않습니다. 원본은 휴지통 이동을 별도로 승인할 때까지 유지합니다. 실패하거나 취소하면 일부만 복사'
        '된 항목이 대상에 남습니다.'
    ),
    'copy_progress': '이 폴더에 {path}: {done} / {total} 파일 복사/확인 중',
    'copy_done': '확인된 사본: {copied}; 건너뛰었습니다: {skipped}; 실패: {failed}. 원본은 그대로 유지됩니다.',
    'copy_partial': '유지된 부분 대상: {path}',
    'copy_trash_confirm': (
        '각 원본을 휴지통으로 이동하기 직전에 복사된 폴더를 다시 검증합니다. 항목 수와 길이를 비교합니다. 64 '
        'MiB 미만의 내용은 SHA-256으로 대조하고, 그 이상의 내용은 길이만 비교합니다. 검증에 실패하면 나머지 '
        '작업을 중지합니다. 동시 변경에 대한 확인은 트랜잭션이 아닙니다.'
    ),
    'copy_errors': '복사 확인 또는 원본 경로 리디렉션에 실패했습니다. 세부정보에서 실제 경로를 검토하세요.',
    'copy_verify_failed': '보관된 원본: {source}\n복사본: {destination}\n확인 거부됨: {reason}',
    'copy_redirect_failed': (
        '원본이 휴지통으로 이동됨: {source}\n확인된 사본 보관됨: {destination}\n리디렉션 실패(빈 원본 경로 디'
        '렉터리가 남아 있을 수 있음): {reason}'
    ),
    'namespace_reason_same_volume': '동일한 볼륨; 폴더로 이동 사용',
    'namespace_source_name': '소스 이름',
    'namespace_destination_name': '목적지 이름',
    'namespace_closed_errors': (
        '중지/폐쇄된 작업에서 오류가 보고되었습니다. 세부정보에서 소스/대상 경로를 검사합니다.'
    ),
    'namespace_refreshed': '{path}: {files} 파일을 새로 고쳤습니다. {errors} 스캔 오류.',
    'namespace_refresh_failed': '{path}에서 새로 고침 실패: {reason}',
    'namespace_refreshing': '영향을 받은 대상 새로 고침: {path}',
    'menu_move_folder': '폴더로 이동…',
    'menu_rename': '이름 바꾸기…',
    'namespace_source': '소스',
    'namespace_destination': '목적지',
    'namespace_status': '상태',
    'namespace_pattern': '파일 이름 패턴',
    'namespace_rename_hint': (
        '모든 소스와 대상을 검토하세요. 리터럴 토큰: {name}, {stem}, {ext}, {n}. 동일한 볼륨만; 덮어쓰기 없음'
        '. 최대 1,000개의 항목을 선택할 수 있습니다.'
    ),
    'namespace_move_hint': (
        '기존 대상 폴더를 선택하고 모든 쌍을 검토하십시오. 동일한 볼륨만; 덮어쓰기 없음. 보호된/링크/사용할 '
        '수 없는/불완전한 항목은 거부됩니다. 최대 1,000개의 항목을 선택할 수 있습니다.'
    ),
    'namespace_collision_skip': '기존 이름: 건너뛰기',
    'namespace_collision_rename': '기존 이름: 번호가 매겨진 접미사 미리보기',
    'namespace_preview': '미리보기 경로',
    'namespace_apply': '검토된 경로 적용…',
    'namespace_reading': '소스 및 대상 메타데이터 확인 중…',
    'namespace_preview_needed': '옵션이 변경되었습니다. 적용하기 전에 경로를 다시 미리 봅니다.',
    'namespace_summary': '{total} 가장 바깥쪽 쌍; {ready} 준비; {skipped} 거부됨/변경되지 않음.',
    'namespace_confirm': (
        '미리보기의 처리 가능한 원본·대상 {count}쌍을 적용하시겠습니까? 나머지 {skipped}쌍은 건너뜁니다. 상세'
        ' 내용에는 처리 가능한 모든 쌍을 표시합니다. 기존 이름을 덮어쓰지 않습니다. 중지 또는 닫기는 진행 중'
        '인 이름 변경이 끝날 때까지 기다리며, 완료된 변경은 유지합니다.'
    ),
    'namespace_progress': '{done} / {total} 쌍 처리됨',
    'namespace_done': (
        '이동/이름 변경: {moved}; 건너뛰었습니다: {skipped}; 실패: {failed}. 스캔을 새로 고치려면 닫으세요.'
    ),
    'namespace_failed': '작업 실패: {reason}',
    'namespace_reason_ready': '준비',
    'namespace_reason_unverified': '알 수 없는 신원',
    'namespace_reason_link': '링크가 거부되었습니다.',
    'namespace_reason_special': '특별입국 거부',
    'namespace_reason_unavailable': '사용할 수 없음/클라우드 항목',
    'namespace_reason_cancelled': '중지됨',
    'namespace_reason_outside': '외부 현재 스캔/루트',
    'namespace_reason_missing': '소스 누락',
    'namespace_reason_kind': '항목 유형이 변경됨',
    'namespace_reason_identity': '소스가 교체됨',
    'namespace_reason_changed': '소스가 변경됨',
    'namespace_reason_incomplete': '불완전한 소스 범위',
    'namespace_reason_unreadable': '읽을 수 없는 소스',
    'namespace_reason_system_managed': '시스템 관리 소스',
    'namespace_reason_protected': '보호된 소스',
    'namespace_reason_unchanged': '이름은 변경되지 않음',
    'namespace_reason_descendant': '선택한 소스 내의 대상',
    'namespace_reason_protected_destination': '보호된 목적지',
    'namespace_reason_volume': '다른 볼륨; 검증된 사본이 필요합니다',
    'namespace_reason_collision': '이름이 이미 존재합니다.',
    'photos_exact': '정확한 중복',
    'photos_find': '비슷한 사진 찾기',
    'photos_similar': '비슷한 사진',
    'photos_distance': '해시 거리(0~16):',
    'photos_hint': (
        '시각적 후보만 해당: 썸네일과 원본을 비교하세요. 해시 충돌이 가능합니다. 자동 유지할 파일, 추가 사본 '
        '선택 또는 복구 추정이 없습니다. 첫 번째 애니메이션 프레임.'
    ),
    'photos_group': '{count} 이미지; 첫 번째 이미지의 {distance} 비트 내',
    'photos_running': '이미지 읽기: {read}; 건너뛰기/실패: {skipped}',
    'photos_summary': '{groups} 유사 이미지 그룹; {read} 이미지 읽기; {skipped} 건너뛰거나 실패했습니다.',
    'photos_limited': '제한된 재고 또는 디스플레이 최대 {count}개의 이미지 행/썸네일이 표시됩니다.',
    'archive_loading': '아카이브 메타데이터를 읽는 중…',
    'archive_virtual_name': '{name} [가상]',
    'archive_virtual_hint': '아카이브 멤버: 선언된 비압축 크기, 디스크 총계 외부. 파일 작업이나 추출이 없습니다.',
    'archive_failed': '미리보기를 사용할 수 없음: {reason}',
    'archive_rejected': '{count} 안전하지 않거나 연결되었거나 충돌하는 구성원이 생략되었습니다.',
    'archive_empty': '미리보기 가능한 회원 없음',
    'archive_stopped': '아카이브 미리보기가 중지되었습니다. 재고가 불완전하다',
    'archive_busy': '두 개의 아카이브 읽기가 이미 실행 중입니다. 다시 스캔하여 다시 시도',
    'archive_stop': '이 아카이브 읽기를 중지하세요',
    'action_count_hard_links': '관찰된 하드 링크를 한 번 계산합니다.',
    'action_count_hard_links_tip': (
        '기본적으로 꺼져 있습니다. 향후 스캔에서는 이름이 지정된 크기를 유지하고 계산된 총계를 추가합니다. Br'
        'anch/Trash는 전체 루트를 재구축합니다.'
    ),
    'column_accounted_size': '계산된 크기',
    'column_accounted_allocated': '계산된 디스크 크기',
    'hard_links_hint': (
        '하드 링크 계정을 활성화하면 처음으로 관찰된 어휘 이름이 바이트에 기여합니다. 여기서 별칭은 0으로 계'
        '산됩니다. 명명된 크기는 실제 파일 길이로 유지됩니다. 알 수 없거나 일관성이 없는 기록은 추정 상태로 '
        '유지됩니다. 공유 범위를 알 수 없습니다.'
    ),
    'hard_links_summary': (
        '계산됨: {size}(디스크 추정치 {allocated}); {aliases} 관찰된 별칭; {unknown} 알 수 없는 레코드입니다.'
        ' 차트에서는 계산된 합계를 사용합니다. 파일/유형/연령 목록은 이름이 지정된 크기를 유지합니다.'
    ),
    'compression_mode_ntfs': 'NTFS 압축',
    'compression_mode_xpress8k': 'XPRESS8K 압축(거의 수정되지 않은 파일)',
    'compression_mode_uncompress': '압축 해제(NTFS 및 실행 모드)',
    'compression_apply': '나열된 파일 처리 중…',
    'compression_restore_summary': (
        '{count}/{total} 녹음된 파일이 검토 대상입니다. {shown}을 표시합니다. 압축 상태를 알 수 없습니다.'
    ),
    'compression_confirm': (
        '범위: {path}\n모드: {mode}\n후보 {total}개 중 목록에 있는 파일 {count}개(논리 크기 {size})만 처리합'
        '니다.\n\n현재 NTFS 범위와 파일이 변경되지 않았는지 다시 확인합니다. 링크, 클라우드·오프라인, 스파스,'
        ' 숨김·시스템, 하드 링크 및 보호된 파일은 처리하지 않습니다. 폴더의 기본 설정과 목록에 없는 파일은 변'
        '경하지 않습니다. 압축하면 쓰기 속도가 느려질 수 있습니다. XPRESS는 변경이 적은 데이터에 적합합니다. '
        '압축 해제에는 여유 공간이 필요합니다. 중지하거나 실패하면 일부 변경이 남을 수 있습니다.\n\n이 창을 '
        '닫으면 진행 중인 명령을 취소하고 종료를 기다린 뒤, 파일별 할당을 확인하여 이 폴더를 다시 스캔합니다.'
        ' 계속하시겠습니까?'
    ),
    'compression_progress': '{done}/{total} 나열된 파일을 처리 중입니다…',
    'compression_done': (
        '{done}/{attempted} 명령이 완료되었습니다. {failures} 실패. 알려진 일치 파일 할당: {before} → {after}'
        '; {unknown} 측정값을 알 수 없습니다. 다시 검색할 예정입니다. 총계는 여유 공간을 보장하지 않습니다. '
        '처음 20개의 오류가 표시됩니다.'
    ),
    'compression_canceled': '중지됨; 이전 또는 현재 파일이 변경되었을 수 있습니다. 재검색이 종료되었습니다.',
    'compression_failed': '작업 실패: {reason}. 부분적인 변경이 가능합니다. 재검사에 가깝습니다.',
    'action_exact_allocation': 'Windows 파일별 할당 측정',
    'action_exact_allocation_tip': (
        '기본적으로 꺼져 있습니다. XPRESS/WOF 파일을 포함하여 향후 스캔을 위한 추가 메타데이터 호출. 활성화하'
        '고 다시 검색합니다. 알려진 클라우드/오프라인 파일은 쿼리되지 않은 상태로 유지됩니다. 실패한 쿼리는 '
        '추정치로 유지됩니다.'
    ),
    'menu_compression': 'NTFS 압축…',
    'compression_reading': '기록된 압축 후보 검토 중…',
    'compression_summary': (
        '{count}/{total} 파일은 유형 후보입니다. {shown} 표시; 논리적 {logical}, 명명된 할당 {allocated}. 잠'
        '재적 절약: 0–{allocated}; 고정된 압축률은 예측되지 않습니다. {unknown} 파일에 알 수 없는 메타데이터'
        '가 있습니다.'
    ),
    'compression_volume': '파일 시스템: {filesystem}; 할당 단위: {unit}',
    'compression_unknown': '알 수 없음',
    'compression_ntfs_only': 'NTFS이 확인되지 않았습니다. 이 범위에서는 기본 압축을 사용할 수 없습니다.',
    'compression_partial': '불완전한 스캔: 생략되었거나 읽을 수 없는 데이터가 이 추정치를 벗어났습니다.',
    'compression_hint': (
        '읽기 전용 유형 추정: 로그, 텍스트, 코드 및 압축되지 않은 이미지 형식일 수 있습니다. 확장자는 압축성'
        '을 증명하지 않습니다. 숨김/시스템, 압축/희소, 재분석/클라우드/오프라인 및 알 수 없는 레코드는 생략됩'
        '니다. 명명된 할당은 하드 링크에 의해 추정되거나 공유될 수 있으므로 복구 가능한 공간이 보장되지 않습'
        '니다. 페이로드를 읽지 않았습니다. 두 번 클릭하면 녹음된 파일이 선택됩니다. Ctrl+C는 행을 복사합니다.'
    ),
    'action_capture_owners': 'Windows 파일 소유자 캡처',
    'action_capture_owners_tip': (
        '기본적으로 꺼져 있습니다. 향후 스캔에 소유자 메타데이터 쿼리를 추가합니다. 활성화 및 다시 검색'
    ),
    'tab_users': '사용자',
    'column_owner': '소유자',
    'column_owner_id': '소유자 신원',
    'owner_unknown': '알 수 없는 소유자',
    'owners_refresh': '기록된 총계 새로 고침',
    'owners_reading': '기록된 소유자 합계 추가 및 계정 이름 확인 중...',
    'owners_unqueried': '기록된 소유자 합계를 쿼리하려면 스캔 후 사용자를 엽니다.',
    'owners_partial': (
        '불완전한 스캔: 생략되거나 읽을 수 없는 바이트와 해당 소유자를 알 수 없는 상태로 남아 있습니다.'
    ),
    'owners_summary': (
        '{count} 소유자 그룹; {shown} 표시; {files} 파일, {size}. 알 수 없는 소유자: {unknown_files} 파일, {u'
        'nknown_size}.'
    ),
    'owners_hint': (
        '전체 스캔, 파일 소유자만 해당; 디렉터리 소유권은 하위 항목을 할당하지 않습니다. POSIX uid는 스캔 통'
        '계에서 나옵니다. Windows에서 옵션을 활성화하고 → Windows 파일 소유자를 캡처하고 다시 검색합니다. 비'
        '활성화, 실패, 변경 또는 클라우드/오프라인 쿼리는 알 수 없는 상태로 유지됩니다. 이름은 uid/SID로 대체'
        '될 수 있습니다. 명명된 할당은 추정된 상태로 유지되며 하드 링크는 이름별로 계산됩니다. 소유권은 실제 '
        '사용 또는 제거 권한을 증명하지 않습니다. 정리 작업이 준비되지 않았습니다.'
    ),
    'bin_labels_refresh': '빈 합계 새로 고침',
    'bin_labels_hint': (
        '최대 256개의 준비된 드라이브에 대한 읽기 전용 스냅샷으로, 검사된 드라이브의 우선 순위를 지정합니다. '
        'POSIX 총계는 논리적 페이로드 바이트입니다. 사용할 수 없거나 부분 합계는 0을 의미하지 않습니다. 범위'
        '는 겹칠 수 있습니다. 합산하지 마십시오. 쿼리하려면 새로고침하세요. 이는 정리 작업을 준비하지 않습니'
        '다.'
    ),
    'bin_label_scope_unknown': '이 스캔 드라이브의 휴지통: 범위가 쿼리되지 않았습니다.',
    'bin_label_unqueried': '{root} 휴지통: 쿼리되지 않음',
    'bin_label_total': '{root} 휴지통: {size}, {count} 항목',
    'bin_label_partial': '{root} 휴지통: 총 알 수 없음; 알려진 {size}, {count} 항목',
    'action_file_times': '파일 시간…',
    'action_file_times_tip': '이 스캔에서 기록된 액세스 및 생성 날짜를 필터링합니다.',
    'action_capture_file_times': '파일 액세스/생성 시간 캡처',
    'action_capture_file_times_tip': (
        '기본적으로 꺼져 있습니다. 향후 스캔에 일반 파일당 16바이트를 추가합니다. 활성화 후 다시 검색'
    ),
    'column_accessed': '기록된 접근',
    'column_created': '생성됨',
    'file_times_hint': (
        '옵션 활성화 → 파일 액세스/생성 시간을 캡처한 다음 다시 검색합니다. 일반 파일만 해당; 디렉토리/링크 '
        '및 사용할 수 없는 생성 날짜는 아직 알 수 없습니다. 액세스 날짜는 백그라운드 도구를 통해 비활성화, 지'
        '연 또는 업데이트될 수 있습니다. 실제 사용을 증명하지 않습니다. POSIX ctime은 생성 시간이 아닙니다. '
        '이 보기는 정리 작업을 준비하지 않습니다.'
    ),
    'file_times_accessed': '다음 이후로 열리지 않았습니다... (접속 날짜 기록)',
    'file_times_created': '적어도… 전에 생성됨',
    'file_times_mode': '기록된 연령 모드',
    'file_times_days': '일',
    'file_times_reading': '녹화된 파일 날짜 필터링 중…',
    'file_times_summary': (
        '{count} 일치, {size}; {shown}을 표시합니다. {unknown}/{total} 파일에는 사용할 수 없거나 미래 날짜가 '
        '있습니다.'
    ),
    'file_times_policy_disabled': (
        'NTFS은 액세스 업데이트가 비활성화되었다고 보고합니다. 접속 연령 매칭이 불가능합니다. 생성 필터링은 '
        '계속 사용할 수 있습니다. 레지스트리 설정은 다시 시작해야 할 수 있으며 모든 파일 시스템을 설명하지는 '
        '않습니다.'
    ),
    'file_times_policy_unknown': (
        'NTFS 액세스 업데이트 구성을 알 수 없습니다. 접속 연령 매칭이 불가능합니다. 생성 필터링은 계속 사용할'
        ' 수 있습니다.'
    ),
    'file_times_policy_enabled': (
        'NTFS 레지스트리 보고서 액세스 업데이트가 활성화되었습니다. 재시작 보류, 파일 시스템/공급자 설정 및 '
        '지연된 업데이트가 여전히 날짜에 영향을 미칠 수 있습니다.'
    ),
    'file_times_policy_platform': (
        '파일 시스템/공급자 설정으로 인해 액세스 업데이트가 지연되거나 억제될 수 있습니다. 이러한 날짜를 기록'
        '된 메타데이터로 취급하십시오.'
    ),
    'action_programs': '설치된 프로그램…',
    'action_programs_tip': '이 스캔에서는 설치 프로그램/게임 메타데이터를 설치 폴더와 비교합니다.',
    'program_name': '프로그램/게임',
    'program_source': '메타데이터 소스',
    'program_version': '버전/빌드',
    'program_publisher': '출판사',
    'program_reported': '보고된 추정치',
    'program_scanned': '스캔된 논리 바이트',
    'program_allocated': '스캔된 명명된 할당',
    'program_coverage': '녹음된 폴더 범위',
    'program_location': '설치 폴더',
    'program_registry': 'Windows 레지스트리',
    'program_steam': '스팀 매니페스트',
    'program_epic': '에픽 매니페스트',
    'program_outside': '정확한 스캔 폴더가 없습니다.',
    'program_hint': (
        'Windows 등록 및 인식된 Steam/Epic 매니페스트를 제거하고 이 스캔에서 정확한 폴더에만 일치합니다. Epic'
        '의 고정 ProgramData 매니페스트 폴더도 읽습니다. 보고된 크기는 추정치입니다. 누락된 메타데이터는 알 '
        '수 없는 상태로 유지됩니다. 공유/중첩 폴더는 겹칠 수 있습니다. 행을 합산하거나 복구 가능한 공간으로 '
        '취급하지 마십시오. 휴대용/패키지 앱이 없을 수 있습니다. 두 번 클릭하면 녹음된 폴더가 선택됩니다. Ctr'
        'l+C는 행을 복사합니다. Windows 또는 실행 프로그램을 통해서만 제거하세요.'
    ),
    'program_reading': '설치 메타데이터를 읽는 중…',
    'program_summary': (
        '{count} 설치 중 {shown} 표시 중; {issues} 사용할 수 없거나 형식이 잘못되었거나 생략된 메타데이터 항'
        '목'
    ),
    'program_failed': '설치를 읽을 수 없습니다: {reason}',
    'program_uninstall_page': 'Windows 설치된 앱 설정 열기',
    'program_open_failed': 'Windows 설치된 앱 설정 페이지를 열 수 없습니다.',
    'action_history': '스캔 기록…',
    'action_history_tip': '시간이 지남에 따라 이 루트의 크기를 검토하고 이전 스캔과 비교합니다.',
    'action_history_settings': '스캔 기록 설정…',
    'action_history_settings_tip': '로컬 스캔 메타데이터를 활성화하고 전역 보존 제한을 설정합니다.',
    'history_enable': '완료된 전체 검사를 로컬에 보관',
    'history_settings_hint': (
        '기록에는 폴더 이름, 경로, 합계 및 적용 범위가 저장되며 파일 내용은 저장되지 않습니다. 기본값: 활성화'
        '됨, 모든 루트에서 총 1GiB. 인식된 기록 메타데이터만 제거됩니다. 가장 오래된 것부터 제거됩니다. 비활'
        '성화하면 기존 기록을 계속 읽을 수 있습니다. 변경 사항은 향후 전체 검색에 적용됩니다. 하한은 다음 저'
        '장 시 적용됩니다.'
    ),
    'history_limit': '총 내역 한도',
    'history_time': '스캔 시간',
    'history_logical': '논리 바이트',
    'history_allocated': '할당된 명명된 바이트',
    'history_coverage': '적용 범위',
    'history_incomplete': '미완성; 알려진 데이터만',
    'history_complete': '녹음된 범위를 완료하세요.',
    'history_chart': '시간 경과에 따른 논리적 폴더 크기',
    'history_chart_range': '{first}: {before}; {last}: {after}',
    'history_empty': '이 루트에 대해 보관된 스캔이 없습니다.',
    'history_compare': '선택한 스캔을 현재 결과와 비교',
    'history_reading': '로컬 검사 기록을 읽는 중…',
    'history_hint': (
        '이 루트에 대한 최근 1,000개의 전체 검색이 보관되었습니다. 중지된 검사와 분기 재검사는 저장되지 않습'
        '니다. 불완전한 스캔은 알려진 데이터만 설명합니다. 누락된 폴더는 삭제된 것으로 입증되지 않습니다. 총'
        '계는 하드링크 이름을 별도로 계산합니다. 차이점은 콘텐츠 확인이 아니라 메타데이터입니다.'
    ),
    'history_summary': '{count} 스캔 중 {shown} 표시 중; {invalid} 유효하지 않거나 사용할 수 없는 메타데이터 파일',
    'history_failed': '기록을 읽을 수 없습니다: {reason}',
    'history_save_failed': '스캔이 완료되었지만 기록을 저장할 수 없습니다: {reason}',
    'action_scan_workers': '작업자 스캔…',
    'action_scan_workers_tip': '새로운 스캔에 대한 동시성을 선택하십시오. 높을수록 항상 빠른 것은 아닙니다',
    'workers_prompt': (
        '새 스캔을 위한 작업자(1–32). 기본값은 {default}입니다. 느린 네트워크 공유는 더 많은 작업자로부터 이'
        '익을 얻을 수 있습니다. 과도한 동시성은 디스크/서버에 과부하를 줄 수 있습니다. 스캔을 실행하면 기존 '
        '작업자가 유지됩니다. 실제 UNC 성능은 귀하의 공유에 따라 달라집니다.'
    ),
    'action_bins': '재활용 쓰레기통…',
    'action_bins_tip': '빈 합계 및 명시적인 범위 OS 비우기 검토',
    'bin_finder_empty': '마운트된 모든 볼륨의 Finder 휴지통을 비우세요…',
    'bin_finder_all': '마운트된 모든 볼륨(Finder 전체 휴지통)',
    'bin_finder_scopes': '현재 사용자 휴지통 범위:\n{scopes}\n\n마운트된 볼륨:\n{roots}',
    'bin_finder_first': (
        '마운트된 모든 볼륨에서 현재 사용자의 Finder 휴지통을 비우시겠습니까?\n\n{root}\n\n논리 페이로드: {si'
        'ze}\n항목: {count}'
    ),
    'bin_finder_irreversible': (
        '마운트된 모든 볼륨에서 현재 사용자의 Finder 휴지통을 영구적으로 비우시겠습니까?\n\n{root}\n\n내용의 '
        '논리 크기: {size}\n항목 수: {count}\n\n이 작업은 되돌릴 수 없습니다. Finder 작업 중 새로 들어온 항목'
        '도 삭제될 수 있습니다. 선택한 행과 관계없이 마운트된 모든 휴지통에 적용됩니다. 운영체제 작업은 취소'
        '할 수 없습니다. 자동화 허용 또는 접근 권한 문제로 일부만 처리될 수 있으며, Finder 작업이 계속 진행 '
        '중일 수도 있습니다.'
    ),
    'bin_preparing': '{root}에서 정확한 휴지통 범위를 검토하는 중…',
    'bin_no_approval': '비어 있지 않은 완전한 휴지통 승인이 없습니다. 새로고침하고 다시 검토하세요.',
    'bin_scope_first': (
        '현재 사용자 휴지통 페이로드/작업 기록 범위를 비우시겠습니까?\n\n{root}\n\n논리 페이로드: {size}\n항'
        '목: {count}'
    ),
    'bin_scope_irreversible': (
        '다음 정확한 범위에서 검토한 내용을 영구 삭제하시겠습니까?\n\n{root}\n\n내용의 논리 크기: {size}\n항'
        '목 수: {count}\n\n이 작업은 되돌릴 수 없습니다. 링크의 대상을 따라가지 않고 링크 자체를 삭제합니다. '
        '변경된 항목은 처리하지 않습니다. 실패하면 일부만 처리된 결과가 남을 수 있습니다. 비우기를 시작한 뒤'
        '에는 취소할 수 없습니다.'
    ),
    'bin_partial': '{count} 검토 항목이 삭제되었습니다. 남은 실패: {reason}',
    'bin_empty': '선택한 드라이브의 휴지통 비우기…',
    'bin_first': '{root}의 휴지통을 비우세요?\n\n보고된 크기: {size}\n항목: {count}',
    'bin_irreversible': (
        '{root}의 휴지통에 현재 있는 모든 항목을 영구 삭제하시겠습니까?\n\n보고된 크기: {size}\n항목 수: {cou'
        'nt}\n\n이 작업은 되돌릴 수 없습니다. 운영체제 작업 중 새로 들어온 항목도 삭제될 수 있습니다. 시작한 '
        '뒤에는 운영체제 작업을 취소할 수 없습니다.'
    ),
    'bin_running': '{root}에서 휴지통 비우기; OS 작업을 기다리는 중…',
    'bin_failed': '비우기가 완료되지 않았습니다: {reason}',
    'bin_hint': (
        '마운트된 볼륨 하나를 선택합니다. Windows은 현재 사용자 OS 저장소를 비웁니다. Linux 인벤토리는 파일/'
        '정보 범위를 인식합니다. 두 가지 질문은 영구 제거 전의 정확한 범위와 합계를 보여줍니다. 중지는 설문조'
        '사를 취소합니다. 활성 비우기가 완료되어야 합니다. macOS는 전체 검토 후 마운트된 모든 Finder 휴지통을'
        ' 비웁니다(기본 유효성 검사 보류 중). 용량/bin 값은 나중에 새로 고쳐집니다. 메인 트리를 업데이트하려'
        '면 다시 스캔하세요.'
    ),
    'action_volumes': '드라이브 개요…',
    'action_volumes_tip': '마운트된 볼륨, 용량, 할당 단위 및 휴지통 총계를 검사합니다.',
    'volume_root': '마운트된 루트',
    'volume_name': '볼륨 이름',
    'volume_fs': '파일 시스템',
    'volume_total': '합계',
    'volume_used': '중고',
    'volume_free': '당신이 사용할 수',
    'volume_cluster': '할당단위',
    'volume_trash': '휴지통 바이트',
    'volume_trash_count': '빈 항목',
    'volume_reading': '마운트된 볼륨 및 휴지통 합계를 읽는 중…',
    'volume_summary': '{count} 중 {shown} 마운트된 볼륨을 표시합니다. 스캔하려면 두 번 클릭하세요.',
    'volume_trash_partial': '알 수 없는 합계({known} 알려짐)',
    'volume_hint': (
        'OS 용량 스냅샷 사용 가능한 공간에는 예약이나 할당량이 제외될 수 있습니다. 반복 마운트는 용량을 공유'
        '할 수 있습니다. 행을 합산하지 마세요. Windows 할당 단위는 클러스터입니다. POSIX 단위는 최적의 전송 '
        '크기가 아닌 파일 시스템 조각입니다. 휴지통에는 회수 가능한 공간이 아닌 OS에서 보고한 Windows 총계 또'
        '는 알려진 POSIX 논리적 페이로드 바이트가 표시됩니다. 디렉터리/작업 기록 메타데이터 및 공유 할당은 제'
        '외됩니다. 오류는 아직 알려지지 않았습니다. 중지는 현재 OS 호출을 기다립니다. 취소된 설문조사는 폐기'
        '됩니다. Ctrl+C는 행을 복사합니다. 여기서는 비우기 작업이 제공되지 않습니다.'
    ),
    'action_export_report_html': '스캔 보고서(HTML)…',
    'action_export_report_html_tip': '3개의 차트 이미지가 포함된 독립형 보고서 저장',
    'action_export_report_xlsx': '보고서 스캔(Excel)…',
    'action_export_report_xlsx_tip': '보고서 목록을 별도의 Excel 워크시트에 저장',
    'html_filter': 'HTML 보고서(*.html)',
    'xlsx_filter': 'Excel 통합 문서(*.xlsx)',
    'report_title': 'FileTree 스캔 보고서',
    'report_note': (
        '알려진 기록 범위만 해당. 할당은 추정치입니다. 제목의 개수는 표시/총계로 표시됩니다. 상위 폴더가 겹칩'
        '니다. 해당 행을 추가하지 마세요. 가장 큰 파일과 폴더는 1,000개로 제한됩니다. 파일 형식을 10,000으로 '
        '늘립니다. 크기는 바이트입니다. 연령은 마지막 액세스가 아닌 기록된 수정 시간을 사용합니다. 이용할 수 '
        '없는 날짜는 기존의 가장 오래된 연령 그룹에 속합니다. HTML 차트는 제한된 형상으로 전체 스캔 루트를 표'
        '시합니다. Excel 텍스트는 이스케이프되고 제어 문자는 16진수로 표시되며 셀은 32,767자로 제한되고 16자'
        '리 이상의 정수는 정확한 텍스트로 저장됩니다.'
    ),
    'report_bytes': '논리 바이트',
    'report_allocated': '할당된 바이트(예상)',
    'report_created': '보고서가 생성되었습니다.',
    'report_reference': '연령 참고',
    'report_skipped': '건너뛴 폴더',
    'report_denied': '읽을 수 없는 폴더',
    'report_pending': '보류 중인 폴더',
    'report_summary': '요약',
    'report_notes': '메모',
    'report_field': '필드',
    'report_value': '가치',
    'report_top_folders': '가장 큰 폴더(겹침)',
    'report_categories': '카테고리',
    'action_projects': '프로젝트 및 재구성 가능한 데이터…',
    'action_projects_tip': '기록된 프로젝트, Git 및 생성된 데이터 크기 검사',
    'project_path': '프로젝트/관리 매장',
    'project_kind': '감지된 종류',
    'project_other': '출처/기타',
    'project_git': '.git',
    'project_generated': '재구성 가능한 데이터',
    'project_coverage': '적용 범위',
    'project_partial': '미완성',
    'project_recorded': '기록된 범위',
    'project_hint': (
        '알려진 논리 바이트만. 중첩된 프로젝트가 겹칩니다. Git 포인터 파일에는 외부 메타데이터가 생략되어 있'
        '습니다. 생성된 데이터에는 사용자 정의 파일이 포함될 수 있습니다. 이동하기 전에 검토하세요. Maven, 글'
        '로벌 Gradle 및 Docker 스토어는 별도로 표시됩니다. 그 내용물은 일회용이 아닌 것으로 추정됩니다.'
    ),
    'project_reading': '기록된 프로젝트 데이터를 검사하는 중…',
    'project_summary': '감지된 {count} 중에서 가장 큰 프로젝트/매장 {shown}개를 표시합니다.',
    'project_review': '재구축 가능한 적격 항목을 검토하세요…',
    'project_review_count': (
        '현재 연령, 적용 범위 및 청소 정책에 따라 적격한 {count} 항목 중 최대 {shown} 항목을 검토하세요. 중지'
        '된 스캔은 항목을 제안할 수 없습니다.'
    ),
    'project_git_kind': '힘내',
    'project_python': '파이썬',
    'project_node': 'Node.js',
    'project_rust': '녹',
    'project_jvm': 'JVM',
    'project_conda': '콘다 프로젝트',
    'project_python_environment': 'Python 환경',
    'project_conda_environment': '콘다 환경',
    'project_maven_store': '메이븐 스토어',
    'project_gradle_store': '글로벌 Gradle 스토어',
    'project_docker_store': '도커 데이터',
    'action_git_history': '힘내 역사…',
    'action_git_history_tip': '모든 Git 참조에서 연결할 수 있는 가장 큰 개체를 검사합니다.',
    'git_oid': '개체 ID',
    'git_kind': '객체 유형',
    'git_length': '비압축 길이',
    'git_type_blob': '파일 콘텐츠(BLOB)',
    'git_type_tree': '디렉토리 목록(트리)',
    'git_type_commit': '커밋',
    'git_type_tag': '주석이 달린 태그',
    'git_hint': (
        '읽기 전용 Git 배관은 모든 참조를 검사하여 최대 1,000개의 개체를 유지합니다. 크기는 디스크 할당이나 '
        '복구 가능한 공간이 아닌 압축되지 않은 길이입니다. Git의 객체 이름 힌트가 모호할 수 있으므로 이름은 '
        '생략됩니다. Ctrl+C는 개체 ID/행을 복사합니다. 선택적 잠금, 자동 유지 관리 및 지연 네트워크 가져오기'
        '가 비활성화됩니다. Git은 --no-lazy-fetch를 지원해야 합니다. 저장소 소유권 오류는 우회되지 않습니다. '
        '중지는 취소됩니다. 여기서는 gc가 실행되지 않습니다.'
    ),
    'git_reading': 'Git 기록을 조사하는 중…',
    'git_summary': '{count} 연결 가능한 객체 중 {shown} 표시 중; 압축되지 않은 총계 {size}.',
    'git_gc_loose': (
        'Git gc는 {count} 느슨한 개체를 통합할 수 있지만 이러한 가장 큰 개체는 참조에서 계속 연결할 수 있으며'
        ' 제거되지 않습니다. 실제 절감액 및 기타 접근할 수 없는/재로그 데이터는 알 수 없습니다.'
    ),
    'git_gc_packed': (
        '통합할 느슨한 개체가 없습니다. Git gc는 참조가 유지하는 동안 이러한 객체를 제거하지 않습니다. 기타 '
        '연결할 수 없는/재로그 데이터 및 실제 절감액은 측정되지 않았습니다.'
    ),
    'git_failed': 'Git 검사 실패: {reason}',
    'tree_filter_placeholder': '펼친 폴더 필터…',
    'tree_filter_hint': (
        '이미 확장된 폴더 내에서만 이름을 일치시킵니다(대소문자 구분 안 함). 조상은 계속 보입니다. 접힌 내용'
        '은 검색되지 않습니다. 트리를 복원하려면 필터를 지우세요. 차트/목록에서 숨겨진 항목을 선택하면 필터가'
        ' 지워집니다. 스캔 합계 및 내보내기는 변경되지 않습니다.'
    ),
    'action_live_compare': '두 폴더를 비교합니다…',
    'action_live_compare_tip': '새로운 상대 경로를 비교하고 요청된 파일 쌍만 확인합니다.',
    'compare_choose_left': '왼쪽 폴더를 선택하세요',
    'compare_choose_right': '올바른 폴더를 선택하세요',
    'compare_relative': '상대 경로',
    'compare_state': '비교',
    'compare_left_size': '왼쪽 사이즈',
    'compare_right_size': '적당한 크기',
    'compare_left_time': '왼쪽 수정됨',
    'compare_right_time': '오른쪽 수정됨',
    'compare_roots': '왼쪽: {left}\n오른쪽: {right}',
    'compare_hint': (
        '읽기 전용: 정확한 유니코드/대소문자 이름이 일치합니다. 링크는 따라가지 않습니다. 동일한 크기/시간은 '
        '동일한 내용을 증명하지 않습니다. 파일 쌍을 선택하고 중지 기능을 사용하여 전체 해시를 확인하세요. 변'
        '경되어 읽을 수 없으며 알려진 클라우드 파일은 계속 사용할 수 없습니다. 결과는 이 스캔/검증 시간을 나'
        '타냅니다. 복사, 이동 또는 동기화가 수행되지 않습니다. Ctrl+C는 행을 복사합니다. CSV은 표시된 행만 최'
        '대 10,000개까지 내보냅니다.'
    ),
    'compare_reading': '두 폴더를 모두 검사하는 중…',
    'compare_error': '비교 또는 내보내기 실패: {reason}',
    'compare_hashing': '선택한 파일 쌍을 확인하는 중…',
    'compare_verify': '선택한 내용을 확인하세요',
    'compare_summary': '{count} 상대 경로 중 {shown} 표시 중(10,000개 제한)',
    'compare_incomplete': '보장이 불완전합니다. 읽을 수 없는 범위의 누락된 경로는 알 수 없는 상태로 남아 있습니다.',
    'compare_unavailable': '사용할 수 없거나 변경됨',
    'compare_link': '링크; 읽지 않은 내용',
    'compare_only_left': '왼쪽에만',
    'compare_only_right': '오른쪽에만',
    'compare_different_kind': '다양한 항목 유형',
    'compare_folder': '양쪽에 폴더',
    'compare_different_size': '다양한 크기',
    'compare_different_time': '다른 시간; 체크되지 않은 내용',
    'compare_unchecked': '확인되지 않은 내용',
    'compare_identical': '전체 해시 일치',
    'compare_different_bytes': '다양한 콘텐츠',
    'problem_mount_boundary': '마운트 경계: 콘텐츠가 스캔되지 않음',
    'action_special_files': '클라우드와 특수 파일…',
    'action_special_files_tip': '기록된 리콜, 오프라인, 압축 및 스파스 파일 상태 검사',
    'special_states': '기록된 상태',
    'special_content_size': '전체 콘텐츠 크기',
    'special_recall': '액세스 시 기억할 수 있음',
    'special_offline': '오프라인',
    'special_compressed': '압축',
    'special_sparse': '스파스',
    'special_allocation_low': '더 낮은 할당; 원인불명',
    'special_reading': '녹음된 파일 메타데이터를 읽는 중…',
    'special_hint': (
        '이 목록은 검색 메타데이터만 사용하며 파일이 열리거나 다운로드되지 않습니다. 리콜/오프라인 플래그는 O'
        'neDrive, Dropbox 또는 기타 제공자를 설명할 수 있습니다. 공급자와 이미 현지에 얼마가 있는지 추론할 수'
        ' 없습니다. 전체 콘텐츠 크기는 온라인 콘텐츠를 포함한 논리적 길이입니다. 다운로드 후 할당을 알 수 없'
        '습니다. 희박한 구멍, 압축 및 상주 데이터로 인해 할당이 줄어들 수 있습니다. 리콜/오프라인 항목에 대한'
        ' 디스크 0은 측정된 클라우드 할당이 아니라 추정치입니다. 두 번 클릭하면 스캔한 항목이 선택됩니다. Ctr'
        'l+C는 선택한 행을 복사합니다.'
    ),
    'special_summary': (
        '{count} 일치하는 파일 중 {shown}을 표시합니다. 전체 콘텐츠 {size}; 기록된 할당 {allocated}. 사용할 '
        '수 없는 파일 메타데이터: {unknown}. 최대 1,000개가 유지됩니다.'
    ),
    'special_partial': '스캔 범위가 불완전합니다. 보이지 않는 파일은 알 수 없는 상태로 남아 있습니다.',
    'action_shell_integration': '탐색기 통합…',
    'action_shell_integration_tip': '탐색기 폴더 메뉴에서 FileTree를 사용하여 스캔을 추가하거나 제거합니다.',
    'shell_enabled': '탐색기의 폴더 메뉴에 FileTree를 사용하여 스캔 추가',
    'shell_scan': 'FileTree로 스캔',
    'shell_hint': (
        '변경 사항은 계정의 폴더 메뉴에만 저장하세요. 관리자 권한이 필요하지 않습니다. Windows 11에서 추가 옵'
        '션 표시 아래를 살펴보세요. 항목을 제거하려면 여기에서 이 기능을 끄세요. 실행 파일 이동 또는 소스 체'
        '크아웃 후 다시 등록하세요.'
    ),
    'shell_failed': 'Explorer 통합을 변경할 수 없습니다.\n{reason}',
    'menu_properties': '속성',
    'properties_failed': 'Windows은(는) 다음에 대한 속성을 열 수 없습니다:\n{path}',
    'menu_theme': '테마',
    'theme_system': '시스템',
    'theme_light': '빛',
    'theme_dark': '어둠',
    'chart_access_keys': (
        '화살표 키는 렌더링된 항목을 선택합니다. Enter를 누르면 폴더가 열립니다. 백스페이스가 올라갑니다. 그'
        '룹화된 항목이나 숨겨진 항목에는 폴더 트리를 사용하세요.'
    ),
    'chart_access_tree_keys': (
        '위/아래는 카드를 선택합니다. 오른쪽/왼쪽은 폴더를 확장/축소합니다. Enter를 누르면 폴더가 열립니다. '
        '백스페이스가 올라갑니다.'
    ),
    'chart_access_folder': '표시 폴더: {path}',
    'chart_access_selected': '선택됨: {path}. 크기 {size}; 디스크 {allocated}; {files} 파일, {folders} 폴더.',
    'system_file_hibernate': (
        '최대 절전 모드 및 빠른 시작 상태. Windows이 이 파일을 관리합니다. 관리자는 powercfg /hibernate off를'
        ' 사용하여 최대 절전 모드를 비활성화할 수 있습니다. 이렇게 하면 최대 절전 모드도 제거되고 빠른 시작에'
        ' 영향을 미칠 수 있습니다. FileTree은 전원 설정만 엽니다.'
    ),
    'system_file_pagefile': (
        '가상 메모리 백업 파일. Windows은 크기를 자동으로 관리할 수 있습니다. 고급 탭의 성능 설정에서 가상 메'
        '모리를 검토하세요. 이를 줄이면 애플리케이션과 크래시 덤프에 영향을 미칠 수 있습니다.'
    ),
    'system_file_swapfile': (
        'Windows 정지된 앱 데이터를 포함한 스왑 백업 파일. Windows은 가상 메모리와 함께 관리합니다. 시스템 메'
        '모리 설정을 제거하는 대신 검토하십시오.'
    ),
    'system_file_old': (
        '이전 Windows 설치. 디스크 정리 → 시스템 파일 정리에서 이전 Windows 설치를 검토합니다. 이를 제거하면 '
        '해당 설치로 돌아갈 수 없습니다.'
    ),
    'system_file_recycle': (
        '삭제된 항목은 휴지통이 비워질 때까지 여전히 디스크 공간을 차지합니다. 휴지통이나 스토리지 센스를 검'
        '토하세요. 비우는 것은 영구적입니다.'
    ),
    'system_file_restore': (
        '시스템 메타데이터, 복원 지점 및 섀도 복사본. 시스템 보호 → 구성을 검토하여 복원 지점 제한을 설정합니'
        '다. 백업 소유의 섀도 복사본에는 자체 백업 도구가 필요할 수 있습니다. 읽지 않은 바이트는 알 수 없는 '
        '상태로 남아 있습니다.'
    ),
    'system_file_winsxs': (
        'Windows 구성요소 저장소. 많은 항목이 Windows 파일과 하드 링크를 공유하므로 이름별 총계가 개별 저장소'
        '를 과장할 수 있습니다. 디스크 정리에서 Windows 업데이트 정리 사용 → 시스템 파일 정리; 구성 요소를 수'
        '동으로 제거하지 마십시오.'
    ),
    'system_file_updates': (
        'Windows 다운로드 데이터를 업데이트합니다. 디스크 정리 → 시스템 파일 정리를 사용하여 Windows 업데이트'
        ' 및 임시 파일을 검토합니다. 활성 다운로드를 관리하려면 업데이트 서비스를 종료하세요.'
    ),
    'system_file_delivery': (
        'Windows 업데이트 및 앱에 대한 배달 최적화 다운로드 캐시입니다. 디스크 정리에서 배달 최적화 파일을 검'
        '토합니다. Windows은 활성 전송을 관리합니다.'
    ),
    'system_tool_power': '전원 설정 열기…',
    'system_tool_memory': '고급 시스템 설정 열기…',
    'system_tool_cleanup': '디스크 정리 열기…',
    'system_tool_storage': '오픈 스토리지 센스…',
    'system_tool_restore': '개방형 시스템 보호…',
    'system_tool_failed': 'Windows 도구를 열 수 없습니다.',
    'trash_skip_system_managed': 'Windows이 이 항목을 관리합니다. 대신 세부정보의 시스템 도구를 사용하세요.',
    'type_locations_title': '폴더 포함(최대 1,000개)',
    'type_location_size': '어울리는 사이즈',
    'type_locations_tip': (
        '총계에는 각 폴더에 직접 일치하는 파일이 포함됩니다. 하위 폴더는 겹치지 않고 분리되어 있습니다.'
    ),
    'action_export_list': '현재 목록(CSV)…',
    'action_export_list_tip': '표시된 필터 및 정렬 순서에 따라 활성 목록의 모든 행을 저장합니다.',
    'list_changed': '캡처 중에 목록이 변경되었습니다. 다시 내보내거나 복사해 보세요.',
    'details_title': '세부정보',
    'details_empty': '세부정보를 보려면 항목을 선택하세요.',
    'details_live': '스캔이 완료되면 배포가 가능합니다.',
    'details_loading': '유형 및 연령 분포를 계산하는 중…',
    'details_recorded': (
        '녹음된 파일 합계만; 읽지 않은 항목은 이러한 배포판 외부에 있습니다. 폴더 수정은 가장 최근에 녹음된 '
        '날짜입니다.'
    ),
    'details_bucket': '{label}: {size} · {count} 파일',
    'breadcrumbs_back': '뒤로(Alt+왼쪽)',
    'breadcrumbs_forward': '앞으로(Alt+오른쪽)',
    'breadcrumbs_more': '…',
    'breadcrumbs_more_tip': '이전 조상 표시',
    'action_print_view': '현재 보기 인쇄…',
    'action_print_view_tip': '시스템 인쇄 대화 상자를 통해 한 페이지에 보이는 결과를 인쇄합니다.',
    'action_export_view_pdf': '현재 보기(PDF)…',
    'action_export_view_pdf_tip': '하나의 적합한 PDF 페이지에 눈에 보이는 결과를 저장하세요.',
    'pdf_filter': 'PDF 문서(*.pdf)',
    'view_pdf_exported': '저장된 현재 보기: {path}',
    'print_failed': '뷰를 인쇄할 수 없습니다: {reason}',
    'print_submitted': '프린터에 제출된 보기',
    'action_export_chart_png': '화면 위의 차트(PNG)…',
    'action_export_chart_png_tip': '현재 뷰포트를 포함하여 보이는 차트를 저장합니다.',
    'action_export_chart_svg': '막대 또는 햇살(SVG)…',
    'action_export_chart_svg_tip': '전체 경계 막대 또는 링을 벡터 모양 및 텍스트로 저장',
    'png_filter': 'PNG 이미지(*.png)',
    'svg_filter': 'SVG 이미지(*.svg)',
    'graphic_exported': '저장된 차트: {path}',
    'treemap_colours_age': '수정된 연령별',
    'age_colour_unknown': '날짜를 알 수 없음',
    'age_colour_tip': (
        '수정 이후 시간입니다. 폴더 색상은 가장 최근에 기록된 수정 사항을 사용합니다. 회색은 사용 가능한 날짜'
        '가 없음을 의미합니다. 그룹화된 타일은 회색으로 유지됩니다.'
    ),
    'action_gentle': '부드러운 스캐닝',
    'action_gentle_tip': '새로운 스캔에 대해서는 CPU 및 I/O 우선순위를 낮춥니다. 더 오래 걸릴 수 있습니다',
    'scan_priority_warning': '일부 스캔 우선순위 설정을 적용할 수 없습니다: {reason}',
    'scan_pause': '일시중지',
    'scan_resume': '이력서',
    'scan_pause_tip': (
        '새 폴더 읽기를 일시 중지합니다. 현재 읽기가 완료되었습니다. 중지는 일시 정지된 동안 작동합니다.'
    ),
    'scan_paused': '일시중지됨 — {progress}',
    'scan_analysing': '폴더 읽기가 완료되었습니다. 결과 분석 중…',
    'column_drive_share': '드라이브 %',
    'columns_reset': '열 재설정',
    'drive_share_tip': (
        '논리 바이트를 총 볼륨 용량으로 나눈 값입니다. 하드 링크 이름은 별도로 계산됩니다. 이는 할당되거나 복'
        '구 가능한 공간이 아닙니다. 용량을 사용할 수 없거나 오래된 동안에는 알 수 없습니다.'
    ),
    'action_recent_actions': '최근 활동…',
    'action_recent_actions_tip': '보관된 작업 메타데이터를 검사하고 수정된 감사 보고서를 내보냅니다.',
    'journal_time': '시간(UTC)',
    'journal_source': '원래 경로',
    'journal_identity': '장치/파일 ID',
    'journal_result': '결과',
    'journal_detail': '세부정보',
    'journal_destination': '휴지통 목적지',
    'journal_reason_duplicates': '명시적 중복 결정',
    'journal_status_approved': '알 수 없는 결과(승인된 경우에만)',
    'journal_status_moved': '휴지통으로 이동됨',
    'journal_status_skipped': '건너뛰었습니다.',
    'journal_status_failed': '플랫폼 이동 실패',
    'journal_reading': '보관된 작업을 읽는 중…',
    'journal_hint': (
        '최근 500개 작업; 메타데이터만, 90일/50MB 동안 보관됩니다. 승인 전용 이벤트에는 알 수 없는 최종 결과'
        '가 있습니다. 기록된 휴지통 경로는 복원을 보장하지 않습니다.'
    ),
    'journal_summary': '{count} 작업이 표시됩니다. {invalid} 손상된 레코드 및 {unavailable} 사용할 수 없는 세그먼트.',
    'journal_read_failed': '작업 일지를 읽을 수 없습니다: {reason}',
    'journal_write_failed': (
        '저널 작성 또는 보관에 실패했습니다. 가능한 경우 나머지 동작은 중지되었습니다. 최근 작업이 완료되지 '
        '않았을 수 있습니다.\n\n{reason}'
    ),
    'trash_skip_journal': '승인된 조치를 기록할 수 없습니다. 아무것도 움직이지 않았어',
    'journal_export': '수정된 CSV 내보내기…',
    'journal_exported': '홈 디렉토리 접두사가 수정되어 저장된 감사 보고서입니다.',
    'duplicate_folder_match': '{copy} = {original} ({size}, {files} 파일; 일치하는 검색 스냅샷)',
    'duplicate_folder_tip': '이름, 크기, 검증된 해시 및 빈 폴더 구조가 일치합니다. 읽기 전용; 청소 승인이 아닙니다.',
    'duplicates_keep_selected': '선택한 사본 유지',
    'duplicates_kept_name': '보관됨: {name}',
    'duplicates_kept_path': '보관된 사본: {path}.',
    'duplicates_choose_keeper': '추가 항목을 선택하기 전에 이 그룹에 보관된 사본을 선택하세요.',
    'duplicates_group_blocked': '그룹은 그대로 유지됩니다. 재검색 필요: {reason}',
    'trash_skip_duplicate_choose': '보관된 사본을 선택한 다음 그룹을 다시 검토하세요.',
    'trash_skip_duplicate_keep': '보관된 사본이 선택되었습니다. 그룹은 그대로 유지되었습니다. 다시 스캔',
    'trash_skip_duplicate_unverified': '이 그룹에 대해 확인된 해시가 없습니다. 다시 스캔하고 다시 검색해 보세요.',
    'trash_skip_duplicate_hard_links': '복사본에는 하드링크 별칭이 있습니다. 그룹은 그대로 유지되었습니다. 다시 스캔',
    'trash_skip_duplicate_content': (
        '그룹 콘텐츠가 변경되었거나 다시 해시될 수 없습니다. 다시 스캔하고 다시 검색해 보세요.'
    ),
    'menu_options': '옵션',
    'action_cleanup_policy': '청소정책…',
    'action_cleanup_policy_tip': '규칙을 활성화하고, 최소 기간을 변경하고, 정리 제안에서 경로를 제외하세요.',
    'policy_enabled': '활성화됨',
    'policy_age': '최소 연령(일)',
    'policy_age_for': '{rule}의 최소 연령',
    'policy_enabled_for': '{rule} 활성화',
    'policy_hint': (
        '정책 변경사항은 제안에만 영향을 미칩니다. 수동 위험 규칙은 선택되지 않은 상태로 유지됩니다. 저장하기'
        ' 전에 미리 보세요.'
    ),
    'policy_exclusions': (
        '이러한 경로나 이름을 제안하지 마십시오(한 줄에 하나씩, 경로는 절대 경로여야 함). 스캔은 변경되지 않'
        '습니다.'
    ),
    'policy_preview': '변경사항 미리보기',
    'policy_import': '가져오기 정책 JSON…',
    'policy_preview_needed': '저장하기 전에 현재 설정을 미리 봅니다.',
    'policy_preview_running': '후보 수와 논리적 크기 비교…',
    'policy_preview_result': (
        '{added} 후보({size})를 추가합니다. {removed} 후보({removed_size})를 제거합니다. 아무것도 움직이지 않'
        '았습니다.'
    ),
    'policy_preview_partial': '스캔이 불완전합니다. 보이지 않는 후보와 바이트는 알 수 없는 상태로 남아 있습니다.',
    'policy_no_scan': '스캔이 완료되지 않음: 효과를 측정할 수 없습니다. 이 설정은 향후 제안에 적용됩니다.',
    'policy_invalid': (
        '정책이 잘못되었습니다. 지원되는 규칙 키, 예/아니요 플래그, 연령 0~36500 및 절대 경로 또는 이름 패턴'
        '을 사용하세요.'
    ),
    'policy_saved': '정리 정책이 저장되었습니다. 제안사항을 새로고침하는 중입니다.',
    'policy_saved_invalid': '저장된 정리 정책이 잘못되었습니다. 옵션에서 정책을 검토할 때까지 제안이 비활성화됩니다.',
    'cleanup_review_manual': '직접 검토',
    'cleanup_evidence': (
        '카테고리: {category}; 최소 연령: {days}일; 위험: {risk}. 증거: {evidence} 재구축/결과: {rebuild}'
    ),
    'cleanup_category_temporary': '임시 파일',
    'cleanup_category_cache': '다운로드/생성된 캐시',
    'cleanup_category_application_state': '애플리케이션 상태',
    'cleanup_category_build': '프로젝트 빌드 출력',
    'cleanup_category_downloads': '사용자 다운로드',
    'cleanup_risk_low': '위험 감소; 이사하기 전에 확인하세요',
    'cleanup_risk_manual': '수동 검토; 선택하지 않은 채 시작됩니다',
    'cleanup_rebuild_temp': '소유 애플리케이션을 닫습니다. 임시 데이터는 반드시 다시 생성될 수 없습니다.',
    'cleanup_rebuild_browser_cache': (
        '브라우저를 닫습니다. 캐시된 페이지를 다시 다운로드합니다. 프로필과 북마크는 제외됩니다.'
    ),
    'cleanup_rebuild_thumbnails': '파일 관리자를 닫습니다. 필요할 때 미리보기가 다시 생성됩니다.',
    'cleanup_rebuild_crash_dumps': '필요한 충돌 증거를 보관하십시오. 과거 크래시 덤프를 다시 생성할 수 없습니다.',
    'cleanup_rebuild_package_caches': (
        '다시 다운로드하려면 패키지 관리자를 사용하세요. 네트워크 액세스를 확인하세요. 패키지 매장은 제외됩니'
        '다.'
    ),
    'cleanup_rebuild_build_output': (
        '프로젝트 내용과 종속성 잠금을 확인한 다음 문서화된 프로젝트 명령을 사용하여 다시 빌드하세요. 작성된 '
        '파일을 보관하세요.'
    ),
    'cleanup_rebuild_old_installers': (
        '설치 프로그램을 오프라인으로 유지하거나 사용할 수 없게 합니다. 아직 사용 가능한 경우 게시자로부터 다'
        '운로드하세요.'
    ),
    'cleanup_rebuild_empty_folders': (
        '응용프로그램에서는 여전히 빈 폴더가 나타날 것으로 예상할 수 있습니다. 먼저 목적을 확인하십시오.'
    ),
    'trash_holder': '{name} (PID {pid})',
    'trash_holders': (
        '{path}: {programs}에서 열려 있는 것으로 관찰되었습니다. 해당 프로그램을 직접 종료하고 다시 시도해 보'
        '세요.'
    ),
    'trash_holders_limited': (
        '{path}: 프로세스 가시성이 제한됩니다. 다른 보유자 또는 원인이 알려지지 않았을 수 있습니다.'
    ),
    'duplicates_savings': '고유 할당 추정치 {allocated}; 휴지통 {recoverable}을 비운 후 복구 가능한 파일 데이터.',
    'duplicates_estimating': '고유 할당 및 복구 가능한 파일 데이터 추정 중…',
    'duplicates_estimate_unavailable': (
        '예상 할당량을 확인할 수 없습니다. 추가 항목을 선택하기 전에 검색을 다시 실행하세요.'
    ),
    'duplicates_estimate_assumption': (
        '견적은 명시적인 보관 사본 선택을 사용합니다. 미정 그룹은 알 수 없습니다. 이동하기 전에 각 그룹을 확'
        '인하고 완전히 다시 해시합니다. 하드 링크 별칭은 결정을 차단합니다. 공유 범위와 디렉터리 메타데이터는'
        ' 아직 알려지지 않았습니다. 휴지통으로 이동해도 공간이 확보되지 않습니다.'
    ),
    'capacity_details': '용량 세부정보',
    'capacity_summary': 'OS 사용량 {used}; 여유 공간 {free}; 중복 제외 할당량 추정 {unique}. {status}',
    'capacity_estimated': '전체 볼륨의 추정치입니다. 설명되지 않은 공간은 세부 정보에 표시합니다.',
    'capacity_folder_only': '폴더만 스캔했습니다. 전체 볼륨 용량과 대조할 수 없습니다.',
    'capacity_incomplete': '스캔이 불완전합니다. 전체 볼륨 용량과 대조할 수 없습니다.',
    'capacity_identity_unknown': '파일 ID가 없습니다. 전체 볼륨 용량과 대조할 수 없습니다.',
    'capacity_capacity_unavailable': 'OS 용량을 확인할 수 없습니다. 전체 볼륨 용량과 대조할 수 없습니다.',
    'capacity_root_changed': '스캔한 루트가 변경되었습니다. 용량을 대조하기 전에 다시 스캔하세요.',
    'capacity_allocation_exceeds_used': '할당량 추정치가 OS 사용량을 초과하여 용량을 대조할 수 없습니다.',
    'capacity_coverage': '건너뛴 {skipped}; 읽을 수 없음 {inaccessible}; {pending} 보류 중',
    'capacity_bin_partial': '휴지통을 완전히 식별하거나 읽지 못했습니다. 표시된 용량은 확인된 데이터만 포함합니다.',
    'capacity_explanation': (
        '알려진 파일 할당에는 표시된 휴지통 데이터가 포함됩니다. 하드링크 이름은 한 번만 계산됩니다. 다른 마'
        '운트된 볼륨은 제외됩니다. 생략된 데이터와 파일 시스템 메타데이터는 알 수 없으며 0이 아닙니다. 설명되'
        '지 않은 항목에는 액세스할 수 없는 데이터, 메타데이터, 스냅샷, 공유 범위 및 할당 추정치가 포함될 수 '
        '있습니다. OS 용량과 파일은 다양한 순간에 측정됩니다. 파일 시스템은 스캔 중에 변경될 수 있습니다. 사'
        '용할 수 없는 여유 공간은 측정된 메타데이터 총계가 아니라 보고된 총계, 사용된 공간 및 사용 가능한 여'
        '유 공간 간의 차이입니다. 이는 NTFS, ext4 및 APFS 볼륨 검증이 보류 중인 추정치입니다.'
    ),
    'capacity_row_total': 'OS 전체',
    'capacity_row_used': 'OS 사용량',
    'capacity_row_free': 'OS 사용 가능한 여유 공간',
    'capacity_row_unavailable_free': '사용할 수 없는 여유 공간',
    'capacity_row_named_allocated': '이름별 할당량 추정',
    'capacity_row_unique_allocated': '중복 제외 할당량 추정',
    'capacity_row_hard_link_overcount': '제외된 하드 링크 중복 집계',
    'capacity_row_recycle_bin_seen': '휴지통 할당 확인(포함)',
    'capacity_row_foreign_allocated_seen': '기타 볼륨 파일 할당 확인(제외)',
    'capacity_row_unaccounted': '설명되지 않음',
    'capacity_row_metadata_bytes': '파일 시스템 메타데이터 / 예약됨',
    'capacity_row_omitted_bytes': '생략된 데이터',
    'capacity_row_other_volumes_bytes': '기타 마운트된 볼륨',
    'capacity_row_mounts': '다른 장치의 마운트 경계',
    'capacity_row_coverage': '적용 범위',
    'review_title': '청소 제안 검토',
    'review_details': '{path}\n규칙: {rule}; 보호: {protection}. {consequence}',
    'review_hint': '모든 경로와 결과를 검토하십시오. 항목을 유지하려면 선택을 취소하세요. 계속 확인이 열립니다.',
    'review_select': '이동',
    'review_rule': '규칙',
    'review_reason': '이유',
    'review_protection': '보호',
    'review_consequence': '결과',
    'review_manual': '수동 선택',
    'review_manual_reason': (
        '사용자가 선택한 항목 이를 제거하면 이에 의존하는 파일이나 프로그램에 영향을 미칠 수 있습니다.'
    ),
    'review_not_protected': '보호된 경로 일치 없음',
    'review_open_folder': '포함된 폴더 열기',
    'review_continue': '계속해서 확인하세요',
    'review_estimating': '{count} 항목이 선택되었습니다. 할당 추정 중…',
    'review_summary': (
        '{count} 항목; 논리적 {logical}; 할당된 추정치 {allocated}; 휴지통을 비운 후 복구 가능한 파일 데이터:'
        ' {recoverable}; 지금 무료입니다 {free}. 공유 범위와 디렉터리 메타데이터는 아직 알려지지 않았습니다. '
        '휴지통으로 이동해도 공간이 확보되지 않습니다.'
    ),
    'size_unknown': '알 수 없음',
    'trash_running': '승인된 항목을 재검증하고 이동하는 중... 중지를 누르면 나머지 항목이 취소됩니다.',
    'trash_batch_done': '{moved} 이동, {skipped} 건너뛰기, {failed} 실패; {size}이(가) 휴지통으로 이동되었습니다.',
    'trash_skipped': '이 항목은 건너뛰었습니다. 다시 시도하기 전에 폴더를 다시 검사하세요.\n{names}',
    'trash_skip_outside': '현재 스캔 외부',
    'trash_skip_unverified': '확인된 스캔 ID 없음',
    'trash_skip_incomplete': '불완전한 스캔 범위',
    'trash_skip_missing': '항목 또는 상위 항목이 누락되었습니다.',
    'trash_skip_unreadable': '항목을 읽을 수 없습니다',
    'trash_skip_link': '항목 또는 상위가 링크가 되었습니다.',
    'trash_skip_kind': '항목 종류가 변경됨',
    'trash_skip_identity': '항목이 교체되었습니다',
    'trash_skip_changed': '크기, 타임스탬프 또는 폴더 내용이 변경됨',
    'trash_skip_protected': '확인된 경로에는 다른 보호 기능이 있습니다.',
    'trash_skip_cancelled': '작업이 취소되었습니다',
    'coverage_complete': (
        '적용 범위: {size}은 {known} 폴더에 알려져 있습니다. {skipped}을 건너뛰고, {denied}에 액세스할 수 없'
        '으며, {pending} 보류 중입니다.'
    ),
    'coverage_partial': (
        '불완전한 적용 범위: {size}은 {known} 폴더에 알려져 있습니다. {skipped}을 건너뛰고, {denied}에 액세스'
        '할 수 없으며, {pending} 보류 중입니다. 생략된 바이트를 알 수 없습니다. 정리하기 전에 불완전한 가지를'
        ' 다시 검사하십시오. 모두 선택이 비활성화됩니다.'
    ),
    'problem_hidden_omitted': '숨겨진 항목은 생략되었습니다. 그들의 크기는 알려져 있지 않습니다.',
    'problem_partial_folder': '일부 항목을 읽을 수 없습니다. 이 폴더는 불완전합니다.',
    'app_title': 'FileTree',
    'about_text': (
        '<h3>FileTree {version}</h3><p>디스크 공간이 어디로 가는지 확인하세요.</p><p>MIT 라이센스 · © 2026 JE'
        '-Chen</p>'
    ),
    'menu_file': '&파일',
    'menu_export': '&내보내기',
    'menu_view': '&보기',
    'menu_unit': '크기 &단위',
    'menu_language': '&언어',
    'menu_help': '&도움말',
    'action_open': '폴더 선택…',
    'action_open_tip': '스캔할 폴더나 드라이브를 선택하세요.',
    'action_rescan': '다시 스캔',
    'action_rescan_tip': '변경 사항을 적용하려면 동일한 폴더를 다시 스캔하세요.',
    'action_stop': '중지',
    'action_stop_tip': '실행 중인 검사를 중지합니다.',
    'action_export_folders': '폴더 목록(CSV)…',
    'action_export_folders_tip': 'Excel 또는 기타 스프레드시트용으로 모든 폴더를 크기와 함께 저장하세요.',
    'action_export_largest': '가장 큰 파일(CSV)…',
    'action_export_largest_tip': '가장 큰 파일 목록 저장',
    'action_export_json': '폴더 트리(JSON)…',
    'action_export_json_tip': '스크립트 및 기타 프로그램을 위한 폴더 트리 저장',
    'action_trash': '휴지통으로 이동',
    'action_trash_tip': '선택한 파일 및 폴더를 휴지통으로 이동합니다(먼저 묻는 메시지가 표시됨).',
    'action_find': '찾기…',
    'action_find_tip': '스캔 내 어디에서나 이름으로 파일 및 폴더 찾기',
    'action_quit': '종료',
    'action_quit_tip': 'FileTree 닫기',
    'action_hidden': '숨겨진 파일 포함',
    'action_exclusions': '스캔하는 동안 건너뛰기…',
    'action_exclusions_tip': 'node_modules와 같이 검사하는 폴더 및 폴더 이름은 생략합니다.',
    'exclusions_title': '스캔하는 동안 건너뛰기',
    'exclusions_hint': (
        '스캔 시 이러한 폴더는 제외됩니다. 해당 폴더는 회색으로 표시되며 크기는 0입니다. node_modules 또는 *.'
        'cache와 같은 이름은 해당 이름의 모든 폴더를 건너뜁니다. 폴더 경로는 해당 폴더 하나를 건너뜁니다. 목'
        '록은 다음 스캔부터 적용됩니다.'
    ),
    'exclusions_add_name': '이름을 추가하세요…',
    'exclusions_add_folder': '폴더 추가…',
    'exclusions_remove': '제거',
    'exclusions_name_prompt': '폴더 이름, * 및 ? 허용됨:',
    'exclusions_saved': '{count} 제외 항목이 저장되었습니다. 다음 스캔부터 적용됩니다.',
    'tooltip_excluded': '{path}\n건너뛰기: 보기 → 스캔 중 건너뛰기 상태입니다.',
    'action_hidden_tip': '숨겨진 파일 및 폴더 수 계산(다음 검사에 적용)',
    'action_help': '사용방법',
    'action_help_tip': 'FileTree에 대한 간략한 가이드',
    'action_about': 'FileTree 정보',
    'action_about_tip': '버전 및 라이센스',
    'app_title_admin': 'FileTree(관리자)',
    'action_elevate': '관리자로 다시 시작',
    'action_elevate_tip': '관리자 권한으로 FileTree를 다시 시작하면 모든 폴더를 읽을 수 있습니다.',
    'action_ask_admin': '시작 시 관리자 권한 요청',
    'action_ask_admin_tip': 'Windows은 FileTree이 시작될 때 권한을 요청하므로 보호된 폴더도 읽을 수 있습니다.',
    'problems_hint': (
        '일부 폴더에는 관리자 권한이 필요합니다. 해당 내용을 읽으려면 FileTree를 관리자로 다시 시작하세요.'
    ),
    'elevate_declined': 'FileTree가 여전히 관리자 권한 없이 실행 중입니다.',
    'unit_auto': '자동',
    'path_placeholder': '폴더 경로를 입력하거나 붙여넣고 Enter를 누르세요.',
    'choose_folder_title': '스캔할 폴더를 선택하세요',
    'welcome_title': '디스크 공간이 어디로 가는지 확인하세요',
    'welcome_subtitle': (
        '폴더 또는 전체 드라이브를 선택하십시오. FileTree은 그 안에 있는 모든 파일을 합산하고 가장 큰 폴더와 '
        '파일을 먼저 표시합니다.'
    ),
    'welcome_choose': '폴더를 선택하세요…',
    'welcome_drives': '드라이브',
    'welcome_drive_tip': '{path} 스캔',
    'welcome_drive_free': '{free}은 {total}에서 무료입니다.',
    'welcome_recent': '최근에 스캔됨',
    'welcome_tip': (
        '팁: 파일 관리자에서 폴더를 이 창으로 끌어서 놓을 수도 있습니다. Windows(\\\\server\\share)에 절대 UN'
        'C 공유 경로를 붙여넣습니다. 액세스는 현재 계정을 사용합니다. 스캔 작업자는 옵션에서 조정할 수 있습니'
        '다. 거부되거나 연결이 끊긴 분기는 비어 있지 않고 불완전한 상태로 유지됩니다.'
    ),
    'scan_starting': '시작 중…',
    'scan_progress': '검색 중… {files} 파일 {folders} 폴더 · {size} · {time}',
    'scan_stop': '중지',
    'scan_stopping': '중지 중…',
    'scan_cancelled': '스캔이 중지되었습니다.',
    'scan_stopped_partial': '스캔 중지됨: 결과에는 지금까지 읽은 내용이 표시됩니다.',
    'scan_failed_title': '스캔할 수 없습니다',
    'scan_mount_changed': '마운트 경계가 변경되었거나 확인할 수 없습니다. 이 결과를 사용하기 전에 다시 스캔하세요.',
    'scan_failed': 'FileTree는 {path}을(를) 읽을 수 없습니다.\n\n이유: {reason}',
    'not_a_folder': '{path}은(는) 존재하는 폴더가 아닙니다.',
    'duration_seconds': '{value}초',
    'duration_minutes': '{minutes} 분 {seconds} 초',
    'summary': '<b>{path}</b> — {files} 파일 및 {folders} 폴더의 {size}(디스크의 {allocated})({time}에서 스캔됨)',
    'summary_live': '<b>{path}</b> — 지금까지 {files} 파일 및 {folders} 폴더의 {size}(디스크의 {allocated})',
    'summary_partial': (
        '<b>{path}</b> — {files} 파일 및 {folders} 폴더의 {size}(디스크의 {allocated}) · <b>불완전</b>: {time'
        '} 이후 검사가 중지되었습니다.'
    ),
    'tab_chart': '차트',
    'chart_treemap': '트리맵',
    'treemap_levels': '레벨',
    'treemap_levels_all': '모두',
    'treemap_colours': '색상',
    'treemap_colours_type': '파일 유형별',
    'treemap_colours_folder': '폴더별',
    'chart_treemap_tip': '모든 파일은 차지하는 공간에 따라 크기가 결정되는 직사각형입니다.',
    'chart_bars': '막대 그래프',
    'chart_sunburst': '선버스트',
    'chart_tree': '트리',
    'chart_tree_tip': '폴더 계층 구조: 분기 확장, 확대/축소하려면 Ctrl+휠, 초점을 맞추려면 두 번 클릭',
    'tree_orientation': '방향',
    'tree_orientation_horizontal': '왼쪽에서 오른쪽으로',
    'tree_orientation_vertical': '위에서 아래로',
    'tree_more': '{count} 추가 폴더 · {size}',
    'tree_unavailable': '스캔되지 않음',
    'chart_sunburst_tip': (
        '중앙에 있는 폴더는 더 깊은 레벨마다 링으로 구성되어 있습니다. 중앙을 클릭하면 위로 올라갑니다'
    ),
    'chart_bars_tip': '폴더 항목당 하나의 막대(크기 및 공유 포함)(가장 큰 것부터)',
    'bars_empty_folder': '이 폴더는 비어 있습니다.',
    'bars_more': '{count} 더보기: {size}',
    'tab_largest': '가장 큰 파일',
    'scope_folder': '선택한 폴더만',
    'scope_folder_named': '{name}에서만',
    'scope_folder_tip': '전체 스캔 대신 트리에서 선택한 폴더의 가장 큰 파일, 유형 및 기간을 표시합니다.',
    'tab_search': '검색',
    'tab_changes': '변경 사항',
    'action_compare': '저장된 스캔과 비교…',
    'action_compare_tip': '내보내기 → 폴더 트리(JSON)로 저장된 스캔을 열고 이후 성장한 내용을 확인하세요.',
    'compare_title': '저장된 스캔과 비교',
    'compare_failed': '이 파일은 FileTree:\n{reason}에 의해 저장된 스캔이 아닙니다.',
    'column_before': '이전',
    'column_now': '지금',
    'column_change': '변경',
    'changes_new': '새로운',
    'changes_gone': '사라졌다',
    'changes_whole_scan': '(스캔한 폴더)',
    'changes_stop': '비교를 중지하세요',
    'changes_running': '비교 중…',
    'changes_waiting': '스캔이 완료되면 비교가 이루어집니다.',
    'changes_unknown_time': '알 수 없는 시간에',
    'changes_summary': (
        '{path}과 비교하여 {when}을 저장했습니다: {before}, 현재 {now}({change}); {count} 폴더가 변경되었습니'
        '다.'
    ),
    'tab_duplicates': '중복',
    'tab_cleanup': '정리',
    'cleanup_suggestions': '제안',
    'cleanup_select_all': '모두 선택',
    'cleanup_select_group': '이 그룹을 선택하세요',
    'cleanup_running': '청소할 물건을 찾고 있습니다…',
    'cleanup_hint': '스캔 후 콘텐츠가 일반적으로 갈 수 있는 장소가 여기에 나타납니다.',
    'cleanup_none': '이 스캔에는 제안할 내용이 없습니다.',
    'cleanup_summary': (
        '{size} {groups} 그룹의 논리적 크기. 휴지통으로 이동하기 전에 경로 및 할당을 검토할 항목을 선택하십시'
        '오. 이동해도 즉시 공간이 확보되지는 않습니다.'
    ),
    'cleanup_group': '{title} — {size} ({count})',
    'cleanup_temp': '임시 파일',
    'cleanup_temp_tip': '한동안 남겨진 파일 프로그램; 아직 실행 중인 프로그램에는 일부가 필요할 수 있습니다.',
    'cleanup_browser_cache': '브라우저 캐시',
    'cleanup_browser_cache_tip': '웹페이지 및 사진 사본 브라우저는 필요에 따라 다시 다운로드합니다.',
    'cleanup_thumbnails': '썸네일 캐시',
    'cleanup_thumbnails_tip': '사진의 작은 미리보기; 폴더를 열 때 다시 만들어집니다.',
    'cleanup_crash_dumps': '크래시 덤프',
    'cleanup_crash_dumps_tip': '프로그램이 충돌할 때 저장된 메모리는 충돌을 보고하는 데에만 유용합니다.',
    'cleanup_package_caches': '패키지 다운로드 캐시(pip, npm…)',
    'cleanup_package_caches_tip': '다운로드한 패키지는 다음 설치를 위해 보관됩니다. 필요할 때 다시 다운로드됩니다.',
    'cleanup_build_output': '빌드 출력(재구축 가능)',
    'cleanup_build_output_tip': '설치된 종속성 및 프로젝트의 컴파일된 파일 프로젝트를 다시 빌드하면 다시 생성됩니다.',
    'cleanup_old_installers': '다운로드의 설치 프로그램',
    'cleanup_old_installers_tip': '오래 전에 실행되었을 가능성이 가장 높은 설정 파일. 다시 설치한 것을 유지하세요.',
    'cleanup_empty_folders': '빈 폴더',
    'cleanup_empty_folders_tip': '아무것도 없는 폴더 또는 다른 빈 폴더만 있습니다.',
    'duplicates_min_size': '다음의 파일 비교',
    'duplicates_any_size': '어떤 크기',
    'duplicates_find': '중복 찾기',
    'duplicates_stop': '중지',
    'duplicates_select_extra': '추가 사본 선택',
    'duplicates_select_extra_tip': (
        '선택한 유지할 파일와 성공적인 확인을 통해 그룹에서 추가 항목을 선택합니다. 그런 다음 삭제를 누르세요'
    ),
    'duplicates_hint': (
        '스캔의 어느 위치에서나 동일한 내용이 포함된 파일을 찾습니다. 같은 크기의 파일만 읽어오는데 읽는 데 '
        '시간이 걸리기 때문에 더 작은 크기를 선택하지 않으면 작은 파일은 제외됩니다.'
    ),
    'duplicates_starting': '같은 크기의 파일을 찾는 중…',
    'duplicates_running': '{total} 파일 중 {files}({bytes} 중 {read}) 읽기…',
    'duplicates_stopped': '검색이 중지되었습니다.',
    'duplicates_none': '중복된 파일이 없습니다.',
    'duplicates_summary': '{groups} 중복 그룹: {extra} 추가 복사본의 논리적 크기.',
    'duplicates_limited': '추가 공간이 가장 많은 {shown} 그룹이 나열됩니다.',
    'duplicates_skipped': '{count} 파일을 읽을 수 없습니다.',
    'duplicates_group': '{count} 복사본 × {size}: {extra} 논리적 추가 복사본 크기.',
    'search_placeholder': '이름 또는 패턴의 일부: 백업, *.mp4, *.iso;*.zip',
    'search_hint': (
        '* 및 ?를 사용하여 이름이나 패턴의 일부를 입력하고 조건을 선택하거나 둘 다를 선택하여 스캔의 어느 위'
        '치에서나 파일과 폴더를 찾습니다.'
    ),
    'search_running': '검색 중…',
    'search_larger': '다음보다 큼',
    'search_smaller': '보다 작음',
    'search_no_limit': '제한 없음',
    'search_changed': '변경됨',
    'search_changed_any': '언제든지',
    'search_changed_week': '지난주에',
    'search_changed_month': '지난달에',
    'search_changed_year': '작년에',
    'search_changed_stale_year': '1년이 아니라',
    'search_changed_stale_2y': '아니 2년동안',
    'search_changed_stale_5y': '아니 5년동안',
    'search_type': '유형',
    'search_type_any': '모든 유형',
    'search_show': '쇼',
    'search_kind_any': '파일 및 폴더',
    'search_kind_files': '파일만',
    'search_kind_folders': '폴더만',
    'search_saved': '저장된 검색',
    'search_saved_none': '(없음)',
    'search_save': '저장…',
    'search_delete': '삭제',
    'search_save_title': '이 검색 저장',
    'search_save_prompt': '이름:',
    'search_none': '일치하는 항목이 없습니다.',
    'search_summary': '{count}개 일치, 총 {size}개.',
    'search_limited': '가장 큰 {shown}이 나열됩니다.',
    'tab_types': '파일 형식',
    'tab_age': '경과 기간',
    'column_age': '마지막으로 변경됨',
    'age_month': '한 달 이내',
    'age_half_year': '1~6개월 전',
    'age_year': '6~12개월 전',
    'age_two_years': '1~2년 전',
    'age_older': '2년 이상 전',
    'largest_focus': '표시 항목: {what}',
    'largest_show_all': '모두 표시',
    'list_files_tip': '가장 큰 파일을 나열하려면 행을 두 번 클릭하세요.',
    'tab_problems': '문제',
    'tab_problems_count': '문제({count})',
    'column_name': '이름',
    'column_size': '크기',
    'column_allocated': '디스크에',
    'column_share': '상위 %',
    'column_share_total': '전체의 %',
    'column_files': '파일',
    'column_folders': '폴더',
    'column_modified': '수정됨',
    'column_folder': '폴더',
    'column_extension': '확장',
    'column_type': '유형',
    'column_path': '경로',
    'column_problem': '문제',
    'problem_access_denied': '액세스가 거부되었습니다.',
    'problem_not_found': '더 이상 거기엔 없어',
    'problem_path_too_long': '경로가 너무 깁니다.',
    'problem_not_scanned': '검사되지 않음: 검사가 먼저 중지되었습니다.',
    'no_extension': '(확장자 없음)',
    'tooltip_unreadable': '{path}\n읽을 수 없습니다: {reason}',
    'tooltip_link': '{path}\n링크: 표시되었지만 팔로우되지 않음',
    'tooltip_not_scanned': '{path}\n스캔되지 않음: 스캔이 먼저 중지되었습니다.',
    'treemap_empty': '표시할 내용 없음',
    'treemap_up': '↑ 위로',
    'treemap_up_tip': '위 폴더를 보여주세요',
    'treemap_tooltip': '<b>{name}</b><br>{size} (이 보기의 {share})<br>{path}',
    'treemap_more': '{count} 더 보기',
    'treemap_more_tooltip': (
        '<b>{count} 더 작은 항목</b> of {name}, 각각 너무 작아서 그릴 수 없음<br>{size}(이 보기의 {share})'
    ),
    'treemap_more_open': '이 폴더를 자체적으로 표시하려면 두 번 클릭하세요.',
    'largest_filter': '이름이나 폴더로 필터링…',
    'types_all': '모든 유형',
    'category_images': '사진',
    'category_video': '비디오',
    'category_audio': '음악 및 오디오',
    'category_documents': '문서',
    'category_archives': '아카이브 및 디스크 이미지',
    'category_code': '코드와 데이터',
    'category_programs': '프로그램',
    'category_other': '기타',
    'status_selected': '{name}: {size}(해당 폴더의 {share})',
    'status_selected_root': '{name}: {size}',
    'menu_open_item': '열기',
    'menu_reveal': '파일 관리자에 표시',
    'menu_copy_path': '경로 복사',
    'menu_show_chart': '차트에 표시',
    'menu_scan_here': '이 폴더를 스캔하세요',
    'menu_rescan_here': '이 폴더를 다시 검사하세요.',
    'rescan_done': '다시 스캔됨 {name}: {before} → {after}',
    'trash_confirm_title': '휴지통으로 이동',
    'protected_title': '시스템 또는 프로그램 폴더',
    'protected_question': (
        '항목 중 {count}은 시스템 또는 프로그램 폴더입니다. 이동하면 시스템이나 프로그램의 작동이 중지될 수 '
        '있습니다.\n\n{names}\n\n그래도 이동하시겠습니까?'
    ),
    'protected_system': '운영 체제의 일부',
    'protected_programs': '설치된 프로그램',
    'protected_settings': '프로그램 설정 및 데이터',
    'protected_profile': '사용자의 프로필 폴더',
    'trash_confirm': '“{name}”({size})을 휴지통으로 이동하시겠습니까?\n\n휴지통에서 복원할 수 있습니다.',
    'trash_failed': '"{name}"을(를) 휴지통으로 이동할 수 없습니다. 사용 중이거나 읽기 전용일 수 있습니다.',
    'trash_done': '“{name}”을 휴지통으로 이동했습니다: {size}이 해제되었습니다.',
    'action_trash_many': '{count} 항목을 휴지통으로 이동',
    'trash_confirm_many': (
        '이 {count} 항목(총 {size})을 휴지통으로 이동하시겠습니까?\n\n{names}\n\n여기에서 복원할 수 있습니다.'
    ),
    'trash_more': '...그리고 {count} 더보기',
    'trash_failed_many': (
        '{count} 항목을 휴지통으로 이동할 수 없습니다. 사용 중이거나 읽기 전용일 수 있습니다. \n\n{names}'
    ),
    'trash_done_many': '{count} 항목을 휴지통으로 이동했습니다: {size}이 해제되었습니다.',
    'status_selected_many': '{count} 선택한 항목: {size}',
    'export_title': '수출',
    'export_running': '{path}에 저장 중…',
    'csv_filter': 'CSV 파일(*.csv)',
    'json_filter': 'JSON 파일(*.json)',
    'export_done': '{count} 행을 {path}에 저장했습니다.',
    'export_failed': '파일을 저장할 수 없습니다.\n\n이유: {reason}',
    'help_title': 'FileTree 사용 방법',
    'help_html': (
        '\n<h2>FileTree 세 단계로</h2>\n<ol>\n<li><b>검사 대상을 선택하세요.</b> <i>폴더를 선택하세요…</i> 또'
        '는 드라이브 중 하나를 선택하고 폴더를 드래그하세요\n창으로 이동하거나 상단 상자에 경로를 입력하고 En'
        'ter 키를 누릅니다.</li>\n<li><b>채워지는 모습을 지켜보세요.</b> 트리가 바로 나타나고 가장 큰 폴더가 '
        '맨 위로 이동합니다\nFileTree은 모든 파일을 추가합니다. 스캔이 끝나면 가장 큰 파일과 파일 형식이 따릅'
        '니다.  누르기\n언제든지 <i>Stop</i>(또는 Esc): 지금까지 읽은 내용이 화면에 유지되고 불완전한 것으로 '
        '표시됩니다.</li>\n<li><b>공간을 차지하는 것이 무엇인지 찾아보세요.</b> 가장 큰 폴더는 트리 상단에 있'
        '습니다. 화살표를 클릭하세요.\n폴더 옆에 있는 내부를 살펴보세요.</li>\n</ol>\n<h2>결과 읽기</h2>\n<ul'
        '>\n<li><b>폴더 트리</b>(왼쪽): 각 폴더 또는 파일의 크기, 디스크에서 차지하는 공간<i></i>(전체\n클러'
        '스터이므로 일반적으로 조금 더 많습니다. 압축 파일의 경우 더 적고 온라인에만 보관된 파일의 경우 아무'
        '것도 없음), a\n상위 </i> 막대의 <i>%(의 양\n이 항목이 차지하는 위의 폴더), 얼마나 많은 파일과 폴더가'
        ' 있는지, 그 안에 무엇인가가 있는 경우\n마지막으로 변경되었습니다. 항목별로 정렬하려면 열 제목을 클릭'
        '하세요.</li>\n<li><b>Chart</b>: 탭 모서리에 있는 동일한 폴더의 4개 보기 간에 전환합니다(트리맵\n먼저'
        ' 오고 FileTree는 선택한 것을 기억합니다. \n<i>Treemap</i>은 모든 파일을 직사각형으로 그립니다. 파일'
        '이 클수록 직사각형도 커집니다. 각 폴더\n이름과 크기가 있는 스트립이 있고 폴더의 파일이 너무 작아서 '
        '볼 수 없는 회색으로 표시된 을 공유합니다.\n타일(<i>12 more</i>): 해당 폴더를 자체적으로 표시하려면 '
        '타일을 두 번 클릭하세요. <i>레벨</i>은 레벨 수를 설정합니다\n파일 형식(범례는 그 아래에 있음) 또는 '
        '최상위 폴더별로 <i>Colours</i> 색상으로 그려집니다.\n<i>Bars</i>은 폴더의 각 항목에 하나의 막대를 가'
        '장 큰 것부터 제공하고 크기와 공유는 가장 쉬운 입니다.\n정확하게 읽으려면. <i>Sunburst</i>은 폴더를 '
        '중앙에 배치하고 각 더 깊은 수준은  주위의 링에 배치합니다.\n그것; 중앙을 클릭하면 위로 올라갑니다. <'
        'i>Tree</i>은 확장 가능한 폴더 카드를 표시합니다. + 또는 "다른 폴더"를 클릭하세요.\n카드를 더 많이 보'
        '려면 방향을 선택하고, Ctrl+휠을 누르면 확대/축소하고 스크롤하여 이동할 수 있습니다. 에서 항목을 찾으'
        '려면 클릭하세요.\n폴더 트리에서 폴더를 두 번 클릭하여 해당 폴더로 이동하세요.\n돌아가려면 <i>Up</i>'
        '을 누르세요.</li>\n<li><b>가장 큰 파일</b>: 스캔 위치에 관계없이 가장 큰 1,000개의 파일입니다. 필터 '
        '상자에 을 입력하세요.\n목록을 좁히십시오. 트리에서 파일을 찾으려면 행을 두 번 클릭하세요.</li>\n<li>'
        '<b>검색</b>(Ctrl+F): 스캔의 모든 위치에서 입력한 내용이 이름에 포함된 파일 및 폴더.\n<code>*.mp4</co'
        'de>과 같은 패턴은 전체 이름과 일치해야 합니다. <code>;</code>로 여러 개를 분리하세요.\n(<code>*.iso;'
        '*.zip</code>). 상자 아래의 조건(크기, 마지막 변경 시기, 파일 형식, 파일 또는)\n폴더) 검색 범위를 좁'
        '히거나 자체적으로 검색을 만들고 <i>Save…</i>은 이름으로 검색을 유지합니다. \n1,000개의 가장 큰 일치 '
        '항목이 모두 개수 및 총 크기와 함께 나열됩니다.</li>\n<li><b>정리 → 제안</b>: 스캔할 때마다 콘텐츠가 '
        '일반적으로 이동할 수 있는 장소,당 한 그룹씩\n종류(임시 파일, 캐시, 크래시 덤프, 다시 빌드할 수 있는 '
        '빌드 출력, 다운로드의 이전 설치 프로그램,\n빈 폴더); 그룹 위로 마우스를 가져가 삭제 작업을 확인한 다'
        '음 <i>이 그룹을 선택</i> 또는\n<i>모두 선택</i>하고 삭제를 누르세요.</li>\n<li><b>정리 → 중복</b>: <'
        'i>중복 항목 찾기</i>을 눌러 동일한 콘텐츠가 포함된 파일을 그룹화합니다. 의 파일만\n동일한 크기를 읽'
        '습니다. 1MB 미만의 파일은 읽는 데 이 걸리므로 더 작은 크기를 선택하지 않는 한 제외됩니다.\n시간. 각 '
        '그룹은 가장 오래된 사본부터 나열합니다. <i>추가 복사본 선택</i>은 가장 오래된 복사본을 제외한 모든 '
        '복사본을 선택하고 \n삭제하면 휴지통으로 이동됩니다.</li>\n<li><b>파일 유형</b>: 확장자당 각 종류의 '
        '파일이 차지하는 공간입니다. 목록에서 유형을 선택하세요\n테이블 위에는 그 종류만 볼 수 있습니다. 해당'
        ' 유형의 가장 큰 파일을 나열하려면 행을 두 번 클릭하십시오.</li>\n<li><b>Age</b>: 한 달 동안, 1~6개월'
        ' 전에 마지막으로 변경된 공간의 양 등 최대 2개까지\n몇 년 전. 오래된 데이터는 보관되거나 삭제될 수 있'
        '는 경우가 많습니다. 가장 큰 행을 나열하려면 행을 두 번 클릭하세요.\n파일.</li>\n<li><b>문제</b>: Fil'
        'eTree 폴더를 읽을 수 없습니다. 그 안에 무엇이 들어 있는지는 계산되지 않습니다.</li>\n</ul>\n<h2>여유'
        ' 공간</h2>\n<p>항목을 마우스 오른쪽 버튼으로 클릭하여 <i>열기</i>, <i>파일 관리자에 표시</i>, <i>경'
        '로 복사</i>,\n<i>트리맵에 표시</i>, <i>이 폴더를 다시 검색</i>(FileTree 외부에서 변경한 후, 나머지\n'
        '결과 유지), <i>이 폴더</i>를 자체적으로 검사하거나 <i>휴지통으로 이동</i>.\n한 번에 여러 항목을 이동'
        '하려면 폴더 트리에서 Ctrl+클릭 또는 Shift+클릭으로 항목을 선택합니다.\n<i>가장 큰 파일</i> 목록 또는'
        ' <i>검색</i> 결과: FileTree이 한 번 묻고 전체 크기와 함께 나열됩니다.\nFileTree은 어떤 것도 영원히 '
        '삭제하지 않습니다. 항상 먼저 묻고 이동한 모든 내용을 복원할 수 있습니다.\n휴지통(macOS 및 Linux의 휴'
        '지통)에서. 다시 스캔하지 않고도 숫자가 즉시 업데이트됩니다.\n시스템 및 프로그램 폴더는 두 번 정도 묻'
        '는 이유가 있습니다. 임시 폴더와 캐시는 그렇지 않습니다.</p>\n<h2>무엇이 성장했는지 살펴보기</h2>\n<p'
        '><i>파일 → 내보내기 → 폴더 트리(JSON)</i>을 사용하여 스캔을 저장합니다. 나중에 새로 스캔한 후 다음을'
        ' 선택하세요.\n<i>파일 → 저장된 스캔과 비교…</i>하고 해당 파일을 엽니다. <b>Changes</b> 탭에는 스캔된'
        ' 모든 폴더가 나열됩니다.\n그 당시와 지금은 크기가 가장 크게 증가했습니다(<i>new</i> 및 <i>gone</i>은'
        ' 폴더를 표시함).\n나타나거나 사라졌습니다). <i>비교 중지</i>.</p>을 누를 때까지 각 재검색 후에 계속 '
        '비교합니다.\n<h2>키보드 단축키</h2>\n<table cellpadding="3">\n<tr><td><b>Ctrl+O</b></td><td>폴더 선'
        '택</td></tr>\n<tr><td><b>F5</b></td><td>재검색</td></tr>\n<tr><td><b>Esc</b></td><td>스캔 중지</td><'
        '/tr>\n<tr><td><b>Ctrl+F</b></td><td>이름으로 검색</td></tr>\n<tr><td><b>삭제</b></td><td>선택한 항목'
        '을 휴지통으로 이동</td></tr>\n<tr><td><b>F1</b></td><td>이 가이드</td></tr>\n<tr><td><b>Ctrl+Q</b></'
        'td><td>종료</td></tr>\n</table>\n<p>On macOS에서는 Ctrl 대신 ⌘를 사용합니다(다시 스캔하려면 ⌘R).</p>'
        '\n<h2>알아두면 좋은 정보</h2>\n<ul>\n<li>Sizes는 Windows Explorer와 동일하게 바이너리 단위(1KB = 1,0'
        '24바이트)의 실제 파일 크기입니다.\n<i>보기 → 크기 단위</i>.</li>에서 고정 단위를 선택합니다.\n<li>바'
        '로가기 및 링크(기호 링크, 교차점)가 나열되지만 따라갈 수 없으므로 아무것도 없습니다.\n두 번 계산되었'
        '습니다.</li>\n<li>On Windows, FileTree는 시작할 때 TreeSize와 같이 읽을 수 있도록 관리자 권한을 요청'
        '합니다.\n보호된 폴더도 마찬가지입니다. 아니오라고 말하면 정상적으로 실행됩니다. 읽을 수 없는 폴더는 '
        '아래에 나열됩니다.\n<i>문제</i>, <i>관리자로 다시 시작</i> 버튼이 있습니다. 아래의 질문을 끄세요.\n<'
        'i>보기 → 시작 시 관리자 권한 요청</i>.</li>\n<li><i>가장 큰 파일</i>, <i>파일 유형</i> 및 <i>Age</i>'
        '은 전체 스캔을 포괄합니다. <i>선택한 폴더만</i>,\n해당 탭의 오른쪽 상단에 있는 트리에서 선택한 폴더'
        '를 따르도록 합니다.</li>\n<li>숨겨진 파일도 계산됩니다. <i>보기를 끄고 → 숨김 파일 포함</i>을(를) 제'
        '외하세요.\n다음 스캔.</li>\n<li>모든 스캔에서 폴더를 제외하려면 <i>보기 → 스캔 중 건너뛰기</i>에 나'
        '열하십시오.\n<code>node_modules</code>은 해당 이름의 모든 폴더를 건너뛰고 경로는 하나의 폴더를 건너'
        '뜁니다. 건너뛴 폴더는\n회색으로 표시되고 크기는 0.</li>입니다.\n<li>결과를 <i>파일 → 내보내기로 저장'
        '합니다</i>: CSV은 Excel에서 열리고 JSON은 스크립트용입니다.</li>\n</ul>\n'
    ),
}

STRINGS: dict[str, dict[str, str]] = {"en": EN, "zh-TW": ZH_TW, "zh-CN": ZH_CN, "ja": JA, "ko": KO}
