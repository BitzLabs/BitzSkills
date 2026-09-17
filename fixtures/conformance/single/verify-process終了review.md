# verify process termination fixture review

Covers `SINGLE-057`, `SINGLE-058` and `SINGLE-059` from
[適合fixture仕様 §6.6](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#66-verify).
`SINGLE-069-01/02` (output truncation) and the deferred `SINGLE-066`/`SINGLE-068` are separate steps.
These are reviewed expectations, not observed Core behaviour.

## All three fail after the pre-checks pass

[verify仕様 §6](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#6-command結果) separates the
"環境不足" conditions, which produce no `commands[]` entry and empty `bindingRefs`, from failures that
happen once process creation has been attempted. These three belong to the second group, so each one
records a `commands[]` entry, keeps `bindingRefs: ["root::default"]`, and reports
`exitCode: null` with `status: error` — the result schema enforces that combination for every
non-`exit` termination.

The Diagnostic sits at top level with `source.kind: environment`, which is what the registry fixes for
`VERIFY-SPAWN-ERROR`, `VERIFY-SIGNAL` and `VERIFY-TIMEOUT`; all three are `skip-binding`, and
[verify仕様 §6](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#6-command結果) places a binding
Diagnostic at top level in a single workspace.

| fixture | command file | termination | code |
|---|---|---|---|
| `SINGLE-057` | `bin/badformat` | `spawn_error` | `SPEC-VERIFY-COMMAND-001` |
| `SINGLE-058` | `bin/signal.sh` | `signal` | `SPEC-VERIFY-COMMAND-001` |
| `SINGLE-059` | `bin/hang.sh` | `timeout` | `SPEC-VERIFY-TIMEOUT-001` |

`bin/badformat` is a regular file carrying the executable bit whose content is neither ELF nor a
shebang script. [verify仕様 §5.1](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#51-実行fileと環境)
rejects a file that is not regular, absent, or not executable *before* spawning; this file passes all
three, and `execve` then fails with `ENOEXEC`. Because Core uses no shell, there is no fallback
interpretation. That is exactly the matrix's "実行bit付きだがOSが拒否する実行形式".

## The audit runs the command files itself

Each fixture's own command file is executed directly — never through Core — to confirm the input still
produces the reviewed cause: that `bin/badformat` raises an OS error on spawn, that `bin/signal.sh`
terminates with `SIGTERM`, and that `bin/hang.sh` survives a group-wide graceful termination and needs
a force kill. Without this the expectations would be assertions about a corpus nobody had run.

This found two real defects while the batch was being written, both in the fixture, not in the audit:

1. The first `bin/hang.sh` ran `sleep 60` in the foreground. A group `SIGTERM` killed the sleep, the
   shell's wait returned, and the script exited — so the fixture would never have required a force
   kill. The loop now tolerates a killed foreground sleep, and the pipe-holding child ignores `TERM`
   as well.
2. The audit signalled immediately after spawn, before the shell had installed its trap, so it was
   only proving that an unprotected startup can be killed. The script now prints a readiness line
   *after* installing the trap, and the audit waits for that line before signalling.

## `SINGLE-059` keeps its readiness line

Because the readiness line is real output, it is also the fixture's expected `stdoutExcerpt`
(`"hang-ready\n"`). That is worth more than an empty excerpt: the descendant keeps the inherited pipe
open forever, so the line can only appear in the result if Core drains the stream and closes its read
handle on the timeout state machine instead of waiting for EOF
([verify仕様 §5.2](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#52-timeoutと有限時間終了)).
`stdoutTruncated` stays `false` because the raw stream is far below 64 KiB.

The effective timeout is set to 1 second through `verify.timeoutSeconds`, the lowest the configuration
accepts, so the fixture stays fast while still exercising the state machine. That value is Digest
material, so `SINGLE-059` carries its own Context Digest, as do `SINGLE-057` and `SINGLE-058` through
their `argv` templates.

## Limits

- No Core has run. Gate B decides agreement with Core, including the requirement that the binding is
  finalised within 5 seconds of the timeout being reached.
- The audit demonstrates that a force kill is *necessary* for `bin/hang.sh`; it does not measure
  Core's own 2-second escalation schedule, which has no observable surface until Core exists.
- `ENOEXEC` is the reference environment's behaviour for a non-ELF, non-shebang executable file on
  Linux, which is the environment fixed for Step 0B. The fixture pins the observable outcome, a failed
  spawn, rather than the specific errno.
- `/bin/sh` is `dash` in the reference environment; the scripts use POSIX constructs only.
