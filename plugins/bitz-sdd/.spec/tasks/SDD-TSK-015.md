---
implements: SDD-FR-130
depends_on: []
boundary: plugins/bitz-sdd/ 配下のみ
status: done
---

### sdd-doctor 環境診断スキルの追加

- **作業内容**: `plugins/bitz-sdd/skills/sdd-doctor/SKILL.md` を新規作成する。
  読み取り専用の標準ライフサイクルスキル `doctor` として、(a) `metadata.dependencies`
  の bitz-flow>=0.2 の有効性・semver 制約充足の診断（欠如時は導入手順つき修正案）、
  (b) `scripts/spec` ラッパーと `installed_plugins.json` からのバージョン非依存解決
  （SI-CORE-022 方式）の診断、(c) `.spec/` があれば `spec_status.py` の実行可否診断、
  を行い、全て OK なら OK 判定と根拠を報告する。env-doctor の構成・frontmatter 書式・
  報告形式を踏襲する。
- **実施記録**: 2026-07-19 実施。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
