# ADR-002: Gate語彙の所有権と診断のcheckpoint一般化

- 状態: Superseded
- Superseded by: [ADR-009](ADR-009_小規模チーム向け軽量コアとEARS-AI中核化.md)
- 決定日: 2026-08-25
- 関連: [01_共通アーキテクチャ.md](../01_共通アーキテクチャ.md), [04_SDDプロセス設計.md](../04_SDDプロセス設計.md), [05_QA品質保証設計.md](../05_QA品質保証設計.md)

## 背景

[01_共通アーキテクチャ.md](../01_共通アーキテクチャ.md) は「`bitz-quality` は `bitz-sdd` の内部実装を参照しない」と定めている。一方、`bitz-quality` の診断は `gate: "G4"` を持ち、Gate ID（G0〜G5）は `bitz-sdd` が定義するSDD固有語彙である。この状態では `bitz-quality` が `bitz-sdd` のステージモデルへ構造的に結合し、宣言した依存方向に違反する。

## 決定

`bitz-quality` の診断および品質プロファイルからGate語彙を除去し、フロー非依存の `checkpoint` へ一般化する。

- `bitz-quality` は「どのcheckpointでどの重大度が致命か」までを所有する。
- checkpoint識別子は `bitz-env` が管理する共通語彙とし、`spec-validate`、`pre-implementation`、`post-implementation`、`compliance-audit`、`sync` を初期値とする。
- checkpoint から Gate（G0〜G5）への写像は `bitz-sdd` が所有し、`bitz-quality` はGateを認識しない。
- EARS-AI の `sdd:GATE` は `bitz-sdd` の語彙として維持する。`quality:*` にGate語彙を置かない。

## 理由

- 依存方向の宣言を後退させずに矛盾を解消できる。
- `bitz-sdd` を使わない利用形態（CI上での仕様検証のみ、他フローエンジンとの併用）で `bitz-quality` を単体利用できる。
- Gate定義の変更が `bitz-quality` の破壊的変更にならない。

## 代替案

1. **Gate IDを `bitz-env` の共通語彙へ昇格**: 却下。Gateは開発フロー概念であり、`bitz-env` の「業務ロジックを持たない」責務に反する。
2. **依存方向の宣言を緩める**: 却下。設計原則3・4の実効性を失う。

## 影響

- [05_QA品質保証設計.md](../05_QA品質保証設計.md) の診断形式から `gate` を削除し `checkpoint` を追加する。
- [04_SDDプロセス設計.md](../04_SDDプロセス設計.md) にGate↔checkpoint対応表を追加する。
- 品質プロファイルのスキーマはcheckpoint単位で判定条件を持つ。
