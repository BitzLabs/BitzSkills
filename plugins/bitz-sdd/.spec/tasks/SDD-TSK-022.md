---
implements: SDD-FR-138
depends_on: []
boundary: sdd-core/scripts/spec_update.py と tests/test_spec_update.py に閉じる
status: done
---

### spec_update.py の日本語ラベル入力の正規化（タスク ID はファイル名が正）

- **作業内容**: テスト先行で `tests/test_spec_update.py` に8件（要件・spec-issue・タスク各種別の
  正規化、権限マトリクスの維持、併記形の非受理、未知語の不正遷移、同値入力が『遷移不要』に
  なること、STATE.md が機械値で記録されること）を追加 → `spec_labels.normalize_status` を
  `cur == new` 判定より前に適用。表示層とは独立コミットに保つ。
