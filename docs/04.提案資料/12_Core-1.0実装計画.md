# Core 1.0実装計画

- 状態: Active
- 作成日: 2026-09-01
- 更新日: 2026-09-03
- 前提: [ADR-039](../02.設計書/10_決定記録/ADR-039_Core-1.0仕様構造の再編とscope縮小.md)、
  [ADR-040](../02.設計書/10_決定記録/ADR-040_モノレポSPEC連合をCore-1.0へ再導入する.md)、
  [ADR-041](../02.設計書/10_決定記録/ADR-041_verify対象別証跡とreport明示保存の分離.md)、
  [ADR-042](../02.設計書/10_決定記録/ADR-042_モノレポ連合のidentity・所有境界・公開契約を確定する.md)、
  [ADR-043](../02.設計書/10_決定記録/ADR-043_モノレポ連合の継続・TASK境界・適合契約を確定する.md)、
  [ADR-044](../02.設計書/10_決定記録/ADR-044_MCP面をCore-1.0のscope外とする.md)、
  [ADR-045](../02.設計書/10_決定記録/ADR-045_実行環境と配布物の確定.md)

## 1. 目的

規範設計と実装順序を分離し、公開面の配管を先に通したうえで、workspace単独のEARS-AI記述から
test実行までの垂直スライスを実証し、同じ契約をモノレポ連合へ拡張する。
Step番号と完了条件は計画であり、Core APIの規範ではない。

適合条件の正本は[適合fixture仕様](../03.詳細設計/00_共通契約/04_適合fixture仕様.md)、
Digestの計算手順は[Context Digest正規化仕様](../03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md)である。
本書はそれらを再定義せず、実装順序と各Stepの完了条件だけを持つ。

## 2. Step 0: 仕様確定（コードを書かない）

実装着手gateである。成果物は次とし、いずれも[提案24](24_Core-1.0実装着手方針.md)の裁定に対応する。

| 成果物 | 対象 | 状態 |
|---|---|---|
| [Context Digest正規化仕様](../03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md) | G1 | 反映済み |
| [適合fixture仕様](../03.詳細設計/00_共通契約/04_適合fixture仕様.md) | G2 | 反映済み |
| Diagnostic表の閉包（共通契約 §6.1と各操作仕様） | G3 | 反映済み |
| 終了コード4の出力契約（共通契約 §3） | G4 | 反映済み |
| [ADR-044](../02.設計書/10_決定記録/ADR-044_MCP面をCore-1.0のscope外とする.md) | G5 | 反映済み |
| 非成功時のtext出力契約（共通契約 §7） | G6 | 反映済み |
| [ADR-045](../02.設計書/10_決定記録/ADR-045_実行環境と配布物の確定.md) | G7 | 反映済み |
| accepted ADRのlink訂正とcheck status語彙の所有 | G8 | 反映済み |

完了条件は、G1〜G8が規範文書だけを読んで一意に実装できることである。

## 3. Step 0-P: 実証条件

Step 1と並行して固定する。

- 通常Markdownまたは従来EARSを使う比較taskを5件固定する。
- 完了時間、仕様記述時間、review時間、欠陥検出数を定義する。
- 単一workspaceと、20 workspace、SPEC 1,000件、relation 20,000件の基準連合fixtureを固定する。
- 平均file byte、statement数、edge密度、横断Contextの到達workspace数と基準環境manifestを固定する。
- Core 1.0対象外機能を確認する。

完了条件は、比較方法と成功基準が実装前に固定されていることである。

## 4. Step 1: 骨格と`doctor`

`doctor`は設定読込み、workspace発見、結果・Diagnostic・終了コードの配管だけで成立する最小の操作であり、
他3操作が同じ土台を使う。ここを先に通し、以後の全Stepを同じ公開面から検証する。

- 適合fixture harness: manifest実行、共通normalizer、副作用比較、終了コード判定
- CLI引数解析、`--format`、終了コード0〜4、引数不正時の標準エラー1行
- 共通結果外形、Diagnostic Schema、source、順序規則、status集約
- text出力の要約行とDiagnostic行
- `bitz.yaml`のYAML subset読込みと禁止構文の拒否
- 単一workspaceの探索と`doctor`（Core、実行環境version、設定、Git、command、cache）

完了条件は、`SINGLE-001`〜`006`と`SINGLE-070`〜`077`が通過し、終了コード0〜4を区別できることである。

## 5. Step 2: EARS-AIと文書モデル

- 候補Scanner、Lexer、Parser、Semantic IR
- Frontmatter Schema、文書ID、statement ID、状態、file名規則
- 関係索引、逆索引、path逆索引
- 正例・反例fixture

完了条件は、同一入力から同一IRとDiagnosticを再現でき、`SINGLE-007`〜`026`が通過することである。

## 6. Step 3: Contextとcheck

- 強い依存の完全閉包、purpose別閉包、role分類
- Constraint Ledger、coverage、Context Digest
- `--expect-digest` stale検出、detailとexpandのprojection
- changed-only check、`--full`、明示対象、Git基準版
- REQ保護、状態遷移、管理済みSPEC削除、TASK境界、影響候補
- relation Diagnosticの1 edge 1 primary規則

完了条件は、参照切れ、循環、上限、Digest不一致を部分成功にせず、`SINGLE-027`〜`054`が通過し、
固定fixtureのDigestが規定値と完全一致することである。

## 7. Step 4: verify

- command名単位のbinding解決、`{tests}`展開、cwd、timeout、出力上限
- target単位Context、`targetResults[]`、共有bindingの1回実行
- verify結果と明示`--report`時だけの最小report

完了条件は、test成功、非0、起動失敗、signal、timeout、対象0件をfixtureで区別でき、異なる2 Contextを持つtarget、
共有binding、Context非成功targetの混在を正しい`targetResults[]`へ対応付けられることである。`--report`なしでは
成功・非成功とも既存reportを変更せず、新しいfileを作らない。`SINGLE-055`〜`069`と`SINGLE-078`〜`080`が通過する。

## 8. Step 5: モノレポ連合

- 明示catalog、active workspace、修飾ID
- 横断Frontmatter索引、完全Context、Context Digest
- code／test／TASK／cwdの所有境界とcanonical path判定
- `--workspace`と`--all-workspaces`
- workspace別`targetResults[]`、共有command結果、集約status、明示連合report
- 未登録member、path重複、Git不在、横断参照、対象0件
- Git既知の未登録設定、symlink所有迂回、case差、初回root ID写像、member移動・削除
- 文書・target・binding単位の継続と`SPEC-MONOREPO-DEPENDENCY-001`
- 単一／連合dual-read consumer、原子的rollback、部分rollback拒否

完了条件は、同名ローカルIDを持つmember、横断refinement、所有境界違反を決定論的に区別し、
`check --all-workspaces`と`verify --all-workspaces`が基準性能を満たし、`MONO-001`〜`024`が通過することである。
別member所有bindingを1回だけ実行し、request targetとowner memberのstatusへ反映してもcommand実体とdurationを
複製しない。

## 9. Step 6: SDD垂直スライスと自己適用

Step 2完了時点でbitz-core自身の`.spec/`を作り、以後の実装をSmall Flowで進める。
最初のREQはParserと結果契約に対するものとし、Coreが自分自身をcheck・verifyできる状態をStep 4の完了条件へ含める。

その上でREQ 1件について次を通す。

```text
SPEC作成 -> context -> pre-check -> code/test変更 -> post-check -> verify -> human review
```

通常Markdown条件と比較し、完了時間、欠陥率、review負荷のいずれも改善しない機能を既定経路へ追加しない。

## 10. 性能受入

性能はCore cacheを使わず、暖機1回後の5回中央値で測定する。基準環境で`check --all-workspaces`を30秒以内、
3 workspaceへ到達する20文書・128 KiB以下のContextを1秒以内、Core peak RSS増分を200 MiB以内とする。
10,000 SPEC fixtureは性能SLOではなくhard limitの安全停止を検証する。索引memoryは入力graph size、target一時memoryは
最大Context閉包へ線形とし、全targetの完全Bundleを同時保持しない。resource dimensionごとに`limit - 1`、`limit`、
`limit + 1`を分離し、最大dimension fixtureをCore peak RSS増分1 GiB以下、2 GiB memory limit下で正常終了させる。

測定条件と性能fixtureの位置づけは
[適合fixture仕様 §8](../03.詳細設計/00_共通契約/04_適合fixture仕様.md#8-性能fixture)に従う。
性能fixtureは合否matrixへ含めず、回帰検査として独立に運用する。

## 11. 1.0以降の再評価候補

- ID改番支援
- 実Profile
- Projection Digest
- formatter／style linter
- より細粒度のtest selector
- MCP面（[ADR-044](../02.設計書/10_決定記録/ADR-044_MCP面をCore-1.0のscope外とする.md)）

候補は提案11の再評価条件を満たした場合だけ新しいADRから開始する。
