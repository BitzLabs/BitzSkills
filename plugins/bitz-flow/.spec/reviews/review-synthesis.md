---
id: FLW-REV-002
title: "bitz-flow ワークスペース多観点レビュー（全 design / requirements / discovery）"
status: active
version: 2.0
updated: 2026-07-22
owner: hide
decision: PASS
---

# FLW-REV-002 bitz-flow ワークスペース多観点レビュー

- **review_id**: FLW-REV-002
- **対象**: `.spec/design/FLW-DSN-001.md`、`.spec/requirements/FLW-FR-001.md`・`FLW-FR-002.md`、
  `.spec/discovery/*.md`（vision / scope / personas / metrics / positioning / assumptions）
- **判定**: **PASS**
- **集計スコア**: 4.29 / 5.00（PASS ≥ 3.5 / CONDITIONAL ≥ 2.5）
- **対象外**: data-integrity（本ワークスペースは git/gh 操作フローの規定であり、
  DB・永続データスキーマ・トランザクション境界を扱わないため。squash cleanup が扱う
  worktree・ローカル/リモート ref は git 自体が管理する参照情報であり、本レビューが対象とする
  「アプリケーションが所有する永続データ」には該当しない）
- **前版との差分**: 旧 FLW-REV-001（version 1.0, 2026-07-18）は FLW-DSN-001 / FLW-FR-001 のみを
  対象としていた。本版は 2026-07-19 に verified となった FLW-FR-002（flow-doctor）と
  discovery 一式を対象に追加し、ワークスペース全体を代表するレビューへ更新した。

## 観点別スコア

| 観点 | スコア | 重み（正規化後） | 主要所見 |
|---|---:|---:|---|
| consistency | 4.30 | 0.20 | 構造・トレース・用語は概ね一貫。FLW-FR-002 の反映漏れが2件（design/discovery） |
| data-integrity | 対象外 | — | 永続データを扱わないため範囲外 |
| operations | 4.70 | 0.267 | squash cleanup 側は完備。flow-doctor の「読み取り専用」主張の裏付けテストが無い |
| risk | 4.00 | 0.333 | 単一プロセスCLIのため分散・Saga次元はN/A。remote候補陳腐化とcleanup誤分類がminor |
| business | 4.20 | 0.20 | 実事故追跡は良好。discovery スコープの後追い反映漏れとH-D1期限未確定がminor |

findings: 統合前17件 → 重複排除後9件（P0: 0 / P1: 0 / P2: 0 / P3: 9）

## P0 — Blocker

なし。

## P1 — Must Fix

なし。

## P2 — Should Fix

なし。

## P3 — Consider

- **SYN-001** [RSK-403, BIZ-401] remote削除候補の陳腐化と安全側縮退（設計へ反映済み）
  - 検査時刻と操作直前の再照会を明示し、削除コマンドを生成しない現行方針を維持する。
- **SYN-002** [OPS-101, OPS-302] 構造化診断契約の回帰固定
  - 許可リストJSON、timeout境界、機密情報非転記を自動テストで固定する。
- **SYN-003** [OPS-201, OPS-202, OPS-301, OPS-401, OPS-402, BIZ-101] 状態機械とトレーサビリティの実装確認
  - 故障注入・入力境界・既存CLI互換性をFLW-FR-001へ紐づけて検証する。
- **SYN-004** [RVC-101, BIZ-102] FLW-FR-002（flow-doctor）が discovery のスコープ表・設計文書へ後追い反映されていない
  - scope.md の Must 帯に doctor 系ライフサイクルスキル（CORE-CON-008 準拠）を追記するか、
    CORE-CON-008 由来の横展開要件は discovery 更新を必須としない旨を明記する。
    設計文書を作らない doctor 系の運用自体は repo 全体の慣行と整合しており要件側のみで完結して良い。
- **SYN-005** [RVC-201] 旧 synthesis（FLW-REV-001）が FLW-FR-002 を対象外のまま PASS 判定していた
  - 本レビュー（FLW-REV-002）で対象範囲を全要件へ拡張し解消済み。以後 verified 要件が増えるたび
    レビュー対象を更新する運用をチェックリスト化する。
- **SYN-006** [OPS-102] flow-doctor の「読み取り専用」主張を裏付ける機械テストが無い
  - flow-doctor が実行するコマンド一覧を SKILL.md に列挙し非破壊性を明示するか、
    SI-FLW-002 の fetch分離パターンを doctor 系にも横展開する。
- **SYN-007** [RSK-201] worktree 未使用の squash merged branch が cleanup-partial に誤分類され得る（SI-FLW-004, open）
  - SI-FLW-004 の cleanup-branch 専用入口の設計に優先度を付ける。
- **SYN-008** [BIZ-402] 崩壊クリティカルな H-D1 仮説の再検証期限が「一定期間」のまま未確定
  - 具体的な期日または見直しイベントに置き換え、STATE.md 相当で追跡可能にする。
- **SYN-009** [RVC-202] open な spec-issue 4件（SI-FLW-002〜005）が要件・設計へ未反映
  - 次回 FLW-FR-00x 起票時に一括で棚卸しする。

## CONDITIONAL_PASS の通過条件

該当なし（PASS 判定のため）。

## 人間への裁定依頼

critical / major finding は無く、squash merge 後のブランチライフサイクル（FLW-FR-001 /
FLW-DSN-001）は前版どおり堅牢。今回追加スコープでは、新設された FLW-FR-002（flow-doctor）が
discovery・design 側の記述に後追い反映されていない点と、既に open で追跡中の spec-issue
（SI-FLW-002〜005）が示す既知の運用ギャップを P3 として明示した。いずれも実装のブロッカーではない。
この判定は推奨です。Design Gate / Promotion Gate の裁定は上記を確認のうえ行ってください。
