---
implements: [ENV-FR-003, ENV-FR-004, ENV-FR-005, ENV-FR-006, ENV-FR-007, ENV-CON-003]
depends_on: []
boundary: plugins/bitz-env/skills/
status: done
---

### 生成層・協調運用スキル4種（env-init / env-orchestration / env-register / env-doctor）の実装

- **作業内容**: env-init（ユーザー確認付き生成・マーカー区間・モデル選択付き
  advisor/worker 生成、references/permissions.md + templates 5種）、env-orchestration
  （3パターンの決定木・検収義務・合議の進め方）、env-register（契約チェック・
  レジストリ登録・委譲マトリクス更新）、env-doctor（3層同期診断・強い方に揃える提案）
  の SKILL.md 一式を実装する。
- **実施記録**: 2026-07-11 実施（v0.1.0、コミット e95834a）。release_check.py 全 PASS
  （frontmatter 検査・claude/agy plugin validate 含む）。
- **備考**: reverse-derived（実装先行）。example-test（evals/）による検証は
  skill-tester の工程として未実施 — 各要件の verified 化はその完了後。
