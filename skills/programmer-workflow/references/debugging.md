# Debugging — instrument, run, triage, clean up

The loop is: propose → (in `workflowMode=plan`: write plan and get approval) → instrument → run → triage → fix → regression → remove logs.

## Trigger

Offer this loop when:

- a bug survives 2 fixes or 3 rounds;
- the user says “还是不行 / 偶尔 / 只在某台机器上”;
- the failure is not reproducible in tests;
- the stack trace is noisy or missing.

If the workspace is already declared dev-only/no-hardware **and** boot reports
`devOnlyDirect=true`, skip the offer and go straight to instrumentation +
instructions (see “Dev-only mode”). Otherwise follow the normal offer.

## Offer

Use `references/ask.md`. Options:

1. Add minimal logs + auto-run + triage (recommended).
2. Add logs only; give commands.
3. Static analysis / bisect / minimal reproduction.
4. Hardware-assisted (checklist).

In `workflowMode=plan`, never run code before the user approves the plan; the runner requires `--yes`. In `full-authority`, routine debug commands do not need a separate approval; use `--full-authority` and keep destructive-command confirmation. The plugin mode never overrides the host's own read-only/sandbox limits.

## Instrumentation contract

Every debug line:

```text
[DBG-<ticket>-<n>] <iso time> <function/phase> key=value key=value
```

Include:

- entry/exit of the suspect function;
- input shape and identifiers (not whole payloads);
- branch taken and the condition value;
- state transitions;
- external call target/status/latency;
- caught exception with type + message;
- thread/request id when concurrent.

Rules:

- One line per event; no multi-line dumps except stack traces.
- Redact secrets/PII; truncate strings to ~200 chars.
- Sample loops (every N or on change), never log every iteration.
- Use a stable prefix so triage can find them.
- Make removal easy: one patch, one `DEBUG` flag, or one commit.

## Language recipes

### Python

```python
import logging, os, time
log = logging.getLogger("dbg")
if os.environ.get("DEBUG"):
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")

log.debug("[DBG-auth-1] enter user_id=%s token_present=%s", user_id, bool(token))
log.debug("[DBG-auth-2] branch=%s expires_at=%s", branch, expires_at)
try:
    ...
except Exception:
    log.exception("[DBG-auth-3] verify failed user_id=%s", user_id)
    raise
```

For hard crashes: `python -X faulthandler`, `faulthandler.enable()`, or `pdb -c continue`. For async: log task id. For tests: `pytest -s --log-cli-level=DEBUG`.

### JavaScript / TypeScript

```js
const dbg = (...args) => process.env.DEBUG && console.error("[DBG-auth-1]", ...args);
dbg({ userId, hasToken: Boolean(token), route: req.path });
```

Browser: `console.debug` with a prefix; Network panel; `debugger;`. Node: `NODE_DEBUG`, `--trace-uncaught`, `--enable-source-maps`. Do not log tokens or full request bodies.

### C / C++

```c
fprintf(stderr, "[DBG-render-1] frame=%llu index=%zu ptr=%p\n",
        (unsigned long long)frame, index, (void*)ptr);
fflush(stderr);
```

For memory bugs: AddressSanitizer (`-fsanitize=address -g`), UBSan, Valgrind, `gdb --args`, crash dumps. Log before/after the suspect call, not inside a tight render loop without sampling.

### C# / .NET

```csharp
Console.Error.WriteLine($"[DBG-order-1] orderId={orderId} state={state}");
Debug.WriteLine(...); // IDE
```

`dotnet-trace`, `dotnet-dump`, `EventSource`, `ILogger` with scopes. For async, include `Task.CurrentId`/correlation id.

### Java / Kotlin

```java
System.err.printf("[DBG-order-1] orderId=%s state=%s%n", orderId, state);
```

Use SLF4J parameterized logging; `jstack`, `jcmd`, async-profiler, exception stack traces.

### Go

```go
log.Printf("[DBG-order-1] order=%s state=%s", orderID, state)
```

`go test -race`, `pprof`, `GOTRACEBACK=all`, `dlv`.

### Rust

```rust
eprintln!("[DBG-order-1] order={} state={:?}", order_id, state);
```

`RUST_BACKTRACE=1`, `tracing`, `cargo test -- --nocapture`, `gdb`/`lldb`, `cargo expand`.

## Running

Show the exact command and why. In `plan`, get approval after presenting the plan; in `full-authority`, proceed and report. Both flags together are invalid.

```bash
python "<skill>/scripts/companion.py" run --host dsh --label login-repro --timeout 120 --yes -- python -m app --case login
# full-authority: replace --yes with --full-authority
```

What it does:

- refuses obvious destructive commands unless `--allow-destructive`;
- captures combined stdout/stderr to `<workspace>/debug-logs/<timestamp>-<label>/combined.log` (configurable in DSH Settings);
- writes `meta.json` (command, cwd, duration, exit code, timeout, git commit);
- kills the process tree on timeout;
- returns a bounded tail.

If the command needs a shell pipeline, use `--shell`. On Windows, quote paths and prefer `python` over `py` if only one exists.

## Triage

```bash
python "<skill>/scripts/companion.py" triage "debug-logs/<dir>/combined.log" --host <host>
```

Outputs `TRIAGE.md` and `TRIAGE.json` beside the log:

- error signatures grouped by normalized text, with count and first context;
- exception/crash stack blocks;
- `[DBG-...]` markers and their frequency;
- hypotheses across 12 common patterns (null, timeout, connection, permission, path, port, memory, pointer, input/type, DB/lock, TLS, dependency);
- a suggested verification order.

Treat hypotheses as candidates, not conclusions. Add **one** probe, rerun, and compare. If the triage says “needs more scene”, add boundary logs rather than guessing.

## Hardware-assisted debugging

When the bug depends on a device, bus, firmware, or physical environment:

1. State what you cannot do from here.
2. Give a checklist:
   - device model/revision, firmware version, host OS;
   - connection (USB/serial/network), port, driver, permissions;
   - exact steps to reproduce, including power cycle and timing;
   - expected vs actual indicator (LED, log, response);
   - what to capture: serial log, `dmesg`, vendor tool output, screenshot, scope trace;
   - safe-state/reset procedure.
3. Ask the user to perform the step and paste the output.
4. Continue analysis locally; do not pretend the device was exercised.

For dev-only/no-hardware workspaces, do not block on this. Add logs and give local commands; note which conclusions remain unverified without hardware.

## Dev-only mode

The direct-instrumentation shortcut is active only when **both** conditions hold:

1. `devOnlyAutoInstrument=true` in this host's config;
2. an **active** workspace environment fact says dev-only/no-hardware (boot
   `workflow.devOnlyDirect=true`).

When active:

- do not ask “can I add logs?”;
- add the smallest reversible instrumentation now;
- tell the user exactly how to reproduce and where to look:

```text
我已加 3 处日志（文件/行号）。运行：
  <command>
日志会写到 <path> 或 stderr。搜索 `[DBG-...]`，把首次出现的前后 10 行贴回来。
```

- record the environment fact with `env set --dev-only --no-hardware`;
- if the user wants you to run it, still ask before executing in `plan` mode; running code is separate from adding logs.

If `devOnlyAutoInstrument=false`, or the fact is missing/proposed, do **not**
claim the shortcut; ask first. Never promote a proposed entry.

## Cleanup

Before closing:

1. Remove temporary logs, or gate them behind `DEBUG`.
2. Run the relevant tests.
3. Add a regression test for the fixed case.
4. Report the root cause, the evidence, files changed, and residual uncertainty.
5. If hardware was involved, note what was verified on-device vs locally.

## Safety

- No secrets in logs; redact tokens, cookies, auth headers, private keys, customer IDs.
- No destructive commands; the runner blocks patterns but is not a sandbox.
- Do not run production migrations or deploy commands as “debug”.
- Do not leave verbose logging in hot paths.
