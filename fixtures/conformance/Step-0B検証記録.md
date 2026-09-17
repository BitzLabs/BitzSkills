# Step 0B validation progress

- Date: 2026-09-17（下表は2026-09-14時点の構成。以後の追加は末尾の日付節を参照）
- Command: `uv run fixtures/validate_step0b.py`
- Runtime: CPython 3.14.6, Linux/POSIX, uv 0.11.32; validator versions pinned in script metadata.
- Gate A: `Blocked`; command exit code: 1 (outstanding evidence).

| Check | Evidence |
|---|---|
| Public JSON | 10 examples passed: operation results, Diagnostic and fixture manifest |
| Other JSON examples | 5 Semantic IR / Digest material examples parsed; not certified by the result Schema |
| EBNF references | 33 definitions plus 3 explicitly prose-defined lexical sets; no unresolved reference |
| Diagnostic review (updated 2026-09-08) | 119 conditions mapped to 17 source documents; three open issues resolved; ledger and regression checks passed |
| Matrix inventory | 310 IDs（2026-09-17時点）、重複とfamily／suffix衝突なし。準備済み250件、未作成60件（連合のみ） |
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
| Relative links | 230 references in current contracts and accepted ADRs（2026-09-17時点）; no missing target/anchor |
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
recorded in [the reviewed ledger](Diagnostic意味網羅review.md); the validator detects missing mappings and changed source documents.
Independently computed golden Context Digests, complete acceptance inputs/results,
and a complete fresh-checkout Gate A run remain pending. No Gate A approval or Core implementation is included.

The 2026-09-11 run used the pinned Step 0B uv environment Python directly (`python -B fixtures/validate_step0b.py`),
following the initial `uv run` baseline. The integrated audit and regression suites reported no errors.
Two full audit reports matched byte for byte; both returned exit code 1 for the outstanding evidence.
This is working-tree repeatability, not the pending fresh-checkout Gate A certification.
Document expectation choices are recorded in [the document fixture review](single/文書構造・UTF-8-review.md).

The subsequent six-case trace batch passed the integrated audit and regression suites, with two byte-identical reports.
Document fixtures SINGLE-017-02 and SINGLE-018-01 had surplus trailing blank lines removed; fixed inputs and snapshots were refreshed.
Trace expectation choices are recorded in [the trace fixture review](single/関係・path・coverage-review.md).

The subsequent four-case graph batch passed integrated checks and regression suites; two full audit reports matched byte for byte.
Graph expectation choices and their limits are recorded in [the graph fixture review](single/文書ID重複・循環review.md).
Working-tree repeatability does not certify the pending fresh-checkout Gate A condition.

The subsequent five-case Git batch passed integrated checks and regression suites; two full audit reports matched byte for byte.
HEAD and index blobs were checked directly against fixed base/current content in addition to snapshots.
Git expectation choices are recorded in [the Git fixture review](single/Git基準版・状態遷移review.md).

The subsequent five-case approved-exemption batch passed integrated checks and regression suites; two full audit reports matched byte for byte.
The Git audit now prepares ten cases, with unchanged supporting inputs checked in HEAD/index/worktree.
Expectation choices are recorded in [the approved-exemption review](single/approved-REQの保護対象外変更review.md).

The 2026-09-14 TASK batch passed integrated checks and regression suites; two full audit reports matched byte for byte.
Both runs used the pinned Step 0B uv environment Python directly (`python -B fixtures/validate_step0b.py`)
and returned exit code 1 solely for pending Gate A evidence. Prepared fixtures: 53/311; missing: 258.
This certifies working-tree preparation repeatability, not Core behavior or the fresh-checkout Gate A condition.
Expectation choices are recorded in [the TASK fixture review](single/TASK境界・対象選択review.md).

The subsequent 2026-09-14 Git selection/impact batch passed integrated checks and regression suites.
Both pinned-environment `python -B fixtures/validate_step0b.py` runs produced byte-identical reports,
with no check errors and exit code 1 for pending Gate A evidence. Prepared fixtures: 57/311; missing: 254.
HEAD/index/worktree comparisons include the empty unborn index and the staged-code/untracked-test split.
Expectation choices are recorded in [the Git selection/impact review](single/Git対象選択・影響候補review.md).
This remains working-tree preparation evidence; Core behavior and fresh-checkout Gate A certification are pending.

The subsequent 2026-09-14 Git environment batch passed integrated checks and regression suites.
Two pinned-environment `python -B fixtures/validate_step0b.py` runs produced byte-identical reports,
with no check errors and exit code 1 for pending Gate A evidence. Prepared fixtures: 60/311; missing: 251.
The new cases fix invalid-base stream shape and report preservation, and distinguish absent Git from an empty Git status.
SINGLE-040/041 now explicitly pass --base HEAD as required by the fixture contract; expected results and snapshots are unchanged.
Matrix regression checks reject omitted required base or a base supplied to a Git-absent case.
Expectation choices are recorded in [the Git environment review](single/Git基準版error・Git不在review.md).
These are preparation checks, not observed Core behavior or complete fresh-checkout Gate A certification.

The subsequent 2026-09-14 Context failure batch passed integrated checks and regression suites.
Two pinned-environment `python -B fixtures/validate_step0b.py` runs produced byte-identical reports,
with no check errors and exit code 1 for pending Gate A evidence. Prepared fixtures: 65/311; missing: 246.
The five cases fix requested roots, exact failure diagnostics, null Digest and empty non-success Bundle data.
Unborn repository checks and mutations reject invented commits, staged inputs, implicit successor replacement and partial success.
Expectation choices are recorded in [the Context failure review](single/Context非成功review.md).
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
[the Digest fixture review](single/Context-Digest-review.md).
The federation golden (MULTI-002-01) is still missing, so the federation half of the Gate A Digest
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
[the non-success Context review](single/Context-stale・上限・coverage-review.md).
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
Expectation choices and their limits are recorded in [the verify review](single/verify実行・事前ブロックreview.md).
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
[the verify process review](single/verify-process終了review.md).
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
recorded in [the verify output review](single/verify出力・文書単位binding-review.md).
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
after the re-review recorded in Diagnostic意味網羅review.md.
The fixture pairs with SINGLE-067: a done root is re-verifiable with its own Digest and binding, while a
cancelled root is blocked with neither. AC-02 is deliberately unaddressed, so neither its statement nor
its test may enter the binding. Expectation choices and their limits are recorded in
[the done TASK root review](single/done-TASK起点review.md).
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
[the report absence review](single/report非作成・引数不正review.md).
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
[the explicit-report review](single/明示report-review.md).
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
Expectation choices and limits are recorded in [the CLI boundary review](single/CLI引数境界review.md).
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
missing repeated option. See [the repeated-expand review](single/expand反復review.md).
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
See [the missing-selection review](single/起点・workspace不存在review.md) for input and expectation choices.
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
See [the output-format review](single/出力形式review.md) for expectation choices and limits.
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
See [the BOM/Frontmatter review](single/BOM・Frontmatter-review.md) for input and expectation choices.
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

The input-limit batch passed two byte-identical integrated audits in the pinned CPython 3.14.6 environment.
All check errors were empty; exit 1 denotes pending Gate A evidence. Prepared: 143/311; missing: 168.
SINGLE-078/079-01/079-02 cross the 64 KiB configuration, 1 MiB SPEC Markdown and 32 KiB Frontmatter limits,
each with the other dimensions inside their limits. SINGLE-080-01 fills 1,000 statements and 1,000 covers
exactly and stays successful; 080-02 adds one statement and 080-03 one covers entry, backed by a second
one-statement REQ so the extra reference still resolves. SINGLE-083 keeps one non-SPEC file directly under
`.spec/`. The audit measures the generated bytes again and rejects any fixture that crosses another dimension.
Both isolated setups match the fixed snapshot per fixture. Regression checks reject changed counts, codes,
severity, source, keys and side effects, and inputs moved to the other side of their limit.
See [the input-limit review](single/上限・未知entry-review.md) for scope and evidence.
Runtime: the same pinned CPython 3.14.6 validator environment recorded above, Linux/WSL2, Git 2.53.0.
No limit check or Core was implemented or executed. Actual continuation units and counts are Gate B work.
Remaining fixtures, federation golden Digest and full fresh-checkout Gate A repeatability stay pending.

The registry-closure batch completed matrix §6.9 and passed two byte-identical integrated audits in the
pinned CPython 3.14.6 environment. All check errors were empty; exit 1 denotes pending Gate A evidence.
Prepared: 150/311; missing: 161. SINGLE-089 fixes the 1-based code point position of a reason-less SHOULD
and keeps the document counted; SINGLE-090 carries only the advisory relation to an absent target.
SINGLE-091 differs from the minimal configuration by one anchor; SINGLE-092 reuses the reviewed type-error
configuration under doctor and returns the shared configuration code with four executed checks.
SINGLE-093 differs from SINGLE-001 by Git absence alone, with a null Git snapshot and the four
`lostGuarantees` names now fixed in the doctor contract; the reviewed source hash was refreshed.
SINGLE-094 returns the check workspace-missing condition rather than the doctor-only code, and SINGLE-095
differs from the minimal configuration by the EARS-AI major alone. Both isolated setups match the fixed
snapshot per fixture. Regression checks reject changed positions, severity, workspace identity, doctor check
status, lost guarantees, codes and side effects, repaired inputs and an added workspace.
See [the registry closure review](single/registry閉包review.md) for scope and evidence.
Runtime: the same pinned CPython 3.14.6 validator environment recorded above, Linux/WSL2, Git 2.53.0.
No YAML loader, Git probe, doctor procedure or Core was implemented or executed. Actual check continuation
and doctor output are Gate B work. Remaining fixtures, federation golden Digest and full fresh-checkout
Gate A repeatability stay pending.

The Scanner/position batch passed two byte-identical integrated audits in the pinned CPython 3.14.6
environment. All check errors were empty; exit 1 denotes pending Gate A evidence. Prepared: 166/311;
missing: 145. Sixteen §6.10 check fixtures keep the reviewed EARS document and replace line 16 alone.
Each Diagnostic column is re-derived from the fixed bytes as a 1-based code point offset, including the
multi-byte and TAB case. The two shared-cause fixtures fix the registry priority primaries, and the four
suppression fixtures wrap one identical statement-like text in a backtick fence, a tilde fence, a quote and
a four-space indent. Failed cases count zero documents and statements; suppression cases count the single
valid statement on line 15. Both isolated setups match the fixed snapshot per fixture. Regression checks
reject shifted columns, changed counts and codes, duplicated diagnostics, a dropped position field, side
effects, replaced statements and unwrapped constructs. The four `context` cases of §6.10 stay outstanding
because they require complete Semantic IR and Digest comparisons.
See [the Scanner review](single/Scanner・位置review.md) for scope and evidence.
Runtime: the same pinned CPython 3.14.6 validator environment recorded above, Linux/WSL2, Git 2.53.0.
No Scanner, Lexer, Parser or Core was implemented or executed. Actual candidate extraction and emitted
positions are Gate B work. Remaining fixtures, federation golden Digest and full fresh-checkout Gate A
repeatability stay pending.

The default-display batch passed two byte-identical integrated audits in the pinned CPython 3.14.6
environment. All check errors were empty; exit 1 denotes pending Gate A evidence. Prepared: 173/311;
missing: 138. SINGLE-104-02/03/04 omit --format and fix the text summary line for check, verify and doctor;
the audit re-derives operation, status, targets and diagnostics from the JSON counterpart through the
published derivation and rejects a doctor line that carries scope=. SINGLE-105-01 adds a base commit to the
golden context corpus and fixes the current revision, with the real 40 digit lowercase commit, the clean
worktree and the per-operation revision shape observed in each isolated setup. SINGLE-105-02 removes Git
entirely and keeps revision and the Git snapshot null. SINGLE-106-04 reuses the truncation corpus with a
silent script, observed to exit 0 and write nothing, and fixes empty excerpts with both truncated flags
false. SINGLE-106-05 returns the same root-missing condition on two targets and counts both in the text
summary. The text contract now states that non-file Diagnostic lines keep path, line and column empty, and
the reviewed source hash was refreshed; the committed-fixture --base rule now applies to check alone, since
context and verify have no base option.
See [the default display review](single/既定表示・revision-review.md) for scope and evidence.
Runtime: the same pinned CPython 3.14.6 validator environment recorded above, Linux/WSL2, Git 2.53.0.
No renderer, Git reader or Core was implemented or executed. Markdown byte equality (SINGLE-104-01) and the
three projection fixtures stay outstanding with the remaining Context and Digest work.

SINGLE-104-01 passed two byte-identical integrated audits in the pinned CPython 3.14.6 environment.
All check errors were empty; exit 1 denotes pending Gate A evidence. Prepared: 174/311; missing: 137.
The Markdown presentation was undefined beyond the section order, so proposal 26 fixed the whole rendering
and context仕様 §9 now carries it; the reviewed source hash was refreshed. `markdown_reference.py` is a
fixture-side reference computation of that contract, and the committed Bundle must equal its output byte for
byte. The audit additionally rejects a changed section order, an altered or unfenced body, a body fence that
is not longer than the longest run inside it, a second H1, and any duration token. The golden context corpus
is unchanged, so the Digest and the JSON counterpart stay identical to SINGLE-042.
See [the Markdown proposal](../../docs/04.提案資料/26_context-Markdown提示仕様案.md) for the decided points.
Runtime: the same pinned CPython 3.14.6 validator environment recorded above, Linux/WSL2, Git 2.53.0.
No Core renderer was implemented or executed. The three projection fixtures of §6.11 and the four `context`
cases of §6.10 stay outstanding with the remaining Digest corpus work.

## 2026-09-17: reason, full projection and Digest versions

Added SINGLE-101-01, SINGLE-106-01 and SINGLE-121. Prepared: 177/311; missing: 134.
Two `uv run fixtures/validate_step0b.py` runs produced byte-identical reports;
all check errors were empty. Both exited 1 solely for outstanding Gate A evidence.
Report SHA-256: `49554c146d9e524c0310e4700806c912ef10388cb595018284936033dd7c784e`.
The existing pinned uv environment and dependencies were used; no runtime changes were made.
Each new fixture has its own complete input, manifest, expected result, Canonical JSON
and read-only snapshots. Two isolated setups and the two independent Digest references
agree. Mutation checks reject missing reason, forbidden/missing full projection fields,
and changed digestVersion/resolverVersion.
See [the Digest review](single/Context-Digest-review.md). Core was not run.
The normative/reference projections, remaining scanner Context cases, federation golden
and full fresh-checkout Gate A evidence remain pending.

## 2026-09-17: internal Parser evidence and normative projection

Prepared: 179/311; missing: 132. Added SINGLE-097-01 and SINGLE-106-02, and added
complete internal Parser IR expectations to SINGLE-101-01.
Two pinned-environment `python -B fixtures/validate_step0b.py` runs produced
byte-identical reports, with no check errors; both exit 1 for outstanding Gate A evidence.
Report SHA-256: `145b9efd0b02033a4f5d9b3148ec6a4f8a5c5e7da9606c5414a4f98669a99027`.
Runtime: the existing CPython 3.14.6 Step 0B uv environment, Linux/POSIX; dependency pins unchanged.
The five text escapes and source/raw/meaning fields agree with fixed full IR expectations.
A distance-two refinement exercises normative projection field omission.
Input, complete JSON, Canonical JSON and snapshots are fixed; two isolated setups and
two independent Digest computations agree. Mutation checks cover semantic fields,
source positions, raw, projection fields and missing/unsafe/duplicate Parser references.
The accepted split is specified in fixture contract §4.1: Step 2 must compare the real
Parser's full IR, while public context acceptance continues comparing JSON and Digest.
No Core Parser or operation was implemented or executed. Code-span and quoted-extension
expectations remain pending semantic decisions; reference projection and federation
golden, other missing fixtures and fresh-checkout Gate A certification also remain pending.

## 2026-09-17: quoted extension acceptance

Prepared: 180/311; missing: 131. SINGLE-098-01 fixes escaped DQUOTE in a quality
extension, with passed_with_warnings as explicitly approved. Two integrated
`python -B fixtures/validate_step0b.py` runs in the existing pinned CPython 3.14.6
environment produced byte-identical reports; all check errors were empty.
Report SHA-256: `edecc666b3ad04a7da27816272fbd398de2a242027511d9d19d2888668df4d07`.
Both exited 1 for outstanding Gate A evidence. Complete IR, source, opaque/unknown
extension value, public result, Canonical JSON and read-only snapshots are checked.
No Core was run. Code spans, reference projection, federation golden, remaining
fixtures and fresh-checkout certification remain pending.

## 2026-09-17: code-span acceptance

Prepared: 181/311; missing: 130. SINGLE-096-01 completes the 20 cases of matrix §6.10.
The approved semantics remove outer delimiters only; unequal internal runs and
span-internal tag/escape-like text remain literal. Full IR, raw/source, JSON and
Canonical JSON are fixed. Two independent reference computations and two isolated
setups agree. Equal-run termination and malformed-run regression checks passed.
Two integrated runs in the same pinned CPython 3.14.6 environment were byte-identical
with no check errors, both exit 1 for pending Gate A evidence.
Report SHA-256: `e4c52beaeb441737c9a8f96f18e4d59b1f9a4bc766f738c60238685d78f272ca`.
No Core was run. Reference projection, remaining fixtures, federation golden and
fresh-checkout Gate A certification remain pending.

## 2026-09-17: Frontmatter境界

準備済み201/311、残り110件。SINGLE-114、115-01〜04、116-01〜05、117-01〜03、118-01、119-01〜04、
120-03、120-04で、REQ／TECH／ADR／TASKの最小definition、titleの120／121 code point境界、空白・複数行・null・
欠落のtitle、空・重複配列、未知key、`x-`拡張、REQの`changes`の優先順位を固定した。
独立にdecodeしたflow valueは審査済みfieldおよびFrontmatter Schemaの判定と一致した。2回の隔離setupは
read-only snapshotと一致した。回帰試験はstatus・件数・codeの改変、二重または削除した診断、cache書込み、
境界内へ修復した121 code point titleを拒否する。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `db8b0defde675722225f72962027265855afbe953971a3379b4bbba0a3e39582`。
Coreは実行していない。SINGLE-118-02／03、120-01／02、残りの適合fixture、連合golden、fresh checkoutでの
Gate A認定は未完了である。

## 2026-09-17: Frontmatter境界の追補

準備済み205/311、残り106件。SINGLE-118-02、118-03、120-01、120-02を加え、matrixの114〜120を完了した。
118-02／03は`tests`要素を`(path, commandの有無と値, covers集合)`のkey tupleで独立に比較し、
JSON Schemaの`uniqueItems`では検出できないcovers順だけの重複を拒否、command／coversの異なる要素を受理する。
120-01／02は明示TASK checkで、`changes: []`かつ差分なしの通過と、`changes`省略かつ未stage差分の
`SPEC-TASK-BOUNDARY-001`を固定した。HEAD／indexのblobと作業treeのbyteを2回の隔離setupで照合した。
回帰試験は受理への改変、covers順の修復、件数・source・argvの改変、差分の消去とstageの追加を拒否する。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `0fff1aa3a4d4ca4b2bbc3e21ac59549a39bc0b5f516ee2cf8a3eaa72ca155bc0`。
Coreは実行していない。残りの適合fixture、連合golden、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: Core副作用

準備済み210/311、残り101件。SINGLE-125-01〜05を追加した。source fixture（042、001、070-01、055、071-01）と
同じ起動・入力を使い、期待結果fileはsourceとbyte一致させた。125-01〜04は`.spec/reports/`を置かないread-only、
HOME／cache／tempは空で固定し、125-04は書込みなしcommand `/bin/true`に限定した。125-05は最終report 1件、
一時file残存0件、既存report不変を要求する。各fixtureを2回の隔離setupで照合した。
回帰試験は書込み許容、外部treeの事前汚染、report要求・件数・policyの改変、追加環境変数、
report directoryの追加、書込みcommandへの置換を拒否する。
SINGLE-125-06は、時刻固定も障害注入もできないfixture形式では、SINGLE-072と異なる排他的作成失敗を
決定論的に起こせないため保留した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `09eb848bfd50680e20ed3fa13eb6f0c4b860281810957f182eff436b8b23e457`。
Coreは実行していない。SINGLE-125-06、残りの適合fixture、連合golden、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: report directoryのsymlink（SINGLE-125-06）

準備済み211/311、残り100件。`.spec`または`.spec/reports`がsymlinkなら解決せず保存失敗とする規定を
結果・Diagnostic・終了コード §8へ、`.spec/reports`をentry種別にかかわらず既知entryとする規定を
workspace・設定仕様 §3へ追加し、registryの`REPORT-WRITE`行へ注記した。新規条件はなく、
Diagnostic台帳は3文書のhashだけを再レビュー後に更新した。
SINGLE-125-06はSINGLE-072と同じ起動・期待結果で、`.spec/reports`を`../report-store`へのsymlinkに替えた。
symlink、symlink先directory、既存reportの不変をread-only snapshotで固定し、2回の隔離setupで照合した。
監査の`copy_fixture`はsymlinkをsymlinkのままcopyするよう修正した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `6ba25afc010d4f839244d4a2f26f3488703d62d67c8f3e70a2209531e3311b81`。
Coreは実行していない。残りの適合fixture、連合golden、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: verify argv・実行環境・出力変換

準備済み225/311、残り86件。SINGLE-126-01〜05、07、09〜16を追加した。
126-01〜05は設定のflow配列を独立にdecodeし、argv template規則の違反がちょうど1件であることを確認した。
126-07、10、11はfixture自身のscriptを直接起動し、期待入力でだけ成功することを観測した。126-11は
POSIX shが`PWD`を再計算するため、awkで環境を読む。126-12は別sessionの子孫が直接process終了後も
5秒以上pipeを保持することを、126-13はSINGLE-059と同じhang観測と後続`/bin/true`の成功を観測した。
126-14〜16はraw出力から独立の参照変換（制御文字、redaction、code point境界の末尾保持）で期待抜粋を再計算した。
各fixtureを2回の隔離setupで照合し、Context Digestは2系統のreferenceで一致した。
126-06は`bitz.yaml`の64 KiB上限により`SPEC-CONFIG-SCHEMA-001`へ到達できないため、126-08はfixture規模のため保留した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `242dd2b0bce32f6e233c849292e3d1d56e00296f5521f3b6285b84a5f5e7c8fd`。
Coreは実行していない。126-06、126-08、残りの適合fixture、連合golden、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: argv上限の裁定とSINGLE-126-08

準備済み226/310、残り84件。SINGLE-126-06は`bitz.yaml`の64 KiB上限により`SPEC-CONFIG-SCHEMA-001`へ到達できないため、
裁定でmatrixから削除し、workspace・設定仕様 §6へ注記した。Diagnostic台帳は同文書のhashだけを再レビュー後に更新した。
SINGLE-126-08は規範文なしTECH 35文書、test path 280件（各約3,770 byte）で、引数なしverifyの展開後argvが
1,055,609 byteとなりbyte上限だけを超える。設定・Frontmatter・文書・要素数・要素長・path長が上限内であること、
1文書分を除くと上限内へ戻ることを独立に確認した。35 targetのContext Digestは2系統のreferenceで一致した。
fixtureは入力と副作用snapshotで約9 MiBである。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `f40dbfc6f38683207e31d53e7fde47d33232b708791a994b51dd980f1ebd8206`。
Coreは実行していない。残りの適合fixture、連合golden、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: 明示起点の不在・ADR起点、共通target展開、Digest材料の順序

準備済み245/310、残り65件。SINGLE-106-03、107-01／02、108-01／02、109、110、111-01〜04、112-01〜04、113、
122〜124の19件を追加した。作成前に、role割当、interpretのdraft refinement、statement起点の提示、
verifyの起点TASKの`requires`を裁定して正本へ反映し、Diagnostic台帳とtarget vectorの根拠hashを再レビュー後に更新した。
target vectorは`TASK-REQUIRES-NOT-TARGET`の期待集合だけが変わり、他の24ケースは不変である。
reference B（`digest_crosscheck.py`）を`requires`の追跡、statementへの`refines`、draft advisory、
command省略時の文書`verify`解決、extensionの正規順へ拡張し、既存fixtureのCanonical JSONが不変であることを確認した。
新規のContext Digestはすべて2系統のreferenceで一致した。各fixtureを2回の隔離setupで照合した。
SINGLE-127-15〜19は、偽Gitの配置、`consumer` runnerのargv、CPython 3.11の選択が未確定のため保留した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `23f787eb283aa4fe0f877ac020ceb070fa6b116282a2046bbd1cd079eca47c8c`。
Coreは実行していない。SINGLE-127-15〜19、連合fixture、連合golden、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: 適合harness外部仕様の裁定と実行環境・配布物

準備済み250/310、残り60件（すべて連合）。提案27とADR-046で、検査対象の受取り（source／wheelと`uv`隔離環境）、
`invocation.python`、`invocation.gitVersion`とGit shim、`bitz.compat`によるconsumer／migration runner、
harness側の`runner: package`を裁定し、適合fixture仕様、実行環境契約 §4（`git --version`による版取得）、
実装計画のGate C（全matrixを3.11と基準環境で通す）、manifest Schemaへ反映した。
Diagnostic台帳は実行環境契約のhashだけを再レビュー後に更新した。
SINGLE-127-15〜19を追加し、Git版と下限CPythonを規範本文から読み取ってmanifestと照合した。
統合検証へ、bitz以外のrunnerの期待結果が`{"outcome": ...}`だけであることの検査を加えた。
各fixtureを2回の隔離setupで照合した。shim生成、`uv`環境構築、package検査の実行部は未作成である。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `08eda7ecd76069a296e42d1a429a81f22cccfcb16a1f529cdf5de790b3fdaba8`。
Coreは実行していない。連合fixture、連合golden、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: 複合workspaceの識別子の改名

準備済み250/310、残り60件（すべて複合workspace）。ADR-047に従い、設定key、Capability、結果field、Diagnostic code、
condition ID、継続単位、fixture ID（`MONO-*`→`MULTI-*`）、結果SchemaのSchema定義名、性能datasetを改名した。
doctorの期待結果11件はCapability一覧の`multiWorkspace.v1`だけが変わり、manifest Schemaとmatrix検査は
`MULTI-*`を受け付ける。Diagnostic台帳とtarget vectorの根拠文書hashは再レビュー後に更新した。
target vectorの期待集合25ケースは変わらない。性能datasetの期待tree digestは設定keyの変更分だけ更新した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `fb0d2efe0a442145d47e47be364a80d45849c0d0af187f4c57769db1ca15e5f5`。
Coreは実行していない。複合workspaceのfixture、そのgolden Digest、fresh checkoutでのGate A認定は未完了である。

## 2026-09-17: file名の改名

用語集 §7に従い78件のfile名を改名し、参照322箇所、ADR 16件の`title`とH1、台帳の根拠文書keyを直した。
提案資料とfixtureの記録を含む全Markdownでlinkを検査し、link切れは改名前と同じ107件（置換済みの旧ADRが
旧構成の文書を指すもの）で、改名による増加はない。台帳とtarget vectorの根拠文書hashは再レビュー後に更新した。
同じpin済みCPython 3.14.6環境での統合実行2回はbyte一致し、check errorは0件、Gate A未完了により両方exit 1。
Report SHA-256: `fb0d2efe0a442145d47e47be364a80d45849c0d0af187f4c57769db1ca15e5f5`（改名前と同じ）。
