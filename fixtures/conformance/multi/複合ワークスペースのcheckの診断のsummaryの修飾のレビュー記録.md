# 複合ワークスペースの`check`の診断のsummaryの修飾のfixtureのレビュー記録

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-056-01`〜`MULTI-056-05`を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/multi_check_qualified_summary_fixtures.py`である。
`context`の診断の`summary`を同じ考え方で扱った群は、[複合ワークスペースの診断のsummaryの修飾のレビュー記録](複合ワークスペースの診断のsummaryの修飾のレビュー記録.md)
（`MULTI-047`）に記録した。

## 追加の理由

実装の確認事項C69・C80に対応する。

- **C69**: 複合ワークスペース内の`check`は、`SPEC-IMPACT-OUTDATED-001`（影響の候補。依存元と変更された文書の2つのID）と`SPEC-ID-DUPLICATE-001`（文書IDの重複）の`summary`に、
  作業ワークスペースの文書IDを修飾せずに差し込んでいた。同じ`check`の`SPEC-TASK-BOUNDARY-001`や、`MULTI-047`で修飾した`CTX-STATE-001`などとは食い違っていた。
  全体操作（`--all-workspaces`）と単独の操作（`--workspace web --full`）の両方で起きていた。
- **C80**: `check --all-workspaces`のメンバーの影響の候補は、自ワークスペースを自身のIDで修飾した参照（`web`の`TECH-010`の`refines: [web::REQ-001:AC-01]`）を、
  変更された文書へ照合せず、その依存元を見落としていた。単独の操作は照合していた。

文型（文言のひな形、`messages.py`）は変えず、差し込む値の形だけが変わる。単一ワークスペースの出力は変わらない。

## 根拠の規範文と決定

- 複合ワークスペース仕様 §4: 複合ワークスペース内で実行したCore操作は、文書IDと規範文IDを複合ワークスペースの正規形式（修飾ID）で返す。
  同じワークスペースを自身のIDで修飾した参照（`web`の文書の`web::REQ-001`）は、非修飾形式と同じ文書または規範文を指す。
- `check` §8: 出発点の変更されたREQまたはTECHへ、強く依存する状態`approved`の文書を`SPEC-IMPACT-OUTDATED-001`（`warning`）として示す。
  `related`、コード、テストの変更は出発点にしない。`check` §3: `--all-workspaces`はカタログ内のすべての仕様文書を完全検査する。
  `check` §6: 単独の操作の影響の候補は作業ワークスペースの文書だけに行う。
- 診断レジストリ: `SPEC-IMPACT-OUTDATED-001`は`warning`／`passed_with_warnings`、`SPEC-ID-DUPLICATE-001`は`error`／`failed`で継続単位は`skip-document`。
- **`summary`の中のIDの形は規範文で1つに決まらない。** ADR-062により、これは管理者が承認した値である。`MULTI-047`のユーザーの決定（2026-10-26）の考え方と、
  確認事項C69のユーザーの決定で、作業ワークスペースのIDも`<ワークスペース>::`で修飾する（[Coreの出力文言のレビュー記録](../Coreの出力文言のレビュー記録.md)）。
- 結果・診断・終了コード §2.1・§3・§7: `--all-workspaces`の結果は`multiWorkspace`と`workspaces`を持ち、ルートを先頭、その後をIDの辞書順に並べる。診断は所有ワークスペースの
  `diagnostics`に置き、最上位へ複製しない。診断の並びは発生元のワークスペースID、`path`、`line`、`column`、`code`、`specRefs`の辞書順。
  `checkedDocumentCount`と`checkedStatementCount`は、そのワークスペースで完全検査した仕様文書の数と規範文の数。

## 入力と起動

基本のリポジトリは、ルート`platform`（`.`）とメンバー`web`（`apps/web`）で、すべてコミットし、`--format json`で起動する。文書は`REQ`と`TECH`だけで、`TECH`は規範文を持たない
（規範文の数を単純にし、`MULTI-029`と同じ形にする）。`platform`は、`web`と同じローカルIDの文書を持つ（`REQ-001`または`REQ-003`）。
これにより、`web::`の修飾が、診断の読み手がワークスペースを区別するために必要であることを入力で示す。

| fixture | 操作 | 入力 | 結果 |
|---|---|---|---|
| `MULTI-056-01` | `check --all-workspaces --base HEAD` | `web`の`REQ-001`（`draft`）を作業ツリーで変更する。`TECH-010`（`approved`）は`refines: [web::REQ-001:AC-01]`、`TECH-011`（`approved`）は`refines: [REQ-001:AC-01]` | `passed_with_warnings`／0 |
| `MULTI-056-02` | `check --all-workspaces --base HEAD` | `MULTI-056-01`から`TECH-011`を除く | `passed_with_warnings`／0 |
| `MULTI-056-03` | `check --workspace web --full --base HEAD` | `MULTI-056-01`と同じ入力 | `passed_with_warnings`／0 |
| `MULTI-056-04` | `check --all-workspaces --base HEAD` | `web`の`REQ-003-a.md`と`REQ-003-b.md`が同じ文書ID`REQ-003`を定義する。`platform`は`REQ-003`を1件持つ | `failed`／1 |
| `MULTI-056-05` | `check --workspace web --full --base HEAD` | `MULTI-056-04`と同じ入力 | `failed`／1 |

変更する`REQ-001`を状態`draft`にするのは、承認済み要求の保護（`SPEC-SAFETY-APPROVED-001`）との関わりを入力から外すためである。本文の`Intent`だけの変更は、文書・フロントマター・状態仕様 §8では意味の変更に当たらないので、`approved`のままでもこの診断は出ない（独立レビューの実測）。§8の比較の範囲の読みに頼らず、影響の候補だけを固定するために`draft`にした。
`REQ-001`の変更は、本文の`Intent`の1文だけである（基準版は「意図。」、現在版は「変更した意図。」）。依存元の`TECH-010`・`TECH-011`は`approved`で、`draft`の`REQ-001`を強い関係で参照する。
参照先の状態が`draft`でも、型の制約（`CTX-RELATION-TYPE-001`）にならない（関係・トレースモデル §4の「`draft`のREQなど…は…`CTX-STATE-*`で扱う」）。

重複の2つのファイルは、同じ文書ID`REQ-003`で、ファイル名だけが異なる（`SINGLE-015`と同じ形）。規範文のラベルは`AC-01`と`AC-02`にして、文書IDの重複に規範文IDの重複
（`EAI-CORE-ID-002`）を混ぜない（`SINGLE-015`のTECHは規範文を持たず、同じ目的を果たす）。

## 期待値の導き方（Coreの出力を根拠にしない）

1. **影響の候補**（`01`〜`03`）。変更集合は`web`の`REQ-001`の1件（基準版から本文が変わる）。出発点は変更された`web::REQ-001`。強い関係で直接依存する状態`approved`の文書は、
   `TECH-010`（`refines`、自ワークスペースを修飾した参照）と`TECH-011`（`refines`、非修飾の参照）。自ワークスペースを修飾した参照は非修飾形式と同じ文書を指すので、2件とも警告する。
   `summary`は`web::TECH-010が強く依存するweb::REQ-001が変更されています。再確認してください`（依存元と変更された文書の2つのIDとも修飾）。
   `source`は依存元の文書（`path`は`web`のルート相対の`.spec/technical/TECH-010.md`など）、`key`は`relations.refines`、`evidence`は持たない（`SINGLE-033`と同じ）。
   並びは、同じワークスペース、`path`の辞書順で`TECH-010`、`TECH-011`。
2. **文書IDの重複**（`04`・`05`）。`REQ-003-a.md`と`REQ-003-b.md`は同じ文書IDなので、1件の`SPEC-ID-DUPLICATE-001`で、発生元はパスの辞書順で先頭の`.spec/requirements/REQ-003-a.md`、`key`は`id`
   （`SINGLE-015`の代表位置の選択と同じ。勝者を選ぶ規則ではない）。`summary`は`文書ID web::REQ-003が重複しています`。`platform`の`REQ-003`は別のワークスペースの文書で、重複しない。
3. **件数**。`checkedDocumentCount`と`checkedStatementCount`は、完全検査した文書と規範文。重複した2つのファイルはどちらも`skip-document`にして数えない（`SINGLE-015`と同じで、`0`／`0`）。
   `01`の`web`は3文書・規範文1件、`02`は2文書・1件、`platform`は1文書・1件、`04`の`web`は0／0。単独の操作（`03`・`05`）は作業ワークスペース`web`の件数だけを返し、
   `workspace`は`{web, apps/web}`、`scope`は`full`。ワークスペースをまたぐ関係を持たないので、他のワークスペースへ到達した文書の件数は加わらない。
4. **状態と終了コード**。`warning`だけなら`passed_with_warnings`／0。`SPEC-ID-DUPLICATE-001`は`failed`／1。全体操作の`web`が`failed`なら全体も最悪値の`failed`、`platform`は`passed`。
   最上位の`diagnostics`は空。`revision`は、影響の候補（作業ツリーの変更あり）が`dirty: true`、重複（コミット済み）が`dirty: false`。
5. **欠陥を検出できる入力であること**（陰性対照の構成）。`reference_workspace`は、`qualify=False`と`match_self_qualified=False`で修正前のCoreの結果を再現する。
   `check_conditions`が、修正前の結果が期待する結果と異なること、`02`の全体操作では修正前のCoreが診断を返さないこと、それ以外では修正前の`summary`がすべて期待する`summary`と異なること
   （どれも`web::`を持たない）を要求する。

## 対照

- 単一ワークスペースの`summary`は修飾しない。既存の`SINGLE-033`（`TECH-002が強く依存するTECH-001が変更されています。再確認してください`）と
  `SINGLE-015`（`文書ID TECH-001が重複しています`）が固定している。この群はそれらを変えない。修正前のCoreと修正後のCoreのどちらでも、両方が通過する
  （次節の実測）。
- 複合ワークスペースの単独の操作は、自ワークスペースを修飾した参照を修正前から照合していた。`03`は、その照合が修正後も維持されることと、`summary`の修飾を、
  `01`と同じ診断で固定する。件数と対象が同じなので、修正前の差は`summary`の修飾だけである。

## 陰性対照（修正前のCoreでの実測）

修正前のCore（`origin/main`の`plugins/bitz-core`を`git archive`で取り出したもの）で、この5件を実行した。5件すべてが失敗した。
修正後のCore（このブランチの`plugins/bitz-core`）では、5件すべてが通過する。

| fixture | 修正前のCore | 差分（期待 → 実際） |
|---|---|---|
| `MULTI-056-01` | 失敗 | `web`の診断の件数: 2件 → 1件（`TECH-010`を照合しない。残る1件の`TECH-011`のsummaryも非修飾） |
| `MULTI-056-02` | 失敗 | 状態: `passed_with_warnings` → `passed`、`web`の診断: 1件 → 0件 |
| `MULTI-056-03` | 失敗 | 2件のsummary: `web::TECH-010が強く依存するweb::REQ-001が…` → `TECH-010が強く依存するREQ-001が…`（`TECH-011`も同じ） |
| `MULTI-056-04` | 失敗 | summary: `文書ID web::REQ-003が重複しています` → `文書ID REQ-003が重複しています` |
| `MULTI-056-05` | 失敗 | summary: 同上 |

`SINGLE-015`、`SINGLE-033`、`MULTI-029-02`、`MULTI-047-01`は、修正前と修正後のどちらのCoreでも通過した。

## 規範から導けなかった点・固定の程度

- `summary`の中のIDの形。上の「根拠の規範文と決定」のとおり、規範文は1つに定めない。管理者の決定（`<ワークスペース>::`で、作業ワークスペースも修飾する）で固定した。
- 重複の診断の代表位置（先頭のファイルの`path`、`key`は`id`）。`SINGLE-015`の選択（勝者を選ぶ規則ではない）と同じにした。`check` §4と診断レジストリは、複数ファイルの重複の発生元を定めない。
- 重複した文書を完全検査の件数へ数えないこと。診断レジストリの継続単位`skip-document`と`SINGLE-015`の記録から導いた。仕様は件数の数え方を明記しない。
  複合ワークスペースでも、同じ継続単位を重複したワークスペースの中の文書へ適用すると読んだ。
- 全体操作の`web`の件数（文書数、規範文数）を、重複する入力で`0`／`0`に固定したこと。`web`がほかの文書を持たない入力にしたため、数えない文書の扱いだけが現れる。
- 重複する入力の`platform`の`REQ-003`は`approved`の1件で、`platform`の件数は1文書・1規範文。ワークスペースをまたぐ関係を持たない入力にしたため、単独の操作で他のワークスペースの文書が
  完全検査に加わる境界（`check` §6の到達した文書）は、この群では固定しない（`MULTI-029`が固定する）。

この群の範囲外とするもの。

- `verify`の`CTX-STATE-001`などの`summary`（`MULTI-047`と単体試験が固定する）。
- 複合ワークスペースで、依存元が他のワークスペースの文書の影響の候補（`check` §6は影響の候補を作業ワークスペースの文書だけに行うと定めるが、全体操作の他のワークスペースの文書への適用は、この群では固定しない）。
- テキスト形式・Markdown形式の出力。この群はJSONだけを固定する。
