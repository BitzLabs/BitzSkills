# Gate B認定記録

[ADR-052](../../docs/02.設計書/10_決定記録/ADR-052_Gate-Bの実行と認定の構成を確定する.md)に従い、
`uv run tests/bitz-core/certify_gate_b.py --step N`でStep 1からNまでの完了fixtureをCoreへ通した結果を記録する。
各Stepの完了fixtureは[実装計画](../../docs/04.提案資料/12_Core-1.0実装計画.md)が正本であり、
`fixtures/conformance/steps.json`はその機械可読な写しである。

## 2026-09-24: Step 1

コミット`28c3cd1a50616e6136fd68aecf61cc2e59ca3872`に対して`uv run tests/bitz-core/certify_gate_b.py --step 1`を実行し、
`gateB: {"step": 1, "result": "Passed"}`、エラー0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1の完了fixture 34件（`SINGLE-001`〜`006`、`073`〜`074`、`078`、`091`〜`095`、`104-04`、`125-02`、`127-01`〜`02`、`127-05`〜`07`、`127-11`、`127-14`〜`19`） |
| 参照harness | 2つのクローンで、各クローンの`plugins/bitz-core`をビルドし、34件すべて`passed`。所要時間と検査対象のパスを除いた結果のSHA-256は両方`64306f9c0d2da97a7e72ee29e2e03ac3ef5efbd9add4b18e49999f891b0699ba` |
| 構文解析器のアダプター | Step 1では不要 |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

参照harnessの判定能力は、期待出力を返す偽のCoreによる自己試験（`fixtures/conformance/test_fake_core.py`）で別に確かめた。
偽のCoreは代表48件をすべて通過した。標準出力のJSON、テキスト出力、終了コード4の標準エラー出力、レポートの内容をそれぞれ1箇所改変すると、
改変したfixtureだけが通過しなくなった。

Core固有の単体試験（`uv run --project plugins/bitz-core python -m unittest discover -s tests/bitz-core`）は72件がすべて成功した。

Step 1のCoreが後続Stepへ残した暫定実装は次のとおりである。いずれも該当Stepの完了fixtureで判定する。

- `check`の明示対象（`scope: selected`）と引数なし（`scope: changed`）は未実装で、終了コード3を返す。
- `check`は仕様文書を解析せず、`checkedDocumentCount`と`checkedStatementCount`を0とする。
- `check --report`はレポートを保存せず終了コード3を返す（黙って無視しない）。
- `context`と`verify`は引数の検査だけを行い、本体は未実装で終了コード3を返す。
- コミットのないリポジトリの`check --full`は`revision: null`を返すが、Gitの縮退の詳細はStep 3で扱う。
- 設定の未知のキーに対する警告は、最上位のキーだけを対象とする。
- 参照harnessは、生成fixture（`setup.generate`）、`stateDigest`形式の副作用の期待値、実行環境に依存するプロセス出力の抜粋の正規化に
  まだ対応しておらず、該当するfixtureはエラーとなる。いずれもStep 4以降の完了条件に属する。

## 2026-09-25: Step 2

コミット`da819d71cc448462af2c5d55f0c3b8f19d998651`に対して`uv run tests/bitz-core/certify_gate_b.py --step 2`を実行し、
`gateB: {"step": 2, "result": "Passed"}`、エラー0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1と2の完了fixture 131件（Step 2は`SINGLE-007`〜`026`、`070-01`〜`02`、`075-01`〜`02`、`076`〜`077`、`079`〜`090`、`096`〜`103`、`104-02`、`114`〜`120`の97件）と、`parserChecks` 4件（`SINGLE-096-01`、`097-01`、`098-01`、`101-01`） |
| 参照harness | 2つのクローンで、各クローンの`plugins/bitz-core`をビルドし、131件すべて`passed`。所要時間と検査対象のパスを除いた結果のSHA-256は両方`aa099ee29d40fecbf7487e08c8d5a04d09f829b11e1f6649cc36cca3fd9bbcbc` |
| 構文解析器のアダプター | 2つのクローンで`tests/bitz-core/parser_adapter.py`が終了コード0、標準出力が一致。4件のすべての意味中間表現が期待値と完全に一致した。作業ツリーでの標準出力のSHA-256は`dfbe4dfba63f86a2d6bcf3714da19356c94b5b95e55ac3f00bb9d4e187a324a9` |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

Core固有の単体試験（`uv run --project plugins/bitz-core python -m unittest discover -s tests/bitz-core -t tests/bitz-core`）は282件がすべて成功した。
fixtureの入力行を構文解析器へ直接与え、`check`経由の期待値にあるEARS-AIの診断23件の診断コード、行、列との一致も別に確かめた。
診断の順序が`PYTHONHASHSEED`に依存しないことは、同じ入力を`PYTHONHASHSEED`の5つの値で実行して確かめた。

仕様の記述だけでは一意に決まらず、実装で次のとおり解釈した。仕様側の明確化を要する候補として残す。

- 規範文IDの文書部分がフロントマターの`id`と異なる場合（`check.md` §4の「文書ID整合」）は、診断レジストリに専用の行がないため、
  診断`EAI-CORE-ID-001`（文書の状態が`draft`でも重大度`error`）とする。
- `tests[].covers`は、宣言文書自身の規範文、規範文を持たない宣言文書自身の文書ID、宣言文書が`relations.refines`で
  直接参照する文書の規範文または規範文そのもの、のいずれかだけを受け付ける。文書・フロントマター・状態仕様 §5の字面は
  「同じ文書の規範文ID」だが、Gate A認定済みの正例（`SINGLE-042`〜`070`系で、規範文を持たないTECHが、`refines`の参照先のREQの規範文を
  `covers`に指定する）と両立させるため、関係・トレースモデル §9の「直接`refines`」の原理にそろえた。
- `requires`の参照先が、状態が`accepted`以外のADRである場合は、診断`CTX-RELATION-TYPE-001`とする（関係・トレースモデル §4の型表が
  `accepted ADR`を型として定義しているため）。状態が`draft`のREQなどの適用可能性は、`context`の診断`CTX-STATE-*`で扱う。
- 同じ`relations.<name>`の中の複数の参照切れは、エッジごとに1件ずつ返す。`source.key`は添字を持たないため、
  診断コード、パス、キーが同じ診断が並ぶ。
- 単一ワークスペースがリポジトリのルートより下にある場合、Gitの変更パスをワークスペースからの相対パスへ変換し、ワークスペース外の変更はTASK境界の
  比較対象から除く（仕様文書のパス表記で表せないため）。
- `.spec/`配下（`reports`を除く）のシンボリックリンクはたどらず、診断`SPEC-WORKSPACE-UNKNOWN-001`とする。
- 期待される位置に現れたCoreのタグは、期待するタグが同じ行の後方にあれば`EAI-CORE-SYNTAX-001`、なければ`EAI-CORE-SYNTAX-002`とする。
  Coreのタグでも妥当な拡張タグでもないタグは、`EAI-CORE-SYNTAX-004`（要約「tagが不正です」）とする。
- EARS-AIの`local-id`（`alnum, { alnum | "-" }`）は、フロントマターのスキーマの`idString`の規範文部分
  （`[A-Z][A-Z0-9-]*-[0-9]{2,}`）より広い。フロントマターから参照できない規範文IDを書けるが、Core 1.0は両者を別々に検査する。

Step 2のCoreが後続Stepへ残した暫定実装は次のとおりである。いずれも該当Stepの完了fixtureで判定する。

- `check`の引数なし（`scope: changed`）、状態遷移、管理済みの仕様文書の削除、承認済み要求の保護、影響候補は未実装で、
  引数なしの`check`は終了コード3を返す。
- `TargetExpansion`は、目的`interpret`だけを実装し、目的`implement`と目的`verify`では例外を送出する。
- `check --report`、`context`、`verify`の本体はStep 1から変わらず未実装である。

## 2026-09-25: Step 3

コミット`139376ac3196f58c7f13d47f7f47a8473674c9d2`に対して`uv run tests/bitz-core/certify_gate_b.py --step 3`を実行し、
`gateB: {"step": 3, "result": "Passed"}`、エラー0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1〜3の完了fixture 202件（Step 3は`SINGLE-027`〜`054`、`071-01`〜`02`、`072`、`096-01`、`097-01`、`098-01`、`101-01`、`104-01`、`105-01`、`106-01`〜`03`、`107-01`、`108-01`、`109`、`110`、`111-01`〜`03`、`112-01`〜`03`、`121`〜`124`、`125-01`、`125-03`、`125-05`〜`06`、`127-03`〜`04`、`127-12`〜`13`の71件）と、`parserChecks` 4件 |
| 参照harness | 2つのクローンで202件すべて`passed`。所要時間と検査対象のパスを除いた結果のSHA-256は両方`e7dbcf8c83a6dd7b8580995fb032f8ebc5a6f724abddb3e98c62c8bebfff0719` |
| 構文解析器のアダプター | 2つのクローンで終了コード0、標準出力が一致。作業ツリーでの標準出力のSHA-256は`dfbe4dfba63f86a2d6bcf3714da19356c94b5b95e55ac3f00bb9d4e187a324a9`（Step 2と同じ） |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

Core固有の単体試験は370件がすべて成功した。コンテキストのハッシュ値は、fixture側の参照計算を読まず、仕様だけから独立に実装し、
golden値（`SINGLE-042`）に一致した。`SINGLE-107-01`、`122`、`123`の入力に対して`context`を`PYTHONHASHSEED`の3つの値で実行し、
結果のJSONが同一であることを確かめた。

仕様の記述だけでは一意に決まらず、実装で次のとおり解釈した。仕様側の明確化を要する候補として残す。

- 診断`CTX-LIMIT-001`のバイト上限は、指定した`--detail`にかかわらず、詳細度`standard`の提示の量で測る（安全な入出力 §4の
  「ContextのSemantic IRと標準提示」、`SINGLE-049`）。
- コンテキストのハッシュ値の材料の`settings.commands`と`verifyTimeouts`は、目的`verify`でテスト割当てを収録した場合だけ置く（`SINGLE-054`）。
- Markdownでの提示の文書ごとの節では、`untrustedText`を`frontmatter`の後、`bodyText`の前に出す（`SINGLE-104-01`。`context`仕様 §9.6の表の並びとは異なる）。
- `--detail compact`のJSONでは、すべての文書を提示形式`reference`とする。fixtureがなく未検証である。
- `standard`では、距離が2以上で、役割が`requirement`の文書を提示形式`full`のままとする（仕様は「間接constraint/refinementをnormative」とだけ定める）。
- `reachedBy`の`<relation>:<source-id>`の`source-id`は、関係を宣言した文書のIDとする（`SINGLE-107-01`、`108-01`）。
- 明示対象の`check`では、状態遷移、承認済み要求の保護、影響候補を、完全検査の対象の文書だけに適用し、管理済みの仕様文書の削除は報告しない。
- 診断`SPEC-GIT-DEGRADED-001`は、引数なしの`check`の縮退だけで返し、明示した`--full`では返さない（安全な入出力 §8）。
- 承認済み要求の保護で比較する規範文の意味は、意味中間表現の`actor`、`activation`、`modality`、`reason`、`operation`、`extensions`とする。
- 影響候補の出発点は、Gitの変更パスから直接写像される`.spec/`配下のREQまたはTECHだけとする。

Step 3のCoreが後続Stepへ残した暫定実装は次のとおりである。

- `verify`の本体と`verify --report`は未実装である。
- 複合ワークスペース（修飾ID、`--all-workspaces`、`resolution.workspaces`）は未実装である。

## 2026-09-25: Step 4

コミット`cac5b0818dd82de0a86e2aac5e93464bf39f7e4c`に対して`uv run tests/bitz-core/certify_gate_b.py --step 4`を実行し、
`gateB: {"step": 4, "result": "Passed"}`、エラー0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1〜4の完了fixture 250件（Step 4は`SINGLE-055`〜`069`、`070-03`〜`04`、`071-03`〜`04`、`104-03`、`105-02`、`106-04`〜`05`、`107`〜`108`、`110`、`111-04`、`112`〜`113`、`125-04`、`126`、`127-08`〜`10`）と、`parserChecks` 4件 |
| 参照harness | 2つのクローンで250件すべて`passed`。所要時間と検査対象のパスを除いた結果のSHA-256は両方`9f5072973618ee24d2d0aec7e3f2608a3925cf43cf2ceee26727cb40d4be91b7` |
| 構文解析器のアダプター | 2つのクローンで終了コード0、標準出力が一致（Step 2から変化なし） |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

Core固有の単体試験は432件がすべて成功した。プロセスの出力の伏せ字化は、秘密情報を含む入力を、ランダムな300通りと全バイト位置の
2分割でチャンクへ分けて与え、一括投入と同じ結果になり、秘密情報が残らないことを確かめた。10 MiBの出力でも、伏せ字化のメモリのピークが
5 MB未満に収まる（出力総量に比例しない）。タイムアウト系のfixtureの後に、子孫プロセスが残らないことも確かめた。

実装計画 §9の「Coreが自分自身をcheck・verifyできる状態」について、リポジトリのルートの`.spec/`のREQ-001とREQ-002を
一時的に`approved`へ変えた複製で`bitz verify`を実行し、両方の検証対象が`passed`（テスト割当て1件、試験83件）となることを確かめた。
現在のREQはいずれも`draft`であり、`approved`への変更は人間の確認を待つ。

仕様の記述だけでは一意に決まらず、実装で次のとおり解釈した。

- プロセスの起動前に遮断したテスト割当ての診断の置き場所は、診断レジストリの継続単位で分ける。継続単位`skip-target`の条件
  （`VERIFY-BINDING-MISSING`）は検証対象の`diagnostics`へ、継続単位`skip-binding`の条件は最上位の`diagnostics`へ置く
  （`SINGLE-061`、`126-08`、`126-09`）。
- 1つの検証対象にテスト割当て不足の原因が複数あっても、最初の1件だけを返し、その検証対象の`contextDigest`を`null`とする（`SINGLE-061`）。

Step 4のCoreが後続Stepへ残した暫定実装は、複合ワークスペース（`--all-workspaces`、修飾ID、`resolution.workspaces`）だけである。

## 2026-09-25: Step 5（未認定時点の記録）

下表の6件と2件は、同日にfixtureを規範文へ訂正して解消した（次節）。

状態は`In progress`である。2026-09-25時点でStep 1〜5の完了条件310件のうち304件がCoreで通過する
（コミット`29c5006`、`uv run fixtures/run_conformance.py --core plugins/bitz-core --step 5`）。
残る6件は、fixtureと規範文が食い違うため、Coreを規範文どおりに実装すると通過しない。
[ADR-051](../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)により、訂正には人間の管理者の承認を要する。

| fixture | 食い違い |
|---|---|
| `MULTI-020-09`、`020-10` | 生成器が1つの`relations.requires`へ同じIDを最大1,000回並べる。文書・フロントマター・状態仕様 §11は、配列の重複を診断`SPEC-FM-SCHEMA-001`とするが、fixtureは`passed`を期待する |
| `MULTI-020-15`、`020-16`、`021-08` | 生成したTECHのフロントマターが最大64,758バイトで、安全な入出力 §4のフロントマターの上限32 KiBを超える。fixtureはテスト割当ての実行、または`verifyBindingCount`の超過を期待する |
| `MULTI-012` | 期待する`EAI-CORE-ID-002`の`line`が見出し行（13行目）を指し、要約も、同じ条件の`SINGLE-011`（2回目の出現位置、「規範文IDが重複しています」）と異なる |

次の2件は、Gate A認定済みのfixtureどうし、またはfixtureと規範文が食い違うが、Coreをfixtureへ合わせて通過させている。

- `multiWorkspace.maxMembers`: 複合ワークスペース仕様 §2は、既定20の実効上限を超えれば`blocked`とするが、`MULTI-020-01`〜`02`は
  `maxMembers`を省略したまま、メンバー数99と100でそれぞれ`passed`を期待し、`MULTI-021-01`は上限100で遮断を期待する。
  Coreはメンバー数を、絶対上限100だけで判定する。
- ファイル名のIDが不一致の文書の`checkedDocumentCount`: `SINGLE-014`は0、`MULTI-011`のメンバーの結果は1を期待する。

## 2026-09-25: Step 5

前節の食い違いは、管理者の承認を得てfixtureを規範文へ訂正し（`f6cfebb`、Gate A再認定は
[適合fixture検証記録](../../fixtures/conformance/適合fixture検証記録.md)）、Coreを、メンバー数の実効上限と
スキップした文書の件数について追従させた（`12ec48e`）。fixtureの訂正とCoreの変更は別のコミットにした。

コミット`12ec48e4b754efc9a87bde24f13155c2935c802a`に対して`uv run tests/bitz-core/certify_gate_b.py --step 5`を実行し、
`gateB: {"step": 5, "result": "Passed"}`、エラー0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1〜5の完了fixture 310件（Step 5は`MULTI-*`の60件）と、`parserChecks` 4件 |
| 参照harness | 2つのクローンで310件すべて`passed`。所要時間と検査対象のパスを除いた結果のSHA-256は両方`0e3ab7041c5769e4856706042aa0207edce7308421a53833378e03d066c6574d` |
| 構文解析器のアダプター | 2つのクローンで終了コード0、標準出力が一致（Step 2から変化なし） |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

Core固有の単体試験は508件がすべて成功した。複合ワークスペースのgoldenのハッシュ値（`MULTI-002-01`）は、fixture側の参照計算を
読まずに仕様から独立に実装して一致した。`PYTHONHASHSEED`の2つの値でも同じ結果になる。入力のバイト数268,435,456の境界
（`MULTI-020-06`）で、Coreの`Maximum resident set size`は約226 MiBだった（複合ワークスペース仕様 §10.1の目標1 GiB以下）。

生成fixture（`resultDigest`）の期待結果は、独立実装の規則のもとでは文面を知る手段がないため、司令塔がfixture側のレビュー済みの参照計算から
再構成し、ハッシュ値の一致を確かめたうえで、作業者へ期待値として渡した（計算手順ではなく期待値の扱い）。

仕様の記述だけでは一意に決まらず、実装で次のとおり解釈した。

- `bitz.compat`の`migration`は、準備手順で適用済みの変更集合が、原子的な複合ワークスペース化または完全なロールバックに
  なっているかを、読取り専用で検証する（fixtureの副作用の期待値が`read-only`であるため）。`to-multi-workspace`は基準版と比較しない。
- `consumer result-shape`は、最上位の`workspace`と、`multiWorkspace`／`workspaces`の有無だけで、排他的な外形を判定する。
- `verify --all-workspaces`は、`commandDefinitionCount`の上限を実行計画が確定した後に判定し、`verifyBindingCount`と同時に
  超過した場合は`verifyBindingCount`を報告する（コマンドの起動前）。

## 2026-09-26: Step 1〜5の再判定

Step 2〜5の節に残した実装時の仕様解釈を、2026-09-25に管理者が承認した方針で規範文へ明記し（`e0793b5`、ADR-054を含む）、
fixtureを追従させ（`235f329`、Gate A再認定は[適合fixture検証記録](../../fixtures/conformance/適合fixture検証記録.md)）、
Coreを追従させた（`ac48fa0`）。Gate Bが`Passed`のStepに属するfixtureを変えたため、ADR-051によりStep 1〜5を判定し直した。
これにより、各節の「仕様側の明確化を要する候補」はすべて規範文に反映済みである。

コミット`ac48fa0dca0bc8ca1ed65b2ee21a88acfcb41d4d`に対して`uv run tests/bitz-core/certify_gate_b.py --step 5`を実行し、
`gateB: {"step": 5, "result": "Passed"}`、エラー0件を得た。Step nのGate BはStep 1からnまでを累積して判定するため、
この結果はStep 1〜5の再判定を兼ねる。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1〜5の完了fixture 318件（追加した`SINGLE-106-06`〜`07`、`128`〜`133`と訂正した`SINGLE-061`を含む）と、`parserChecks` 4件 |
| 参照harness | 2つのクローンで318件すべて`passed`。所要時間と検査対象のパスを除いた結果のSHA-256は両方`77b2f92060330ffff17ccd39ce1acbc04af2b2c519af2d5484a7306a92d5235a` |
| 構文解析器のアダプター | 2つのクローンで終了コード0、標準出力が一致 |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

Core固有の単体試験は517件がすべて成功した。

## 2026-09-26: 簡易フローの実証を行った後の確認

簡易フローの実証（TASK-001、REQ-003）で`reportio.py`を変更した（`ce75f5f`）ため、Step 1〜5を確認した。
コミット`09dbb451dae49fa2dc1e6e844f4c98cfbb5ee30f`に対して`uv run tests/bitz-core/certify_gate_b.py --step 5`を実行し、
`gateB: {"step": 5, "result": "Passed"}`、エラー0件を得た。2つのクローンで318件すべて`passed`、結果のSHA-256は両方
`77b2f92060330ffff17ccd39ce1acbc04af2b2c519af2d5484a7306a92d5235a`（前回と同じ）。構文解析器のアダプターも2つのクローンで一致した。

## 2026-09-27: 複合ワークスペース全体の`doctor`を実装した後のStep 1〜5の再判定

`MULTI-026-01`〜`02`の追加に伴い、従来は未実装のまま終了していた`doctor --all-workspaces`に、次を実装した。
ルートワークスペースと全メンバーのワークスペースに固有の検査、メンバーをID順に並べた結果、
非成功の後も処理を継続すること、最上位の状態の集約、テキスト出力の集計である。
fixtureを追加した後、Coreを追従させる前に、新規の2件が0件`passed`であることを確認した。追従させた後には、2件とも`passed`となった。

コミット`1b64033862841b9547dcb4048fe693a60638300c`に対して
`uv run tests/bitz-core/certify_gate_b.py --step 5`を実行し、
`gateB: {"step": 5, "result": "Passed"}`、エラー0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1〜5の完了fixture 320件（`MULTI-026-01`〜`02`を含む）と、`parserChecks` 4件 |
| 参照harness | 2つのクローンで320件すべて`passed`。所要時間と検査対象のパスを除いた結果のSHA-256は両方`669f222ae310eac0e86dd6b2ffda163ec49dbfe152f0d25c84c5961ead324a38` |
| 構文解析器のアダプター | 2つのクローンで終了コード0、標準出力が一致 |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

Core固有の単体試験は549件がすべて成功した。

## 2026-10-05: 先行TASKが完了済みのTASKの`implement`を直した後のStep 1〜5の再判定

目的`implement`でTASKを起点にしたとき、`requires`する先行TASKが`done`でも`CTX-STATE-001`で止めていた欠陥を直し
（`targetexpand.py`。`done`のTASKを止めるのは起点にした場合だけ）、これを固定する`SINGLE-134`（Step 3）を追加した。
fixtureを追加した後、修正前のCoreでは`SINGLE-134`が`blocked`／終了コード2（`CTX-STATE-001`）で失敗し、修正後のCoreでは`passed`となることを確かめた。

コミット`283bf33b4634f227d74316b5b3ebbd04f398583a`に対して
`uv run tests/bitz-core/certify_gate_b.py --step 5`を実行し、
`gateB: {"step": 5, "result": "Passed"}`、エラー0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1〜5の完了fixture 321件（`SINGLE-134`を含む）と、`parserChecks` 4件 |
| 参照harness | 2つのクローンで結果が一致した。所要時間と検査対象のパスを除いた結果のSHA-256は両方`2f2806785f93c39cb3bbbe60a4c4f8cd3e2aed5efdbcbc8256f39496d5522e84` |
| 構文解析器のアダプター | 2つのクローンで一致 |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

Core固有の単体試験は578件がすべて成功した。

## 2026-10-05: 具体化文書の提示形式を直した後のStep 1〜5の再判定

距離2以上の具体化文書を、所有する規範文が制約台帳になくても提示形式`normative`にしていた欠陥を直し（`context.py`。
`normative`にするのは所有する規範文がすべて制約台帳に収録される具体化文書だけ）、これを固定する`SINGLE-135`と`SINGLE-136`（Step 3）を追加した。
fixtureを追加した後、修正前のCoreでは2件が`normative`を返して失敗し、修正後のCoreでは2件とも`passed`となることを確かめた。

コミット`d7b91a57c096a4a393aeae750dac9197418087e4`に対して
`uv run tests/bitz-core/certify_gate_b.py --step 5`を実行し、
`gateB: {"step": 5, "result": "Passed"}`、エラー0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1〜5の完了fixture 323件（`SINGLE-135`と`SINGLE-136`を含む）と、`parserChecks` 4件 |
| 参照harness | 2つのクローンで結果が一致した。所要時間と検査対象のパスを除いた結果のSHA-256は両方`247d53070dadd839e831f084f9485fa2d52fcf6120a7d617b3cf7004a76354c6` |
| 構文解析器のアダプター | 2つのクローンで一致 |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

Core固有の単体試験は583件がすべて成功した。

## 2026-10-05: 目的verifyでの先行TASKの検査を直した後のStep 1〜5の再判定

目的`verify`でTASKを起点にしたとき、先行TASKが`done`でなくても検査せずに通していた欠陥を直し（`targetexpand.py`。
`CTX-TASK-DEPENDENCY-001`を目的`implement`と`verify`の両方で返す）、これを固定する`SINGLE-137`と`SINGLE-138`（Step 4）を追加した。
fixtureを追加した後、修正前のCore（コミット`a869bbc7`の版）では`SINGLE-137`が`passed`／終了コード0で失敗し、`SINGLE-138`は修正の前後とも
`passed`となることと、修正後のCoreでは2件とも`passed`となることを確かめた。

コミット`588e3b1e4d54af0925d913e8262b93f2bc95bbc6`に対して
`uv run tests/bitz-core/certify_gate_b.py --step 5`を実行し、
`gateB: {"step": 5, "result": "Passed"}`、エラー0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1〜5の完了fixture 325件（`SINGLE-137`と`SINGLE-138`を含む）と、`parserChecks` 4件 |
| 参照harness | 2つのクローンで結果が一致した。所要時間と検査対象のパスを除いた結果のSHA-256は両方`d3c827d01412b450df4c205eb2f1daa4594527afdc3ece9a09b2c50c861671c5` |
| 構文解析器のアダプター | 2つのクローンで一致 |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

Core固有の単体試験は587件がすべて成功した。

## 2026-10-06: 文書の距離を最短にした後のStep 1〜5の再判定

文書の距離を、閉包を作るときに辿ったエッジ1本を1段とした起点からの最短の段数にし（`targetexpand.py`。置換済みの起点の後継は距離1）、
これを固定する`SINGLE-139`〜`141`（Step 3）を追加した。修正の前後で、既存の325件の期待値はすべて変わらないことを確かめた。
fixtureを追加した後、修正前のCore（コミット`5d4ab90c`の1つ前の版）では3件とも失敗し（差異は並び順と提示形式だけで、コンテキストのハッシュ値と
診断は一致する）、修正後のCoreでは3件とも`passed`となることを確かめた。

コミット`e734456fc6bea6661619bb85d0d3f7d3323fa580`に対して
`uv run tests/bitz-core/certify_gate_b.py --step 5`を実行し、
`gateB: {"step": 5, "result": "Passed"}`、エラー0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1〜5の完了fixture 328件（`SINGLE-139`〜`141`を含む）と、`parserChecks` 4件 |
| 参照harness | 2つのクローンで結果が一致した。所要時間と検査対象のパスを除いた結果のSHA-256は両方`414feb812703e35006595a6245a02fe0f3a8c6c2ee69fe72d1eaa1074a46daae` |
| 構文解析器のアダプター | 2つのクローンで一致 |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

Core固有の単体試験は595件がすべて成功した。

## 2026-10-06: 目的implementとverifyで状態draftの文書を含めないようにした後のStep 1〜5の再判定

目的`implement`と`verify`では、閉包の文書を`refines`する状態`draft`の文書を閉包へ含めないようにし（`targetexpand.py`）、これを固定する
`SINGLE-142`（Step 3）と`SINGLE-143`（Step 4）を追加した。修正の前後で、既存の328件の期待値はすべて変わらないことを確かめた。
fixtureを追加した後、修正前のCore（コミット`90ba92a3`の版）では2件とも失敗し、修正後のCoreでは2件とも`passed`となることを確かめた。

コミット`b3b14b113312089505eaea845bf5d9c438370509`に対して
`uv run tests/bitz-core/certify_gate_b.py --step 5`を実行し、
`gateB: {"step": 5, "result": "Passed"}`、エラー0件を得た。

| 項目 | 結果 |
|---|---|
| 対象 | Step 1〜5の完了fixture 330件（`SINGLE-142`と`SINGLE-143`を含む）と、`parserChecks` 4件 |
| 参照harness | 2つのクローンで結果が一致した。所要時間と検査対象のパスを除いた結果のSHA-256は両方`bbdedfa655f1f4d9717c9d1088a146d76ef248dc7d973f3ca22a385d9a187fe5` |
| 構文解析器のアダプター | 2つのクローンで一致 |
| 実行環境 | CPython 3.12.3、uv 0.11.28（x86_64-unknown-linux-gnu）、git 2.43.0、Linux x86_64 |

Core固有の単体試験は597件がすべて成功した。
