---
id: SDD-FR-053
version: 1.0
status: verified
domain: upstream
priority: high
origin: skills/sdd-ops/SKILL.md v0.3.0（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-053 バックアップリストア検証およびDR試験の定義

- **説明**: 災害発生時におけるデータおよびサービスの確実な復旧力を保証するため、バックアップ設計と災害復旧（DR）設計において定期的なテスト計画と判断基準を伴う手順が定義されなければならない。
- **受入基準 (EARS)**:
  - WHEN バックアップおよび災害復旧（DR）設計を実施するとき THEN 開発者はバックアップの取得頻度と保持期間だけでなく定期的なリストア試験の計画を明文化し、かつ責任者と判断基準を含む障害シナリオ別の復旧手順（ランブック）を定義する SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
