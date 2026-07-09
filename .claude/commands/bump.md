---
description: プラグインの version を2マニフェスト（Claude Code / Antigravity）同時に semver bump する
argument-hint: <plugin名> [major|minor|patch]
allowed-tools: ["Bash", "Read"]
---

`python3 scripts/bump_version.py $ARGUMENTS` を実行し、結果を日本語で報告する。

- 失敗した場合はエラー内容を説明し、正しい引数（plugins/ 配下の実在プラグイン名）を提示する
- スキルの metadata（version/updated）更新漏れの警告が出たら、該当スキルが
  今回の変更対象かを確認し、対象なら frontmatter の更新を提案する
