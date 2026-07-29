---
id: SI-SDD-028
raised_by: SI-SDD-011/014/016 実装後の振り返り（2026-07-29）
target: 代行遷移の担保である Promotion Gate が運用されていない
proposed_change_type: modify
status: accepted
---
- **目的**: 代行可視化経路（`--on-behalf-of`）は「裁定の真正性は機械検証されない。
  Promotion Gate で人間が decision-ref を確認する」ことを唯一の担保として設計されている
  （SDD-FR-145）。ところが実測では bitz-sdd は 63 件すべてが verified 止まりで
  **promoted が 0 件**であり、担保が一度も行使されていない。bitz-env 19 件、bitz-flow 2 件、
  bitz-ddd 2 件も同様に 0 件で、promoted 実績があるのはルートの 26 件だけである。
  一方で代行遷移は 2026-07-29 時点で 14 件まで増えた。提案・裁定記録の作成・実装・検証を
  すべてエージェントが回し、それを人間が検分する場が動いていない状態を解消する。
- **提案する修正**:
  1. 未検分の代行遷移（provenance が `agent-proxy-unverified` で、対象要件が promoted に
     達していないもの）を `spec_status` の次アクション候補と `sdd-report` に**滞留として明示**する
  2. 滞留件数・最古の滞留日数を計測項目として `adoption-metrics.md` に定義し、機械集計する
  3. Promotion Gate の実行単位（要件単体か feature 単位か）と、decision-ref の確認結果を
     どこに記録するかを Design Gate で確定する。現状 promoted 遷移そのものに確認記録の欄がない
  4. verified のまま滞留し続けることが正常状態でないことを lifecycle.md に明記する
     （「verified = 完了」と読める現行記述が滞留を追認している）
- **対象ファイル**: `skills/sdd-core/references/lifecycle.md`、`skills/sdd-core/references/adoption-metrics.md`、
  `skills/sdd-core/scripts/spec_status.py`、`skills/sdd-report/scripts/sdd_report.py`、
  関連する SDD-FR 要件（SDD-FR-145 の改訂または後継）、関連テスト、bitz-sdd マニフェスト。
- **確認観点**: 未検分の代行遷移が滞留として可視化されること。滞留ゼロのワークスペースで
  ノイズが出ないこと。promoted 遷移に確認記録が伴うこと。既存の promoted 済み要件を
  遡及的に不整合としないこと。
- **影響推定・ロールバック**: ライフサイクル契約と可視化の変更であり軽量レーン不可。
  計測と可視化の追加は加法的で、問題時は当該セクションごと revert できる。
  3（Gate の実行単位と記録先）は契約変更のため Design Gate 必須。
- **依存**: SDD-FR-145（人間裁定必須遷移の2経路）、SI-SDD-027（代行可視化経路の導入）。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。SDD-FR-145 の担保を実効化する方向であり、経路自体は変えない |
| ガードレール抵触 | なし。可視化と計測の追加が主で、権限マトリクスは変更しない |
| 影響範囲 | sdd-core（lifecycle / metrics / status）、sdd-report、検査・テスト |
| 軽量レーン適否 | 不適。ライフサイクル契約に触れ、Gate の記録形式を新設する |

**推薦: accept**。担保が設計上1点に集約されているのに、その1点が動作していない。
現状は「裁定記録は残っているが誰も検分していない」状態であり、代行可視化経路の
前提が満たされていない。ただし優先度は SI-SDD-029 と同等かやや高い（規律の根幹に触れるため）。
