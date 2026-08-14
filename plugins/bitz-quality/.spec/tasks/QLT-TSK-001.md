---
implements: [QLT-FR-001, QLT-FR-002, QLT-FR-003, QLT-FR-004, QLT-FR-005]
depends_on: []
boundary: tests/test_quality_*.py, plugins/bitz-quality/skills/
status: done
---

### M1基盤ユニットテスト実装とEARS検証

- **作業内容**: M1 で実装した 4 つのスキル（`quality-init`, `quality-doctor`, `quality-score`, `quality-gate`）および `quality-core` の振る舞いに対するユニットテスト（`tests/test_quality_*.py`）を実装する。EARS 受入基準の境界値・異常系・CLI 実行結果を網羅する。
- **完了条件**:
  - `tests/test_quality_init.py`: 必須サブディレクトリ生成、台帳初期化、既存保護、--dry-run の検証
  - `tests/test_quality_doctor.py`: 正常診断、サブディレクトリ欠落、台帳欠落、破損JSONの検証
  - `tests/test_quality_score.py`: レベルA/B/Cスコア境界値、セキュリティ/影響範囲=3の強制レベルA、--save によるレポート出力検証
  - `tests/test_quality_gate.py`: クリーン差分PASS、デバッグ文検知FAIL、シークレット検知FAIL、--staged 検証
  - 全 pytest が PASS すること。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
