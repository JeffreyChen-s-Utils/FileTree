# FileTree UI and UX design

## Goals

The primary flow is choose a source, understand its space usage, then explicitly review any source
operation. The interface should expose that order, keep analysis views discoverable, and explain
waiting without inventing a completion percentage or implying that an incomplete tree is empty.

## Layout and interaction

- **Welcome:** a primary folder chooser beside all-drive scanning, followed by a short workflow hint,
  cached drive rows, grouped drive tools and recent folders. The content scrolls when many drives or
  recent entries exceed the window height. Recent-path buttons preserve literal ampersands and expose
  their entire path through tooltips and accessible names.
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
  about 45% / 55% of its actual width. Later user resizing is retained within the tab. Inactive pages'
  minimum widths do not squeeze the chart's tree pane; the active page retains its control minimum.
  Selected-folder list scope stays above the views. A short hint explains when whole-scan analysis
  lists will become available.
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

`test/test_ui_ux.py` covers five-language counters, unit changes, stopped/unreadable coverage,
keyboard/sidebar/dropdown synchronization, comparison visibility, selected-folder scope, slow-read
elapsed feedback, literal long paths, a scrollable many-drive home, blank/guarded Enter activation,
and theme changes without data/selection loss. The full regression suite and Ruff remain required.
`tools/make_screenshots.py` renders all five README pictures at 1,200 × 800 from the same in-memory
fixture. Native Windows review also checks welcome/results/live compact views across all three
themes without displaying windows. Offscreen widget tests do not establish real-world hanging paths
or native macOS/Linux interaction; those existing verification items remain in `progress.md`.
