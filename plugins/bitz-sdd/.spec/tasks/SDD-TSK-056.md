---
implements: SDD-FR-167
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_scaffold.py, plugins/bitz-sdd/skills/sdd-review/SKILL.md, tests/test_spec_scaffold_review.py
status: done
---

### spec_scaffoldへreview種別を実装する

- **作業内容**: `spec_scaffold.py` へ `review` 種別を追加し、`<REV-ID>.json` と
  `<REV-ID>.md` を採番付きで生成する。

  - JSON は `SDD-FR-158` / `SDD-FR-161` の必須キーをすべて含む。
  - `--findings N` / `--preconditions N` で雛形の件数を指定できる。
  - `gate_preconditions[].id` は **`GP-NNN`** 形式（`tracked_by` 側は `<REV-ID>:GP-NNN`）。
  - `basis: verified` の雛形には `evidence` を置く。
  - `findings[].source` は**空配列にしない**（`tracked_by` 以外は空だと必須キー欠落と判定される）。
  - 既定の `verdict` / `decision` は **FAIL**。埋めないまま PASS が残る事故を防ぐ。
  - `next_number` は JSON も走査する（review は JSON が実体で、`.md` だけ見ると採番が衝突する）。
  - `sdd-review` の SKILL.md 手順4へ「まず scaffold で雛形を作る」を追記する。

- **完了条件**: 生成した雛形が**そのまま** `spec_inspect` を通ること（問題 0）。
  件数指定つきの雛形も通ること。採番が既存 ID と衝突しないこと。既存4種別が壊れないこと。
  `.venv/bin/pytest -q` が全件 PASS し、
  `python3 <リポジトリ>/scripts/spec inspect --workspace . plugins/*` が全ワークスペース PASS であること。

- **備考**: テスト内のダミー ID は文字列連結で分割する。直書きすると本リポジトリの
  `spec_inspect` が幽霊参照として誤検知する（`tests/test_spec_update.py` の `REF_ISSUE_ID` と同じ回避）。
