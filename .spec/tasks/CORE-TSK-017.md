---
implements: CORE-FR-014
depends_on: []
boundary: plugins/bitz-flow/**, .claude-plugin/marketplace.json
status: implementing
---

### bitz-flow プラグイン構造の新設（3マニフェスト + marketplace + .spec/PROJECT.md）

- **作業内容**: AGENTS.md の「新しいプラグインの追加手順」に従い `plugins/bitz-flow/` を新設する。
  3マニフェスト（`.claude-plugin/plugin.json` / `plugin.json` / `.codex-plugin/plugin.json`、
  version 0.1.0 同値）、`skills/` ディレクトリ、共有 marketplace.json への末尾エントリ追加、
  `.spec/PROJECT.md`（FLW- プレフィックスの宣言・sdd-git 切り出しの経緯）まで。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
