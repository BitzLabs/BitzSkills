---
implements: [QLT-FR-013]
depends_on: [QLT-TSK-007]
boundary: plugins/bitz-quality/README.md, plugins/bitz-quality/.spec/
status: done
---

### bitz-quality v1.0.0 総合ドキュメント整備と総合検証

- **作業内容**: `plugins/bitz-quality/README.md` および `.spec/ROADMAP.md`、`.spec/PROJECT.md` を M1〜M5 の完成版に合わせて更新し、全テストおよびリリースチェックを完了する。
- **完了条件**:
  - `plugins/bitz-quality/README.md` の更新（全スキル・アーキテクチャ・使い方）
  - `python3 scripts/bump_version.py bitz-quality major` による v1.0.0 への昇格
  - `release_check.py` および全 pytest が PASS すること。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
