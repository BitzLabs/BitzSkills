---
implements: SDD-FR-137
depends_on: []
boundary: sdd-core/scripts/(spec_labels,spec_status,spec_inspect).py, sdd-report/scripts/, scripts/release_check.py, tests/ に閉じる
status: done
---

### 対訳辞書の SSOT 化と表示層の日本語化（タスク ID はファイル名が正）

- **作業内容**: テスト先行で `tests/test_spec_labels.py` に13件（辞書網羅性・確定訳語の固定・
  併記形・逆引き一意性・正規化・複製一致）を追加 → sdd-core に `spec_labels.py` を新設 →
  sdd-report へ複製 → `spec_status.py` / `spec_inspect.py` / `sdd_report.py` を辞書経由の表示に
  差し替え → `release_check.py` に複製一致検査を追加（bitz-sdd 不在時は SKIP）→
  `tests/test_release_check.py` に4件追加 → 既存 `tests/test_sdd_report.py` の表示期待値を更新。
