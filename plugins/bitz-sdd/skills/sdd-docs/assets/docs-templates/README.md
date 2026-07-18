# docs/ テンプレート一式 (app / library 両対応)

`docs/`（人間ナラティブ / 遅く変わる意図）側の起動テンプレート。既存の `.spec/` 側
（EARS 契約・実行状態）、ADR、`sdd-core` スキルと整合する設計。

## 収録物（必須6章 + 任意1章）

```
docs/
  _conventions.md         ← frontmatter・ライフサイクル・配置ルール（最初に読む）
  _scaling.md             ← 最小→最大規模の拡張と docs↔.spec 境界
  MASTER.md               ← 索引。project_type / optional_chapters / excluded_paths を宣言
  00_はじめに/            ビジョン・スコープ・指標・ペルソナ・用語・ガバナンス
  01_システム仕様/        機能・非機能・制約の人間向け索引
  02_ユースケース/        利用シナリオと個別ユースケース
  03_設計仕様/            アーキテクチャ・API・データ・セキュリティ・ADR・実装規約
  04_テスト仕様/          テスト戦略・品質ゲート
  05_リリース・運用/      リリース・SLO・runbook・postmortem・教訓

optional/
  06_リファレンス/        外部API・CLI/SDK・移行ガイド（必要な場合のみdocs/へコピー）
```

必須6章は常に維持する。個々の文書は必要性に応じて増減できるが、各章の索引文書は残す。
`06_リファレンス` は `MASTER.md` に `optional_chapters: reference` を宣言した場合だけ追加する。

## app と library の使い分け

- 各テンプレの frontmatter `project_type` を `app` / `library` に設定する。
- 本文中の `<!-- app 固有 -->` / `<!-- library 固有 -->` ブロックは、該当しない側を削除。
- **app**: `公開API.md` は不要（削除可）。`アーキテクチャ.md` の app ブロックを使う。
- **library**: `公開API.md` は**必須**。C#/TS/Rust の互換性項を埋める。

## 管理対象外と段階拡張

調査メモやアーカイブを正式ナラティブと分ける場合は、docsルート相対パスを
`MASTER.md` の `excluded_paths` にカンマ区切りで宣言する。必須6章と任意章自身は除外できない。
外部API・CLI/SDK・移行ガイドが増えた時だけoptionalテンプレートを展開する。

## 既存フレームワークとの接続

- 意図は `docs/`、契約と状態は `.spec/`。同じ事実が両方にあれば意図=docs、契約=spec が勝つ。
- 派生は `docs/` → `.spec/` の一方向。閉じ戻し（昇格）は人間承認のみ。
- changeImpact に応じた version bump は `_conventions.md` の表に従う。
