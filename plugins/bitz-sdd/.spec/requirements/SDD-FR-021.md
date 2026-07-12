---
id: SDD-FR-021
version: 1.0
status: approved
domain: upstream
priority: high
origin: skills/sdd-discovery/SKILL.md v0.2.2（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-021 仮説検証ゲート判定の記録

- **説明**: プロジェクトの主要仮説のリスクを管理するため、仮説検証ゲートにおける Go/No-Go 判定の結果と判定エビデンスを `.spec/discovery/assumptions.md` に記録しなければならない。
- **受入基準 (EARS)**:
  - WHEN 仮説検証の評価を実施するとき THEN 開発者はテスト実行前に事前定義された kill/pivot 閾値を決定する SHALL
  - WHEN 崩壊クリティカルな仮説の中に「未検証」かつ「テストおよび閾値が未定義」のものが存在する状態で Discovery Gate 判定を実施するとき THEN システムまたは開発者は No-Go または Pivot 判定を決定し、`.spec/discovery/assumptions.md` に記録する SHALL
  - WHEN すべての崩壊クリティカルな仮説が「検証済み」または「テストおよび事前閾値が定義済み」の状態で Discovery Gate 判定を実施するとき THEN システムまたは開発者は Go 判定を決定し、`sdd-design` フェーズへ進む SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v1.4.5 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
