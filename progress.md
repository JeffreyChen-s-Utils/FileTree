# progress.md: FileTree

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md`.

## Open

- **#14** Rename the package `file_tree` to `je_file_tree` (distribution and import): the PyPI name `file_tree` belongs to FSL's `file-tree`, which installs a `file_tree` module of its own. Everything that names the package moves with it: `file_tree/`, `pyproject.toml`, `start_file_tree.py`, `tools/`, tests, `README*.md`, `nuitka*.md`, `architecture.md`, `CLAUDE.md`, the `-m file_tree` restart in `file_tree/gui/elevation.py:65`. Needed before #1.
- **#1** Release flow like the other projects: on a pull request merged into `main`, CI bumps the version, publishes `je_file_tree` to PyPI, builds `FileTree.exe` with `tools/build_nuitka.py` on a Windows runner and attaches it to a GitHub release (template: Imervue `.github/workflows/release.yml`). [BLOCKED] on the `PYPI_API_TOKEN` repository secret, which only the owner can create.
- **#12** Duplicate files: group files by size, then by a hash of their first 64 KB, then by a full hash; a Duplicates tab lists each group with the space the extra copies take, runs on a worker thread with Stop, and lets the extra copies go to the Recycle Bin. Measure how long it takes on a large folder first.
- **#13** Compare with an earlier scan saved as JSON (the format of Export → Folder tree (JSON), `file_tree/core/export.py`): open a saved scan, then show how much each folder grew or shrank, and which folders are new or gone.
- **#4** [UNVERIFIED] Linux: check drag and drop, "Show in file manager" (it opens the folder without selecting the entry, `file_tree/gui/file_actions.py`) and moving to the Trash in a Docker container with a real X server. macOS [BLOCKED]: there is no Mac or macOS VM on this machine (VMware Workstation has no VMs).
