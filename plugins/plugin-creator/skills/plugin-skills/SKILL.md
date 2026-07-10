---
name: plugin-skills
description: Claude Code / Antigravity 2.0 プラグインにスキル（skills/<name>/SKILL.md）を同梱するときのプラグイン固有の考慮事項（配置場所・自動発見・両対応・ローカルトリガーテスト）を案内する。「プラグインにスキルを追加したい」「プラグイン内のスキル構成」「スキルがプラグインで発動しない」と言われたときに使用する。スキル自体の作成・検証・テスト・最適化・配置の実作業と方法論は skill-creator プラグイン（skill-creator / skill-validator / skill-tester / skill-optimizer / skill-packager / skill-pipeline）が正であり、そちらへ誘導する。
metadata:
  version: "0.3.0"
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-11"
---

# plugin-skills — プラグインへのスキル同梱

プラグインにスキルを同梱する際の**プラグイン固有の考慮事項だけ**を扱う。

> **スキルの作り方そのもの（SKILL.md の記述指針・progressive disclosure・トリガー設計・
> 検証・テスト・最適化）は `skill-creator` プラグインが正**。本スキルでは重複させない。
> 新規作成は `skill-creator`、仕様準拠チェックは `skill-validator`、改善は `skill-optimizer` を使う。

## プラグイン固有の考慮事項

- **配置場所**: プラグインの `skills/` フォルダ内にスキルごとのサブフォルダ
  （`plugin-name/skills/skill-name/SKILL.md`）
- **自動発見**: `SKILL.md` を含むサブフォルダが自動で読み込まれる。マニフェストへの列挙は不要
- **ポータビリティ**: SKILL.md の形式は Agent Skills 標準として Claude Code と
  Antigravity 2.0 で共通。スキルは最もポータブルなコンポーネントであり、
  **両対応プラグインの中核はスキルで作るのが原則**
- **パッケージ不要**: プラグインの一部として配布されるため、スキル単体の zip 化は不要
  （単体配布したい場合のみ `skill-packager` スキルを使う）
- **命名**: プラグイン内のスキルは単一プレフィックスで統一する（例: `sdd-*`, `ddd-*`, `plugin-*`）

## ローカルトリガーテスト

```bash
# Claude Code
claude --plugin-dir /path/to/plugin
# スキルがトリガーされるはずの質問をして、読み込まれるか確認する

# Antigravity 2.0
agy plugin install /path/to/plugin && agy
# 確認後は agy plugin uninstall <name> で戻せる
```
