# EARS-AI 統合規格 設計資料

## 1. ステータス

- 規格名: EARS-AI
- 状態: Draft
- Core初期版: 1.0.0
- Core管理主体: `bitz-core`
- 主対象: 個人から数人のAI支援開発

正式規格の履歴はCore 1.0.0から開始する。`01.検討資料/`の第2版・第3版・第5版は非規範の
調査資料であり、正式版履歴へ含めない（[ADR-001](../../02.設計書/10_決定記録/ADR-001_EARS-AI旧検討版の位置づけ.md)）。

## 2. EARS-AIを中核にする理由

EARS-AIは、自然言語要求へ次の機械可読な軸を付与する。

- 安定ID
- 実行主体
- 発動条件
- 規範強度
- 応答・生成・制約の区別

これにより、人間は通常の文章として読み、Parserは同じ構造を軽量なSemantic IR（AST互換名）へ変換し、
AIはpurpose別に投影された要求を利用できる。EARS-AIはBitz AI-SDDの中心的な入力形式である。
関連文書の選択はLLMへ委ねず、[Context Resolution仕様](../02_SPECファイル規定/10_Context%20Resolution仕様.md)の
型付き依存と完全閉包を使用する。完全閉包を検査した後、全`MUST`を含むConstraint Ledgerと、
`full` / `normative` / `reference`の段階的Projectionを生成する（[ADR-014](../../02.設計書/10_決定記録/ADR-014_Semantic-IRと段階的Context-Projection.md)）。

## 3. 保証境界

EARS-AI Coreが保証するもの:

- 構文、タグ順序、ID、語彙の決定論的解析
- 同一入力・同一バージョンから同一Semantic IRを生成すること
- 参照・トレース・機械的制約の検査可能性
- 自由記述本文と拡張情報を失わないこと

EARS-AI Coreが保証しないもの:

- 自由記述本文の意味が正しいこと
- 異なる文章が意味的に同一かどうか
- LLMが要求どおりに実装すること
- LLM出力が決定論的になること
- タグだけでハルシネーションを防止できること

意味上の妥当性は人間が承認し、実装の適合性は実行可能なテストで確認する。

## 4. 構造

```text
EARS-AI Core 1.0                 bitz-core
├── 構文・共通語彙・共通Semantic IR（AST互換名）
├── Parser / Serializer / Core Validator
└── 拡張登録プロトコル

任意Profile（1.0後に実証して追加）
├── SDD Profile
├── Quality Profile
└── DDD Profile
```

Core 1.0の実装対象はCore Parser、Semantic IR、Validatorに限定する。Profile文書は拡張点を予約する設計資料であり、
Core 1.0の出荷条件ではない。

## 5. 原則

1. Coreは小さく、安定し、特定の開発フローやドメインに依存しない。
2. 発動条件、規範強度、処理種別を別軸として扱う。
3. 1規範文は1つの安定IDと1つの主要結果を持つ。
4. Markdownは1回だけ解析し、拡張とContext Projectionは共通Semantic IRを利用する。
5. 未知の拡張情報を保持し、無断で削除しない。
6. Parserはネットワーク、LLM、文書中の命令に依存しない。
7. EARS-AI本文は仕様データであり、ツール権限を付与しない。
8. Profileは実タスクで便益が確認されるまで既定で無効とする。

## 6. 文書一覧

| 文書 | 内容 | Core 1.0 |
|---|---|:--:|
| [01_Core構文仕様.md](01_Core構文仕様.md) | 共通タグ、文法、意味軸 | 必須 |
| [02_拡張プロファイル仕様.md](02_拡張プロファイル仕様.md) | 名前空間とValidator契約 | 必須 |
| [06_AST・パーサー仕様.md](06_AST・パーサー仕様.md) | Semantic IR、Parser、Diagnostic | 必須 |
| [07_適合性・バージョン・移行仕様.md](07_適合性・バージョン・移行仕様.md) | 互換性と旧版移行 | 必須 |
| [08_記述例・アンチパターン.md](08_記述例・アンチパターン.md) | 例とアンチパターン | 必須 |
| [03_SDDプロファイル.md](03_SDDプロファイル.md) | 軽量SDD拡張候補 | 将来・任意 |
| [04_Qualityプロファイル.md](04_Qualityプロファイル.md) | 品質拡張候補 | 将来・任意 |
| [05_DDDプロファイル.md](05_DDDプロファイル.md) | DDD拡張候補 | 将来・任意 |

## 7. 参考規格

EARSの少数テンプレートによる構造化方針を基礎とする。ただし原典の`shall`を、発動条件、規範強度、
処理種別へ分解する。EARS-AI固有の有効性は前提とせず、通常Markdown・従来EARSとの比較で検証する。

- Alistair Mavinほか, EARS, RE 2009, DOI `10.1109/RE.2009.9`
