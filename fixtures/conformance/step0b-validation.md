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

The subsequent 2026-09-14 verify binding batch passed integrated checks and regression suites.
Two pinned-environment `uv run fixtures/validate_step0b.py` runs produced byte-identical reports,
with no check errors and exit code 1 for pending Gate A evidence. Prepared fixtures: 86/311; missing: 225.
SINGLE-063 and SINGLE-064 use a two-root workspace so two targets request one command name: each target
reports its own Digest while a single command entity runs the deduplicated shared test path once.
SINGLE-064 keeps the blocked target at bindingRefs [] and excludes its statement from the executed
command's covers. SINGLE-065 pins that a command template without {tests} is executed once and never
receives the paths. Reference B's strong-edge guard now fires only for edges touching the closure being
computed, because a workspace may legitimately hold several independent roots.
SINGLE-066 and SINGLE-068 are deferred to their own step; both need closure behavior this reference does
not yet derive. Expectation choices and their limits are recorded in
[the verify binding review](single/verify-binding-review.md).
These are preparation checks, not observed Core behavior or complete fresh-checkout Gate A certification.

The subsequent 2026-09-14 verify process batch passed integrated checks and regression suites.
Two pinned-environment `uv run fixtures/validate_step0b.py` runs produced byte-identical reports,
with no check errors and exit code 1 for pending Gate A evidence. Prepared fixtures: 89/311; missing: 222.
SINGLE-057, 058 and 059 all fail after the pre-checks pass, so each records a commands[] entry with a
null exit code and error status while keeping bindingRefs, and each Diagnostic sits at top level with an
environment source, matching the registry's skip-binding classification.
The audit runs each fixture's own command file directly, never through Core, to confirm the input still
produces the reviewed cause. That found two defects in the fixtures themselves: the first hang script
exited on a group SIGTERM because its foreground sleep was killed, and the audit was signalling before
the shell had installed its trap. The script now tolerates a killed foreground sleep, its pipe-holding
child ignores TERM, and it prints a readiness line after installing the trap which the audit waits for.
That readiness line is also the expected stdoutExcerpt of SINGLE-059, which can only appear if the
stream is drained and the read handle closed rather than waiting for an EOF that never comes.
Expectation choices and their limits are recorded in
[the verify process review](single/verify-process-review.md).
These are preparation checks, not observed Core behavior or complete fresh-checkout Gate A certification.

The subsequent 2026-09-14 verify output and document-binding batch passed integrated checks and
regression suites. Two pinned-environment `uv run fixtures/validate_step0b.py` runs produced
byte-identical reports, with no check errors and exit code 1 for pending Gate A evidence.
Prepared fixtures: 92/311; missing: 219.
SINGLE-069-01/02 fix a 70,400-byte stream of 64-byte lines whose first and last lines are marked
differently, so the committed 64 KiB excerpt provably holds the tail marker and not the head marker;
the audit runs the command file and compares the produced tail byte for byte. Both share one Context
Digest because the script body is not Digest material, while their exit codes differ.
SINGLE-066 targets a TECH with no normative statement and a document-level test, reporting statements []
together with a bindingRefs entry and covers [TECH-001], which the Frontmatter contract permits only for
such a TECH.
SINGLE-068 is still absent on purpose: whether the documents owning a root TASK's addresses targets are
part of the verify Context is not settled by the normative documents, and a fixture must not enter the
executable set ahead of its contract. Expectation choices, the reasoning and the reported gap are
recorded in [the verify output review](single/verify-output-review.md).
These are preparation checks, not observed Core behavior or complete fresh-checkout Gate A certification.

The subsequent 2026-09-14 done-TASK root batch passed integrated checks and regression suites.
Two pinned-environment `uv run fixtures/validate_step0b.py` runs produced byte-identical reports,
with no check errors and exit code 1 for pending Gate A evidence. Prepared fixtures: 93/311; missing: 218.
This completes matrix §6.6 verify, all 16 rows.
SINGLE-068 required settling a contract first: 関係・トレースモデル §6.3 now states that a TASK root brings
its addresses targets and their owning documents into contextDocuments, that the interpret closure rules
then apply from those documents, and that unlike implement the root TASK's requires closure is excluded.
No decision changed. The target-expansion reference calculation already implemented that reading, so all
25 expected target sets are unchanged, and no Diagnostic condition is added because an unresolvable
addresses target is already SPEC-RELATION-MISSING-001. The audit detected the edit by itself through the
source hashes pinned in diagnostic-coverage.json and targets/cases.json, and those were re-pinned only
after the re-review recorded in diagnostic-review.md.
The fixture pairs with SINGLE-067: a done root is re-verifiable with its own Digest and binding, while a
cancelled root is blocked with neither. AC-02 is deliberately unaddressed, so neither its statement nor
its test may enter the binding. Expectation choices and their limits are recorded in
[the done TASK root review](single/verify-task-root-review.md).
These are preparation checks, not observed Core behavior or complete fresh-checkout Gate A certification.

The subsequent 2026-09-14 report-absence and argument-error batch passed integrated checks and
regression suites. Two pinned-environment `uv run fixtures/validate_step0b.py` runs produced
byte-identical reports, with no check errors and exit code 1 for pending Gate A evidence.
Prepared fixtures: 102/311; missing: 209.
SINGLE-070-01/02/03/04 cover both operations on both outcomes without --report. Each corpus already
holds .spec/reports/existing.json, because a corpus without one could only show that no new file was
created and never that an existing report survived; the audit refuses a fixture whose snapshot lacks it.
The two verify cases reuse the reviewed results of SINGLE-055 and SINGLE-056 directly, since the added
report file is not SPEC material and the Context is unchanged.
SINGLE-073-01/02 and SINGLE-074-01/02/03 carry no status and no result file, which the manifest contract
allows only when no common result exists. SINGLE-074-03 is a lexical ID error rather than an absent ID,
which the CLI contract separates from CTX-ROOT-MISSING-001.
The stderr contract was hard-wired to check and is now operation-aware, so all five fixtures and the
earlier Git-environment one share one statement of it; the audit exercises it per operation and rejects
a wrong prefix, an empty reason, a second line and a non-4 exit code.
Expectation choices and their limits are recorded in
[the report absence review](single/report-absence-review.md).
These are preparation checks, not observed Core behavior or complete fresh-checkout Gate A certification.

The subsequent 2026-09-14 explicit-report batch passed integrated checks and regression suites.
Two pinned-environment `uv run fixtures/validate_step0b.py` runs produced byte-identical reports,
with no check errors and exit code 1 for pending Gate A evidence. Prepared fixtures: 107/311; missing: 204.
side-effects.schema.json now takes policy explicit-report with a report object, and the schema pairs the
two so that explicit-report requires report and read-only forbids it. Report file names carry a
generation time and sequence which the common normalizer excludes, so before and after describe only
pre-existing paths, all of which must be unchanged, and the report object carries the delta.
The audit requires the committed name pattern to accept a well-formed name and reject a missing
timestamp, a zero sequence, another operation and a leftover .tmp suffix.
Each SINGLE-071-* corpus keeps a pre-existing report, because creating into an empty directory would not
distinguish exclusive creation from replacement. The four cases reuse the reviewed results of the
SINGLE-070-* pair, since saving a report does not change the computed result.
SINGLE-072 is based on the failing check rather than the passing one, so that "the original result
survives" is not vacuous: the result body is unchanged, SPEC-RELATION-MISSING-001 survives,
SPEC-REPORT-WRITE-001 is appended and the status rises from failed to error. Its destination is blocked
by a regular file at .spec/reports rather than by a directory mode, because Git does not record
directory permissions and a fresh checkout would not restore one.
Expectation choices and their limits are recorded in
[the explicit-report review](single/report-write-review.md).
These are preparation checks, not observed Core behavior or complete fresh-checkout Gate A certification.

The subsequent 2026-09-14 CLI boundary batch passed integrated checks and regression suites.
Two pinned-environment `uv run fixtures/validate_step0b.py` runs produced byte-identical reports,
with no check errors and exit code 1 for pending Gate A evidence. Prepared fixtures: 116/311; missing: 195.
SINGLE-127-01/02/05/06/07/08/09/10/11 cover duplicate options, empty arguments, a missing context root,
timeout boundaries/notation and arbitrary report-path syntax. All nine carry exit 4 without a result
body or report; their fixed before/after snapshots prohibit writes in the repository and isolated
HOME/cache/TMPDIR, and preserve Git status/index. Each setup was reproduced twice.
Mutation tests reject removal of invalid arguments, replacement with valid timeout values and a new
out.json path. The existing operation-aware stderr checks remain shared by all fourteen CLI cases.
Expectation choices and limits are recorded in [the CLI boundary review](single/cli-boundary-review.md).
Host: Linux 6.18.33.2-microsoft-standard-WSL2, x86_64, CPython 3.14.4, Git 2.53.0;
validator dependencies remain pinned in the entry script.
These are preparation checks, not observed Core behavior, CPython 3.11 acceptance or complete
fresh-checkout Gate A certification. Federation golden Digest and remaining fixture evidence stay pending.

The subsequent 2026-09-14 repeated-expand batch passed integrated checks and regression suites.
The first run used `uv run fixtures/validate_step0b.py`; the second invoked the same cached, pinned
validator environment's Python directly with `-B`. Both audit reports were byte-identical, with no
check errors and exit 1 only for pending Gate A evidence. Prepared fixtures: 118/311; missing: 193.
SINGLE-127-03 supplies TECH-001 then REQ-001 and expects sorted expansion IDs; SINGLE-127-04 repeats
TECH-001 and expects one ID. Complete result bodies retain the golden resolution, coverage and Digest.
Two independent references agree with committed Canonical JSON, and both isolated setups per fixture
agree with fixed read-only snapshots. Mutation tests reject unsorted/duplicate expansion IDs and a
missing repeated option. See [the repeated-expand review](single/expand-repeat-review.md).
Validator runtime: CPython 3.14.6; jsonschema 4.23.0, attrs 26.1.0, jsonschema-specifications 2025.9.1,
referencing 0.37.0, rpds-py 2026.6.3, typing-extensions 4.13.2; Linux/WSL2, Git 2.53.0.
Core was not executed. The full fresh-checkout Gate A check, remaining fixture evidence and federation
golden Digest remain pending.

The subsequent 2026-09-14 missing-selection batch passed integrated checks and regression suites.
Two runs of fixtures/validate_step0b.py through the cached pinned validator Python with -B produced
byte-identical reports, with no check errors and exit 1 for pending Gate A evidence.
Prepared fixtures: 120/311; missing: 191. Each new fixture passed two isolated setup comparisons.
SINGLE-127-13 preserves the requested missing root and emits failed/1 with an incomplete, empty Context
and CTX-ROOT-MISSING-001. SINGLE-127-14 selects a syntactically valid but absent workspace and emits
exit 4 without a common result. Mutation tests reject changing the workspace to root, confusing the
exit/status contracts, making the failed Context complete and changing its Diagnostic source.
See [the missing-selection review](single/missing-selection-review.md) for input and expectation choices.
Runtime: the same pinned CPython 3.14.6 validator environment recorded above, Linux/WSL2, Git 2.53.0.
Core was not executed. Remaining fixtures, federation golden Digest and full fresh-checkout Gate A
repeatability remain pending; these runs certify preparation only.

The subsequent 2026-09-14 output-format batch passed integrated checks and regression suites.
Two runs of fixtures/validate_step0b.py through the cached pinned validator Python with -B produced
byte-identical reports, with no check errors and exit 1 for pending Gate A evidence.
Prepared fixtures: 123/311; missing: 188. Each new fixture passed two isolated setup comparisons.
SINGLE-075-01/02 retain the complete JSON counterpart while selecting text output. Their fixed UTF-8
text preserves status, scope, document count and Diagnostic count; missing source line/column fields
remain empty. Duration-only byte normalization rejects changes to status/counts/spacing/newlines,
non-ASCII digits and fractional duration spelling. Mutation tests reject altered JSON, text counts
and side-effect expectations. SINGLE-127-12 explicitly combines --format json and --report, preserving
existing files and permitting exactly one report with no temporary-file residue.
See [the output-format review](single/output-format-review.md) for expectation choices and limits.
Runtime: the same pinned CPython 3.14.6 validator environment recorded above, Linux/WSL2, Git 2.53.0.
Core was not executed; actual text rendering, report contents and side effects remain Gate B work.
Remaining fixtures, federation golden Digest and full fresh-checkout Gate A repeatability stay pending.

The subsequent 2026-09-14 BOM/Frontmatter batch passed integrated checks and regression suites.
Two runs through the cached pinned validator Python with -B produced byte-identical audit reports,
with no check errors and exit 1 for pending Gate A evidence. Prepared fixtures: 134/311; missing: 177.
SINGLE-081/082/084/085 continue with one checked document/statement after their single warning.
SINGLE-086/087-01..05/088 skip the malformed document with one Schema Diagnostic and zero counts.
Each fixture passed two isolated setup comparisons. Mutation tests reject repaired input bytes,
wrong counts/status/codes, removed or duplicated Diagnostics and new cache side effects.
See [the BOM/Frontmatter review](single/frontmatter-review.md) for input and expectation choices.
Runtime: the same pinned CPython 3.14.6 validator environment recorded above, Linux/WSL2, Git 2.53.0.
No YAML loader or Core was implemented/executed. Actual continuation, rejection and side effects are
Gate B work. Remaining fixtures, federation golden Digest and full fresh-checkout Gate A stay pending.

The Diagnostic-control batch passed two byte-identical integrated audits in the pinned CPython 3.14.6
environment. All check errors were empty; exit 1 denotes pending Gate A evidence. Prepared: 135/311;
missing: 176. SINGLE-076 passed two isolated setups with a control-character path generated by rename.
The approved field escaping rule was added to the result contract. JSON retains original field values;
text alone uses lowercase four-digit escapes. Regression checks cover the full C0/DEL/C1 ranges,
LF/TAB, adjacent visible characters and literal backslashes. Diagnostic semantic conditions are unchanged;
the reviewed source hash was refreshed. See the terminal-control review for scope and evidence.
No Core was executed. Remaining fixture evidence, federation golden and fresh-checkout Gate A stay pending.

SINGLE-077 passed two byte-identical integrated audits in the pinned CPython 3.14.6 environment.
All check errors were empty; exit 1 denotes pending Gate A evidence. Prepared: 136/311; missing: 175.
Three TECH documents independently reference missing TECH-999. JSON/text retain all three Diagnostics
in path order and count all five documents/two statements. Both isolated setups match the fixed snapshot.
Regression checks reject reversed/missing Diagnostics and a reduced document count. See the diagnostic-order
review for scope. Core execution, remaining fixtures, federation golden and full Gate A remain pending.
