# 複合ワークスペースのcontextの並びのfixtureのレビュー記録

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-042-01`〜`MULTI-042-03`を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/multi_context_order_fixtures.py`である。

## 追加の理由

複合ワークスペースの`context`は、`documents`・`constraintLedger.statements`・`coverage`の各配列の並びで、起点ワークスペースの文書と規範文を
修飾しない内部のID（`TECH-005`）のまま辞書順に比べていた。他のメンバーの文書は修飾したID（`api::TECH-010`）で比べるので、
同じ距離・同じ種別の文書が、出力のID（修飾ID）の辞書順と食い違って並んだ（大文字の`T`が小文字の`a`より前）。
実装の確認事項C46に対応する。ルート`platform`のREQ-001を、`platform`のTECH-005、`api`のTECH-010、`web`のTECH-010が距離1で具体化すると、
修正前は`platform::TECH-005`、`api::TECH-010`、`web::TECH-010`の順、規範は`api::TECH-010`、`platform::TECH-005`、`web::TECH-010`の順になる。
目的`implement`では制約台帳と`coverage`の配列も同様である。コンテキストのハッシュ値は並びの影響を受けない
（材料の文書は別に修飾IDの順で作る。正規化仕様 §3の「提示の順は材料に含めない」）。

`MULTI-038-07`は、並びが分かれる入力を避けていた（`MULTI-038`のレビュー記録の「同じ距離の文書の並び」）。
この群は、その入力を固定する。既存の477件の入力と期待値は変えない。

## 根拠の規範文

- 複合ワークスペース仕様 §6: 「`documents`、制約台帳、カバレッジの並び（関係・トレースモデル §7の6.の文書の並びと7.の規範文の並び）の『IDの辞書順』と『IDの順』は、出力する修飾IDで比べる」。
- 関係・トレースモデル §7の6.: 「最短距離、種別の順REQ／TECH／ADR／TASK、IDの辞書順で並べる」。距離は、起点を所有する文書を0とし、閉包を作るときに
  辿ったエッジ1本を1段とした、起点からの最短の段数。7.: 規範文を文書順、行番号、IDの順で並べる。
- 同 §6.4: `targetStatements`は`contextDocuments`の順、行番号、IDの順。§8: カバレッジの対象規範文の集合は`targetStatements`だけから得る。
  `requires`の参照先の規範文は`targetStatements`へ昇格しない（§6.4の4.）。
- 同 §6.1・§6.2: 目的`interpret`は、起点を所有する文書からの`requires`、起点またはその規範文を`refines`する適用可能な文書（推移的）を含め、
  TASKを自動で追加しない。目的`implement`は、さらに対象規範文を`addresses`する状態`open`のTASKを含める。
- 複合ワークスペース仕様 §4・§6: 複合ワークスペースの各文書ID、規範文ID、エッジのIDは修飾IDで出力する。
- `context` §5: `documents[]`は上の順で出力する。`constraintLedger`と`coverage`は`TargetExpansion`の対象規範文の順を保つ。
  詳細度`compact`は全文書を提示形式`reference`にし、ハッシュ値を変えない。
- コンテキストのハッシュ値の正規化仕様 §3: 閉包の文書ごとの材料。提示の順は材料に含めず、文書は修飾IDの順に置く。

## 入力と起動

基本のリポジトリは、ルート`platform`（`.`）、メンバー`web`（`apps/web`）と`api`（`services/api`）で、すべてコミットし、`--format json --detail compact`で起動する。
`platform`はテスト対応のコマンドを持つ（カタログの設定へ`verify.commands`を足す）。

| 文書 | 関係と規範文 |
|---|---|
| `platform::REQ-001` | `requires: [web::REQ-003]`。規範文`AC-01`。テスト対応あり |
| `platform::TECH-005` | `refines: [REQ-001:AC-01]`（距離1）。規範文`C-01`。テスト対応あり |
| `platform::TECH-002` | `refines: [TECH-005:C-01]`（距離2）。規範文`C-01`。テスト対応あり |
| `platform::TASK-001` | 状態`open`。`addresses: [REQ-001:AC-01, TECH-005:C-01, TECH-002:C-01]` |
| `api::TECH-010` | `refines: [platform::REQ-001:AC-01]`（距離1）。規範文`C-01`。テスト対応あり |
| `api::TECH-020` | `refines: [platform::TECH-005:C-01]`（距離2）。規範文`C-01`。テスト対応あり |
| `api::TASK-001` | 状態`open`。`addresses: [platform::REQ-001:AC-01, TECH-010:C-01, TECH-020:C-01, web::TECH-010:C-01]` |
| `web::REQ-003` | 関係なし。規範文`AC-01`（`requires`で到達するだけ） |
| `web::TECH-010` | `refines: [platform::REQ-001:AC-01]`（距離1）。規範文`C-01`。テスト対応あり |

| fixture | 実行ディレクトリと引数 | 結果 |
|---|---|---|
| `MULTI-042-01` | `.`、`context platform::REQ-001 --purpose interpret --detail compact` | `passed`／0 |
| `MULTI-042-02` | `.`、`context platform::REQ-001 --purpose implement --detail compact` | `passed`／0 |
| `MULTI-042-03` | `.`、`context REQ-001 --purpose implement --detail compact`（単一。ID`root`）。REQ-001を、TECH-005とTECH-010（距離1）が`refines`し、TECH-002（距離2）がTECH-005を`refines`する。TASK-001が4件の規範文を`addresses` | `passed`／0 |

TASKの`addresses`は、どちらも起点の規範文`REQ-001:AC-01`を含める。TASKの距離は、起点の規範文を直接`addresses`するので1になる
（具体化文書の規範文だけを`addresses`するTASKの距離は、この群では固定しない）。

## 期待値の導き方（Coreの出力を根拠にしない）

1. **文書の並び**。`reference_order`が、`multi_closure_alias_fixtures.interpret_closure`で入力の木構造から閉包と距離を導き、(距離, 種別の順, 修飾ID)で並べる。
   リテラルの期待する並び（`EXPECTED_DOCUMENTS`）がこの結果と一致することを要求する。
   - `MULTI-042-01`（`interpret`）: `platform::REQ-001`（距離0）、`web::REQ-003`（距離1、種別REQ）、`api::TECH-010`、`platform::TECH-005`、`web::TECH-010`（距離1、種別TECH）、
     `api::TECH-020`、`platform::TECH-002`（距離2）。
   - `MULTI-042-02`（`implement`）: 上の並びの距離1に、種別TASKの`api::TASK-001`、`platform::TASK-001`が、TECHの後ろ・距離2の前に加わる。
   - 並びの要点: 同じ距離・同じ種別のTECH 3件は出力のIDの辞書順（`api::`、`platform::`、`web::`）。`platform::TECH-002`のIDは距離1の`TECH-005`より小さいが、
     距離2なので後ろに並ぶ（距離が先）。`web::REQ-003`は`api::TECH-010`より修飾IDが大きいが、種別REQなので先に並ぶ（種別が先）。
2. **制約台帳とカバレッジ**。`reference_targets`が、起点と具体化文書（役割`refinement`）の規範文を、文書の順、行番号の順に導く。
   `reference_coverage`が、閉包のTASKが`addresses`する規範文を対応済み、閉包の文書が`covers`する規範文をテスト済みとして導き、対象規範文の順のまま並べる。
   `web::REQ-003:AC-01`は`requires`で到達しただけなので含めない。`unaddressed`と`untested`は空で、警告はない。
   対象規範文の並び（`MULTI-042-02`）: `platform::REQ-001:AC-01`、`api::TECH-010:C-01`、`platform::TECH-005:C-01`、`web::TECH-010:C-01`、`api::TECH-020:C-01`、`platform::TECH-002:C-01`。
3. **ハッシュ値**。独立に書いた2系統の参照計算の正規JSONのバイト列の一致を要求する。A（`reviewed_digest_input`）は文書ごとの材料を表からリテラルで書き、
   B（`multi_closure_alias_fixtures.derived_material`、単一ワークスペースは`digest_crosscheck.build`）は入力の木構造から導く。
   ハッシュ値は並びの修正の前後で同じ値になる（修正前のCoreの実行でも`contextDigest`の差分はない）。
4. **欠陥を検出できる入力であること**（陰性対照の構成）。`defective_order`が、修正前の比較（起点ワークスペースの文書を修飾しないIDで比べる）の並びを再現し、
   `check_conditions`が次を要求する。複合ワークスペース（`01`、`02`）では、距離1のTECHが3つのワークスペースにあり、修正前の並びが期待する並びと異なること、
   目的`implement`では対象規範文の並びも異なること。単一ワークスペース（`03`）では、修正前の比較の並びが期待する並びと同じであること（対照）。

## 陰性対照（修正前のCoreでの実測）

修正前のCore（コミット`a2ca532b`の`plugins/bitz-core`）で、`run_conformance.py --step 5`を実行した。

全480件（既存の477件と追加の3件）の結果は`passed` 478件、`failed` 2件、`error` 0件で、失敗した2件は`MULTI-042-01`と`MULTI-042-02`だけである（既存の477件はすべて通過する）。修正後のCore（コミット`77d48b73`）では480件がすべて通過する。3件の内訳は次のとおりである。

| fixture | 修正前のCore | 失敗の内容 |
|---|---|---|
| `MULTI-042-01` | 失敗 | `documents`の並びだけが異なる（`platform::TECH-005`が`api::TECH-010`の前、`platform::TECH-002`が`api::TECH-020`の前）。`contextDigest`は同じ |
| `MULTI-042-02` | 失敗 | `documents`に加えて、制約台帳の並び、`coverage.must`の`total`・`addressed`・`tested`の並びが異なる。`contextDigest`は同じ |
| `MULTI-042-03` | **通る** | 単一ワークスペースの対照。修正後も通り続けることを要求する |

## 規範から導けなかった点・固定の程度

- 「IDの辞書順」の比較の対象。関係・トレースモデル §7の6.は「IDの辞書順」と書くだけで、複合ワークスペースの起点ワークスペースの文書を
  修飾して比べるか、修飾せずに比べるかを書かない。複合ワークスペース仕様 §4・§6は、出力する文書ID・規範文ID・エッジのIDを修飾IDと定める。
  この群は、出力するID（修飾ID）の辞書順で比べる読みで固定した（実装の確認事項C46の指示）。この読みは、`MULTI-038`のレビュー記録の
  「同じ距離の文書の並び」が未確定としていた点を確定する。この読みは、その後、複合ワークスペース仕様 §6に「`documents`、制約台帳、カバレッジの並びの
  『IDの辞書順』と『IDの順』は、出力する修飾IDで比べる」と明記して確定した（同じPR）。
- 具体化文書が文書IDだけで`refines`するときの対象規範文。関係・トレースモデル §6.4の1.は「所有するすべての規範文と、それらの具体化文書が持つ規範文」と書き、
  具体化文書を「選択済みの文書または規範文を`refines`する適用可能な文書」と定める。文書ID（`refines: [REQ-001]`）だけで起点を`refines`する具体化文書の規範文が
  対象規範文に入るかは、文面から決まらない。Coreは、規範文IDで`refines`する具体化文書の規範文だけを対象規範文に入れる（文書IDだけで`refines`する文書は`documents`に含めるが、
  規範文は制約台帳に入れない）。この群は、具体化文書をすべて規範文ID（`refines: [REQ-001:AC-01]`）で宣言し、どちらの読みでも同じ期待値になる入力にした。
- 具体化文書の規範文だけを`addresses`するTASKの距離。関係・トレースモデル §7の6.の距離の数え方（辿ったエッジ1本を1段）を文字どおり読むと、
  距離1のTECHの規範文だけを`addresses`するTASKは距離2になり得る。この群は、どのTASKも起点の規範文を含めて`addresses`するので、距離が1に定まる入力にした。
- 複数の起点の統合。この群は単一の起点だけを固定する。複数の起点は単体試験（`tests/bitz-core/test_multi_context_order.py`）で固定している。
- `unaddressed`・`untested`の並び。警告（`CTX-COVERAGE-TASK-001`、`CTX-COVERAGE-TEST-001`）の`summary`が複合ワークスペースで文書IDをどう書くかを規範が定めていない
  （`MULTI-038`のレビュー記録の最後の項目と同じ）ので、警告を伴うfixtureは置かない。両配列の並びは単体試験で固定している。

この群の範囲外とするもの。

- テキスト形式の出力。この群はJSONだけを固定する。
- `check`と`verify`の出力。これらは本修正の対象外で、出力は変わらない（単体試験で対照を置く）。
