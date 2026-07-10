---
id: SI-CORE-001
raised_by: skill-evaluator（Phase 5b eval / evals/bitz-sdd/report.md 改善提案2）
target: plugins/bitz-sdd/skills/sdd-design/SKILL.md（成果物定義と同期の表）
proposed_change_type: bump
status: accepted
---
- **矛盾/曖昧の内容**: sdd-design の成果物表では api-design.md が必須に見えるが、
  実際には API を持たないシステムでは未作成のまま `sdd_sync.py pull` が正しく SKIP する
  （Phase 5b eval TC-01 で実測）。表の見た目と実挙動が食い違い、利用者が不要な成果物を
  作ってしまう恐れがある。
- **提案する修正**: 成果物表に必須 / 任意の区別を明示する（ドメインストーリー = 任意、
  API 設計 = API を公開するシステムのみ、等）。文言のみの変更で挙動は変えない。
- **影響推定**: sdd-design/SKILL.md の表1箇所のみ。同期マッピング・スクリプトへの影響なし。
