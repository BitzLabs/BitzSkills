# Step 0B conformance preparation

Run from the repository root:

```text
uv run fixtures/validate_step0b.py
```

The command audits public result/Diagnostic/manifest JSON examples, schema structure, EBNF references,
registry structure, matrix inventory, and relative links in current design contracts and accepted ADRs.
It also executes Step 0-P validation and the fixture infrastructure self-tests.
Pinned dependencies are declared in the script; the first run requires package download access.

Exit 0 means Gate A is allowed; exit 1 means errors or outstanding evidence remain. Currently exit 1 is expected:
290 of the 311 matrix fixtures, independent golden Context Digests,
and per-fixture side-effect expectations are still outstanding. Missing fixtures are listed individually.
Static checks do not prove that a fixture has only one independent cause. Diagnostic mappings have a reviewed ledger:
see [Diagnostic review](diagnostic-review.md). The audit checks its integrity and source freshness, not natural-language semantics.

[Target vectors](targets/README.md) fix 18 kind/purpose combinations and seven graph cases. The audit compares four ordered
sets with a limited reference calculation and checks input-order invariance. This does not certify Core execution or bindings.

[Initial single-workspace fixtures](single/README.md) provide nine real inputs, manifests, complete expected JSON results,
and read-only before/after expectations. Two isolated setups are checked against each fixed before snapshot.
This validates preparation evidence, not Core execution or observed post-operation side effects.
The missing-cwd case requires an executable `/bin/true` on the Linux validation host; missing prerequisites fail the audit.

[EARS fixtures](single/ears-review.md) provide twelve syntax/ID/candidate/extension cases, bringing preparation to 21/311.
Their fixed REQ inputs, Frontmatter schema, full expected JSON, token positions, and two isolated setups are audited.
This does not implement or certify the Core Scanner/Parser.

The `harness-input` directory contains infrastructure test inputs, not `SINGLE-*` or `MONO-*` acceptance fixtures.
`harness.py` builds isolated Git repositories and compares files, executable bits, symlink targets, and directories.
Snapshots exclude `.git`; self-tests compare Git status and index separately. Setup rejects parent traversal and
symlink ancestors. It never runs a Core operation. Callers must validate full acceptance manifests against the schema.

`process_helper.py` reproduces successful/nonzero exits, signal termination, timeout, and a descendant holding pipes.
`test_harness.py` bounds those tests and kills only the isolated process group it created. These tests demonstrate
helper/harness behavior, not the future Core process runner's acceptance.

Validation runtime: Linux/POSIX with Python 3.11+ and Git. The audit writes temporary fixture repositories only;
it does not update acceptance results or documentation automatically.
