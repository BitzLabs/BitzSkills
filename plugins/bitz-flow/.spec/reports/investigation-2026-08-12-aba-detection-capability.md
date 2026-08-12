# 調査記録 — ABA 検出 provider capability の実在性

- **日付**: 2026-08-12
- **調査者**: claude
- **対象**: `FLW-REV-012:GP-004`（blocking）
- **問い**: GitHub は「plan 時 snapshot 以降に remote ref 更新イベントが発生していないこと」を
  観測可能な形で提供するか。実在しなければ `FLW-DSN-016` の capability 分岐を削除して
  単一経路へ確定させる。
- **方法**: `gh api` による実測（github.com、対象 repo は `BitzLabs/BitzSkills`）

## 結論

**capability は実在する。ただし ABA の「不在」を証明する用途には使えない。**

`FLW-DSN-016` の現行記述は「capability あり → 停止 / なし → 承認要求」の2分岐だが、
これは **capability があれば ABA を否定できる**という前提を暗に含んでいる。実測の結果、
その前提は成り立たない。分岐は削除せず、**3経路へ再構成**したうえで
**いずれの経路も人間承認を省略しない**ことを明示する必要がある。

## 実在性 — Repository Activity API

`GET /repos/{owner}/{repo}/activity` が ref 更新イベントを返す。ABA 判定に必要な
情報は揃っている。

| 項目 | 実測結果 |
|---|---|
| 提供 field | `activity_type` / `before` / `after` / `ref` / `timestamp` / `actor` |
| 観測した `activity_type` | `push` / `force_push` / `branch_creation` / `branch_deletion` / `pr_merge` |
| `force_push` の第一級サポート | **あり**。直近100件中1件、`activity_type=force_push` での絞り込みも成功 |
| `ref` 絞り込み | **可**（`?ref=refs/heads/main`） |
| `activity_type` 絞り込み | **可** |
| 時間絞り込み | `time_period` パラメータあり |
| ページング | cursor 方式（`Link: rel="next"`） |
| 遡及範囲 | 対象 repo では作成時（2026-07-05）まで到達。上限は未確認 |
| 必要権限 | `repo` scope で取得できた |

実測した `force_push` の例（before/after が別系列であることの確認）:

```
2026-08-11T23:25:37Z refs/heads/docs/bitz-flow-si-flw-039-write-state-notation e9dc73fb->101fa1e2
2026-07-14T21:34:03Z refs/heads/fix/si-core-023-canonical-inspect-cmd         d87f22b9->3029a367
```

## 使えない理由 — 不在証明が成立しない

ABA 検出が必要とするのは**否定的な主張**である。

> plan 時 snapshot `T0` から apply 時 `T1` の間に、対象 ref の更新が **1件も発生していない**

Activity API が提供できるのは**肯定的な主張**だけである。

> これらの更新が記録されている

この2つは同じではない。**Git Refs API（`GET /git/ref/...`）と Activity API は別サブシステム**であり、
GitHub は両者の整合性について保証を文書化していない。したがって次が起こり得る。

1. 攻撃者が `X → Y → X` と force push する
2. apply 直前に Refs API を読む → `X`（plan 時と一致。CAS は成立してしまう）
3. Activity API を読む → **該当エントリがまだ現れていない**
4. 「更新なし」と誤って結論し、削除を実行する

**遅延の上限を実測で確定することはできない。** 実験で「速いことが多い」は示せても、
「遅くならない」は示せない。不在証明はこの性質上、観測遅延がゼロであることの保証を要する。

なお本調査では、この不健全性を確認するための **push 実験は行っていない**。
実験が示せるのは典型値だけであり、上限の保証にはならないため、
リポジトリを変更するコストに見合わないと判断した。

## 設計への影響

### 現行記述の問題

`FLW-DSN-016` §「`git.delete-remote-branch` の安全条件」の ABA 行、および
fixture `M2-FLT-038`（「capability ありで停止、なしで承認要求」）は、
**capability あり かつ activity が空**のケースを扱っていない。
このまま実装すると「観測範囲で更新なし ⇒ 安全」と解釈され、上記の誤結論へ至る。

### 是正案 — 3経路へ再構成し、承認は常に要求する

| 経路 | 条件 | 結果 |
|---|---|---|
| A | capability あり ＋ activity に `T0` 以降の更新**あり** | **`BLOCKED`**（積極的検出。最も強い証跡） |
| B | capability あり ＋ activity に更新**なし** | 承認要求。**「観測範囲では更新なし。これは不在証明ではない」**と明示 |
| C | capability **なし**（GHES・権限不足・API 不提供） | 承認要求。**「ABA 不検出」**と明示 |

**capability は承認を省略する根拠にならない。** 変わるのは human へ提示する証跡の質だけである。
経路 A だけが自動的な安全側停止を与え、B と C は「人間が判断するための材料の濃さ」が違う。

この整理により、GP-004 が懸念した**死に枝は生じない**。経路 A は実在する capability の
正当な用途であり、B / C は capability の有無で提示内容が変わるため、どの枝も到達可能である。

### capability 検出の扱い

`FLW-DSN-014` の capability matrix へ `ref activity read` を追加する。
GHES での提供状況は本調査では確認していない（github.com のみ実測）。
capability contract の既定どおり、実行時に検出して
`AVAILABLE` / `UNSUPPORTED` / `UNAVAILABLE` を判定する。
**判定不能を「更新なし」へ倒さない**（経路 C として扱う）。

## GP-004 の充足

GP-004 の指示は「実在しなければ capability 分岐を削除して単一経路へ確定させる」だった。
実在したため分岐は残すが、**分岐の意味を「承認の要否」から「証跡の質」へ変更**する。
これは GP-004 の趣旨（死に枝を残さない・実在性を先に確かめる）を満たす。

## 反映先

| 対象 | 変更 |
|---|---|
| `FLW-DSN-016` | ABA 行を3経路へ再構成。`M2-FLT-038` を3ケースへ分割 |
| `FLW-DSN-014` | capability matrix へ `ref activity read` を追加 |
| `FLW-CON-006` | **変更不要**。現行の受入基準は「観測できない THEN 承認要求」であり、観測できる場合に承認を省略できるとは書いていない |
