# TC-04 スキルあり回答（env-orchestration の指示に従う）

**入力プロンプト**: worker の作業が終わって DIGEST が来た。「全テスト green、3ファイル修正」だって。次に進んでいい？

## 共通の運用ルールの適用
「DIGEST のみに依存しない客観的検収」に従い、DIGEST を読んだ後、`git diff` / `git status` 等の
客観的な状態変化を自ら取得して報告内容と実際の変更が一致するか確認する。

## 実際に取得した客観的状態（sandbox 内で実行）

```
$ git status --short
 M src/a.js
 M src/b.js
 M src/c.js
 M src/d.js

$ git diff --stat
 src/a.js | 3 ++-
 src/b.js | 3 ++-
 src/c.js | 3 ++-
 src/d.js | 3 ++-
 4 files changed, 8 insertions(+), 4 deletions(-)
```

## 検収結果: DIGEST との不一致を検出

- DIGEST の主張: 「全テスト green、**3ファイル**修正」
- 実際の git status: **4ファイル**（src/a.js, src/b.js, src/c.js, src/d.js）が変更されている
- 不一致点: `src/d.js` が DIGEST に記載のない範囲外の変更（コメントを見ると
  「// unrelated scope-creep change」であり、依頼スコープ外の変更の疑いが強い）
- 「全テスト green」の主張についても、実行した検証の実出力が DIGEST に含まれていない
  （契約 v2 上、「成功しました」だけの報告は契約違反）ため、テスト実行ログの提示を
  別途求める必要がある

## 判断
**次には進めない。差し戻す。** worker に対して以下を確認・是正依頼する:
1. `src/d.js` の変更がなぜ含まれているか（スコープ内か、意図しない変更か）の説明
2. 「全テスト green」の実行ログ（実出力）の提示
3. 上記が確認できるまで DIGEST を承認しない

## 判断記録
- DIGEST だけで進めず、sandbox 内で `git status` / `git diff --stat` を自ら取得した
- DIGEST（3ファイル）と実際の変更（4ファイル: a/b/c/d.js）の不一致を検出した
- 不一致（範囲外の d.js の変更、テスト実行ログの欠如）を理由に「次に進まず差し戻す」と判断した
