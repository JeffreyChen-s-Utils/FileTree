# progress.md: FileTree

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md`.

## Open

- **#1** [BLOCKED] The release workflow (`.github/workflows/release.yml`) is in place but needs the `PYPI_API_TOKEN` repository secret, which only the owner can create: a PyPI token scoped to the whole account for the first upload (it creates the `je_file_tree` project), then one scoped to `je_file_tree`. Until it is set, merging into `main` fails at the first step and releases nothing. After the first release, switch the install sections of `README.md` and both translations to `pip install je_file_tree` and the `FileTree-<version>.exe` on the Releases page.
- **#15** Export runs on the GUI thread: writing the Folder tree JSON of D:\Codes (86,000 folders, 21.8 MB) took 1.3 s with the window frozen (`je_file_tree/gui/main_window.py` `export_results`). Run it on a worker thread like `CompareWorker`, with the result in the status bar.
- **#4** [UNVERIFIED] Linux: check drag and drop, "Show in file manager" (it opens the folder without selecting the entry, `je_file_tree/gui/file_actions.py`) and moving to the Trash in a Docker container with a real X server. macOS [BLOCKED]: there is no Mac or macOS VM on this machine (VMware Workstation has no VMs).
