---
id: DSN-002
title: "電卓CLI アーキテクチャ統合（最小限）"
status: draft
version: 1.0
updated: 2026-07-11
owner: br7.hide
---

# アーキテクチャ統合（最小限）

## 論理ビュー

```mermaid
flowchart LR
    User[ユーザー] -->|CLI引数/標準入力| Parser[Parser: 式の構文解析]
    Parser --> Evaluator[Evaluator: 式の評価]
    Evaluator --> Output[標準出力への結果表示]
```

- 永続化層は存在しない（`.spec/design/domain-model.md` のとおり完全ステートレス）
- Parser/Evaluator はいずれもプロセス内メモリのみで完結し、プロセス終了と同時に状態は破棄される

## プロセスビュー

- 1回のCLI起動 = 1回の計算 = 1プロセスのライフサイクル。常駐プロセスなし

## 配置ビュー

- ユーザーのローカル環境にバイナリ/スクリプトとして配置。サーバー・DBなし

## 技術適合性評価

| レイヤー | 技術 | 適合性 | 根拠 |
|---|---|---|---|
| Parser/Evaluator | 標準ライブラリの式評価 or 軽量パーサー | High | 状態を持たない単純な計算のみのため、外部依存を増やす根拠がない |
