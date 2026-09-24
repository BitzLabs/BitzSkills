# Gate B認定記録

[ADR-052](../../docs/02.設計書/10_決定記録/ADR-052_Gate-Bの実行と認定の構成を確定する.md)に従い、
`uv run tests/bitz-core/certify_gate_b.py --step N`でStep 1からNまでの完了fixtureをCoreへ通した結果を記録する。
各Stepの完了fixtureは[実装計画](../../docs/04.提案資料/12_Core-1.0実装計画.md)が正本であり、
`fixtures/conformance/steps.json`はその機械可読な写しである。

## 2026-09-24: Step 1

commit `28c3cd1a50616e6136fd68aecf61cc2e59ca3872`に対して`uv run tests/bitz-core/certify_gate_b.py --step 1`を実行し、
`gateB: {"step": 1, "result": "Passed"}`、error 0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1の完了fixture 34件（`SINGLE-001`〜`006`、`073`〜`074`、`078`、`091`〜`095`、`104-04`、`125-02`、`127-01`〜`02`、`127-05`〜`07`、`127-11`、`127-14`〜`19`） |
| 参照harness | 2つのcloneで各cloneの`plugins/bitz-core`をbuildし、34件すべてpassed。所要時間と検査対象のpathを除いた結果のSHA-256は両方`64306f9c0d2da97a7e72ee29e2e03ac3ef5efbd9add4b18e49999f891b0699ba` |
| Parser adapter | Step 1では不要 |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

参照harnessの判定能力は、期待出力を返す偽のCoreによる自己試験（`fixtures/conformance/test_fake_core.py`）で別に確かめた。
偽のCoreは代表48件をすべて通過し、標準出力のJSON、text、終了コード4の標準エラー、reportの内容をそれぞれ1箇所改変すると、
改変したfixtureだけが不通過になった。

Core固有の単体試験（`uv run --project plugins/bitz-core python -m unittest discover -s tests/bitz-core`）は72件がすべて成功した。

Step 1のCoreが後続Stepへ残した暫定実装は次のとおりである。いずれも該当Stepの完了fixtureで判定する。

- `check`の明示対象（`scope: selected`）と引数なし（`scope: changed`）は未実装で、終了コード3を返す。
- `check`はSPEC文書を解析せず、`checkedDocumentCount`と`checkedStatementCount`を0とする。
- `check --report`はreportを保存せず終了コード3を返す（黙って無視しない）。
- `context`と`verify`は引数の検査だけを行い、本体は未実装で終了コード3を返す。
- unborn repositoryの`check --full`は`revision: null`を返すが、Git縮退の詳細はStep 3で扱う。
- 設定の未知keyの警告は最上位keyだけを対象とする。
- 参照harnessは生成fixture（`setup.generate`）、`stateDigest`形式の副作用期待値、実行環境に依存するprocess出力の抜粋の正規化に
  まだ対応しておらず、該当fixtureはerrorとなる。いずれもStep 4以降の完了条件に属する。

## 2026-09-25: Step 2

commit `da819d71cc448462af2c5d55f0c3b8f19d998651`に対して`uv run tests/bitz-core/certify_gate_b.py --step 2`を実行し、
`gateB: {"step": 2, "result": "Passed"}`、error 0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1と2の完了fixture 131件（Step 2は`SINGLE-007`〜`026`、`070-01`〜`02`、`075-01`〜`02`、`076`〜`077`、`079`〜`090`、`096`〜`103`、`104-02`、`114`〜`120`の97件）と、`parserChecks` 4件（`SINGLE-096-01`、`097-01`、`098-01`、`101-01`） |
| 参照harness | 2つのcloneで各cloneの`plugins/bitz-core`をbuildし、131件すべてpassed。所要時間と検査対象のpathを除いた結果のSHA-256は両方`aa099ee29d40fecbf7487e08c8d5a04d09f829b11e1f6649cc36cca3fd9bbcbc` |
| Parser adapter | 2つのcloneで`tests/bitz-core/parser_adapter.py`が終了コード0、標準出力が一致。4件の全Semantic IRが期待値と完全一致した。作業treeでの標準出力のSHA-256は`dfbe4dfba63f86a2d6bcf3714da19356c94b5b95e55ac3f00bb9d4e187a324a9` |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

Core固有の単体試験（`uv run --project plugins/bitz-core python -m unittest discover -s tests/bitz-core -t tests/bitz-core`）は282件がすべて成功した。
fixtureの入力行をParserへ直接与え、`check`経由の期待値にあるEARS-AI Diagnostic 23件のcode、line、columnとの一致も別に確かめた。
Diagnosticの順序が`PYTHONHASHSEED`に依存しないことは、同じ入力を5つのseedで実行して確かめた。

仕様の記述だけでは一意に決まらず、実装で次のとおり解釈した。仕様側の明確化を要する候補として残す。

- 規範文IDの文書部分がFrontmatterの`id`と異なる場合（check.md §4の「文書ID整合」）は、registryに専用の行がないため
  `EAI-CORE-ID-001`（draftでもerror）とする。
- `tests[].covers`は、宣言文書自身の規範文、規範文を持たない宣言文書自身の文書ID、宣言文書が`relations.refines`で
  直接参照する文書の規範文または規範文そのもの、のいずれかだけを受け付ける。文書・Frontmatter仕様 §5の字面は
  「同じ文書の規範文ID」だが、Gate A認定済みの正例（`SINGLE-042`〜`070`系で規範文なしTECHが`refines`先REQの規範文を
  `covers`する）と両立させるため、関係モデル §9の「直接`refines`」の原理にそろえた。
- `requires`のtargetが`accepted`以外のADRである場合は`CTX-RELATION-TYPE-001`とする（関係モデル §4の型表が
  `accepted ADR`を型として定義しているため）。draft REQなどの適用可能性は`context`の`CTX-STATE-*`で扱う。
- 同じ`relations.<name>`の中の複数の参照切れは、edgeごとに1件ずつ返す。`source.key`は添字を持たないため、
  同じcode・path・keyのDiagnosticが並ぶ。
- 単一workspaceがGit rootより下にある場合、Gitの変更pathをworkspace相対へ変換し、workspace外の変更はTASK境界の
  比較対象から除く（SPECのpath表記で表せないため）。
- `.spec/`配下（`reports`を除く）のsymlinkは辿らず、`SPEC-WORKSPACE-UNKNOWN-001`とする。
- 期待位置に現れたCore tagは、期待するtagが同じ行の後方にあれば`EAI-CORE-SYNTAX-001`、なければ`EAI-CORE-SYNTAX-002`とする。
  Core tagでも妥当なextensionでもないtagは`EAI-CORE-SYNTAX-004`（summary「tagが不正です」）とする。
- EARS-AIの`local-id`（`alnum, { alnum | "-" }`）はFrontmatter Schemaの`idString`の規範文部分
  （`[A-Z][A-Z0-9-]*-[0-9]{2,}`）より広い。Frontmatterから参照できない規範文IDを書けるが、Core 1.0は両者を別々に検査する。

Step 2のCoreが後続Stepへ残した暫定実装は次のとおりである。いずれも該当Stepの完了fixtureで判定する。

- `check`の引数なし（`scope: changed`）、状態遷移、管理済みSPEC削除、承認済みREQ保護、影響候補は未実装で、
  引数なしの`check`は終了コード3を返す。
- `TargetExpansion`は`purpose=interpret`だけを実装し、`implement`と`verify`は例外を送出する。
- `check --report`、`context`、`verify`の本体はStep 1から変わらず未実装である。

## 2026-09-25: Step 3

commit `139376ac3196f58c7f13d47f7f47a8473674c9d2`に対して`uv run tests/bitz-core/certify_gate_b.py --step 3`を実行し、
`gateB: {"step": 3, "result": "Passed"}`、error 0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1〜3の完了fixture 202件（Step 3は`SINGLE-027`〜`054`、`071-01`〜`02`、`072`、`096-01`、`097-01`、`098-01`、`101-01`、`104-01`、`105-01`、`106-01`〜`03`、`107-01`、`108-01`、`109`、`110`、`111-01`〜`03`、`112-01`〜`03`、`121`〜`124`、`125-01`、`125-03`、`125-05`〜`06`、`127-03`〜`04`、`127-12`〜`13`の71件）と、`parserChecks` 4件 |
| 参照harness | 2つのcloneで202件すべてpassed。所要時間と検査対象のpathを除いた結果のSHA-256は両方`e7dbcf8c83a6dd7b8580995fb032f8ebc5a6f724abddb3e98c62c8bebfff0719` |
| Parser adapter | 2つのcloneで終了コード0、標準出力が一致。作業treeでの標準出力のSHA-256は`dfbe4dfba63f86a2d6bcf3714da19356c94b5b95e55ac3f00bb9d4e187a324a9`（Step 2と同じ） |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

Core固有の単体試験は370件がすべて成功した。Context Digestはfixture側のreference計算を読まず、仕様だけから独立に実装し、
golden値（`SINGLE-042`）へ一致した。`SINGLE-107-01`、`122`、`123`の入力へ`context`を`PYTHONHASHSEED`の3値で実行し、
結果JSONが同一であることを確かめた。

仕様の記述だけでは一意に決まらず、実装で次のとおり解釈した。仕様側の明確化を要する候補として残す。

- `CTX-LIMIT-001`のbyte上限は、指定した`--detail`にかかわらず`standard`提示の量で測る（安全な入出力 §4の
  「ContextのSemantic IRと標準提示」、`SINGLE-049`）。
- Digestの`settings.commands`と`verifyTimeouts`は、`purpose=verify`でbindingを収録した場合だけ置く（`SINGLE-054`）。
- Markdownの文書sectionでは`untrustedText`を`frontmatter`の後、`bodyText`の前に出す（`SINGLE-104-01`。context仕様 §9.6の表の並びとは異なる）。
- `--detail compact`のJSONでは全文書を`reference`提示とする。fixtureがなく未検証である。
- `standard`では、距離2以上の`requirement`文書を`full`のままとする（仕様は「間接constraint/refinementをnormative」とだけ定める）。
- `reachedBy`の`<relation>:<source-id>`の`source-id`は、relationを宣言した文書のIDとする（`SINGLE-107-01`、`108-01`）。
- 明示対象checkでは、状態遷移、承認済みREQ保護、影響候補を完全検査対象の文書だけへ適用し、管理済みSPEC削除は報告しない。
- `SPEC-GIT-DEGRADED-001`は引数なしcheckの縮退だけで返し、明示`--full`では返さない（安全な入出力 §8）。
- 承認済みREQ保護で比較する規範文の意味は、Semantic IRの`actor`、`activation`、`modality`、`reason`、`operation`、`extensions`とする。
- 影響候補の起点は、Gitの変更pathから直接写像される`.spec/`配下のREQ/TECHだけとする。

Step 3のCoreが後続Stepへ残した暫定実装は次のとおりである。

- `verify`の本体と`verify --report`は未実装である。
- 複合workspace（修飾ID、`--all-workspaces`、`resolution.workspaces`）は未実装である。
