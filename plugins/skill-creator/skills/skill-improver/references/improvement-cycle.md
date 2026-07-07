# 自己改善サイクル詳細

`skill-improver` の各フェーズの詳細ルール。観察ログの書式そのものは
skill-observer の observation-schema.md が正典（このファイルでは繰り返さない）。

## Inspect: 集計テンプレート

open な観察を次の表に集計してユーザーに提示する。

```markdown
| スキル | ステップ | 件数 | 最大severity | 観察の要旨 | 修正候補 |
| --- | --- | --- | --- | --- | --- |
| skill-tester | 3. 実行 | 3 | medium | 保存先の迷いが3回 | 保存先の明記 |
| skill-packager | インストール | 1 | high | Antigravityパス誤り | パス表の修正 |
```

## Inspect: 優先順位の基準

上から順に優先する。

1. **critical**（件数によらず必ず対応候補に入れる）
2. **high かつ 2件以上**
3. **同一スキル・同一ステップで 2件以上**（severity 不問。繰り返し = スキル
   記述の構造的問題の兆候）
4. **high 1件**
5. medium / low の単発は、対象スキルを別の理由で修正するときに同時対応する
   か、open のまま蓄積を待つ

## Amend: 過学習を避ける修正の指針

- suggested_fix をそのまま貼り付けない。「この観察が二度と起きないためには
  スキルの何が曖昧だったのか」を特定し、その曖昧さを解消する記述にする
- 特定の固有名詞・特定プロジェクトの事情を SKILL.md に持ち込まない
  （例外: references/ の実測値表など、もともと具体値を持つファイルの修正）
- 修正で本文が肥大化しそうなら、references/ への分離（progressive
  disclosure）を含めて `skill-optimizer` に委ねる
- version bump の粒度: 文言の明確化・誤記修正は patch、手順やステップの
  追加・変更は minor（規則の正典は skill-creator の spec.md「metadata運用規約」）

## Evaluate: 検証の使い分け

| 修正の内容 | 検証 |
| --- | --- |
| すべての修正（共通） | `skill-validator` |
| critical / high 起因の修正 | + `skill-tester` → `skill-evaluator` を提案 |
| description の変更 | + 発動判定ケースの再テストを提案 |

## status 遷移

```
open ──(修正を反映)──→ resolved
  └──(対応しないと判断)──→ wontfix
```

- 遷移させるのは improver のみ。observer は open で書くだけ
- `resolved` / `wontfix` にする際は `resolved_by` に
  `"2026-07-07 skill-tester 0.1.1 で保存先を明記"` のように日付と要旨を書く
- 判断に迷う観察は open のまま残してよい（次回サイクルで再評価する）
- 行の書き換えは status / resolved_by の2フィールドに限る。ts や observation
  を後から編集しない（観察は記録された事実として保存する）

## サイクルの回し方（目安）

- open が 5〜10 件溜まったら、または critical が1件でも入ったら回す
- 1サイクルで修正するスキルは多くても 3〜5 個に抑え、修正→検証→人間の
  コミットまでを1単位で完結させる
- 同じ問題が resolved 後に再発した場合は、前回の修正が不十分だった証拠として
  severity を1段階上げて扱う
