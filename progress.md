# progress.md: FileTree

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md`.

## Open

- **#1** [DECIDE] No release flow yet: nothing publishes a package or a Windows executable, and nothing bumps the version on `main` (`pyproject.toml:7`, `file_tree/__init__.py:7`). Choose between a PyPI package (the workspace's usual CI-bumped release on `main`), a PyInstaller / Nuitka executable, or both.
- **#2** "Size on disk" (allocated space, what TreeSize shows next to the size) is not computed: `file_tree/core/scanner.py` `_entry_node` only reads `st_size`. On Windows it needs `GetCompressedFileSizeW` per file, an extra system call the scan does not make today; measure its cost on a large folder before adding it, and make it an option if it slows the scan noticeably.
- **#3** No search across the whole tree: the only filter is the one over the 1,000 largest files (`file_tree/gui/results_view.py`). A name / pattern search that lists every match with its size would cover what the largest-files list misses.
- **#4** [UNVERIFIED] The window has only been exercised on Windows (and on the offscreen platform in tests). On macOS and Linux, check drag and drop, "Show in file manager" (Linux opens the folder without selecting the entry, `file_tree/gui/file_actions.py`) and moving to the Trash.
- **#11** Select several entries and move them to the Recycle Bin together, with one confirmation that shows the total size (`file_tree/gui/main_window.py` `move_to_trash`).
- **#12** [DECIDE] Duplicate files (same size, then same content hash) — useful for cleanup but needs reading every candidate file; decide whether it belongs in a "simpler" tool.
- **#13** [DECIDE] Compare with an earlier scan (save a scan, show what grew): needs a saved-scan format and a place to keep it.
