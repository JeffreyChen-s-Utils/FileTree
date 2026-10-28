# FileTree UI and UX design

## Goals

The primary flow is choose a source, understand its space usage, then explicitly review any source
operation. The interface should expose that order, keep analysis views discoverable, and explain
waiting without inventing a completion percentage or implying that an incomplete tree is empty.

## Layout and interaction

- **History trends:** a copyable full path, loaded-folder chooser and root action make scope explicit.
  The chooser pages through captured direct folders on its own cancellable workers and retains the
  query on Cancel. Recent 30/90-day and all-history choices share custom local date boundaries and
  optional calendars. Invalid text remains and receives focus. Chart and table share point indices,
  including same-time observations and unknown markers in a separate band. Arrows navigate points;
  Tab leaves tables. Selected details distinguish unknown size from unknown change and expose exact
  bytes beside global-unit signed changes. Empty, single, capped and incompatible results have
  separate explanations. Full-root comparison remains an independent tab. Compact bottom actions
  keep the table usable on a 1024×768 logical desktop. `tools/verify_trend_ux.py` uses hidden native
  windows, private history and actual keyboard focus; local contrast simulation does not verify
  operating-system contrast or screen readers.

- **Workspace templates:** a labelled save section captures the workspace when the manager opens.
  Add and Update name that source; edits in the separate load preview apply only to this load and
  require another path check. Active tabs have a text label. Beside Replace tabs, live counts explain
  which tabs, scans and results will close and how many checked preview paths are unavailable.
  Complete existing scopes remain copyable in scrollable details. Tab reaches the name, save actions,
  preview, check, replacement and cancel; arrows navigate preview cells. Cancel preserves tabs and
  results, and replacement retires workers asynchronously before installing idle inputs.

- **Folder budgets:** the table follows the active tab's display unit and provides exact-byte
  tooltips and accessible descriptions. Observation time stays separate from usage. Never-scanned
  rules and limits awaiting a new full scan have distinct text; a changed limit retains dated old
  usage but cannot produce current excess. The editor converts byte integers into exact finite
  binary-unit input without display rounding. Row refresh, language and unit changes preserve the
  unsubmitted form and its identity selection. An external path request does not overwrite a dirty
  form. Choose folder only fills the path. Labels have buddies, validation focuses its input, the
  form scrolls, and the action row stays outside the scroll area.

- **Cleanup completion:** a compact header retains moved/skipped/failed counts and logical moved
  bytes across rescans. Its transient scrollable details preserve the analysis pane's geometry,
  show refusal reasons and point to complete existing reports/records. Records, existing expiring
  Undo and original-folder rescan reuse their guards; details close before dispatch. Free-space
  changes are separately dated same-root scan observations including other activity; missing
  observations remain unknown. No bin emptying or new operation approval is implied.

- **Named presets:** the welcome page and Options offer the same editor for one-path presets.
  Add/Update capture current scan options; Rename preserves saved choices. Load fills inputs and
  reports that Scan path is still required. Existing results/selection remain. Invalid settings
  produce a translated error without overwriting data. No administrator or source-operation
  approvals are saved. Current-tab scans/source reviews disable the editor; opening it does not
  suspend peer readers. The settings-dialog shutdown contract closes it safely with the application.

- **Result highlights:** a keyboard-collapsible section below the metric cards links the three largest
  direct folders to the tree, candidate cleanup data to Clean up, and skipped/unreadable/pending
  coverage to Problems. Pending analysis differs from a completed empty result; partial sizes remain
  explicit. Candidate bytes never imply free-space recovery. The section keeps its expansion and the
  tree's selection across language/unit changes, using worker-captured data without source queries.

- **Welcome:** a primary folder chooser beside all-drive scanning, followed by a short workflow hint,
  cached drive rows, grouped drive tools and recent folders. The content scrolls when many drives or
  recent entries exceed the window height. Recent-path buttons preserve literal ampersands and expose
  their entire path through tooltips and accessible names. Drive rows show the root in native form
  (`C:\`), free and total space on one line in the selected size unit, and the used share in the bar's
  tooltip and accessible name; the bar turns red from 90 % used. Each drive's Recycle Bin caption sits
  muted under its bar. Choose a folder and Scan all drives share one height.
- **Path toolbar:** an explicit Scan path action next to the input, alongside existing chooser, rescan,
  stop and help actions. Enter activates that button. Blank input and the shared source-operation
  guard disable it; typing does no filesystem validation. Replacing a running scan retains the
  existing queued worker cancellation and ownership rules.
- **Results overview:** four cards distinguish logical size, recorded allocation, file count and
  folder count. Large values support copying; captions and values have accessible names/descriptions.
  Live, finished and incomplete states remain explicit. Unreadable-entry counts link to Problems.
  Exclusions/mount boundaries remain applicable; allocation may be estimated/shared and is never
  presented as recoverable space. The existing detailed summary and capacity ledger remain visible.
- **Analysis navigation:** a vertical list provides all existing result views without a crowded tab
  strip. Below 1,000 logical pixels of result-page width, a dropdown replaces the sidebar. Hidden
  comparison pages stay absent from both until available. Keyboard selection, menu shortcuts,
  comparison reveals and cross-view selections synchronize with the original page indexes.
- **Analysis workspace:** the tree and current analysis share a noncollapsible splitter, initially
  about 45% / 55% of its actual width unless a valid saved split is restored. Later user resizing is
  retained within the tab and the saved split survives reopening. Legacy saved states cannot restore
  collapsible panes; both the tree and analysis remain available. Inactive pages'
  minimum widths do not squeeze the chart's tree pane; the active page retains its control minimum.
  Selected-folder list scope stays above the views. A short hint explains when whole-scan analysis
  lists will become available.
- **Result lists:** folder columns in Largest files, Search, type locations, Clean up and Duplicates
  elide from the left so the nearest folders stay visible; names keep middle elision to retain their
  extension, and full paths remain in tooltips. Share bars use a more opaque highlight on dark surfaces.
  Empty lists explain themselves: Problems says a complete scan read every entry (nothing while
  scanning or after a stop, which did not read everything), and Largest files says nothing matches a
  filter or type/age focus. Chart breadcrumbs draw on the pane's own background.
- **Chart legends:** keep each color marker and translated category/age label in one nonwrapping
  label and flow complete entries onto new rows as the pane narrows. Inherit fonts and theme ink;
  expose literal accessible names. Do not add invisible word joiners to labels: they trigger slow
  first-use native Windows font fallback. Empty legends reserve no row height.
- **Closing:** display a translated closing status, cancel pending readers and release paused scans,
  and keep ordinary Qt events running until native calls and exports finish. Retain each tab and all
  its workers until joined; peer scans remain independent. Report late source-operation failures
  before releasing the owner. Close-to-tray keeps its explicitly enabled behavior.
- **Elevation identity:** administrator-action tips explain that Python source elevates Python/pythonw,
  so UAC identifies the interpreter. Compiled Windows FileTree embeds its own product/file descriptions;
  changing Qt titles cannot change source-mode UAC identity or establish publisher verification.
- **Small windows:** overview cards wrap to two columns below 680 logical pixels. The welcome scroll
  area retains access to tools and recent sources. Existing list horizontal scrolling continues to
  expose extra columns; it does not hide or discard data.
- **Scanning feedback:** the indeterminate bar avoids a fabricated percentage. A one-second
  presentation timer updates elapsed time between worker replies, including a slow native read.
  Pause freezes its activity animation, explains cooperative pausing, and leaves Stop available.
  Analysis disables Pause. Stopping disables repeat requests and explains waiting for current native
  work; available partial results keep their incomplete state. The current path uses a plain-text
  middle-elided label with the full path in its tooltip and re-elides on resize.

## Visual and accessibility constraints

Use Qt palette roles for card borders, surfaces, secondary text and selection, retaining the user's
System/Light/Dark choice and native platform controls. Use restrained spacing, rounded card/selection
surfaces, a stronger welcome primary button and readable numeric hierarchy. All new sentences go
through the existing five-language catalogues. Counters follow the selected size unit. Standard Qt
list/combo/button controls retain native accessibility and keyboard focus; the primary welcome
button has a visible focus border. Preserve tab ownership, selection synchronization and review
confirmations rather than creating a parallel action path.

## Execution and verification

`ResultOverview` renders only root scalar counters and captured coverage/error counts, without
traversal or disk queries. `ResultNavigation` copies at most nine page labels/visibility states.
`AnalysisTabs` derives its minimum geometry from the active page. Qt widgets/models and the elapsed
timer remain on the GUI thread; scanning, discovery, validation and analysis retain their workers.
No nested event loop, blocking join, new storage query or native filesystem call is added by these
presentation components. Existing worker cancellation and source-operation exclusion remain intact.
`EmptyHint` reads only its view's row count when the model announces a change, and its label is
transparent to the mouse, so the view keeps every click, selection and context menu.

`test/test_ui_ux.py` covers five-language counters, unit changes, stopped/unreadable coverage,
keyboard/sidebar/dropdown synchronization, comparison visibility, selected-folder scope, slow-read
elapsed feedback, literal long paths, a scrollable many-drive home, blank/guarded Enter activation,
and theme changes without data/selection loss. The full regression suite and Ruff remain required.
`tools/make_screenshots.py` renders all five README pictures at 1,200 × 800 from the same in-memory
fixture. Native Windows review also checks welcome/results/live compact views across all three
themes without displaying windows. Offscreen widget tests do not establish real-world hanging paths
or native macOS/Linux interaction; those existing verification items remain in `progress.md`.

Search derives its removable condition summary from SearchFilters.state(), with explicit entire-scan scope. Name, each size bound, dates, type and kind have keyboard-accessible removal actions. Filter controls and long summaries scroll independently above the retained result table. Optional dates use a localized calendar with explicit acceptance; errors remain beside the input and move focus to that field. Typing immediately invalidates old results before the debounce delay. Native evidence is reproducible with tools/verify_search_ux.py; contrast is a local simulated palette.

Budget tables use arrow keys for row selection and Tab to leave for the editor. Opening or expanding search scrolls its focused name field into view. Calendar minimum geometry includes every week under the applied stylesheet. The budget/search probes send keys only to actual focus and exercise each language/theme/desktop combination at a checked native pixel ratio; hidden-window action setup does not establish operating-system shortcut delivery or screen-reader speech.
