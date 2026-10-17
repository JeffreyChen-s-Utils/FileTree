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
3. Any user-facing change (features, menus, shortcuts, install, settings) updates `README.md` **and all
   translations** in `README/` (Traditional/Simplified Chinese, Japanese and Korean) in the same commit, with the same
   sections, tables and commands. `test/test_readme_parity.py` checks the structure; the content is a
   manual check.
   Keep READMEs as short, plain-language project introductions with installation and basic use.
   Put detailed workflows, implementation constraints and validation evidence in `docs/guide.md`
   and its four `docs/guide_<language>.md` translations or the relevant technical/update documents.
4. A change to what the window looks like reruns `py -3 tools/make_screenshots.py` so the README pictures
   stay current. Never edit the pictures by hand.
5. A change to how FileTree is built into a stand-alone program (`tools/build_nuitka.py`, its options, a new
   language catalogue) updates `nuitka.md` and its `zh-TW`, `zh-CN`, `ja`, `ko` translations together; the parity test
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
- **Never bump the version by hand.** `je_file_tree/__init__.py` and `pyproject.toml` carry it; the release
  workflow (`.github/workflows/release.yml`) raises both with `tools/bump_version.py` when a pull request is
  merged into `main`, publishes to PyPI and attaches the complete Windows folder ZIP and MSI to a GitHub release.

## No AI attribution (HARD REQUIREMENT)

Never mention AI tools or models — in commit messages, PR titles and bodies, branch names, issues, code
comments or documentation — and never add `Co-Authored-By` lines or generation footers. This overrides any
tool default.

## Code rules

- **`je_file_tree.core` never imports Qt or `je_file_tree.gui`** (`test/test_layers.py`). Scanning, analysis,
  layout and export stay usable and testable without a window; the GUI only wraps them.
- **Measure before optimising, and write the measurement down** next to the code it justifies (the
  scanner's worker count, the single-pass analysis). Performance rules that exist for a reason:
  - the tree model wraps the scanned `Node` objects and never copies the tree; rows are created lazily;
  - the treemap layout is bounded (`max_tiles`, `min_side`) and drawn once into a cached pixmap;
  - anything that walks the whole tree runs on a worker thread (`ScanWorker`, `AnalyseWorker`,
    `SearchWorker`), not the GUI thread, and calls `core.pacing.give_way()` once per folder so the window
    goes first while it is busy; the window waits for a worker only through `scan_worker.wait_for`;
  - no recursion over the tree: deep folders must not hit the recursion limit.
- **The scanner never follows links** (symlinks, junctions, mount points) and never stops on an
  unreadable folder: it records it in `ScanResult.errors`.
- **Nothing is ever deleted permanently.** The only removal is `QFile.moveToTrash`, always after a
  confirmation. Do not add a permanent delete. Everything that moves entries to the Recycle Bin goes through
  `MainWindow.move_to_trash`, so system and program folders (`je_file_tree/core/protected.py`) always get
  their second question.
  An explicit Windows *Empty Recycle Bin* operation may permanently remove the current user's OS bin
  on one local drive through `SHEmptyRecycleBinW`, only after two questions naming that drive, its
  reported size/item count and irreversibility; the worker rechecks totals before starting. This
  exception never permits arbitrary path deletion or an empty/null all-drive scope.
  Explicit freedesktop *Empty Trash* may remove only reviewed, recognized current-user `files`/`info`
  scopes on one mounted Linux volume, after two questions naming their exact paths, reported
  bytes/items and irreversibility. Approval captures complete no-follow metadata; changed entries,
  unknown receipts, foreign owners, linked scope directories and mount boundaries are refused.
  Descriptor-relative operations never follow payload links or remove the OS-bin directories.
  Failures and partial completion must remain visible and trigger fresh bin/capacity metadata.
  Explicit macOS Finder *Empty Trash* may invoke only fixed `/usr/bin/osascript` with Finder's global
  empty-trash command after two questions naming all current-user mounted Trash scopes, bytes/items
  and irreversibility. A complete native mounted-root provider and deduplicated no-follow private-uid
  inventories must be rechecked before invoking it; incomplete/changed scopes or volumes are refused.
  Require the same unelevated uid as the primary console user and the account's home directory;
  an overridden HOME, root process or another switched/console user never grants Finder approval.
  No arbitrary paths are passed and no direct deletion is permitted. Explain that Finder acts on all
  mounted bins and may remove new arrivals. Join the OS call; surface automation/permission/partial
  errors and refresh metadata, including errors where Finder may still be working.
  Retention may permanently remove FileTree's own recognized operation-journal segments under its
  application data directory; it never applies to scanned user entries. Atomic temporary files may
  also be removed after a failed write.
  Explicit undo of a successful Trash move may exclusively restore its captured payload to its exact
  original path. It never overwrites an existing entry or deletes payloads. After successful native
  freedesktop restoration, only that recognized, identity-checked current-user `.trashinfo` receipt
  may be removed from its anchored private OS-bin `info` scope. Changed receipts or cleanup errors
  retain metadata and remain visible; this exception never authorizes deleting recorded source paths.
  Explicit duplicate *Link the extra copies* may replace only reviewed ordinary extra files with
  hard links to their explicitly kept file on the same mounted volume. Rehash complete main data,
  every named stream and supported extended-attribute payload; refuse protected, changed, linked,
  cloud/special, unknown and already hard-linked originals. Retain each captured old copy under an
  exclusive operation-owned backup name in its anchored original parent, publish the captured new
  alias without overwriting arrivals, and reverify complete equality before retiring only that exact
  captured backup. Windows retirement uses its identity-checked DELETE handle; POSIX uses the
  anchored parent descriptor and immediate no-follow identity checks. Cleanup may also unlink only
  an identity-checked temporary hard-link alias created by this operation. Never delete an unrelated
  arrival, directory or recorded history path. Failure attempts exclusive rollback; retain/report
  actual backup/alias paths if rollback or cleanup fails. Approval explains that old data is not kept
  in Trash and all names share future data/metadata changes. Concurrency remains observational.
  Scan-history retention may remove only recognized FileTree history JSON under its application-owned
  history directory, after validating its format/root bucket/name. It never removes recorded source
  paths. Retention anchors POSIX directories by descriptor and pins Windows directory handles against
  rename/delete; linked directories and linked metadata are rejected.
  Isolated validation tools may remove only disposable fixtures they created in a fresh owned scratch
  directory or its private test-volume image. They must refuse existing volumes/bins and the host mount
  namespace; this never authorizes removing scanned user entries.
- **Every text goes through `tr()`**; add a key to all five tables in `je_file_tree/gui/strings.py`
  (`test/test_i18n.py` checks keys and placeholders). Traditional Chinese uses Taiwanese wording
  (檔案、資料夾、設定、預設、資源回收筒); Simplified Chinese uses Mainland wording and characters.
- Files are read and written with an explicit `encoding=`; exports are written to a temporary sibling and
  moved into place.
- Subprocesses: no shell, fixed programs only. `explorer /select,` needs the path in quotes (see
  `je_file_tree/gui/file_actions.py`).
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
