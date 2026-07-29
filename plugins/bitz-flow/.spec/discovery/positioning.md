---
id: FLW-DSC-005
title: "bitz-flow v2 ポジショニング"
status: draft
version: 2.0
updated: 2026-07-29
owner: hide
---

# bitz-flow v2 ポジショニング

## 競合代替

| 代替 | 強み | bitz-flow v2 が埋める差 |
|---|---|---|
| 生の `git` / `gh` をエージェントが実行 | 完全な機能、追加導入なし | 入力検証、共通診断、圧縮出力、再開状態機械がモデル依存 |
| 現行 bitz-flow v1 | worktree / PR の重要事故を既にガード | スキルとCLIが分散し、release・Issue階層・共通schema・圧縮指標が不足 |
| GitHub Flow の手運用 | 単純で広く理解される | エージェント向け実行契約、worktree-first、圧縮結果、再開可能性を自前で用意する必要 |
| 自作shell / Python script | プロジェクトに最適化可能 | 毎回の再発明、モデル間差、テスト・配布・保守の重複 |

## Points of Parity

- Git feature branch、worktree、GitHub Issue、Draft PR、CI、squash merge、release を扱う。
- Conventional Commits と明示的な作業 ID を利用できる。
- Git / `gh` CLI の既存認証・設定・branch protection を尊重する。

## Points of Difference

1. **Single Gateway** — 通常操作を1つの dispatcher に集約し、SKILL.md から生コマンドの
   選択肢を除く。
2. **Decision-preserving Compression** — LLM要約ではなく Git / GitHub の構造化出力を
   決定論的に圧縮し、省略を明示する。
3. **Worktree-first** — 単独作業も物理分離し、並列化を後付け可能にする。
4. **Plan / Apply / Resume** — 外部状態変更を dry-run 既定、明示実行、再照会による
   冪等再開に統一する。
5. **SDD Boundary** — `.spec` の裁定・契約と GitHub の協調・実行状態を混ぜずに
   双方向リンクする。
6. **Evidence over prose** — エージェントの成功報告ではなく、短い機械出力と検証結果を
   merge / cleanup / release の根拠にする。

## Category

**AIエージェント向け Git / GitHub 操作カーネル兼開発フロー**

単なる「Gitの使い方スキル」ではなく、既存CLIの上に安全な操作契約を置き、その契約を使って
開発ライフサイクルを組み立てる。

## Positioning Statement

> 複数のAIエージェント／モデルで GitHub 開発を行う個人・小規模チームのための bitz-flow v2 は、
> Git / GitHub 操作を毎回再発明せず、少ないトークンで安全に完了したいという課題に対する
> 操作カーネル兼開発フローである。生CLIや個別の自作scriptと異なり、単一dispatcher、
> worktree-first、段階的な状態変更、BitzSDD接続、Issueからreleaseまでの再開可能な契約を
> Agent Skillとして自己完結で提供する。

## 採用技術の位置づけ

- Python 標準ライブラリ版は配布互換性を検証する reference implementation。
- Git / `gh` CLI が事実取得と状態変更の実行エンジン。
- 研究資料にある外部製品の削減率は方向性の参考であり、bitz-flow の性能主張には使わない。
