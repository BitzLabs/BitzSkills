---
description: plugins/<name> の雛形（2マニフェスト + skills/）を作成し marketplace.json に登録する
argument-hint: <plugin名> [説明]
allowed-tools: ["Read", "Write", "Edit", "Bash"]
---

AGENTS.md の「新しいプラグインの追加手順」に従い、$ARGUMENTS で指定された
プラグインの雛形を作成する:

1. `plugins/<name>/.claude-plugin/plugin.json` を作成
   （name / description / version: "0.1.0" / author: "BitzLabs"）
2. `plugins/<name>/plugin.json` を作成（name / version: "0.1.0" / description。
   version は 1. と**必ず同じ値**）
3. `plugins/<name>/skills/` ディレクトリを作成
4. `.claude-plugin/marketplace.json` の `plugins[]` に
   `{"name": "<name>", "source": "./plugins/<name>", "description": "..."}` を追加
5. `python3 scripts/release_check.py` を実行して整合性を確認し、結果を報告する

スキルの追加は skill-creator スキル（プラグイン同梱の考慮事項は plugin-creator の plugin-skills）へ誘導する。
