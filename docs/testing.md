# Test diagnostics

Run the full suite once with a fresh evidence directory:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$testScratch = 'D:/Codes/tests/filetree-' + [guid]::NewGuid().ToString('N')
py -3 -m tools.run_pytest --evidence build/pytest-context-local -- -v --tb=short --basetemp $testScratch
```

Choose another evidence directory for each run; an existing directory is refused. The regular
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

## APFS final-busy observations

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
warming or mounting an image before those samples; actual final-busy capture and recovery remain #96.
