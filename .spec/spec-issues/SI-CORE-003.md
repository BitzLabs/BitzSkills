---
id: SI-CORE-003
raised_by: sdd-core 準拠運用（bitz-env のタスク分解 ENV-TSK-006〜012 で発見）
target: plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py（幽霊参照検出）
proposed_change_type: bump
status: proposed
---
- **矛盾/曖昧の内容**: SI-CORE-002 の修正は「ファイル自身の ID」の自己言及除外に
  留まったため、タスクファイルが `depends_on: [TSK-xxx]` で**他タスク**を参照すると
  依然として幽霊参照 FAIL になる（例: ENV-TSK-007 の `depends_on: [ENV-TSK-006]`）。
  sdd-implement の task-decomposition.md（公開契約に準ずる規約）は depends_on への
  タスク ID 列挙を必須と定めており、規約に従うほど検証が FAIL する矛盾。
- **提案する修正**: SI-CORE-002 で採らなかったもう一方の案を実施する —
  `.spec/tasks/` を既知 ID レジストリに登録する（ファイル名 stem をタスク ID として
  known set に加える。要件と同じ成果物扱いにする必要はなく、幽霊判定の除外で足りる）。
- **影響推定**: spec_inspect.py の inspect（ghosts 判定）のみ。誤検知の解消方向で、
  既存 PASS を FAIL に変えない。tests/test_spec_inspect.py にタスク間 depends_on の
  回帰ケースを追加する。
