---
implements: SDD-FR-166
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_update.py, plugins/bitz-sdd/skills/sdd-core/references/lifecycle.md, tests/test_spec_update.py
status: done
---

### verified → implementing の戻り経路を追加する

- **作業内容**: `spec_update.py` の `TRANSITIONS["requirement"]` に
  `("verified", "implementing"): "human"` を追加する。値を `"human"` にすることで、
  既存の人間裁定必須遷移と同じ扱い（`--interactive-decision` または
  `--on-behalf-of` + `--decision-ref`）になり、**機械が verified を勝手に取り消せない**。

  - `references/lifecycle.md` の状態遷移図と遷移表へ同じ行を追加し、
    **なぜ人間裁定必須なのか**（無条件に開くと verified の意味が薄れる）を一文で添える。
  - **`promoted → implementing` は追加しない**。Promotion Gate を通ったものは
    deprecated 経由でのみ変更する。
  - **既存の検証証跡を無効化しない**。`.spec/verification/` の記録は削除・改変せず、
    再び verified になるときに新しい証跡が追加される。

- **完了条件**: `tests/test_spec_update.py` に次のテストがあり PASS すること —
  人間裁定経路なしの `verified → implementing` が `authorization-required` で拒否され
  対象と STATE が変わらないこと、`--on-behalf-of` + `--decision-ref` なら遷移して STATE に
  provenance と裁定参照が残ること、`promoted → implementing` が `precondition-failed` で
  拒否されること、遷移後も `.spec/verification/` の既存ファイルが変わらないこと。
  `.venv/bin/pytest -q` が全件 PASS し、
  `python3 scripts/spec inspect --workspace . plugins/*` が全ワークスペース PASS のままであること。

- **備考**: 本変更は全ワークスペースへ波及する。委託元（bitz-flow `SI-FLW-040`）は
  本変更が main へ入り、消費側の固定版が更新されるまで該当タスクへ着手できない。
