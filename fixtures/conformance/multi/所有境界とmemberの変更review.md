# 所有境界とmemberの変更 fixture review

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合workspace)の
`MULTI-008`、`MULTI-009`、`MULTI-010`、`MULTI-011`、`MULTI-017`、`MULTI-018-01/02`を扱う。
いずれもreview済みの期待値であり、Coreの挙動を観測したものではない。

## 所有境界は実pathで、TASK境界は字句pathで判定する

[複合workspace仕様 §5.1・§5.2](../../../docs/03.詳細設計/02_SPECモデル/05_複合workspace仕様.md#51-canonical-path判定)は
2つの判定を分けて定める。fixtureもこれに合わせて別の入力で固定する。

- `MULTI-008`は`apps/web/src/shared.py`をsymlinkにし、link文字列`../../../services/api/src/session.py`で
  別memberのcodeへ出る。`web::TECH-010`はこれを`implements`へ宣言するので`SPEC-MULTI-OWNERSHIP-001`になる。
  このcorpusはTASKを持たないので、TASK境界のcodeは起こり得ない。監査はsymlinkの解決先が
  `services/api`の配下であることを確かめ、web内を指すlinkへ直した写しを拒否する。
- `MULTI-009`は`changes: [src/]`のTASKと、変更した`src2/outside.py`を持つ。`src/`は`src2/`を許可しない。
  ここはsymlinkを使わず、字句のsegment境界だけを問う。
- `MULTI-010`は`changes: [src/]`のTASKと`src/link`のsymlinkを持ち、基準版では別memberを指し、
  現在版ではweb内へ向け直す。現在版だけを判定すると不適合を見落とすので、基準版のGit treeの
  entry mode（`120000`）とlink targetを監査が直接確かめる。`src/link`は字句上`src/`の内側にあるため、
  TASK境界のcodeではなく所有境界のcodeだけを返す。

## memberの非成功は後続memberを止めない

`MULTI-011`はapiの文書を、file名IDとFrontmatter IDが一致しない1件だけに置き換える。処理順は
root、`api`、`web`なので、`api`が`failed`でもその後ろの`web`の`checkedDocumentCount`は落ちない。
監査試験は、後続memberの件数を0にした写し、member要素を削った写し、`api`を`blocked`にした写しを拒否する。
この群のcorpusではapiの文書がwebから参照されないため、依存による遮断（`SPEC-MULTI-DEPENDENCY-001`）は起こらない。

## workspace IDは永続同一性、pathは移動できる

[複合workspace仕様 §4.1](../../../docs/03.詳細設計/02_SPECモデル/05_複合workspace仕様.md#41-workspace-identity)に従い、
IDを保ったpath変更は同一workspaceの移動、ID変更は旧workspaceの削除と新workspaceの追加として扱う。

| fixture | 基準版 → 現在版 | 結末 |
|---|---|---|
| `MULTI-017` | `web`が`apps/web`から`frontend/web`へ移動 | `passed`。同じIDで対応付ける |
| `MULTI-018-01` | `web`のIDが`webui`へ変更（pathは同じ） | `SPEC-STATE-TRANSITION-001`／`failed` |
| `MULTI-018-02` | `web`をcatalogから外しtreeも削除 | `SPEC-STATE-TRANSITION-001`／`failed` |

削除検査のDiagnosticは、現在版に存在しないworkspaceの管理済みSPECを指すので、最上位の`diagnostics`へ置き、
`source`は基準版のworkspace ID `web`とそのworkspace root相対pathとする。member結果へは複製しない。
監査は、基準版のcatalogをGitのblobから読み、現在版のcatalogと突き合わせて、各fixtureが名乗るとおりの
変更になっていることを確かめる。IDを元へ戻した写しは拒否する。

## 訂正（2026-09-25）：MULTI-011のcheckedDocumentCount

根拠の規範文：[check操作仕様 §9](../../../docs/03.詳細設計/03_操作仕様/02_check.md#9-結果)
「`checkedDocumentCount`は全SPECを完全検査した文書数」、
[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)の`skip-document`
（file名IDとFrontmatter IDが一致しない文書は完全検査せずskip-documentとする）。

食い違い：`MULTI-011`のapi member結果は、file名IDが一致せずskip-documentになった文書
（`services/api/.spec/technical/TECH-020.md`、Frontmatter IDは`TECH-010`）を`checkedDocumentCount: 1`と
数えていた。同じ条件の単一workspace fixture`SINGLE-014`は`checkedDocumentCount: 0`であり、規範文と
矛盾していた。

訂正内容：`MULTI-011`のapi member結果の`checkedDocumentCount`を`0`へ訂正した
（`fixtures/conformance/multi_member_fixtures.py`の`reviewed_result`、
`fixtures/conformance/multi/MULTI-011/expected/check.json`）。他のworkspace（platform、web）の
件数、`status`、Diagnosticの内容には影響しない。

2026-09-25に管理者（ユーザー）が、ADR-051（[適合fixtureの変更手続きを確定する](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)）
と適合fixture仕様 §1.1「期待値の訂正」に基づき、この訂正を承認した。根拠は規範文だけであり、
Coreの観測出力は参照していない。

## 限界

- Coreは実行していない。Diagnosticの文面と、検査した文書数の実際の値はGate Bで判定する。
- `MULTI-008`はsymlinkによる所有境界違反を1件だけ固定する。case-insensitive filesystemでの同一視、
  repository外への解決、memberの`.spec`への解決は、このmatrixでは区別しない。
- `MULTI-017`は移動を1回だけ扱う。移動と同時に文書を変更した場合の削除検査は扱わない。
