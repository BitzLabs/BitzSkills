---
id: SI-CORE-002
raised_by: sdd-core 準拠運用（Phase 8b の実演サイクル中に発見）
target: plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py（幽霊参照検出）
proposed_change_type: bump
status: accepted
---
- **矛盾/曖昧の内容**: `.spec/tasks/` のタスクファイルが frontmatter `id:` や見出しに
  自分自身のタスク ID（TSK 系）を書くと、幽霊参照として FAIL になる。
  tasks/ は load_requirements の走査対象外（成果物レジストリに登録されない）なのに、
  scan_refs は tasks/ 内の ID 出現をすべて参照として数えるため。
  一方で artifact-frontmatter.md（公開契約）は Tasks に `TSK` プレフィックスを定義しており、
  契約とツールの挙動が噛み合っていない。
- **提案する修正**: scan_refs で「ファイル自身の ID（ファイル名 stem と一致する ID）」を
  参照から除外する、または tasks/ を成果物レジストリに登録する。いずれかで
  「タスクが自分の ID を名乗れる」状態にする。
- **影響推定**: spec_inspect.py の scan_refs / load_requirements のみ。既存 PASS 判定を
  FAIL に変える方向の変更ではない（誤検知の解消）。
