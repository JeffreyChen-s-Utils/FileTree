# progress.md: FileTree

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md`.

## Open

- **#4** [UNVERIFIED] Linux: "Show in file manager" now asks the file manager over D-Bus (`org.freedesktop.FileManager1.ShowItems`, `je_file_tree/gui/file_actions.py` `show_items`) and falls back to opening the folder, but has not run against a real session bus: whether PySide6 sends the list of URIs as the `as` the interface expects is unchecked. Also unchecked on Linux: moving to the Trash (`QFile.moveToTrash`, freedesktop trash spec), a real drag from a file manager, CJK text under X11. A Docker check (Debian, Xvfb, `dbus-run-session`, a stand-in file manager with the strict `(as, s)` signature, a logging `xdg-open`) was written but its image build was stopped when the machine ran low on memory (0.9 GB free of 31 GB); run it when memory allows. macOS [BLOCKED]: no Mac or macOS VM on this machine.
