# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## リポジトリの役割

[Agent Skills](https://agentskills.io/specification) オープン標準に準拠したスキルの
**ライブラリ**。ここの `skills/` に置いただけではどのエージェントにも認識されず、
実環境で使うには `skill-packager` で各プラットフォームのパスへ配置する。

## 構成

```
skills/
├── skill-creator/      # 新規スキルの設計・雛形作成
├── skill-validator/    # 仕様準拠チェック（lint）
├── skill-optimizer/    # description最適化・本文分離・構造改善
├── skill-tester/       # テストケース設計と実行
├── skill-evaluator/    # 実行結果の採点・レポート作成
├── skill-packager/     # 実環境への配置・配布用zip化
└── skill-pipeline/     # 全工程を案内する統括スキル
evals/                  # tester/evaluator の作業成果物（cases.md, runs/, report.md）
```

スキル開発の標準フロー: creator → validator → tester → evaluator →
（不合格なら optimizer で改善して反復）→ packager。全体は `skill-pipeline` が統括する。

## 規約

- 各スキルは自己完結させる（フォルダ単位でコピーされるため、他スキルの
  `references/` を相対パスで参照しない。連携はスキル名の言及で行う）
- SKILL.md の frontmatter 仕様は `skills/skill-creator/references/spec.md` が正
- テスト成果物はスキルフォルダ内ではなく `evals/<skill-name>/` に置く
  （書式は `skills/skill-tester/references/test-design.md` で定義）
- スキルを追加・変更したら `skill-validator` のチェックリスト
  （`skills/skill-validator/references/checklist.md`）で検証する
- 全スキルの frontmatter に `metadata`（version/author/created/updated）を必須で
  持たせる。内容を変更したら semver で version を bump し updated を更新する
  （規則は `skills/skill-creator/references/spec.md` の「metadata運用規約」）
- インストール状態は配置先 frontmatter の `installed-at` / `installed-from` で
  自己記述する（`skill-packager` が管理。ライブラリ側には書かない）
