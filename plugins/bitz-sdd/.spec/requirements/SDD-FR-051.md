---
id: SDD-FR-051
version: 1.0
status: draft
domain: upstream
priority: high
origin: skills/sdd-ops/SKILL.md v0.3.0（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-051 可観測性設計におけるアラートおよびランブック定義

- **説明**: アラート疲れを防ぎ、障害発生時の迅速な復旧を支援するため、すべてのアラートは定義済みの SLO に紐づけられ、かつ障害対応用のランブックへの参照が定義されなければならない。
- **受入基準 (EARS)**:
  - WHEN アラート設計を定義するとき THEN 開発者はすべてのアラートを定義済みの SLO に紐づけ、かつ障害復旧手順を記述したランブックへの参照をアラートごとに必須として定義する SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
