---
implements: SDD-FR-136
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/(spec_status.py, SKILL.md, gates.md) と tests/test_spec_status.py に閉じる
status: done
---

### spec_status のフェーズ語彙正規化と design フェーズ追加（タスク ID はファイル名が正）

- **作業内容**: テスト先行で `tests/test_spec_status.py` に5系統の fixture
  （design のみ / discovery のみ / 両方 / design+draft 要件 / どちらも無し）と
  7語の値集合テストを追加 → `spec_status.py` に `PHASE_CODES` 定数・`.spec/design/` 検出・
  `design` フェーズ判定・`done` ラベル変更・`next_actions()` の Design Gate 準備提案を実装 →
  `sdd-core/SKILL.md` のフェーズ・ルーティング表と `references/gates.md` の語彙を7語に整合 →
  sdd-core の metadata bump と bitz-sdd のプラグイン bump。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
