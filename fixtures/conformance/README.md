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
138 of the 311 matrix fixtures, the independent federation golden Context Digest,
and per-fixture side-effect expectations are still outstanding. Missing fixtures are listed individually.
Static checks do not prove that a fixture has only one independent cause. Diagnostic mappings have a reviewed ledger:
see [Diagnostic review](diagnostic-review.md). The audit checks its integrity and source freshness, not natural-language semantics.

[Target vectors](targets/README.md) fix 18 kind/purpose combinations and seven graph cases. The audit compares four ordered
sets with a limited reference calculation and checks input-order invariance. This does not certify Core execution or bindings.

[Initial single-workspace fixtures](single/README.md) provide nine real inputs, manifests, complete expected JSON results,
and read-only before/after expectations. Two isolated setups are checked against each fixed before snapshot.
This validates preparation evidence, not Core execution or observed post-operation side effects.
The missing-cwd case requires an executable `/bin/true` on the Linux validation host; missing prerequisites fail the audit.

[EARS fixtures](single/ears-review.md) provide twelve syntax/ID/candidate/extension cases.
Their fixed REQ inputs, Frontmatter schema, full expected JSON, token positions, and two isolated setups are audited.
This does not implement or certify the Core Scanner/Parser.

[Document fixtures](single/document-review.md) add nine filename, required statement/heading, placement,
ignored style and invalid UTF-8 cases, with fixed preparation evidence. Fixed input bytes, complete expected JSON,
Frontmatter and side-effect schemas, and two isolated setups are audited. Skip/continue counts and the rejection
of repaired UTF-8 or additional causes are covered by regression checks. Core acceptance remains in Gate B.

[Trace fixtures](single/trace-review.md) add six strong-reference, relation-type, legacy refs, path and coverage cases,
with fixed preparation evidence. The audit verifies complete expected JSON, fixed input bytes, reviewed Frontmatter values,
read-only snapshots and two isolated setups, with mutation tests for missing or additional causes.

[Graph fixtures](single/graph-review.md) add four duplicate-document-ID and requires/refines/related self-cycle cases,
with fixed preparation evidence. Complete expectations, reviewed Frontmatter values and two isolated setups are checked;
mutation tests reject changed causes, duplicate diagnostics, renumber suggestions and side effects.

[Git fixtures](single/git-review.md) add five forbidden transition, new document, deletion, rename and approved-meaning cases,
with fixed preparation evidence. HEAD and index blobs and working-tree bytes are checked directly, alongside complete
expected results, read-only snapshots and two isolated setups. Mutation tests reject unintended staging or commits.

[Approved-REQ exemption fixtures](single/exempt-review.md) add five implements/tests/related/extension/prose-only changes,
bringing preparation to 50/311. Supporting files exist unchanged in HEAD; only the REQ changes in the worktree.
They use the Git fixture audit, with complete success expectations and mutation tests for additional causes.

[TASK scope fixtures](single/task-review.md) add three explicit/changed/full boundary cases.
[Git selection/impact fixtures](single/selection-review.md) add four direct-dependency, unborn and empty/unowned selection cases.
[Git environment fixtures](single/git-environment-review.md) add invalid-base and Git-absence cases, bringing preparation to 60/311.
The latter fix CLI error stream shape without matching human reason text and use null Git snapshots only for explicitly absent Git.

[Context failure fixtures](single/context-failure-review.md) add five missing-root, unfinished-task, superseded-root/dependency and duplicate-successor cases, bringing preparation to 65/311.
Complete non-success JSON, empty Bundle expectations, unborn Git snapshots and mutation tests are checked without running Core.

The `harness-input` directory contains infrastructure test inputs, not `SINGLE-*` or `MONO-*` acceptance fixtures.
`harness.py` builds isolated Git repositories and compares files, executable bits, symlink targets, and directories.
Snapshots exclude `.git`; self-tests compare Git status and index separately. Setup rejects parent traversal and
symlink ancestors. It never runs a Core operation. Callers must validate full acceptance manifests against the schema.

`process_helper.py` reproduces successful/nonzero exits, signal termination, timeout, and a descendant holding pipes.
`test_harness.py` bounds those tests and kills only the isolated process group it created. These tests demonstrate
helper/harness behavior, not the future Core process runner's acceptance.

Validation runtime: Linux/POSIX with Python 3.11+ and Git. The audit writes temporary fixture repositories only;
it does not update acceptance results or documentation automatically.

[CLI boundary fixtures](single/cli-boundary-review.md) add nine duplicate-option, empty-argument,
timeout-range/notation and report-syntax cases. That batch brought preparation to 116/311 fixtures.
The fourteen argument-error fixtures in that batch share the output contract and two isolated setup checks.

[Repeated expand fixtures](single/expand-repeat-review.md) add sorted distinct values and duplicate
removal, with two independent Digest references and two isolated setups. That batch brought preparation to 118/311.

[Missing selection fixtures](single/missing-selection-review.md) distinguish a missing context root
(failed/1 with a result) from a missing workspace (exit 4 without a result). That batch brought preparation to 120/311.

[Output format fixtures](single/output-format-review.md) add successful/failed check text output and
JSON with explicit report. That batch brought preparation to 123/311.

[BOM and Frontmatter fixtures](single/frontmatter-review.md) add eleven warning/skip-document cases.
That batch brought preparation to 134/311.

[Diagnostic control characters](single/terminal-control-review.md) fix the approved visible escaping rule.
That batch brought preparation to 135/311.

[Diagnostic ordering](single/diagnostic-order-review.md) fixes three independent same-condition errors.
That batch brought preparation to 136/311.

[Input limit fixtures](single/input-limit-review.md) add the 64 KiB configuration, 1 MiB SPEC Markdown,
32 KiB Frontmatter, statement-count and array-count cases, plus the unknown `.spec/` entry. Inputs are generated
from reviewed constants and measured again, so the audit rejects a fixture that crosses any other dimension.
That batch brought preparation to 143/311.

[Registry closure fixtures](single/registry-closure-review.md) complete matrix §6.9 with the reason-less
SHOULD warning, the missing `related` target, forbidden configuration YAML, the doctor configuration and
Git-absence cases, the missing workspace and the unsupported EARS-AI major. The doctor contract now fixes
the four `lostGuarantees` names. That batch brought preparation to 150/311.

[Scanner and position fixtures](single/scanner-review.md) add the sixteen §6.10 check cases: run-length code
spans, unknown escapes, unclosed quoted extension values, four candidate-suppression constructs, four
malformed IDs, misplaced reason fields, a code point column after multi-byte text and TAB, and the two
shared-cause primaries. The four `context` cases of that section remain outstanding.
That batch brought preparation to 166/311.

[Default display fixtures](single/presentation-review.md) add the omitted `--format` for check, verify and
doctor, the committed context revision and the Git-absent verify revision, a command with no output, and the
same condition on two verify targets. The summary line is re-derived from the JSON counterpart, and the
revision shape is observed in the isolated repository. Current preparation: 173/311; 138 remain.
