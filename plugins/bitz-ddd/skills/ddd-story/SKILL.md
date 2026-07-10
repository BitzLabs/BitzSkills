---
name: ddd-story
description: BitzDDD — Domain Storytelling（ドメインストーリーテリング）でペルソナ×重要ジョブのハッピーパスを物語として記述し、.spec/design/stories/ に成果物を作成する設計手法スキル。ユーザーが「ドメインストーリー」「domain storytelling」「ストーリーで設計」「ユーザーの流れを物語に」と言及したとき、または bitz-sdd の設計工程（sdd-design）でグリーンフィールドのドメイン設計を始めるときに使用する。bitz-sdd プラグインとの併用が前提。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-10"
  updated: "2026-07-10"
---

# DDD Story — ドメインストーリーテリング

特定のペルソナが重要ジョブを達成する一本道（ハッピーパス）を物語として記述し、
後続のドメインモデリング（`ddd-model`）と要件派生（1 Activity ≒ 1 EARS 節）の根拠を作ります。

## 前提（bitz-sdd との契約）

*   本スキルは **bitz-sdd プラグインとの併用が前提**です。成果物は `.spec/design/stories/story-<ペルソナ>-<ジョブ>.md` に書き込みます。
*   frontmatter 書式は bitz-sdd の `sdd-core` スキルにある assets/artifact-frontmatter.md（公開契約）に従います。
*   ペルソナ・ジャーニーが未確立の場合は、先に `sdd-discovery` の実行を提案します（黙って一般フローに劣化させない）。

## 実行手順

1.  手法の詳細は `references/domain-story.md` を読み、規律（1ストーリー = 1ペルソナ × 1重要ジョブ、ユーザータスク粒度、根拠のないステップのでっち上げ禁止）に従います。
2.  `assets/domain-story.md` テンプレートをコピーして `.spec/design/stories/` 配下に作成します。
3.  作成後は bitz-sdd 側の工程に戻ります: `ddd-model` でドメインモデルへ昇華し、`sdd-docs` の pull で `docs/02-design/domain-story.md` に自動集約されます。
