---
id: SDD-FR-060
version: 1.0
status: approved
domain: verification
priority: high
origin: skills/sdd-review/SKILL.md v0.2.2（reverse-derived）
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-060 統合報告書への decision キー必須出力

- **説明**: sdd-review は複数の観点からのレビュー結果を統合する際、統合報告書（REV-NNN）の frontmatter に判定結果（PASS / CONDITIONAL_PASS / FAIL）を示す `decision` キーを必須で出力しなければならない（公開契約に該当）。
- **受入基準 (EARS)**:
  - WHEN レビューの統合判定 (synthesis) を行い統合報告書を生成する THEN sdd-review は frontmatter に `decision: PASS | CONDITIONAL_PASS | FAIL` を必須で出力 SHALL
- **検証手段**: SKILL.md / references の目視確認 + skill-validator チェックリスト
- **Revision History**:
  - 1.0 (2026-07-12) 初版（実装 v0.2.2 からの reverse-derived。ワークスペース新設に伴う逆起票）
  - 1.0 (2026-07-12) 人間裁定により approved 化（チャット指示）
