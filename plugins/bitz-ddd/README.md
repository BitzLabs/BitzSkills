# bitz-ddd — DDD 設計手法プロバイダ

ドメイン駆動設計（DDD）の手法群を BitzSDD（`bitz-sdd` プラグイン）の設計工程へ
差し込む**設計手法プロバイダ**プラグインです。

> **併用前提**: 本プラグインは `bitz-sdd` プラグインとの併用が前提です。
> 成果物はすべて bitz-sdd が管理する `.spec/` に書き込み、`.spec` のファイル配置と
> frontmatter 書式（`sdd-core` スキルの assets/artifact-frontmatter.md が公開契約）に従います。
> 依存方向は bitz-ddd → `.spec` → bitz-sdd の一方向で、bitz-sdd は本プラグインを知りません
> （未導入でも SDD 単体で設計工程は完結します。`sdd-design` の軽量デフォルト設計に
> フォールバックするだけで、フローは止まりません）。

## 収録スキル

| スキル | 役割 | 成果物 |
|---|---|---|
| `ddd-story` | Domain Storytelling（ドメインストーリーテリング）。1ペルソナ × 1重要ジョブのハッピーパスを物語として記述し、要件派生（1 Activity ≒ 1 EARS 節）の根拠を作る | `.spec/design/stories/story-*.md` |
| `ddd-model` | 戦略設計・戦術設計。Entity / Value Object / Aggregate の判断、Bounded Context（境界づけられたコンテキスト）、CRUD マトリクスによる2パス導出 | `.spec/design/domain-model.md` |
| `ddd-evaluate` | ブラウンフィールド向け成熟度評価。DDD 12基準（Strategic 30% / Tactical 45% / Architecture 25%）+ MMI（Modularity Maturity Index）4軸の採点と統合改善計画 | `.spec/design/evaluation/` + `.spec/reviews/` |

### 発動の例

- 「ドメインストーリーを書こう」「ユーザーの流れを物語にして」 → `ddd-story`
- 「ドメインモデルを作って」「集約の境界を決めたい」 → `ddd-model`
- 「このコードベースの DDD 成熟度を測って」「MMI を評価して」 → `ddd-evaluate`

## インストール

```
# Claude Code
/plugin marketplace add BitzLabs/BitzSkills
/plugin install bitz-ddd@bitzskills      # bitz-sdd も併せて導入すること

# Antigravity 2.0
agy plugin install <このリポジトリ>/plugins/bitz-ddd
```

## bitz-sdd 工程との対応

- **グリーンフィールド（新規開発）**: `ddd-story` → `ddd-model` → `sdd-design`（API・アーキテクチャ）→ `sdd-review` → Design Gate
- **ブラウンフィールド（既存刷新）**: 現状分析 → `ddd-evaluate` → 統合改善計画 → 再設計
- トランザクション境界は `ddd-model` の集約境界が正となり、`sdd-data`（データ格納設計）が
  これに従って永続化戦略を組む

## 契約（.spec インターフェース）

本プラグインが bitz-sdd と連携できるのは、共有ファイルシステム上の**公開契約**があるためです:

1. **ファイル配置**: 成果物は `sdd-design` の成果物表と同じパスに書く
   （stories/ は自動集約、domain-model.md は docs/ へ同期される）
2. **frontmatter 書式**: `sdd-core` の assets/artifact-frontmatter.md に従う
   （ID は `DSN-NNN` 体系。Review 由来の成果物は `decision:` キー必須）
3. この契約に従う成果物は、書き手を問わず sdd-review / sdd-report / sdd-docs の
   処理対象として同一に扱われます

## 帰属（Attribution）

各スキルの手法は [wfukatsu/nexus-architect](https://github.com/wfukatsu/nexus-architect)
（MIT License, Copyright (c) 2026 Wataru Fukatsu）の domain-storytelling / domain-modeling /
evaluate-ddd / evaluate-mmi 系スキル群から、BitzSDD の憲法（proposed 機構・一方向派生・
権限分離）に合わせて翻案・蒸留したものです。原文は本リポジトリの
`docs/調査報告/04.nexus-architect/` に出所保存されています（原ライセンス全文は
bitz-sdd の README を参照）。
