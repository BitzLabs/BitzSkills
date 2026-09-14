# Step 0B validation progress

- Date: 2026-09-14
- Command: `uv run fixtures/validate_step0b.py`
- Runtime: CPython 3.14.6, Linux/POSIX, uv 0.11.32; validator versions pinned in script metadata.
- Gate A: `Blocked`; command exit code: 1 (outstanding evidence).

| Check | Evidence |
|---|---|
| Public JSON | 10 examples passed: operation results, Diagnostic and fixture manifest |
| Other JSON examples | 5 Semantic IR / Digest material examples parsed; not certified by the result Schema |
| EBNF references | 33 definitions plus 3 explicitly prose-defined lexical sets; no unresolved reference |
| Diagnostic review (updated 2026-09-08) | 119 conditions mapped to 17 source documents; three open issues resolved; ledger and regression checks passed |
| Matrix inventory | 311 IDs, no duplicate or family/suffix collision; 65 prepared, 246 real fixtures missing |
| EARS fixtures | SINGLE-007, 008, 009-01/02/03, 010-01/02, 011, 012-01/02/03, 013: fixed REQ bytes, Frontmatter Schema, complete expected results, Unicode token/end-of-line positions and two isolated setups checked; position/severity/code/count/input corruption rejected |
| Document fixtures (2026-09-11) | SINGLE-014, 016, 017-01/02/03, 018-01/02/03, 019: fixed input bytes including invalid UTF-8, complete expected JSON, Frontmatter and side-effect schemas, and two isolated setups each passed; skip/continue counts, Diagnostic, report, side-effect and input corruption rejected |
| Trace fixtures (2026-09-11) | SINGLE-020, 021, 023, 024, 025, 026: fixed YAML/decoded Frontmatter pairs, complete expected JSON, read-only snapshots and two isolated setups each passed; duplicate diagnostics, wrong primary/count/severity/source, input repair and additional causes rejected |
| Graph fixtures (2026-09-11) | SINGLE-015, 022-01/02/03: duplicate TECH IDs and self-referential requires/refines/related, fixed complete results and read-only snapshots; two isolated setups and mutation tests passed |
| Git fixtures (2026-09-11) | SINGLE-027–031: fixed HEAD/index/worktree contents, transitions/new/deleted/renamed/approved-meaning cases, complete JSON and read-only snapshots; two isolated setups and mutation tests passed |
| Approved-REQ exemptions (2026-09-11) | SINGLE-032-01–05: implements/tests/related/x-field/prose-only changes, unchanged supporting files, complete success JSON, two isolated HEAD/index/worktree comparisons and mutation tests passed |
| TASK scopes (2026-09-14) | SINGLE-034, 035-01/02: identical two-path unstaged changes, explicit TASK segment-boundary failure versus changed/full success; complete JSON, HEAD/index/worktree and read-only snapshots checked in two isolated setups; corrupted scope, source, selection counts, permissions and staging rejected |
| Git selection/impact (2026-09-14) | SINGLE-033, 039–041: direct strong dependency warning with weak/transitive controls, unborn full fallback, clean empty selection, staged unowned code and untracked test; complete JSON, HEAD/index/worktree and read-only snapshots checked in two isolated setups; corrupted diagnostics, revision, counts, ownership and Git state rejected |
| Git environment (2026-09-14) | SINGLE-036–038: invalid explicit base with --report preserves existing report and emits no result; Git-absent full/selected results use null revision and null Git snapshots; two isolated setups, CLI stream assertions and mutation tests passed |
| Context failures (2026-09-14) | SINGLE-050, 051, 052-01/02, 053: missing root, unfinished predecessor TASK, superseded root/dependency and multiple successors; complete non-success JSON, null Digest and unborn revision, empty Bundle/coverage, two isolated setups and mutation tests passed |
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
Read-only before/after expectations are fixed for the nine introduction/config, twelve EARS, nine document, six trace, four graph, ten Git/approved-exemption three TASK-scope and four Git selection/impact and three Git environment and five Context failure cases; the remaining cases still need expectations.
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

The 2026-09-14 TASK batch passed integrated checks and regression suites; two full audit reports matched byte for byte.
Both runs used the pinned Step 0B uv environment Python directly (`python -B fixtures/validate_step0b.py`)
and returned exit code 1 solely for pending Gate A evidence. Prepared fixtures: 53/311; missing: 258.
This certifies working-tree preparation repeatability, not Core behavior or the fresh-checkout Gate A condition.
Expectation choices are recorded in [the TASK fixture review](single/task-review.md).

The subsequent 2026-09-14 Git selection/impact batch passed integrated checks and regression suites.
Both pinned-environment `python -B fixtures/validate_step0b.py` runs produced byte-identical reports,
with no check errors and exit code 1 for pending Gate A evidence. Prepared fixtures: 57/311; missing: 254.
HEAD/index/worktree comparisons include the empty unborn index and the staged-code/untracked-test split.
Expectation choices are recorded in [the Git selection/impact review](single/selection-review.md).
This remains working-tree preparation evidence; Core behavior and fresh-checkout Gate A certification are pending.

The subsequent 2026-09-14 Git environment batch passed integrated checks and regression suites.
Two pinned-environment `python -B fixtures/validate_step0b.py` runs produced byte-identical reports,
with no check errors and exit code 1 for pending Gate A evidence. Prepared fixtures: 60/311; missing: 251.
The new cases fix invalid-base stream shape and report preservation, and distinguish absent Git from an empty Git status.
SINGLE-040/041 now explicitly pass --base HEAD as required by the fixture contract; expected results and snapshots are unchanged.
Matrix regression checks reject omitted required base or a base supplied to a Git-absent case.
Expectation choices are recorded in [the Git environment review](single/git-environment-review.md).
These are preparation checks, not observed Core behavior or complete fresh-checkout Gate A certification.

The subsequent 2026-09-14 Context failure batch passed integrated checks and regression suites.
Two pinned-environment `python -B fixtures/validate_step0b.py` runs produced byte-identical reports,
with no check errors and exit code 1 for pending Gate A evidence. Prepared fixtures: 65/311; missing: 246.
The five cases fix requested roots, exact failure diagnostics, null Digest and empty non-success Bundle data.
Unborn repository checks and mutations reject invented commits, staged inputs, implicit successor replacement and partial success.
Expectation choices are recorded in [the Context failure review](single/context-failure-review.md).
These are preparation checks, not observed Core behavior or complete fresh-checkout Gate A certification.

The subsequent 2026-09-14 Context Digest batch passed integrated checks and regression suites.
Two pinned-environment `uv run fixtures/validate_step0b.py` runs produced byte-identical reports,
with no check errors and exit code 1 for pending Gate A evidence. Prepared fixtures: 71/311; missing: 240.
SINGLE-042 owns the single-workspace golden Canonical JSON and Digest; SINGLE-043-01/02 and SINGLE-045
are byte-identical to it, and SINGLE-044-01/02 differ from it and from each other.
Two independently written reference computations agree: A states the digest input as reviewed literals,
B rebuilds it from the fixture's own tree with a separate reader and a separate RFC 8785 emitter.
Writing B independently found and fixed a defect in B: it accepted `[MUST] [REASON]`, which the EBNF
allows only for `[SHOULD]`. Expectation choices and their limits are recorded in
[the Digest fixture review](single/digest-review.md).
The federation golden (MONO-002-01) is still missing, so the federation half of the Gate A Digest
condition remains open. These are preparation checks, not observed Core behavior or complete
fresh-checkout Gate A certification.

The subsequent 2026-09-14 non-success Context batch passed integrated checks and regression suites.
Two pinned-environment `uv run fixtures/validate_step0b.py` runs produced byte-identical reports,
with no check errors and exit code 1 for pending Gate A evidence. Prepared fixtures: 77/311; missing: 234.
This completes the context and Digest section of the matrix (SINGLE-042 through SINGLE-054).
Two rules are applied across the group and enforced by the audit: a non-success Context delivers no
Bundle material, and contextDigest is non-null exactly when complete resolution held.
SINGLE-046 and SINGLE-047 report the Digest committed by SINGLE-042 rather than a separate constant.
SINGLE-049 crosses the fixed 1 MiB presentation hard limit with 1,071,063 bytes of body text while its
standard presentation and closure stay inside the configured maxima.
SINGLE-054 has its own implement-purpose digest input, which records no binding and adds the
addressing TASK. Reference B gained two fixes found by writing it against these corpora: it now reads
context.maxDocuments/maxBytes from configuration instead of assuming defaults, and follows the
transitive refinement chain. Expectation choices and their limits are recorded in
[the non-success Context review](single/context-limit-review.md).
These are preparation checks, not observed Core behavior or complete fresh-checkout Gate A certification.

The subsequent 2026-09-14 verify batch passed integrated checks and regression suites.
Two pinned-environment `uv run fixtures/validate_step0b.py` runs produced byte-identical reports,
with no check errors and exit code 1 for pending Gate A evidence. Prepared fixtures: 83/311; missing: 228.
SINGLE-055/056 execute a command and SINGLE-060/061/062/067 stop before any spawn.
Unlike the Context fixtures these stage their inputs, because verify blocks startup on a configuration
untracked in the index; a base commit is not usable since verify has no --base, so the repository stays
unborn with a populated index and revision is null. The audit reads the index back for every case.
SINGLE-055 reports the Digest committed by SINGLE-042; the audit enforces that a target Digest is
present exactly where the Context still resolved, and that bindingRefs and commands[] describe the
same executions. Diagnostic placement follows the registry continuation unit: skip-target conditions
stay on the target, and the stop-operation empty-target condition is top level.
Expectation choices and their limits are recorded in [the verify review](single/verify-review.md).
These are preparation checks, not observed Core behavior or complete fresh-checkout Gate A certification.
