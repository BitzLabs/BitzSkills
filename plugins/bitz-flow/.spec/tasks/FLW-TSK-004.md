---
implements: FLW-FR-002
depends_on: []
boundary: plugins/bitz-flow/ 配下のみ
status: done
---

### flow-doctor 環境診断スキルの実装

- **作業内容**: `plugins/bitz-flow/skills/flow-doctor/SKILL.md` を新規作成する。
  読み取り専用で (a) git の存在とバージョン（2.5 以上）、(b) gh CLI の存在と認証状態
  （`gh auth status`。欠如・未認証は導入・認証手順つき修正案。flow-pr を使わない運用では
  警告に留める）、(c) Git リポジトリ内ならリモート origin の有無とデフォルトブランチの
  特定可否を診断する。全て OK なら OK 判定と根拠を報告する。frontmatter は兄弟スキル
  （flow-core 等）の書式に合わせる。実装後はプラグイン version を bump する。
- **完了条件**: skill-validator チェックリスト通過、release_check / spec inspect / pytest が
  すべて PASS すること。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
