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
137 of the 311 matrix fixtures, the independent federation golden Context Digest,
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
revision shape is observed in the isolated repository. That batch brought preparation to 173/311.

SINGLE-104-01 follows the Markdown presentation decided in proposal 26 and now fixed in context仕様 §9.
`markdown_reference.py` renders that contract from a reviewed result, and the audit compares the committed
Bundle against it while checking the section order, untouched bodies and the absence of a duration token.
Current preparation: 174/311; 137 remain.

[Frontmatter境界fixture](single/frontmatter-boundary-review.md)として、種別definition、title長、必須／null、
空・重複配列、未知key、`x-`拡張、REQの`changes`の20件を加えた。各fieldはJSON構文のflow valueとして書き、
独立にdecodeして`frontmatter.schema.json`と照合する。
この時点でSINGLE-118-02／03と120-01／02は未作成であり、準備済みは201/311、残りは110件だった。

Frontmatter境界の追補として、SINGLE-118-02／03（test要素のkey tuple重複判定）と120-01／02（`changes`空・省略TASKの
明示TASK check）を加え、matrixの114〜120を完了した。準備済みは205/311、残りは106件である。

[Core副作用fixture](single/side-effect-review.md)として、SINGLE-125-01〜05を加えた。監査済みsource fixtureと
同じ起動・入力・期待結果を使い、context、doctor、reportなしcheck、書込みなしverifyでは`.spec/reports/`を置かずに
書込み0件を、明示report付きcheckでは最終report 1件だけと一時file残存0件を固定する。
SINGLE-125-06は発生条件の裁定待ちである。準備済みは210/311、残りは101件である。

SINGLE-125-06は、`.spec/reports`をrepository内directoryへのsymlinkにした保存失敗として追加した。
symlinkを解決せず保存失敗とする規定を結果・Diagnostic・終了コード §8へ追加している。準備済みは211/311、残りは100件である。

[verify argv・実行環境・出力変換fixture](single/verify-runtime-review.md)として、SINGLE-126-01〜05、07、09〜16を加えた。
argv template違反5件、空引数・PATH解決不能・stdin・環境継承、子孫がpipeを保持するtimeout、timeout後の独立binding、
制御文字変換、chunk境界をまたぐredaction、redaction後の64 KiB超過を固定する。実行caseはfixture自身のscriptを
直接観測する。126-06は設定64 KiB上限との矛盾、126-08はfixture規模のため保留した。準備済みは225/311、残りは86件である。

SINGLE-126-06は、設定64 KiB上限により到達できないため裁定でmatrixから削除した（matrixは310件）。
SINGLE-126-08は、約3,770 byteのtest path 280件を規範文なしTECH 35文書へ置き、引数なしverifyの展開後argvだけが
byte総和1 MiBを超える入力として追加した。準備済みは226/310、残りは84件である。

[明示起点の不在・ADR起点fixture](single/target-root-review.md)として、SINGLE-111-01〜04と112-01〜04を加えた。
構文上妥当な不在起点を終了コード4や既知文書の検査へ置き換えず`CTX-ROOT-MISSING-001`で返すこと、ADR起点は
interpretのcontextと明示checkだけで受理することを固定する。

[共通target展開・advisory提示fixture](single/expansion-review.md)として、SINGLE-106-03、107-01／02、108-01／02、
109、110、113を加えた。作成前にrole割当、draft refinement、statement起点の提示、verifyの起点TASKの`requires`を
裁定して正本へ反映した。contextの4集合を完全比較し、同じ起点のverifyが同じtarget集合とDigestを使うことを確認する。

[Digest材料の完全順序・reverse solidus fixture](single/ordering-review.md)として、SINGLE-122〜124を加えた。
同一pathのtest対応と同一namespace／termのextensionの正規順、path型以外のreverse solidus保持を固定する。
準備済みは245/310、残りは65件（SINGLE-127-15〜19と連合60件）である。
