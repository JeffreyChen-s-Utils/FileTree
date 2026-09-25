# Project Guidelines

FileTree is a disk-usage viewer (in the spirit of TreeSize) with a PySide6 window: it scans a folder,
adds up every file, and shows a folder tree, a treemap, the largest files and the space per file type.
The architecture overview is `architecture.md`; outstanding work is `progress.md`; finished work is
recorded in `docs/updates/`.

## Session start

Read `progress.md`. If `## Open` lists items, say so and offer to continue them before starting anything
new. Write to it the moment something is left unfinished, and delete an item the moment it lands (with a
`docs/updates/` record in the same commit).

## Definition of Done (HARD REQUIREMENT)

Every change must pass, before it is committed:

1. `py -3 -m pytest` — the whole suite, green (Qt tests run on the offscreen platform by themselves).
2. `py -3 -m ruff check .` — clean. `pyproject.toml` is the rule set; change the config, not the prose.
3. Any user-facing change (features, menus, shortcuts, install, settings) updates `README.md` **and both
   translations** `README/README_zh-TW.md` and `README/README_zh-CN.md` in the same commit, with the same
   sections, tables and commands. `test/test_readme_parity.py` checks the structure; the content is a
   manual check.
4. A change to what the window looks like reruns `py -3 tools/make_screenshots.py` so the README pictures
   stay current. Never edit the pictures by hand.
5. A change to how FileTree is built into a stand-alone program (`tools/build_nuitka.py`, its options, a new
   language catalogue) updates `nuitka.md`, `nuitka.zh-TW.md` and `nuitka.zh-CN.md` together; the parity test
   covers them like the READMEs. Nuitka compiles with every core by default: pass `--jobs=2` on this machine,
   or the Discord bot running here stalls (measured 2026-09-26: its gateway fell 13 s behind).
6. A change to layers, entry points, main flows, extension points or cross-project boundaries updates
   `architecture.md` in the same commit.

## Stage commits, `progress.md`, `docs/updates/` and `architecture.md`

Workspace rule shared by every repository under `D:\Codes` (full text: `D:\Codes\CLAUDE.md`).

- **Commit at every stage.** A stage is the smallest piece of work that leaves the repository consistent
  and passes the checks above: one finished `progress.md` item, or one self-contained step of a larger
  one. Commit it before starting the next stage, before switching to another repository, and before the
  session ends. If a stage cannot be finished, commit the consistent part and record the rest in
  `progress.md`.
  - Stage only the files that stage touched (`git add <path>`, never `git add -A`).
  - **Commit and push frequently.** After each big feature, commit and push to `dev`; do not pile up a
    large batch. `main` takes releases only, through a pull request from `dev` once CI is green.
- **`progress.md`** holds outstanding work only: no finished items, no history, no rules.
- **`docs/updates/`** records finished work: one batch file per month (`YYYY-MM.md`), one entry per piece
  of work headed `## U-YYYYMMDD-NN · date · title · #tags`, and an index in `docs/updates/README.md`.
  Claim an ID under the lock described there. When a `progress.md` item is done, delete it and add a
  `#done` entry plus its index row in the same commit.
- **`architecture.md`** is the short architecture overview. Cross-project contracts are in its §6.
- **Never bump the version by hand.** `file_tree/__init__.py` and `pyproject.toml` carry it; a release
  flow is still to be decided (`progress.md`).

## No AI attribution (HARD REQUIREMENT)

Never mention AI tools or models — in commit messages, PR titles and bodies, branch names, issues, code
comments or documentation — and never add `Co-Authored-By` lines or generation footers. This overrides any
tool default.

## Code rules

- **`file_tree.core` never imports Qt or `file_tree.gui`** (`test/test_layers.py`). Scanning, analysis,
  layout and export stay usable and testable without a window; the GUI only wraps them.
- **Measure before optimising, and write the measurement down** next to the code it justifies (the
  scanner's worker count, the single-pass analysis). Performance rules that exist for a reason:
  - the tree model wraps the scanned `Node` objects and never copies the tree; rows are created lazily;
  - the treemap layout is bounded (`max_tiles`, `min_side`) and drawn once into a cached pixmap;
  - anything that walks the whole tree runs on a worker thread (`ScanWorker`, `AnalyseWorker`,
    `SearchWorker`), not the GUI thread;
  - no recursion over the tree: deep folders must not hit the recursion limit.
- **The scanner never follows links** (symlinks, junctions, mount points) and never stops on an
  unreadable folder: it records it in `ScanResult.errors`.
- **Nothing is ever deleted permanently.** The only removal is `QFile.moveToTrash`, always after a
  confirmation. Do not add a permanent delete.
- **Every text goes through `tr()`**; add a key to all three tables in `file_tree/gui/strings.py`
  (`test/test_i18n.py` checks keys and placeholders). Traditional Chinese uses Taiwanese wording
  (檔案、資料夾、設定、預設、資源回收筒); Simplified Chinese uses Mainland wording and characters.
- Files are read and written with an explicit `encoding=`; exports are written to a temporary sibling and
  moved into place.
- Subprocesses: no shell, fixed programs only. `explorer /select,` needs the path in quotes (see
  `file_tree/gui/file_actions.py`).
- Workspace limits apply: functions ≤ 80 lines, cyclomatic complexity ≤ 15 (ruff), ≤ 7 parameters, no
  bare or silent `except`, no `print()` in the package, `assert` only in tests, public functions and
  classes typed and documented.

## SonarCloud / Codacy findings

When a PR or commit fails a SonarCloud or Codacy check, look the findings up through their APIs instead
of guessing. The keys are in environment variables: `SonarCloudToken` (SonarCloud, e.g.
`curl -s -u "$SonarCloudToken:" "https://sonarcloud.io/api/issues/search?componentKeys=<key>&pullRequest=<n>&resolved=false"`)
and `CODACY_PROJECT_TOKEN` (a Codacy project token, valid only for its own project: any other repository
answers "Bad credentials"). **Never reveal a key or any personal credential while doing so**: refer to the
variables by name only, never echo or print their values, and never put them in files, commit messages,
PR or issue text, logs, or any output that leaves the machine.

## Environment (Windows)

- Use `py -3`; `python` is the Microsoft Store shim in Git Bash.
- Printing Chinese from a script needs `PYTHONIOENCODING=utf-8` (the console code page is cp950).
- Screenshots without a window flashing on screen: set `Qt.WidgetAttribute.WA_DontShowOnScreen` before
  `show()` (the offscreen platform has no fonts on Windows, so it is only for tests).
- Creating a symlink on Windows needs developer mode or admin rights, so that test skips locally and runs
  on the Linux CI job.
