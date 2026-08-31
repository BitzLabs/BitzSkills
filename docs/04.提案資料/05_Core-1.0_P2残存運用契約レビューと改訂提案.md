# Core 1.0 P2残存運用契約レビューと改訂提案

**状態**: **Closed（P2 7件裁定・反映済み）**

**作成日**: 2026-08-31

**裁定日**: 2026-08-31

## 1. 目的

P1残存契約レビューを反映した正本を対象に、出荷までに実装差を解消すべき運用契約を再確認した。
レビュー03の旧P2 7件はADR-019／020で裁定済みであり、本書はその後に残った別の7件を扱う。
現在の正本は`docs/02.設計書`と`docs/03.詳細設計`であり、本書の例だけを実装根拠にしない。

## 2. P2指摘

### 2.1 SPEC文書の状態遷移が一致しない

上位設計はREQの`outdated -> draft`だけを示したが、要求SPEC仕様は見直し後の
`outdated -> approved`も許可していた。TECH、ADR、TASKも状態値だけで許可遷移と終端状態がなかった。

### 2.2 Gitの基準版と変更集合が未定義

変更範囲検査、承認済みREQ保護、TASK境界が同じ「Gitの基準版」を参照する一方、HEAD、index、
merge-base、未追跡ファイルの扱いが確定していなかった。clean checkoutのCIでbranch内変更を検査する方法もなかった。

### 2.3 `bitz check`の明示対象が未定義

公開文法は`ids-or-paths`を受け付けたが、対象種別、pathの許可範囲、複数対象、`--full`との排他、
検査範囲が読み取れなかった。

### 2.4 verifyのtimeout・実行結果・Digestが不足

設定仕様はCLI timeout短縮を許可したが公開文法に引数がなく、Context Digestはcommand名だけを含んでいた。
起動失敗、signal、timeout時の結果SchemaとDiagnosticもなかった。

### 2.5 TASKと規範文なしTECHの接続が不一致

Contextの型制約はTASKから規範文なしTECHへの`addresses`を許可したが、TASK仕様と明示verifyは
規範文だけを前提にしていた。規範文ID起点の兄弟句を`adjacent`へ表示する規則も、coverage説明へ反映されていなかった。

### 2.6 Diagnostic集約とモノレポsourceが不十分

Diagnosticインスタンスに操作効果がなく、条件付きstatusを持つコードを機械的に区別できなかった。
集約順序は操作ごとに重複し、workspace相対pathだけでは連合内の同名pathを一意にできなかった。

### 2.7 レポート生成条件が一致しない

失敗時の自動保存と`--report`指定時だけの保存が文書間で混在し、`context`が存在しない`--report`を
受け付けるようにも読めた。

## 3. 裁定

| 項目 | 裁定 | 対応 |
|---|---|---|
| 状態遷移 | 採用・反映済み | [ADR-024](../02.設計書/10_決定記録/ADR-024_SPEC文書の状態遷移契約.md)。REQ／TECH、ADR、TASKの作成時状態、許可遷移、終端を定義 |
| Git基準版 | 採用・反映済み | [ADR-025](../02.設計書/10_決定記録/ADR-025_Git基準版とcheck明示対象の確定.md)。`--base`、変更集合、CI利用を定義 |
| `check`明示対象 | 採用・反映済み | ADR-025。SPEC ID／規範文ID／SPEC pathへ限定し、検査範囲と排他を定義 |
| verify実行契約 | 採用・反映済み | [ADR-026](../02.設計書/10_決定記録/ADR-026_verify実行binding・timeout・結果Schemaの確定.md)。timeout cap、command結果、Digest入力を定義 |
| TASK接続 | 修正採用・反映済み | 規範文なしTECHの文書単位testsと、規範文ID起点の`adjacent`を正本へ接続 |
| Diagnostic集約 | 採用・反映済み | [ADR-027](../02.設計書/10_決定記録/ADR-027_Diagnostic結果効果・集約・workspace-sourceの確定.md)。`resultStatus`、`workspaceId`、共通集約順を定義 |
| レポート生成 | 修正採用・反映済み | 既存の失敗時保存を正とし、`failed`／`blocked`／`error`だけ自動保存。引数不正とcontextは保存しない |

## 4. 主な反映先

- `02.設計書/01_共通アーキテクチャ.md`
- `02.設計書/02_specディレクトリ仕様.md`
- `02.設計書/03_CLI統合設計.md`
- `02.設計書/05_QA品質保証設計.md`
- `02.設計書/06_運用設計.md`
- `02.設計書/07_セキュリティとガバナンス.md`
- `03.詳細設計/02_SPECファイル規定/02_bitz.yaml仕様.md`
- `03.詳細設計/02_SPECファイル規定/03_Frontmatter共通仕様.md`
- `03.詳細設計/02_SPECファイル規定/04_要求SPEC仕様.md`
- `03.詳細設計/02_SPECファイル規定/05_補助SPEC仕様.md`
- `03.詳細設計/02_SPECファイル規定/06_参照・トレース・検証仕様.md`
- `03.詳細設計/02_SPECファイル規定/07_更新・互換性・安全性.md`
- `03.詳細設計/02_SPECファイル規定/10_Context Resolution仕様.md`
- `03.詳細設計/02_SPECファイル規定/12_モノレポSPEC連合仕様.md`

## 5. 実装前チェックリスト

- [x] 全文書種別の作成時状態、許可遷移、終端状態が定義されている
- [x] ローカル既定とCI明示のGit基準版が区別され、未追跡pathを変更集合へ含める
- [x] `check`の対象種別、path、複数対象、`--full`との排他、展開範囲が定義されている
- [x] CLI timeoutが設定値を延長せず、command終了理由と実効値を結果へ残す
- [x] command定義変更でContext Digestが変わる
- [x] TASKが規範文なしTECHを対象にしたverifyと、規範文ID起点の`adjacent`が定義されている
- [x] Diagnostic単位の`resultStatus`とfile sourceの`workspaceId`がある
- [x] 全操作が同じstatus集約順位を使用する
- [x] レポートの自動保存、明示保存、非保存条件が排他的に定義されている

## 6. クローズ判定

P2 7件はADR-024〜027と正本同期として裁定・反映した。状態遷移、Git差分、CLI入力、verify実行、
Diagnostic集約、レポート書込みの実装分岐を解消したため、P2残存運用契約レビューは**完了**とする。
