---
id: SDD-FR-033
version: 1.0
status: approved
domain: upstream
priority: medium
origin: skills/sdd-design/SKILL.md v0.4.1（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-033 設計手法プロバイダによる代替可能性 (graceful degradation)

- **説明**: プラグインの導入状況に応じた設計プロセスの柔軟な適応を可能にするため、本格的な DDD ツールを提供する `bitz-ddd` プラグインの有無に応じて設計フローが自動的または手動で適応されなければならない。
- **受入基準 (EARS)**:
  - WHEN `bitz-ddd` プラグインが導入されているとき THEN システムまたは開発者は `ddd-story`、`ddd-model`、`ddd-evaluate` による詳細な設計プロセスを優先して適用する SHALL
  - WHEN `bitz-ddd` プラグインが導入されていないとき THEN システムまたは開発者は軽量ドメインスケッチを用いて本スキル単体でドメイン、API、アーキテクチャの設計を完結させる SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
