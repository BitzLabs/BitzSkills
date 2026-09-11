# Step 0B validation progress

- Date: 2026-09-11
- Command: `uv run fixtures/validate_step0b.py`
- Runtime: CPython 3.14.6, Linux/POSIX, uv 0.11.32; validator versions pinned in script metadata.
- Gate A: `Blocked`; command exit code: 1 (outstanding evidence).

| Check | Evidence |
|---|---|
| Public JSON | 10 examples passed: operation results, Diagnostic and fixture manifest |
| Other JSON examples | 5 Semantic IR / Digest material examples parsed; not certified by the result Schema |
| EBNF references | 33 definitions plus 3 explicitly prose-defined lexical sets; no unresolved reference |
| Diagnostic review (updated 2026-09-08) | 119 conditions mapped to 17 source documents; three open issues resolved; ledger and regression checks passed |
| Matrix inventory | 311 IDs, no duplicate or family/suffix collision; 50 prepared, 261 real fixtures missing |
| EARS fixtures | SINGLE-007, 008, 009-01/02/03, 010-01/02, 011, 012-01/02/03, 013: fixed REQ bytes, Frontmatter Schema, complete expected results, Unicode token/end-of-line positions and two isolated setups checked; position/severity/code/count/input corruption rejected |
| Document fixtures (2026-09-11) | SINGLE-014, 016, 017-01/02/03, 018-01/02/03, 019: fixed input bytes including invalid UTF-8, complete expected JSON, Frontmatter and side-effect schemas, and two isolated setups each passed; skip/continue counts, Diagnostic, report, side-effect and input corruption rejected |
| Trace fixtures (2026-09-11) | SINGLE-020, 021, 023, 024, 025, 026: fixed YAML/decoded Frontmatter pairs, complete expected JSON, read-only snapshots and two isolated setups each passed; duplicate diagnostics, wrong primary/count/severity/source, input repair and additional causes rejected |
| Graph fixtures (2026-09-11) | SINGLE-015, 022-01/02/03: duplicate TECH IDs and self-referential requires/refines/related, fixed complete results and read-only snapshots; two isolated setups and mutation tests passed |
| Git fixtures (2026-09-11) | SINGLE-027–031: fixed HEAD/index/worktree contents, transitions/new/deleted/renamed/approved-meaning cases, complete JSON and read-only snapshots; two isolated setups and mutation tests passed |
| Approved-REQ exemptions (2026-09-11) | SINGLE-032-01–05: implements/tests/related/x-field/prose-only changes, unchanged supporting files, complete success JSON, two isolated HEAD/index/worktree comparisons and mutation tests passed |
| Initial fixtures | SINGLE-001, 002, 003, 004-01/02, 005-01/02, 006-01/02: manifest/result/side-effect schemas and reviewed input checks passed; two isolated setups each matched fixed before snapshots |
| Command preconditions | Absent explicit executable / absent cwd isolated; /bin/true executable prerequisite checked without running commands; extra or missing causes rejected by regression tests |
| Target vectors (2026-09-08) | 18 basic combinations + 7 supplementary cases; four ordered sets, input-order invariance and rejection regression checks passed |
| Relative links | 218 references in current contracts and accepted ADRs; no missing target/anchor |
| Git infrastructure | unborn, clean, worktree, staged, rename, delete, create; two identical setups per vector |
| Snapshot comparison | Content, executable bit, symlink target changes detected; unsafe path traversal rejected |
| Process helpers | Exit 0/7, SIGTERM, timeout, descendant pipe holding; isolated process groups cleaned up within bounded tests |
| Audit regression checks | Invalid public result and unknown grammar reference rejected; Semantic IR correctly classified; missing fixtures detected; initial result/status/key/argv/recovery and snapshot mutations rejected |
| Step 0-P | Passed again via the integrated command |

The Git and process vectors are infrastructure tests, not conformance fixtures or Core acceptance results.
Read-only before/after expectations are fixed for the nine introduction/config, twelve EARS, nine document, six trace, four graph and ten Git/approved-exemption cases; the remaining cases still need expectations.
The initial fixtures have not run Core. Their after snapshots are expectations, not observed Core side effects.
Exact doctor check names and Diagnostic strings chosen for this batch are recorded in [the initial fixture review](single/README.md).
Structural registry and matrix checks cannot prove semantic coverage or single-cause isolation. Diagnostic semantic decisions are
recorded in [the reviewed ledger](diagnostic-review.md); the validator detects missing mappings and changed source documents.
Independently computed golden Context Digests, complete acceptance inputs/results,
and a complete fresh-checkout Gate A run remain pending. No Gate A approval or Core implementation is included.

The 2026-09-11 run used the pinned Step 0B uv environment Python directly (`python -B fixtures/validate_step0b.py`),
following the initial `uv run` baseline. The integrated audit and regression suites reported no errors.
Two full audit reports matched byte for byte; both returned exit code 1 for the outstanding evidence.
This is working-tree repeatability, not the pending fresh-checkout Gate A certification.
Document expectation choices are recorded in [the document fixture review](single/document-review.md).

The subsequent six-case trace batch passed the integrated audit and regression suites, with two byte-identical reports.
Document fixtures SINGLE-017-02 and SINGLE-018-01 had surplus trailing blank lines removed; fixed inputs and snapshots were refreshed.
Trace expectation choices are recorded in [the trace fixture review](single/trace-review.md).

The subsequent four-case graph batch passed integrated checks and regression suites; two full audit reports matched byte for byte.
Graph expectation choices and their limits are recorded in [the graph fixture review](single/graph-review.md).
Working-tree repeatability does not certify the pending fresh-checkout Gate A condition.

The subsequent five-case Git batch passed integrated checks and regression suites; two full audit reports matched byte for byte.
HEAD and index blobs were checked directly against fixed base/current content in addition to snapshots.
Git expectation choices are recorded in [the Git fixture review](single/git-review.md).

The subsequent five-case approved-exemption batch passed integrated checks and regression suites; two full audit reports matched byte for byte.
The Git audit now prepares ten cases, with unchanged supporting inputs checked in HEAD/index/worktree.
Expectation choices are recorded in [the approved-exemption review](single/exempt-review.md).
