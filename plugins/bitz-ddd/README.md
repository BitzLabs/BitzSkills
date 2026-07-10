# bitz-ddd — DDD 設計手法プロバイダ

ドメイン駆動設計（DDD）の手法群を BitzSDD（`bitz-sdd` プラグイン）の設計工程へ
差し込む**設計手法プロバイダ**プラグインです。

> **併用前提**: 本プラグインは `bitz-sdd` プラグインとの併用が前提です。
> 成果物はすべて bitz-sdd が管理する `.spec/` に書き込み、`.spec` のファイル配置と
> frontmatter 書式（`sdd-core` スキルの assets/artifact-frontmatter.md が公開契約）に従います。
> 依存方向は bitz-ddd → `.spec` → bitz-sdd の一方向で、bitz-sdd は本プラグインを知りません
> （未導入でも SDD 単体で設計工程は完結します）。

## スキル一覧

| スキル | 役割 |
|---|---|
| `ddd-story` | Domain Storytelling（ドメインストーリーテリング）。ペルソナ×重要ジョブのハッピーパスを `.spec/design/stories/` に記述 |
| `ddd-model` | 戦略設計・戦術設計（Entity / Value Object / Aggregate、Bounded Context（境界づけられたコンテキスト）、2パス導出）。`.spec/design/domain-model.md` を作成 |
| `ddd-evaluate` | ブラウンフィールド向けの DDD 成熟度（12基準）+ MMI（Modularity Maturity Index）評価。採点は `.spec/design/evaluation/`、レポートは `.spec/reviews/` へ |

## インストール

```
# Claude Code
/plugin marketplace add <このリポジトリ>
/plugin install bitz-ddd@bitzskills

# Antigravity 2.0
agy plugin install <このリポジトリ>/plugins/bitz-ddd
```

## bitz-sdd 工程との対応

- グリーンフィールド: `ddd-story` → `ddd-model` → `sdd-design`（API・アーキテクチャ）→ `sdd-review`
- ブラウンフィールド: 現状分析 → `ddd-evaluate` → 統合改善計画 → 再設計

蒸留元: nexus-architect（MIT License、`docs/調査報告/04.nexus-architect/` に出所保存）の
domain-storytelling / domain-modeling / evaluate-ddd / evaluate-mmi 系スキル群。
