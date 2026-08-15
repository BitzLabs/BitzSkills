# 裁定記録 — SI-FLW-059 の「公開 dispatcher 経由 E2E」の成立方法

- **日付**: 2026-08-16
- **裁定者**: hide
- **対象**: `SI-FLW-059`（公開 dispatcher の write 網羅）の着手方法
- **提示した選択肢**: A（dispatcher へハンドラ表を注入）/ B（他条件を先に満たし同一 PR で公開）/
  C（出口条件から「公開 dispatcher 経由」を外す）
- **裁定原文**: 「A. dispatcher へハンドラ表を注入する」
- **記録者**: claude（裁定者の明示指示に基づく代行記録・実行者未検証）

## 背景 — 着手前に判明した循環

`SI-FLW-059` は「`create` / `resume` を `cli.main` 経由の E2E で網羅する」ことを求める。
しかし 2026-08-15 の裁定で worktree operation は `_HANDLERS` から外れており、
`cli.main` は `UNSUPPORTED` を返す。一方、公開を戻すには M2 出口条件を満たす必要があり、
その出口条件に「公開 dispatcher 経由の capability 検証」が含まれている。

出口条件の文言は次のとおりで、求めているのは **dispatcher のコード経路を通ること**であり、
「事前に公開されていること」ではない。

| 出典 | 文言 |
|---|---|
| `FLW-DSN-014` | 承認capabilityが `create` / `resume` の write で**公開dispatcher経由**でin-band検証される |
| `FLW-REV-016:GP-001` | **公開dispatcherから** M2 scope の worktree write を起動し、capability検証とreceipt prefix収束をE2Eで確認する |

## 裁定

**A を採用する。** `cli.main()` がハンドラ表を引数で受け取れる形にし（既定は `_HANDLERS`）、
テストは `{**_HANDLERS, **_GATED_HANDLERS}` を渡して公開経路を丸ごと通す。

- **production に切替スイッチや環境変数を作らない。** 依存性注入であり、実行時に
  破壊的 operation を公開する経路を新設しない
- E2E は引数解析・承認モード判定・trusted key registry の読み取り・`apply()`・result 組み立ての
  全経路を通る。注入するのはハンドラ表の索引だけである
- 「出荷表に載っているか」は別途 `PUBLISHED_OPERATIONS` ⇔ `_HANDLERS` の import 時
  不変条件検査（`SI-FLW-061` で追加）と、公開集合を固定するテストが担保する。
  この2つで `GP-001` の要求を分割して満たす

## B / C を採らない理由

- **B**（他条件を先に満たし同一 PR で公開）: 実際の出荷面を検証できる点は優れるが、
  Completion Gate（人間の裁定）より先に destructive write の公開が起きる。
  2026-08-15 の裁定は「出口条件の充足時点で公開できる」としており、
  公開の是非そのものは Completion Gate の対象である。順序を崩さない
- **C**（出口条件の緩和）: `FLW-REV-015` / `016` が「ライブラリ直呼びでは公開経路を証明しない」と
  した指摘を巻き戻すことになる。指摘を消すのではなく満たす

## 帰結

| 対象 | 変更 |
|---|---|
| `flowlib/cli.py` | `main()` にハンドラ表の注入口を設ける（既定は `_HANDLERS`） |
| `tests/test_flow_m2_runtime.py` | `create` / `resume` と主要 fault 経路を公開経路で再構成 |
| `SI-FLW-059` | 本文へ本裁定を反映 |

予算は 2026-08-15 の M2 是正枠（残 2 PR / 10 session）から支出する。
