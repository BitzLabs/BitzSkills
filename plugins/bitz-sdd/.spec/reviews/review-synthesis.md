---
id: SDD-REV-005
title: "SDD-DSN-005 仕様変更の完全性境界レビュー"
status: active
version: 1.0
updated: 2026-07-27
owner: codex
decision: PASS
---

# SDD-REV-005 SDD-DSN-005 仕様変更の完全性境界レビュー

- **対象**: `SDD-DSN-005.md`、`design/worksheet.md`、SI-SDD-022 / 023 / 024、
  SI-CORE-035、CORE-FR-004 / 005
- **判定**: **PASS**
- **集計スコア**: 3.94 / 5.00
- **Gate状態**: レビューPASS、SI-CORE-035 accepted、Design Gate承認済み（2026-07-27）

## 観点別スコア

| 観点 | スコア | 重み | 判定 |
|---|---:|---:|---|
| consistency | 4.35 | 0.15 | PASS |
| data-integrity | 4.00 | 0.25 | PASS |
| operations | 4.00 | 0.20 | PASS |
| risk | 3.33 | 0.25 | PASS |
| business | 4.35 | 0.15 | PASS |

findings: P0 0件 / P1 1件 / P2 0件 / P3 1件。criticalは0件、majorは1件。

## P0 — Blocker

なし。

## P1 — Must Fix / 人間裁定

- **SYN-001**: 人間裁定はCLI外部の統制に依存する。
  - TTYと確認文字列は対話入力を強制するが、人間本人を証明しない。
  - provenanceを`interactive-confirmation-unverified`へ限定したため虚偽の機械保証は解消した。
  - SI-CORE-035で保証downgradeを明示的にacceptするまで、CORE-FR-005をsupersedeしない。
  - 人間性の機械強制が必要な環境は、host permissionsまたは検証可能なreceiptを別要件で扱う。

## P3 — Consider

- **SYN-002**: 非協調writerの最終競合窓は保証外として残る。
  - 全対応writerは共通workspace lockへ参加させる。
  - status・STATEの手編集と旧版CLIとの並行実行を禁止し、lifecycleと回帰テストへ反映する。

## レビュー中に設計へ反映した事項

- STATE hashの自己参照を避け、journalに完全after payloadを保持
- scaffoldにもWAL、atomic no-replace、3分類recoveryを適用
- PREPARED / APPLIED / COMMITTEDとcleanupのfsync順序を規範化
- SHA-256、raw UTF-8 byte、canonical JSON、Base64のschema v1契約を固定
- target commit SHAとmerge直前のrequired checkを束縛
- RPO=0の対象障害、媒体バックアップ責任、repository writerの信頼境界を明記

## Design Gateへの入力

レビュー基準を満たし、次の2点は2026-07-27にユーザーが承認した。

1. ルートのSI-CORE-035をacceptし、CORE-FR-004 / 005の後継化方針を承認する。
2. `design/worksheet.md`の8項目を承認し、SDD-DSN-005をactiveへ進める。
