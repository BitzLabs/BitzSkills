---
implements: CORE-CON-012
depends_on: []
boundary: tests/test_skill_script_reference.py, plugins/*/skills/*/SKILL.md, AGENTS.md
status: done
---

### SKILL.md のスクリプト呼び出し表記を3形式へ統一し機械検証する

- **作業内容**: `tests/test_skill_script_reference.py` を新設し、`plugins/*/skills/*/SKILL.md` を
  動的収集して実行例のパス表記を検査する。許容は `<このスキル>/` / `<NAME スキル>/` /
  `<リポジトリ>/` の3形式で、裸の `scripts/<name>.py` を規約違反とする。各形式について
  参照先スクリプトの実在を解決し、`<NAME スキル>/` が自スキルを指す場合も違反とする
  （フォルダ単位でコピーされたとき別スキルの導入が要ると誤解されるため）。
  プレースホルダ語彙は3形式に閉じ、収集がゼロ件になったら失敗させる。
  実データの修正として全プラグインの SKILL.md 44件を統一する。うち5件は `sdd_sync.py` を
  自スキル相対に見える形で参照していた `CORE-CON-004`（スキルの自己完結）違反であり、
  `<sdd-docs スキル>/` へ是正する。1件は消費先リポジトリの `bump_version.py` で
  `<リポジトリ>/` とする。AGENTS.md の定型手順節に3形式の表を追記する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
