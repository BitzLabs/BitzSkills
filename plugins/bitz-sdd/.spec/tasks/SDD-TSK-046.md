---
implements: SDD-FR-157
depends_on: [SDD-TSK-044]
boundary: skills/sdd-core/scripts/spec_update.py, skills/sdd-core/references/lifecycle.md, skills/sdd-core/references/gates.md, skills/sdd-core/SKILL.md, tests/test_spec_update.py
status: done
---

### verified→promoted に GatePassage の参照を必須化する

- **作業内容**: `spec_update.py` に `--gate-passage` を追加し、`verified → promoted` を含む
  要求では必須にする。GatePassage の実在・`gate` が `promotion` であること・遷移対象の
  全 ID が `scope` に列挙されていることを**適用前**に検査し、満たさない要求は対象と STATE を
  変更せず非ゼロで終了する。`verified → promoted` 以外で `--gate-passage` が渡された場合は
  黙認せず拒否する。受理した遷移は STATE の構造化 event へ `gate_passage` を追加し、
  表示行にも Gate 通過記録を明示する（`schema_version` は 2 のまま — 必須キー集合は不変で
  追加キーは既存検査を通るため、順序6 を加法的に保てる）。既存の promoted 済み成果物へは
  遡及しない。`lifecycle.md` に「verified は完了ではない」節、`gates.md` に GatePassage の
  起票手順、`SKILL.md` に CLI 例と権限節の追記を行う。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
