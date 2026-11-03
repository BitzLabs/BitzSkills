# 文書IDでrefinesする具体化文書の規範文のfixtureのレビュー記録

[適合fixture仕様 §6.9](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)の`SINGLE-169-01`〜`SINGLE-169-09`を扱う。
いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/document_refines_fixtures.py`である。複合ワークスペースの対は
[複合ワークスペースの文書IDでrefinesする具体化文書の規範文のレビュー記録](../multi/複合ワークスペースの文書IDでrefinesする具体化文書の規範文のレビュー記録.md)に記録した。

## 追加の理由

用語集と関係・トレースモデル §6.4は、具体化文書を「選択した文書または規範文を`refines`する適用可能な文書」とするが、規則1は規範文IDで`refines`する文書の規範文しか
対象規範文に含めないと読めた（実装の確認事項C54）。ユーザーの決定で、規則1に「起点の文書を文書IDで`refines`する適用可能な文書も具体化文書であり、その規範文を含める」と明記した。
独立レビューの指摘（H1・M1・M2）とユーザーの決定で、§6.4の具体化文書の段落に「見つけた具体化文書は選択済みの文書とし、その規範文を規範文IDで`refines`する文書と、その文書を文書IDで`refines`する文書の両方を辿る
（どの起点でも同じ）。起点の文書自身を文書IDで`refines`する文書を含めるのは規則1の場合だけ」と明記した。規則2の起点の所有文書、規則3で`addresses`する規範文のないTECH、規則5の起点は、文書IDの`refines`を辿る起点にしない。
修正前のCoreは、文書IDで`refines`するTECHを閉包に入れて本文も提示するのに、その規範文を制約台帳、カバレッジ、`verify`の対象規範文に入れなかった。
そのため`verify`は、そのTECHの未テストの`MUST`を通していた。既存のfixtureはTECHを規範文のない文書にするか規範文IDで`refines`させており、この欠陥を押さえていなかった。

## 根拠の規範文

- 関係・トレースモデル §6.4の規則1: 起点がREQ、または規範文のあるTECHの文書である場合は、その所有するすべての規範文と、それらの具体化文書が持つ規範文を含める。
  起点の文書を文書IDで`refines`する適用可能な文書も具体化文書であり、その規範文を含める。§6.4の本文: 具体化文書は推移的な具体化を終端まで辿って得る。
- 規則2: 規範文を起点にした場合は、指定した規範文と、その具体化文書が持つ規範文を含める。起点の所有文書を文書IDで`refines`する文書は含めない。
- §6.4の具体化文書の段落: 見つけた具体化文書は選択済みの文書とし、その規範文を規範文IDで`refines`する文書と、その文書を文書IDで`refines`する文書の両方を辿る（規則1・2・3で同じ）。
  文書IDの`refines`を辿る起点は、規則1の起点の文書だけで、規則2の起点の所有文書、規則3で`addresses`する規範文のないTECH、規則5の起点は辿る起点にしない。
- 規則3: TASKを起点にした場合は、そのTASKが`addresses`する規範文と、その具体化文書を含める。
- 関係・トレースモデル §6.1の4.（目的`interpret`の閉包を`implement`と`verify`が継ぐ）: 起点を所有する文書またはその規範文を`refines`する適用可能な文書を閉包へ含める。
  §6.1の末尾: 目的`implement`と`verify`は、`refines`する状態`draft`の文書を閉包へ含めない。
- `context` §4: 制約台帳は対象規範文を`id`、`documentId`、`documentRole`と意味フィールドで1回ずつ保持する。§5: 距離2以上の具体化文書は、所有する規範文がすべて
  制約台帳にあれば`normative`、1件でもなければ`full`にする。距離1の文書は`full`。
- `context` §10と診断レジストリ: 目的`implement`の対象の`MUST`が未対応なら`CTX-COVERAGE-TASK-001`、未テストなら`CTX-COVERAGE-TEST-001`は`passed_with_warnings`。
  目的`verify`の`MUST`の未テストは`blocked`。
- `verify` §8: 検証対象の`statements`は対象規範文の重複なし辞書順。コンテキストを解決できても`blocked`の検証対象は、テストを開始しない（`SINGLE-060`）。
- 結果・診断・終了コード §7: 診断は`path`、`code`の辞書順。

## 入力と起動

基本の入力は`REQ-001`（`approved`、規範文`AC-01`の`MUST`1件、テスト対応1件）と、`REQ-001`を`relations.refines: [REQ-001]`（文書ID）で具体化する`TECH-001`
（`approved`、規範文`C-01`の`MUST`1件、テスト対応なし）である。設定はコマンド`default`だけを持つ（`SINGLE-168`と同じ）。

| fixture | 操作 | 構成 | 期待 |
|---|---|---|---|
| `SINGLE-169-01` | `context REQ-001 --purpose implement` | 基本の入力 | `passed_with_warnings`／0。制約台帳と`coverage.must`に`TECH-001:C-01`が入る。診断3件 |
| `SINGLE-169-02` | `verify REQ-001` | 同上（ステージ） | `blocked`／2。`statements`は2件、`CTX-COVERAGE-TEST-001`1件、テストを開始しない |
| `SINGLE-169-03` | `context REQ-001 --purpose implement` | 鎖: `TECH-001`→`REQ-001`（文書ID）、`TECH-002`→`TECH-001`（文書ID）、`TECH-003`→`TECH-002:C-01`（規範文ID）。`TECH-003`だけテスト対応なし | `passed_with_warnings`／0。4件の規範文、距離2以上は`normative` |
| `SINGLE-169-04` | `verify REQ-001` | 同上（ステージ） | `blocked`／2。`statements`は4件、`TECH-003:C-01`だけ`CTX-COVERAGE-TEST-001` |
| `SINGLE-169-05` | `verify REQ-001:AC-01`（対照） | 基本の入力（ステージ） | `passed`／0。`statements`は`REQ-001:AC-01`だけ |
| `SINGLE-169-06` | `verify REQ-001`（対照） | 基本の入力。ただし`TECH-001`は状態`draft`（ステージ） | `passed`／0。`statements`は`REQ-001:AC-01`だけ |
| `SINGLE-169-07` | `verify REQ-001` | `TECH-002`→`REQ-001:AC-01`（規範文ID）、`TECH-003`→`TECH-002`（文書ID）。`TECH-003`だけテスト対応なし | `blocked`／2。`statements`は3件、`TECH-003:C-01`だけ`CTX-COVERAGE-TEST-001` |
| `SINGLE-169-08` | `verify REQ-001:AC-01` | `07`の入力に、`REQ-001`を文書IDで`refines`する`TECH-001`（テスト対応なし）を加える | `blocked`／2。`statements`は`07`と同じ3件で`TECH-001:C-01`を含めない |
| `SINGLE-169-09` | `verify TASK-001` | `08`の入力に、`REQ-001:AC-01`を`addresses`する状態`open`の`TASK-001`を加える | `blocked`／2。`08`と同じ`statements`と診断 |

`context`は基準版のコミットを置かず（`revision: null`）、`verify`はインデックスへステージする（`SINGLE-168`と同じ）。

## 期待値の導き方（Coreの出力を根拠にしない）

1. **対象規範文**。選択済みの規範文を規範文IDで`refines`する適用可能な文書は、どの起点でも具体化文書として規範文を加える。見つけた具体化文書は選択済みの文書とし、その文書を文書IDで
   `refines`する文書も、規範文IDの`refines`と同じく推移的に辿る。起点の文書自身を文書IDで`refines`する文書を加えるのは、規則1（文書の起点）の場合だけである。
   - `SINGLE-169-01`〜`04`（規則1）: 起点`REQ-001`の規範文に、`REQ-001`を文書IDで`refines`する`TECH-001`の規範文を加える。鎖は`TECH-001`（`REQ-001`を文書ID）、`TECH-002`（`TECH-001`を文書ID）、
     `TECH-003`（`TECH-002:C-01`を規範文ID）の順に、見つけた文書の規範文を足す。
   - `SINGLE-169-07`（規則1）: `TECH-002`は`REQ-001:AC-01`を規範文IDで`refines`して見つかり、`TECH-003`は見つかった`TECH-002`を文書IDで`refines`するので、規範文が加わる。
   - `SINGLE-169-08`（規則2）: 起点は`REQ-001:AC-01`。`TECH-002`が見つかり、`TECH-003`はそこから文書IDで辿る。起点の所有文書`REQ-001`を文書IDで`refines`する`TECH-001`は、辿る起点にしないので加えない（`SINGLE-169-05`と同じ）。
   - `SINGLE-169-09`（規則3）: 起点`TASK-001`が`addresses`する`REQ-001:AC-01`から`08`と同じ。
   - `SINGLE-169-05`は指定した`REQ-001:AC-01`だけ。§6.1の末尾から、`SINGLE-169-06`は`draft`の`TECH-001`を含めない。
2. **文書の並びと提示形式**。距離、種別、IDの順（`REQ-001`が0、以降は1ずつ）。`SINGLE-169-03`は、距離2の`TECH-002`と距離3の`TECH-003`が、所有する規範文を
   制約台帳に収録するので`normative`（`statementRefs`だけ）、距離1の`TECH-001`は`full`。`reachedBy`は`refines:<自身のID>`。役割は`root`、`refinement`。
3. **カバレッジと診断**。目的`implement`の対象の`MUST`はTASKがないので全件が`unaddressed`で、`CTX-COVERAGE-TASK-001`を1件ずつ返す。`tested`は、閉包の文書のテスト対応が`covers`する規範文。
   未テストの規範文は`CTX-COVERAGE-TEST-001`（目的`implement`は警告、`verify`は`blocked`）。診断は`path`、`code`の辞書順。`summary`は既存の承認済みの文言
   （`SINGLE-060`、`MULTI-047-03`）を使い、新しい文言は足していない。
4. **ハッシュ値**。独立に書いた2系統の参照計算（リテラルのA、入力の木構造から導く`digest_crosscheck`のB）のバイト列の一致を要求する。
   対象規範文はハッシュ値の材料に入らない（閉包の文書、その規範文の意味、強い関係、テスト割当てだけ）ので、閉包が同じなら修正前のCoreと同じ値になる。実際に、修正前と修正後のCoreで`contextDigest`の差分はなかった。
5. **対象規範文の参照計算**。準備手順の後の入力の木構造から、§6.4の規則を別に書いた関数で導き、リテラルの期待値と、corpusのリテラルの宣言から導いた結果の両方と一致することを、2回の準備手順のそれぞれで要求する。
   さらに、修正前のCoreの2つの再現を導く。`main`は`origin/main`のCore（文書IDの`refines`を辿らない）、`midway`は途中のCore（コミット`232b2067`。規則1の起点の文書と、それを文書IDで見つけた文書からだけ文書IDで辿り、
   規範文IDで見つけた文書の先は辿らない）である。欠陥のケースでは対象規範文の真部分集合になり、対照では同じになることを要求する。`01`〜`04`は`main`だけが取りこぼし、`07`〜`09`は`main`と`midway`の両方が取りこぼす。
6. **コマンドの実行**。`passed`の`verify`は、対象規範文を`covers`するテスト対応のコマンド`default`を1回実行する。`blocked`はテストを開始しない。

## 規範から決まらず、既存の慣例と仕様の該当箇所で決めた点

1. **目的`implement`の入力にTASKを置かない**。TASKを足すと、閉包でのTASKの距離（§7の6.、確認事項C55）が並びと提示形式に影響する。この群の対象外なので、TASKを置かず、
   警告の形（`CTX-COVERAGE-TASK-001`）で固定した（`SINGLE-054`、`MULTI-047-03`の形）。
2. **`blocked`の検証対象も`contextDigest`を持つ**（`SINGLE-169-02`、`04`）。コンテキストは完全に解決できるので、`SINGLE-060`と同じく値を持つ。`bindingRefs`と`commands`は空。
3. **規範文を起点にした`verify`の閉包に、文書IDで`refines`するTECHを含める**（`SINGLE-169-05`）。§6.1の4.は「起点を所有する文書またはその規範文を`refines`する適用可能な文書」を
   閉包へ含めると定め、規則2は対象規範文だけを限る。よって`TECH-001`は閉包に入り`contextDigest`の材料になるが、その規範文は対象規範文にならない。
4. **TASKの起点（`SINGLE-169-09`）の閉包**。TASKは規範文を持たず、`addresses`する`REQ-001:AC-01`の所有文書`REQ-001`を距離1で閉包へ含める（§6.3）。`REQ-001`を文書IDで`refines`する`TECH-001`は、
   §6.1の4.により閉包の文書として入り（`contextDigest`の材料）、対象規範文にはならない。`verify`の起点のTASKは`requires`の閉包を含めない（§6.3）が、この入力は`requires`を持たない。
5. **Stepの割当て**。操作が実装される最初のStepに置く。`context`の2件（`01`、`03`）はStep 3、`verify`の7件（`02`、`04`〜`09`）はStep 4（`SINGLE-168`と同じく操作ごとに分けた。実装計画 §6・§7）。
6. **テスト対応の置き場所**。`REQ-001`のテスト対応を`REQ-001`自身のフロントマターに置き、`TECH-xxx`も自身の規範文を`covers`する（`SINGLE-168`の`TECH-001`のように別の文書の規範文を`covers`しない）。

## 検証の記録

- 修正後のCore（このブランチ）では、9件すべてが`passed`となる。期待値は規範から導いたもので、Coreに合わせて曲げていない。食い違いはなかった。
- 途中のCore（コミット`232b2067`の`plugins/bitz-core`）では、`SINGLE-169-01`〜`06`が通り、`07`〜`09`が失敗する（`statements`が2件で`passed`／0）。
- 修正前のCore（`origin/main`の`plugins/bitz-core`）では、欠陥の`SINGLE-169-01`〜`04`と`07`〜`09`が失敗し、対照の`05`と`06`が通る。
  `01`と`03`は制約台帳とカバレッジが`REQ-001:AC-01`の1件だけになり診断も減る。`03`は距離2以上の文書も`full`になる。`02`と`04`は`statements`が`REQ-001:AC-01`だけで`passed`／0になる。
