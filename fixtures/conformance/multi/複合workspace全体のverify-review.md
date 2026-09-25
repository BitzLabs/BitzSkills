# 複合workspace全体のverify fixture review

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合workspace)の
`MULTI-012`から`MULTI-016`を扱う。いずれもreview済みの期待値であり、Coreの挙動を観測したものではない。

## 継続単位はworkspaceではなくtargetとbindingである

[verify仕様 §10](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#10-全体実行)に従い、全体verifyは
root workspaceを先頭、以降をworkspace ID辞書順に処理し、通過targetのbindingを和集合として1回ずつ実行する。
この群は、そこで起こる4つの場面を1件ずつ固定する。

| fixture | 入力 | 固定する性質 |
|---|---|---|
| `MULTI-012` | 規範文IDが重複するinvalid文書へ強く依存するtarget | 依存targetは`blocked`、独立targetは実行 |
| `MULTI-013` | 2つのtargetが同じcommand名を参照 | Digest 2件、command 1件 |
| `MULTI-014` | webのcommandが失敗 | 後続のapiのbindingを実行する |
| `MULTI-015` | apiがSPECを持たない | member warningで全体は成功 |
| `MULTI-016` | どのworkspaceもSPECを持たない | 空のCIを成功にしない |

## 派生遮断は、具体的Diagnosticのないtargetにだけ付ける

`MULTI-012`のapiは、同じ規範文ID `TECH-020:AC-01`を2件持つ文書を置く。Coreはこれをskip-documentとして扱うので、
この文書自身のtargetは`EAI-CORE-ID-002`／`failed`になる。これを`requires`する`web::TECH-010`と、
その先にある`platform::REQ-001`は、自身に具体的なDiagnosticがないまま完全Contextを作れないので、
`SPEC-MULTI-DEPENDENCY-001`／`blocked`とし、`contextDigest: null`、`bindingRefs: []`とする。`evidence`は
`stage`、`dependencyWorkspaces`、`dependencySpecRefs`を持ち、根本原因のfileは`evidence`からだけ参照する。
独立した`platform::REQ-002`と`api::TECH-030`は通過し、`api::backend`を実行する。最上位statusは最悪値順
（`error > failed > blocked > passed_with_warnings > passed`）により`failed`である。

監査は、重複IDを別IDへ直した写しを拒否する。依存先が解決できるようになれば、この入力は派生遮断の証拠ではなくなる。

## 共有bindingは1回だけ実行する

`MULTI-013`のcatalogはmemberを`web`だけ登録する。`platform::REQ-001`と`web::TECH-010`は別のContextを持つので
Digestは2件だが、bindingはどちらも`web::frontend`なので実行は1件である。監査は、Digestが2件であること、
command実体が所有workspaceに1件だけ置かれること、参照されたbindingと実行したbindingの集合が一致することを
検査する。memberを2件にするとapiが対象0件のwarningを持ち、全体が`passed_with_warnings`へ下がるため、
この構成ではmemberを1件にした。

`MULTI-014`はwebのcommandを`/bin/false`にする。webのtargetとmemberは`failed`になるが、apiの独立bindingは
計画どおり実行し、`platform::REQ-002`は通過する。参照しないtargetへcommand結果を波及させない。

## 対象0件は、member単位と全体で扱いが違う

`MULTI-015`のapiはSPECを持たない。workspace単位の対象0件は`SPEC-VERIFY-BLOCKED-002`をwarningとし、
member結果を`passed_with_warnings`にするので、全体も`passed_with_warnings`（終了コード0）になる。
`MULTI-016`はどのworkspaceもSPECを持たない。各memberのwarningはそのままだが、複合workspace全体の対象が
0件の場合だけerror／`blocked`を最上位へ加える。最上位のDiagnosticはmemberのwarningの複製ではなく、
severityと`resultStatus`が異なる全体判定である。

## Digestは2系統で照合する

Contextが完成するtargetのDigestは、review済みliteral（参照計算A、本module）で期待値を作り、監査で
入力treeからの導出（参照計算B、`multi_crosscheck`）とCanonical JSONのbyte列まで照合する。
`blocked`または`failed`のtargetは`contextDigest: null`であり、照合の対象にしない。

## 訂正（2026-09-25）：MULTI-012のEAI-CORE-ID-002 source

根拠の規範文：文書・Frontmatter・状態仕様と同じ規約を単一workspaceで固定した`SINGLE-011`の期待値
（2回目の出現行を`source.line`とし、summaryを「規範文IDが重複しています」とする）、
[EARS-AI 言語・Semantic-IR仕様](../../../docs/03.詳細設計/01_EARS-AI/01_言語・Semantic-IR仕様.md)と
[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)の
`EAI-CORE-ID-002`（規範文IDの文書内重複）。

食い違い：`MULTI-012`の`api::TECH-020`診断は`source.line: 13`（`TECH-020.md`の見出し行より前の
`## Context`行）と、summary「規範文IDが文書内で重複しています」を期待していた。同じ条件の
`SINGLE-011`は2回目の出現行（`AC-01`を2つ持つ規範文のうち後の行）とsummary「規範文IDが重複しています」
を期待しており、`MULTI-012`だけ異なるsource位置と表現になっていた。`TECH-020.md`の2回目の出現は
20行目（`- [TECH-020:AC-01] ... 監査logを保持する。`）である。

訂正内容：`MULTI-012`の`EAI-CORE-ID-002`診断を、`source.line: 20`、summary「規範文IDが重複しています」へ
訂正した（`fixtures/conformance/multi_verify_fixtures.py`の`DUPLICATE_ID`、
`fixtures/conformance/multi/MULTI-012/expected/verify.json`）。column（3）、入力repo
（`services/api/.spec/technical/TECH-020.md`）は変えていない。

2026-09-25に管理者（ユーザー）が、ADR-051（[適合fixtureの変更手続きを確定する](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)）
と適合fixture仕様 §1.1「期待値の訂正」に基づき、この訂正を承認した。根拠は規範文だけであり、
Coreの観測出力は参照していない。

## 限界

- Coreは実行していない。command実行、抜粋、所要時間はGate Bで判定する。
- `MULTI-012`の根本原因は規範文IDの重複1件だけである。未対応major、上限超過による遮断は扱わない。
- timeout、signal、spawn error、出力の切詰めは単一workspaceのprocess群が扱い、この群では扱わない。
