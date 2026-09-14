# verify binding fixture review

Covers `SINGLE-063`, `SINGLE-064` and `SINGLE-065` from
[適合fixture仕様 §6.6](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#66-verify).
`SINGLE-066` and `SINGLE-068` are deliberately not in this batch; see "Deferred" below.
These are reviewed expectations, not observed Core behaviour.

## A two-root workspace

`SINGLE-063` and `SINGLE-064` need two targets that request the same command name, so the corpus
holds two independent chains — `REQ-001 ← TECH-001` and `REQ-002 ← TECH-002` — in one workspace.
Both TECH documents declare the same test path `tests/test_shared.py` under the same command name.

[verify仕様 §4](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#4-処理) resolves a separate
`purpose=verify` Context per target, then unions the `bindingRefs` and deduplicates the test paths per
`(workspaceId, commandName)`. So the expectation is two `targetResults[]` with **different** Digests
and one `commands[]` entry whose `tests` holds the shared path once.

- `SINGLE-063`: both targets pass. `covers` lists both statements; `argv` expands the shared path once.
- `SINGLE-064`: `TECH-001` declares no `tests`, so `REQ-001:AC-01` is an untested MUST and that target
  is `blocked` with `bindingRefs: []`, while `REQ-002` still executes. `covers` names only
  `REQ-002:AC-01`: the command must not claim statements from a target that never reached execution.
  The top-level status is the worst of the two, `blocked`/2.

## `{tests}` is a placeholder, not an append

`SINGLE-065` reuses the Digest corpus with the command template reduced to `["/bin/true"]`.
[verify仕様 §5](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#5-command実行) runs argv once
regardless of path count when the placeholder is absent, so `argv` stays `["/bin/true"]` while `tests`
still lists both declared paths. A regression test asserts no test path leaks into `argv`.
The `argv` template is Digest material, so this fixture carries its own Digest rather than the golden.

## Invariants the audit enforces

`check_sharing` rejects a result where the shared binding is duplicated into more than one command
entity, where test paths are not deduplicated, where a deduplicated path is expanded more than once,
where two targets report the same Digest, or where a non-success target still requests a binding.
These are the properties the matrix rows name, so they are checked as properties and not only as
literal field equality.

## Reference B change

B previously rejected any strong edge it could not account for, which assumed a single-root corpus.
With two independent roots in one workspace, an edge belonging to the *other* Context is legitimate.
The guard now fires only for an edge that touches the closure being computed — its source, its target,
or the document owning a target statement is in the closure — and still refuses anything unaccounted
inside it. Without this, B could not compute either Digest for `SINGLE-063`.

## Deferred

`SINGLE-066` (document-level tests on a TECH with no normative statements) and `SINGLE-068` (done TASK
root) are held back. Both need closure behaviour this reference does not yet derive: a forward
`refines` edge from the root for `SINGLE-066`, and the Context contents of a TASK root whose target
statements live in another document for `SINGLE-068`. Rather than invent those shapes to fit a
deadline, they get their own step where the resolver questions can be worked through and recorded.

## Limits

- No Core has run. Gate B decides agreement with Core.
- `SINGLE-064` places `CTX-COVERAGE-TEST-001` on the blocked target, following the registry's
  `skip-target` continuation unit, consistent with `SINGLE-060`.
- The deduplicated path order is the sorted declaration order; with one shared path this fixture does
  not discriminate between ordering rules that agree on a single element.
