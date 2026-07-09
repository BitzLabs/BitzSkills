# docs/ テンプレート一式 (app / library 両対応)

`docs/`（人間ナラティブ / 遅く変わる意図）側の起動テンプレート。既存の `.spec/` 側
（EARS 契約・実行状態）、ADR、`bitz-sdd` スキルと整合する設計。

## 収録物（最大規模構成）

```
docs/
  _conventions.md         ← frontmatter・ライフサイクル・配置ルール（最初に読む）
  _scaling.md             ← 最小→最大規模の拡張と docs↔.spec 境界
  MASTER.md               ← 索引。ここで project_type を宣言（★=最小起動 / ☆=library必須）
  01-context/             mission-vision★ / glossary★ / non-goals★ / constraints / stakeholders
  02-design/              ARCHITECTURE★ / domain-model / public-api☆ / security-model / decisions/
  03-implementation/      PATTERNS（恒久実装規約）
  04-quality/             TESTING（テスト戦略）
  05-operations/          OPERATIONS（運用・リリース）
  06-reference/           EXTERNAL-APIS / migration/
  07-governance/          GOVERNANCE（プロセス・方針・ロードマップ意図）
  08-knowledge/           LESSONS_LEARNED★ / postmortems/
```

最小起動は ★ の6点（library は ☆ public-api を足して7点）。03〜07 は必要になった層だけ
`_scaling.md` の拡張トリガーに従って足す。空フォルダを先に切らない。

## app と library の使い分け

- 各テンプレの frontmatter `project_type` を `app` / `library` に設定する。
- 本文中の `<!-- app 固有 -->` / `<!-- library 固有 -->` ブロックは、該当しない側を削除。
- **app**: `public-api.md` は不要（削除可）。ARCHITECTURE の app ブロックを使う。
- **library**: `public-api.md` は**必須**。C#/TS/Rust の互換性項を埋める。

## 最小起動セット → 段階拡張

まずは MASTER + mission-vision + glossary + non-goals + ARCHITECTURE + LESSONS の6点で開始
（library はこれに public-api を足して7点）。成長したら `06-reference/`（外部 API・移行ガイド）
などを追加する。「増やしすぎない」ことがドリフト防止の要。

## 既存フレームワークとの接続

- 意図は `docs/`、契約と状態は `.spec/`。同じ事実が両方にあれば意図=docs、契約=spec が勝つ。
- 派生は `docs/` → `.spec/` の一方向。閉じ戻し（昇格）は人間承認のみ。
- changeImpact に応じた version bump は `_conventions.md` の表に従う。
