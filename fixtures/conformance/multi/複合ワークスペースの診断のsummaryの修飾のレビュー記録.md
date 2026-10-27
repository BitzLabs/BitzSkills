# 複合ワークスペースの診断のsummaryの修飾のfixtureのレビュー記録

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-047-01`〜`MULTI-047-05`を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/multi_qualified_summary_fixtures.py`である。

## 追加の理由

複合ワークスペースの次の`summary`は、作業ワークスペース（起点を所有するワークスペース）の文書IDと規範文IDを修飾せず、他のメンバーのIDだけを修飾していた。
同じ出力の中で修飾の有無が混在し、すでに修飾していた`CTX-STATE-SUPERSEDED-*`（`MULTI-038-20`）や、`verify`の`CTX-COVERAGE-TEST-001`とも食い違った。
実装の確認事項C47・C65に対応する。

- `CTX-STATE-001`（起点または強い関係の参照先が目的に適用できない）の`summary`
- `CTX-TASK-DEPENDENCY-001`（先行するTASKが未完了）の`summary`と`suggestedAction`
- `context`の`CTX-COVERAGE-TASK-001`と`CTX-COVERAGE-TEST-001`の`summary`

`MULTI-038`のレビュー記録の「複合ワークスペースの診断の`summary`に書く文書IDの形」は、ほかの診断の`summary`の修飾を確認事項C47としていた。
この群は、それを確定して固定する。文型（文言のひな形、`messages.py`）は変えず、差し込む値の形だけが変わる。単一ワークスペースの出力は変わらない。
既存のfixtureの入力と期待値は変えない（既存の複合ワークスペースのfixtureに、この4つの診断を期待値に持つものはなかった）。

## 根拠の規範文と決定

- 複合ワークスペース仕様 §4・§6: 複合ワークスペース内で実行したCore操作の文書`id`、規範文ID、`roots`は、複合ワークスペースの正規形式（修飾ID）で返す。
- 表記規則 §3.5の6・7: 差し込む値はそのまま差し込み、同じ条件IDの診断は操作によらず同じ文型にする。
- **`summary`の中のIDの形は規範文で1つに決まらない。** ADR-062により、これは管理者が承認した値である。ユーザーの決定（2026-10-26）で、すでに修飾している
  `CTX-STATE-SUPERSEDED-*`と`verify`の`CTX-COVERAGE-TEST-001`にそろえ、作業ワークスペースのIDも`<ワークスペース>::`で修飾する
  （[Coreの出力文言のレビュー記録](../Coreの出力文言のレビュー記録.md)の2026-10-26の節）。
- 結果・診断・終了コード §7: 診断の並びは、発生元のワークスペースID、`path`、`line`、`column`、`code`、`specRefs`の辞書順で、すべて同じものは生成元の宣言に現れた順。
- 関係・トレースモデル §6.2: 起点のTASKの`requires`が直接指すTASKがすべて状態`done`でなければ`blocked`（`CTX-TASK-DEPENDENCY-001`）。検査するのは直接の先行TASKだけ。
  同 §6.1・§6.2・§7: 目的`implement`の対象規範文は、起点と具体化文書の規範文。文書は距離、種別、修飾IDの順に並べる。
- 診断レジストリ: `CTX-STATE-001`と`CTX-TASK-DEPENDENCY-001`は`blocked`（終了コード2）、`CTX-COVERAGE-TASK-001`と、目的`implement`の`MUST`の`CTX-COVERAGE-TEST-001`は
  `passed_with_warnings`（終了コード0）。
- コンテキストのハッシュ値の正規化仕様 §3: `MULTI-047-03`の`contextDigest`は、独立に書いた2系統の参照計算のバイト列の一致を要求する。

## 入力と起動

基本のリポジトリは、ルート`platform`（`.`）とメンバー`api`（`services/api`）で、すべてコミットし、`--format json`で起動する。
文書はすべてREQ・TECH・TASKで、規範文は`MUST`1件、テスト対応は持たない（コマンドの定義も置かない）。

| fixture | 実行ディレクトリと引数 | 文書 | 結果 |
|---|---|---|---|
| `MULTI-047-01` | `.`、`context REQ-001 --purpose implement` | `platform::REQ-001`（状態`draft`）だけ | `blocked`／2 |
| `MULTI-047-02` | `.`、`context TASK-002 --purpose implement` | `platform`: REQ-050、TASK-001（`open`）、TASK-002（`open`、`requires: [TASK-001, api::TASK-100]`）。`api`: REQ-101、TASK-100（`open`）。TASKは各自のREQの規範文を`addresses` | `blocked`／2 |
| `MULTI-047-03` | `.`、`context REQ-050 --purpose implement --detail compact` | `platform::REQ-050`（`approved`）。`api::TECH-100`（`approved`）が`platform::REQ-050:AC-01`を`refines`。TASKもテスト対応もない | `passed_with_warnings`／0 |
| `MULTI-047-04` | `.`、`context REQ-004 --purpose implement` | `platform`: REQ-004（`approved`、`requires: [REQ-003, api::REQ-100]`）、REQ-003（`draft`）。`api`: REQ-100（`draft`） | `blocked`／2 |
| `MULTI-047-05` | `services/api`、`context TASK-101 --purpose implement` | `platform`: REQ-050、TASK-001（`open`）。`api`: REQ-101、TASK-100（`open`）、TASK-101（`open`、`requires: [TASK-100, platform::TASK-001]`） | `blocked`／2 |

`01`以外は、作業ワークスペースのIDと他のメンバーのIDが、同じ出力に出る。これにより、修飾がそろっていること（片方だけが修飾されないこと）を、1つの結果で固定する。
`01`は、作業ワークスペースのIDだけが出る最小の入力である。

## 期待値の導き方（Coreの出力を根拠にしない）

1. **診断の文言**。`reference_blocked`と`reference_coverage_diagnostics`が、入力の木構造から診断を導く。リテラルの期待値（`EXPECTED_DIAGNOSTICS`）がこの結果と一致することを要求する。
   - 状態の診断（`01`、`04`）: 起点がTASKでなければ、起点と`requires`で到達した文書のうち、状態`approved`でないもの。
   - 先行TASKの診断（`02`、`05`）: 起点のTASKが状態`open`で、`requires`が直接指すTASKのうち、状態`done`でないものごと。`suggestedAction`は同じ参照先を使う。
   - カバレッジの診断（`03`）: 対象規範文のうち、未対応なら`CTX-COVERAGE-TASK-001`、未テストなら`CTX-COVERAGE-TEST-001`。規範強度は規範文から読む。
   - 差し込むIDは、すべて`<ワークスペース>::<ID>`の形（修飾ID）。ひな形は変えない。
2. **診断の並び**。`02`と`05`は、発生元（起点のTASKの`relations.requires`）とコードが同じなので、宣言の順（`02`は`platform::TASK-001`、`api::TASK-100`の順。`05`は`api::TASK-100`、`platform::TASK-001`の順）。
   `03`と`04`は、発生元のワークスペースIDの辞書順（`api`が`platform`より前）。`03`は同じ発生元の中でコードの辞書順（`CTX-COVERAGE-TASK-001`、`CTX-COVERAGE-TEST-001`）。
3. **状態で止まる結果の形**。`SINGLE-159`・`SINGLE-051`と同じく、閉包を作らず、`contextDigest: null`、`resolution.complete: false`、`documents`と制約台帳は空、カバレッジは空。
   コミットのある準備手順なので、`revision`は`{commit, dirty: false}`（`SINGLE-166-05`、`MULTI-038-08`と同じ）。`roots`は修飾ID、`workspace`は作業ワークスペース。
4. **`MULTI-047-03`の閉包とカバレッジ**。`reference_order`・`reference_targets`・`reference_coverage`（`multi_context_order_fixtures`）が、入力の木構造から文書、対象規範文、対応済み・テスト済みを導く。
   文書は`platform::REQ-050`（`root`）、`api::TECH-100`（`refinement`、`reachedBy`は`refines:api::TECH-100`）。対象規範文は`platform::REQ-050:AC-01`、`api::TECH-100:C-01`。
   2件とも未対応・未テストで、診断は4件（上の並び）。横断するエッジは`api::TECH-100` → `platform::REQ-050:AC-01`（`refines`）の1件。
5. **ハッシュ値**（`MULTI-047-03`）。独立に書いた2系統の参照計算の正規JSONのバイト列の一致を要求する。A（`reviewed_digest_input`）は文書ごとの材料を表からリテラルで書き、
   B（`multi_closure_alias_fixtures.derived_material`）は入力の木構造から導く。
6. **欠陥を検出できる入力であること**（陰性対照の構成）。`reference_blocked`と`reference_coverage_diagnostics`は、`qualify_active=False`で修正前の書き方
   （作業ワークスペースのIDを修飾しない）を再現する。`check_conditions`が、その`summary`が期待する`summary`と異なること、
   `01`以外では、診断の文に作業ワークスペースと他のメンバーの両方のIDが現れることを要求する。

## 陰性対照（修正前のCoreでの実測）

修正前のCore（コミット`7fca47d3`の`plugins/bitz-core`）で、`run_conformance.py --step 5`を実行した。

全526件（既存の521件と追加の5件）の結果は`passed` 521件、`failed` 5件、`error` 0件で、失敗した5件は`MULTI-047-01`〜`05`だけである（既存の521件はすべて通過する）。
修正後のCore（コミット`028cb928`）では526件がすべて通過する。失敗した差分は`summary`と`suggestedAction`の作業ワークスペースのIDの修飾だけで、
診断の件数、並び、`code`、`source`、`resultStatus`、結果の状態、終了コード、`contextDigest`は同じである（`MULTI-047-03`の`contextDigest`も修正の前後で同じ値になる）。

| fixture | 修正前のCore | 差分（期待 → 実際） |
|---|---|---|
| `MULTI-047-01` | 失敗 | `summary`: `platform::REQ-001は状態draft…` → `REQ-001は状態draft…` |
| `MULTI-047-02` | 失敗 | 1件目の`summary`と`suggestedAction`: `先行するplatform::TASK-001…` → `先行するTASK-001…`（2件目の`api::TASK-100`は修飾済みで同じ） |
| `MULTI-047-03` | 失敗 | `platform`の2件の`summary`: `MUST platform::REQ-050:AC-01` → `MUST REQ-050:AC-01`（`api::TECH-100:C-01`の2件は修飾済みで同じ） |
| `MULTI-047-04` | 失敗 | 2件目の`summary`: `platform::REQ-003は状態draft…` → `REQ-003は状態draft…`（1件目の`api::REQ-100`は修飾済みで同じ） |
| `MULTI-047-05` | 失敗 | 1件目の`summary`と`suggestedAction`: `先行するapi::TASK-100…` → `先行するTASK-100…`（2件目の`platform::TASK-001`は修飾済みで同じ） |

修正前のCoreは、他のメンバーのIDだけを修飾し、作業ワークスペースのIDは修飾しなかった。`02`〜`05`は、同じ出力の中で修飾の有無が混在していた。

## 規範から導けなかった点・固定の程度

- `summary`と`suggestedAction`の中のIDの形。上の「根拠の規範文と決定」のとおり、規範文は1つに定めない。管理者の決定（`<ワークスペース>::`で、作業ワークスペースも修飾する）で固定した。
- 状態の診断で止まった結果の`resolution.workspaces`と`crossWorkspaceEdges`。規範（`context` §4、複合ワークスペース仕様 §6）は到達ワークスペースの定義を書くが、
  閉包を作る前に止まった結果の値を定めない。強い関係の失敗の既存のfixture（`MULTI-038-08`、`MULTI-027-01`。`MULTI-027-01`は他のメンバーの文書へ到達しても起点ワークスペースだけを置く）と同じ、
  起点ワークスペースだけ・横断するエッジなしを置いた。`MULTI-047-04`のように、他のメンバーの文書が原因でも同じである。
- 複数の先行TASKが未完了のときの件数。関係・トレースモデル §6.2は「すべて状態`done`でなければ`blocked`」とだけ書き、診断の件数を定めない。
  既存のfixture（`SINGLE-051`、`SINGLE-144`）は先行TASKが1件の入力だけを固定する。この群は、未完了の先行TASKごとに1件を返すと読み、`02`・`05`で2件を固定した。
  1件にまとめる読みを取るなら、この2件の期待値を管理者の承認を得て直す。
- 同じ原因の診断が複数あるときの並び。結果・診断・終了コード §7の規則（発生元、`code`、宣言の順）で定まる。
- 状態の診断の発生元。依存先が原因のとき（`04`）、発生元を依存先の文書にする読みで固定した（`SINGLE-148`の`CTX-STATE-001`と同じ）。

この群の範囲外とするもの。

- `verify`の`CTX-STATE-001`・`CTX-TASK-DEPENDENCY-001`の複合ワークスペースでの修飾（単体試験`tests/bitz-core/test_multi_summary_qualified_ids.py`で固定している）。
- テキスト形式・Markdown形式の出力。この群はJSONだけを固定する。
- 単一ワークスペースの対照。修飾しない形は、既存の`SINGLE-051`、`SINGLE-144`、`SINGLE-159`、`SINGLE-142`などが固定している。
