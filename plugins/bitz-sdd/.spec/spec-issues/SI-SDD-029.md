---
id: SI-SDD-029
raised_by: SI-SDD-011/014/016 実装後の振り返り（2026-07-29）
target: manual-check 比率の監視未実装と機械検査からの二重免除
proposed_change_type: modify
status: open
---
- **目的**: `adoption-metrics.md` は「verification_method の `manual-check` 比率（20%超で見直し）」を
  補助監視項目として宣言しているが、**比率を計算する実装がどこにも無い**。実測では全ワークスペース
  合計 120 件のうち manual-check が **51 件（42.5%）**で、宣言した閾値の 2 倍を超えている。
  加えて直近の2つの改善が manual-check を機械検査から外している:
  SDD-FR-148（未参照要件の報告を manual-check だけ別セクションへ分離）と
  SDD-FR-153（証跡欠落 WARN の対象から manual-check を除外）。
  いずれも個別には正当（自動テスト参照・自動証跡が原理的に生じない）だが、結果として
  **最大カテゴリが両方の機械検査から二重に免除**され、検証が最も弱い領域が最も監視されていない。
  「検証中心」を掲げる枠組みとして倒立しているため解消する。
- **提案する修正**:
  1. manual-check 比率を機械集計し、閾値超過を `spec_status` / `sdd-report` に警告として出す
     （閾値は `adoption-metrics.md` の宣言を単一の正とし、コードへ直書きしない）
  2. manual-check 要件に対する**実施記録の形式**を定義する。現状は verification.md が
     「要件内に列挙した手順を人間が実施し記録」とだけ述べ、記録先も書式も未定義であり、
     実施したか否かを機械はもちろん人間も判定できない
  3. 実施記録を持たない manual-check 要件を verified 相当として扱ってよいかを Design Gate で裁定する
     （SI-SDD-016 の証跡機構を manual-check 向けに拡張するか、別形式にするか）
  4. 既存 51 件の棚卸し方針（自動化可能なものを他の verification_method へ移すか、
     manual-check のまま実施記録を遡及するか、遡及しないか）を裁定する
- **対象ファイル**: `skills/sdd-core/references/adoption-metrics.md`、`skills/sdd-core/references/verification.md`、
  `skills/sdd-core/scripts/spec_status.py`、`skills/sdd-core/scripts/spec_inspect.py`、
  `skills/sdd-report/scripts/sdd_report.py`、関連する SDD-FR 要件、関連テスト、bitz-sdd マニフェスト。
- **確認観点**: 比率が実測と一致すること。閾値が文書とコードで二重定義にならないこと
  （SDD-FR-150 のマーカー方式が使える）。manual-check を持たないワークスペースで警告が出ないこと。
  実施記録の形式が秘密値を保存しないこと（SDD-FR-152 と同じ制約）。
- **影響推定・ロールバック**: 1 は集計の追加で加法的。2〜4 は検証契約に触れるため軽量レーン不可。
  4 の棚卸しは範囲が大きいため、方針裁定と実施を分離して段階的に進める。
- **依存**: SDD-FR-148（manual-check の未参照報告分離）、SDD-FR-151〜153（検証証跡）、
  `adoption-metrics.md` の補助監視宣言。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。SDD-FR-148 / 153 の除外判断自体は維持し、代わりの監視を足す |
| ガードレール抵触 | なし。実施記録の形式は SDD-FR-152 の非保存制約を継承する |
| 影響範囲 | sdd-core（metrics / verification / status / inspect）、sdd-report、検査・テスト |
| 軽量レーン適否 | 不適。検証契約に触れ、新しい記録形式を定義する |

**推薦: accept**。宣言した閾値の 2 倍を超えたまま誰も気づけない状態であり、
manual-check が「検証しないための逃げ道」として機能し始めている。ただし 4（既存 51 件の棚卸し）は
本 spec-issue のスコープに含めず、方針裁定の結果を受けて別途起票するのが妥当。
