# Test diagnostics

## Grouped view layout measurements

Run each operation in its own process, without concurrent tests or benchmarks:

```powershell
py -3 -m tools.measure_grouped_layout noop
py -3 -m tools.measure_grouped_layout headers
py -3 -m tools.measure_grouped_layout language --no-counts
py -3 -m tools.measure_grouped_layout unit --groups 3 --members 33334
```

The tool builds the production grouped view over owned in-memory Node objects. It never scans,
opens or changes source files. All members remain exposed, including those outside the viewport.
The default is 1,000 groups of 100 members; refuse more than 1,000 groups or 1,000,000 total members.
`headers` isolates the native header notification; `language` additionally updates keeper names.
`unit`, `labels`, `keeper` and `noop` isolate the other model updates. These are synthetic model/view
measurements, not full-panel or whole-window interaction tests.

JSON records the handler and cumulative elapsed time after each of three Qt event passes, actual
binding/Qt/platform/model/view classes, header/data/reset notification counts and before/after geometry.
Index/flags counters belong to the model actually passed to the production view builder. Counter
snapshots precede state verification, so QA queries cannot inflate them. Instrumentation adds dispatch
overhead; use `--no-counts` for ordinary model timings and retain every observation. Compare repeated
runs only within the same runtime/platform/shape, and never interpret an event pass as a settled frame
or an input-latency guarantee. The tool checks source identities, every row, member tuples, selection,
current/persistent indexes, collapsed first group, name-column width and scroll clamping. It returns
nonzero on a failed check, detaches its view and restores the previous language even if an update fails.

Record native header and viewport geometry independently before/after translation. They can change
with the translated text's native size hint; macOS has reported header height 19 → 16 with a matching
viewport adjustment. Equal geometry is not a platform-independent invariant. Tests compare recorded
geometry with actual native observations and deliberately resize the header to guard this case;
they retain callback counting, complete-row/state checks and ordinary Qt layout behavior.

Qt's native header notification can schedule a full item layout even when visible geometry stays
unchanged: see [the Qt 6.8 connection](https://github.com/qt/qtbase/blob/6.8/src/widgets/itemviews/qabstractitemview.cpp),
[private layout scheduling](https://github.com/qt/qtbase/blob/6.8/src/widgets/itemviews/qabstractitemview_p.h)
and [tree layout/accessibility updates](https://github.com/qt/qtbase/blob/6.8/src/widgets/itemviews/qtreeview.cpp).
Retain those notifications and native handling. This tool diagnoses the remaining #95 pause; it does
not fix it or establish the owner's original hanging path.

## Pytest native context

Run the full suite once with a fresh evidence directory:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$testScratch = 'D:/Codes/tests/filetree-' + [guid]::NewGuid().ToString('N')
py -3 -m tools.run_pytest --evidence build/pytest-context-local -- -v --tb=short --basetemp $testScratch
```

Choose another evidence directory for each run; an existing directory is refused, and so is one
that resolves outside the directory the wrapper was started from. Forwarded pytest arguments may
contain letters, digits, spaces and the punctuation of options, paths and `-k`/`-m` expressions;
quotes, control characters and shell metacharacters are refused, and `-p` may only disable a plugin
(`-p no:<name>`), never load one. The regular
`py -3 -m pytest` command still works and does not load the phase plugin. The wrapper runs the same
interpreter once, forwards pytest arguments, waits for its actual exit and retains:

| File | Meaning |
|---|---|
| `process.json` | Parent/launched-process PID, start observation, Python version, running/exited state, actual child return code and elapsed time |
| `active.json` | Latest collection/setup/call/teardown/session-finished observation, case and timestamp |
| `phase-threads.txt` | Python thread stacks captured on entry to that phase, without locals or environment values |
| `output.log` | Combined stdout/stderr, including native Qt messages and fault-time Python traces when available |

`active.json` is replaced before each phase snapshot. Compare the snapshot's first JSON line with
`active.json` (especially PID and monotonic timestamp); an interruption between writes can leave an
older snapshot. These snapshots describe phase entry, **not the instant of a later fault**. The latest
case is capped at 4,096 characters with an explicit truncation flag. Files are replaced rather than
accumulating phase history. Python's traceback dumper bounds thread/frame output.
The phase record's PID is the actual pytest interpreter. On Windows a virtual environment can launch
through a redirector, so this PID can differ from `process.json`'s immediate `Popen` child PID. Neither
PID observation grants authority over an unrelated process.

The child uses unbuffered Python output, `--capture=tee-sys`, `PYTHONFAULTHANDLER=1`, a 60-second
non-terminating pytest traceback timer and `QT_FORCE_STDERR_LOGGING=1`. The latter routes Qt's default
logging to the retained stderr stream; the runner installs no Qt message handler. Existing custom
handlers and explicit capture fixtures still take precedence, so messages they consume may be absent.
Python output still participates in pytest reports; native FD output passes directly to the log.
These choices follow [pytest's capture behavior](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html)
and [Qt's logging sink setting](https://doc.qt.io/qtcreator/creator-how-set-project-environment.html).

The local Windows Qt 6.11.2 controlled `qFatal()` cases exit with `0xc0000409` and retain the Qt message
but no fault-time Python traceback. Phase-entry snapshots cover that diagnostic gap partially; they
cannot identify the exact native fault or prove why an earlier uninstrumented run failed. A separately
owned `os.abort()` child verifies the fault-time traceback route. See
[Python's fault-handler limits](https://docs.python.org/3/library/faulthandler.html).

Normal pytest exit codes pass through. Native signal/Windows failure codes are kept in `process.json`
and cause wrapper exit 1 when outside the portable 0–255 range. A missing `exited` state is incomplete
evidence, and even a `session-finished` observation cannot override a later nonzero process exit.
The runner never reruns pytest or helpers or adds a process deadline; existing CI job/helper bounds remain.
Diagnostic replacement uses its captured OS primitive so application fault-injection tests cannot
intercept it. Teardown runs fixture cleanup even if a diagnostic write fails, then reports that error.
On Windows, a reader that does not share deletion can briefly prevent atomic replacement, as described
by [Microsoft's sharing rules](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).
Diagnostic publication alone retries error 5/32/33 at most ten times with nine 10 ms pauses. Persistent
and unrelated errors remain visible; tests, helpers and native cleanup operations are never retried by this rule.
Output is retained while the child runs and copied to the console after it exits. Interrupted CI runs
can still leave partial evidence. Full Windows/Linux/macOS and Qt 6.8 jobs always upload the evidence
directory for seven days. No memory dumps are collected or uploaded.

## Selected-list capture responsiveness

`ListCapture(selected=True)` prepares native selection ranges and ancestor order keys in the same
cooperative 128-work-unit / 4 ms turns as row reads. A heap merges range candidates without allocating
all selected row indexes before the first yield. Deduplication includes actual parent identity, so
equal numeric paths under different parent columns keep both rows in native stable order. Full-width
selected ranges still read every column's enabled/selectable flags, excluding wholly disabled rows;
partial-cell ranges delegate to native `isRowSelected`. Default native selection models take this
path; custom classes and Python instance/class method overrides retain `selectedRows` delegation.
The [Qt 6.11 selection implementation](https://raw.githubusercontent.com/qt/qtbase/v6.11.2/src/corelib/itemmodels/qitemselectionmodel.cpp)
and [Qt 6.8 implementation](https://raw.githubusercontent.com/qt/qtbase/v6.8.3/src/corelib/itemmodels/qitemselectionmodel.cpp)
show why repeated global row checks revisit selection ranges and why selectable/enabled flags matter.

Keep model/data/header/row/column invalidation, selection changes, view rebinding and destruction
observable. Cancellation clears pending output and releases preparation state; a reentrant data
change cannot refill canceled rows or restart a timer. Existing bounded streams, formula escaping,
atomic CSV writes and original selection state remain. Structural tests bound callbacks, compare
native row semantics across partial/disabled/proxy/tree and pending Select/Toggle/Deselect cases,
exercise deep ancestors and parent columns, and check cancellation preserves existing files. Run
them in both pinned Qt 6.8 lanes as well as the full matrix.

The time budget is cooperative: an individual model/Qt API, opaque custom selection callback,
final string extraction or native clipboard access may still block. Native performance probes must run
sequentially without a concurrent local full test suite, retain rejected prototypes and every sample,
and distinguish first-turn/one-heartbeat observations from total capture and end-to-end input latency.

## APFS final-busy observations

The original owned-image `hdiutil detach` attempts include its documented `-verbose` diagnostic option
([macOS hdiutil manual](https://man.freebsd.org/cgi/man.cgi?manpath=macOS+13.6.5&query=hdiutil&sektion=1)).
Each successful attempt retains up to 64 KiB of stdout with an explicit truncation flag; failures keep
their existing capped stdout/stderr and original exception. Output is diagnostic text, never device
authority. Preserve the checked target, three-attempt maximum, original 0.5/1-second delays, 60-second
command bound, complete-binding recovery checks and independent final absence verification. This
adds evidence for the next native failure; mocked flag/output tests cannot prove the busy cause.

`tools.macos_busy_observer` runs only after the third owned-image detach returns native exit 16.
It fences a literal-file `lsof` query with fresh image/scratch identity, complete registration and
canonical volume/container/store checks. The original detach error, attempts, delays and cleanup
guards remain authoritative. A ten-second native-command budget allows at most two seconds per
read. Queries never retry detach, force an unmount, inspect process command lines or signal a holder.

The [`lsof` field format and `-f --` semantics](https://raw.githubusercontent.com/lsof-org/lsof/master/Lsof.8)
keep selectors as literal files. Arguments contain only the owned image and registered device paths;
the query does not walk the fixture filesystem. Output selects PID, short command, descriptor,
type and filename fields. Retain capped NUL-separated bytes in base64, including stderr; fields
may be incomplete or include permissions warnings. Global image inventory output is hashed rather
than copied into proof. A stable scope and an open-file association do not establish the busy cause.
No visible result is still incomplete, especially for other-user/kernel holders and unqueried aliases.

On unelevated macOS, validate the literal-file backend independently:

```sh
python -m tools.validate_macos_busy_observer --output build/literal-open-file.json
```

The probe exclusively creates and holds one temporary ordinary file, requires its own PID in the
native output, verifies bytes/identity and records cleanup even on failure. It refuses existing proof.
The macOS CI job runs it after the original three APFS samples, including when an earlier step fails,
and retains `macos-evidence/literal-open-file.json`. This verifies the native query backend without
warming or mounting an image before those samples. A final-busy capture with a backing-image helper
association still cannot establish the busy cause; identifying it and verifying recovery remain #96.

The 143 hosted samples of 2026-10-16/17 (`docs/updates/apfs-cleanup-survey-20261017.json`) show the
verbose refusal: the disk-image driver is already quiet, the APFS volume is already unmounted, and
only the whole-disk eject reports `Resource busy`. Within the original bounds 134 samples detach on
the first attempt and 3 recover on the second or third; 6 exhaust them, none after run 39000091134.
`lsof` cannot see kernel or other-user holders, so any detach with a busy refusal now also keeps a
`refusal_log` on its last attempt: `log show --style ndjson` for DiskArbitration entries and entries
naming the device, from two seconds before the first refusal to two seconds after the last attempt.
It runs only after the attempts end (its own 20-second bound, at most 200 parsed entries), so delays,
attempts and outcomes are unchanged. DiskArbitration names the dissenter of a refused eject; an entry
is an observation, not an established cause, and a missing or refused log read changes nothing.

## PowerShell clock evidence

The native disconnect helper emits `FILETREE_SMB_CLOCK`; the mocked helper harness additionally emits
`FILETREE_TEST_CLOCK`. Each contains the actual shell PID and UTC samples immediately before/after
its own Stopwatch start. Existing step/phase record schemas stay intact. Receipt processing now has
separate `receipt-read`, `receipt-parse` and `receipt-identity` markers. The same Get-Content options,
JSON conversion and ownership comparisons remain, with zero/one raw outputs captured before parsing.
A frozen original function verifies empty, null, array, malformed, missing, wrong-SID, ordinary,
BOM and Unicode receipts on each available PowerShell runtime. SMB commands remain mocked in tests.

`windows_trace_clock` reports missing/invalid/ambiguous origins explicitly. It supplies integer
`creation_to_origin_100ns` offsets only when the previously captured owned-child observation and
identity PID match the clock PID and include a valid creation time. A sample without birth metadata
retains its origin without inventing startup time. An origin before creation is inconsistent.
Clock metadata does not change native exit/timeout or existing trace-completion decisions.

The wait observer records UTC samples around each WCT query and at record emission. These share the
[Windows FILETIME epoch used by DateTime](https://learn.microsoft.com/en-us/dotnet/api/system.datetime.tofiletimeutc)
and [process creation times](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes).
The Python observer converts integer Unix nanoseconds to those units. Units do not imply measurement
precision: UTC changes/resolution and diagnostic overhead can limit ordering. Creation-to-clock
offsets include runtime/script preparation before instrumentation and assume a stable host UTC clock;
they are not monotonic durations or proof of a blocking syscall. Raw WCT wait-time fields remain raw.

Each sample also emits one `modules` record after the thread list: the count and at most the newest
160 module file names in load order from a read-only Toolhelp snapshot, with `truncated` and any
native `error` kept. #100's reproduction (U-20261017-51) stalled idle at start-up and in the first
`ConvertFrom-Json` with no WCT-attributable owner; the newest names show what was loading then. A
module name is an observation, not a cause: loading can finish between the snapshot and the wait.

A `thread-states` record follows: one read-only `SystemProcessInformation` snapshot gives the
process's I/O operation/byte counters and, for at most 48 threads ordered by creation time (so the
main thread leads), the kernel thread state, `KWAIT_REASON`, context switches and raw wait time. Each
thread's own start routine (`ThreadQuerySetWin32StartAddress`, through a handle pinned to the target
process) is reported as module plus offset. Two samples per timeout show whether the main thread is
blocked in user requests, executive (I/O) waits or ALPC, and whether I/O counters still move. The
x64 layout is fixed; other layouts record an explicit error instead of guessed fields.

Both helpers still launch once with their original 30/20-second deadline; the observer starts after
five seconds and retains its five-second bound, thread/node caps and ownership checks. A still-live
target receives at most one later observation five seconds before its original deadline, provided
the scheduled samples are at least five seconds apart. Deduplicate short schedules and honor the
requested initial delay. Every communicate subtracts elapsed monotonic time, including observer
startup; perform normal final observation collection/cleanup only after target exit so pipe joins
do not delay target termination. Existing partial-start failure cleanup remains synchronous, with
its cost included in the remaining target budget. Keep the first report unchanged and attach a one-entry `later_samples` list only when
a second sample actually starts. Caps apply per observer (at most twice the original retained bytes). No permissions,
cross-process flags, object names, dumps, retries or target-control operations are added. A passing
run cannot resolve a prior intermittent timeout; the next reproduced failure must supply aligned data.

The standard-library observer starts with the runtime's base executable when available, falling back
to its current executable only when that metadata is absent/empty. A Windows virtual-environment
redirector would otherwise add a parent and cause the unchanged exact sibling check to reject an
owned target. CPython also selects the base executable for [Windows process spawning from a virtual
environment](https://github.com/python/cpython/blob/3.13/Lib/multiprocessing/popen_spawn_win32.py).
This changes only the observer program: target commands/environments, parent/handle authorization,
hidden-window flags, query caps, timers and remaining execution deadlines stay the same. It never
follows descendants or accepts a grandparent in place of the actual parent. Tests use a fresh pip-free
Windows environment and a base-interpreter target held until observation ends, requiring its actual
controller PID in the native identity record. A healthy observation does not establish a timeout cause.

Observer stdout and stderr are drained concurrently from launch, with at most 64 KiB retained for each
stream. Readers keep draining overflow so the child cannot block on an anonymous pipe before its
bounded WCT capture finishes; truncation stays explicit. Finish joins the observer, both readers and
its canceled timer, closes the pipes and retains partial records without inventing completion.
Read errors are reported separately in `capture_errors`, preserving the observer's actual exit.
Partial reader-start failure reaps only that observer and closes both streams, including an unstarted
reader; caller interruptions receive the same cleanup and are re-raised. Tests cover a real owned
20-thread Windows child without an early `communicate`, a real 200,000-byte producer on each stream,
exact retention boundaries, partial read/start errors, interruption and both stop reasons. The existing
five-second observer timer, 32-record/16-thread/16-node caps, target deadlines and ownership remain.

`test_observed_timeline.py` uses a controlled monotonic clock to exercise both sample windows,
successful/failed/timeout outcomes, exact retained streams, one launch, no deadline reset, startup
cost, slow cleanup after target exit, interruption during later startup, short/disabled schedules
and the maximum two-sample bound. Native PowerShell fixtures bracket early/late sleep phases with
UTC samples and require two complete sibling observations of the same live process birth under
Python 3.14 and a Python 3.13 virtual environment, including real 20-second timeouts. These fixtures
verify later observation capability, not the cause of #100's import wait or #99's native SMB timeout.

The direct native mutex test launches both its target and observer with the base interpreter, so
the retained Popen PID is the actual waiting process. A separate native comparison retains the
virtual-environment launcher refusal and the successful direct sibling identities. The original
production ownership guard remains unchanged.

## Owned-child timeout fixtures

The post-output timeout test prepares one real child and waits, for at most ten seconds, for its owned
receipt written after both output streams are flushed. It then supplies that captured child once at
the Popen boundary, keeping the tested 0.5-second communication deadline and 0.1-second sample point.
It checks exact launch arguments, exact streams, one request and reaping, with cleanup even on fixture
failure. A deliberate 0.7-second first-emission delay verifies that preparation is independent of
the communication deadline. A separate real no-output child must retain empty streams and its timeout.

This corrects an unsynchronized test assumption; empty historical stdout alone does not establish a
startup delay or output loss. The production runner still starts its clock before Popen, launches
once and uses the remaining deadline. Its modeled remaining-time checks and native helpers' original
30/20-second execution bounds and five-second observation bounds remain unchanged.

## Clipboard text preparation

`test_clipboard_copy.py` checks encoding before the last capture turn, byte-for-byte TSV equality
with the synchronous helper (formulas, quotes, tabs, newlines and Unicode), GUI-thread publication,
and one current request across views. Exercise stale callbacks and reentrant requests during header
reads or clipboard publication in either observer order. Check model/selection changes, observed
clipboard changes during row escaping and after completion, close/hide/destruction, empty selection,
and an actual QApplication exit in a fresh child. Recording QObject sinks avoid touching the OS
clipboard. Both Qt 6.8 compatibility jobs execute these cases.

[QClipboard](https://doc.qt.io/qt-6/qclipboard.html) documents the application clipboard and its
change notification; macOS external changes may only be detected on activation. Cancellation starts
when a notification is observed, without a claim about undelivered OS changes. The pending-only
[QObject event filter](https://doc.qt.io/qt-6/qobject.html#installEventFilter) runs on the GUI thread
and returns false to preserve normal event delivery. Native probes measure the actual shortcut and
capture with a recording sink; they exclude native clipboard conversion/ownership and OS interaction.
Retain all callback durations, runtime/source hashes, validated row counts and complete text digests.

## Private native Windows clipboard

The `Windows private clipboard` job runs `python -m tools.measure_clipboard_tail` for 100,000
synthetic rows with 80/512-character folder suffixes, using the existing pinned/hash-checked Qt
requirements and native Windows backend. It creates only new station/desktop objects in a fresh
helper before importing Qt; its protected DACL grants the owner and System access. No scan,
source operation, elevation, desktop switch for user input, or existing-station fallback is used.
[Window stations contain their own clipboard](https://learn.microsoft.com/en-us/windows/win32/winstation/window-stations),
and only WinSta0 is interactive. Exact private station/desktop names and a noninteractive flag are
required before clipboard calls. [CreateWindowStation](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-createwindowstationw)
uses CWF_CREATE_ONLY, refusing any existing name. Local named creation returns access denied and
generated-name creation returns already-exists; neither exploratory call reaches Qt or a clipboard.
Do not replace this gate with an interactive clipboard save/restore or reuse an unknown station.

The actual view shortcut and incremental capture publish through a timed proxy over the real
private QClipboard. A separate native reader, launched on that exact desktop with the base Python
executable, receives only the new station/desktop handles through the supported STARTUPINFO handle
list with close_fds enabled. It verifies their names/noninteractive flag and actual parent, then
explicitly joins those handles before fetching CF_UNICODETEXT (at most 128 MiB). The unsupported
Python lpDesktop attribute is not used. A desktop-metadata-only local probe verifies handle transport
under both Python runtimes; it calls no clipboard API and is not private clipboard readback proof.
Compare the complete text hash after Windows CRLF normalization and decode/check every quoted,
formula-safe Unicode row against the capture. Preserve source identities/selection and all rows.
Record every capture callback and 5 ms heartbeat interval, final StringIO extraction, native Qt
setText call, consumer fetch/decode, complete elapsed time and source/runtime hashes. The native
reader's 30-second self-exit, GUI's 45-second watchdog and outer helper's 60-second owned-process
deadline apply only to the probe and do not change production copy behavior. Keep partial output,
return codes and cleanup failures; nonempty diagnostic stderr alone is not failure. A reader start
that setText queued but that runs only after cleanup began is recorded as `late_consumer_start` and
never launched, so no reader outlives the probe unreported.

Stop/join only the retained reader, clear only the guarded private clipboard, destroy Qt while the
private scope still matches, then retire the windows this thread still owns on the private desktop
before restoring/verifying the original context and closing only created handles. SetThreadDesktop
refuses a thread that owns windows, and Qt 6.11/6.12 keep a theme-change observer window after
QApplication is deleted: run 39034413839 measured and verified the readback, then failed to restore
with error 170 (ERROR_BUSY). The thread had no windows when it entered the private desktop, so each
remaining window is on it; retirement happens only while the thread is still on that desktop. The
system IME window retires with the last other window and is never destroyed directly. Each retired
class, failure and residual window is recorded in `cleanup`.
If scope cannot be verified before Qt destruction, the fresh helper reports failure and exits without
Qt finalization or station switching; the outer driver retains that nonzero result. Reserving a new
report path prevents overwriting old evidence. The always-run artifact step retains JSON/logs even
on native failure; the job/step bounds remain 10/3 minutes. Hosted runs 39037318629 and 39038187983
established all these assertions for both widths (U-20261017-53). Modeled boundary tests and
offscreen recording tests are not native proof, interactive clipboard-manager contention, settled
frames, or input latency.

## Workflow command scalars

Quote a complete single-line `run` value or use a block when a command contains a colon followed by
whitespace, including `pip --only-binary :all: -r ...`. YAML interprets that separator structurally
even when it is part of a shell argument. `test_workflow_actions.py` checks workflow/composite run
scalars, preserving quoted/block values, URLs, times and comments. This focused guard is not a
general YAML/schema parser; workflow creation and the actual hosted jobs still require validation.
