# progress.md: FileTree

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md`.

## Open

- **#1** [DECIDE] No release flow yet: nothing publishes a package or a Windows executable, and nothing bumps the version on `main` (`pyproject.toml:7`, `file_tree/__init__.py:7`). Choose between a PyPI package (the workspace's usual CI-bumped release on `main`), a PyInstaller / Nuitka executable, or both.
- **#4** [UNVERIFIED] The window has only been exercised on Windows (and on the offscreen platform in tests). On macOS and Linux, check drag and drop, "Show in file manager" (Linux opens the folder without selecting the entry, `file_tree/gui/file_actions.py`) and moving to the Trash.
- **#12** [DECIDE] Duplicate files (same size, then same content hash) — useful for cleanup but needs reading every candidate file; decide whether it belongs in a "simpler" tool.
- **#13** [DECIDE] Compare with an earlier scan (save a scan, show what grew): needs a saved-scan format and a place to keep it.
