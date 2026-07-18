---
id: SDD-REV-001
title: "検証証跡と unit-test 語彙の設計レビュー"
status: active
version: 1.0
updated: 2026-07-18
owner: codex
decision: PASS
---

# SDD-REV-001 検証証跡と unit-test 語彙の設計レビュー

- **対象**: SDD-DSN-001 / SDD-FR-123 / SDD-FR-124 / SI-SDD-008 / SI-SDD-009
- **統合判定**: PASS
- **正規化総合点**: 4.50 / 5.00
- **重大度件数**: critical 0 / major 0 / minor 1 / info 3
- **対象外**: data-integrity（永続データを扱わないため）

| 観点 | スコア | 判定要約 |
|---|---:|---|
| consistency | 5.00 | Gate 順序、双方向トレース、用語が一貫 |
| operations | 4.20 | 証跡、秘密値除去、原子的リリース、撤回手順が具体的 |
| risk | 4.33 | 非分散として縮退。重大な未対処リスクなし |
| business | 4.70 | 責任分担、完了条件、実装粒度が妥当 |

## 非ブロッキングの継続観察

- 証跡不足による差し戻しが反復した場合は、STATE.md の必須フィールドを機械検査する
  spec-issue を起票する。
- 証跡不足差し戻し件数、verification_method 分類不能件数、旧版による語彙外停止件数を
  導入後の改善指標として観察する。

Design Gate を妨げる finding はない。
