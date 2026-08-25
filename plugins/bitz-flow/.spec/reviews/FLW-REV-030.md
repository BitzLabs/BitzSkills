---
id: FLW-REV-030
title: "GP-001〜006消化主張の検証"
status: active
version: 1.0
updated: 2026-08-25
owner: claude
decision: FAIL
---

# GP-001〜006「全件消化」主張の検証

- **対象**: `FLW-TSK-130`／`131`／`132`（`FLW-REV-029` の GP-001〜006 是正）、
  `FLW-DSN-017` v3.2、`FLW-CON-008` v1.2、flow-core の実装と test
- **判定**: **FAIL**
- **集計スコア**: **2.28**（閾値 2.5 未達。`risk` 2.00 も floor 2.5 に未達）
- **セカンドオピニオン**: codex（OpenAI）**FAIL**、antigravity（Gemini）**FAIL**。
  **統合判定より前に実施**（`FLW-REV-029` で確立した手順）

## 観点別スコア

| 観点 | 今回 | 前回(029) | 重み | 主要所見 |
|---|---:|---:|---:|---|
| consistency | **1.80** | 2.00 | 0.15 | §13.7 の表と散文が矛盾。§9.1／§10 に Linux 限定が未反映。行3 が §13.4 の実測と食い違う |
| data-integrity | **2.50** | 3.80 | 0.25 | `verify_receipt` を壊しても全 test が通る。`quarantine` の意味論が公開契約から外れた |
| operations | 1.80 | 1.80 | 0.20 | 公開経路の deadline に前段の抜け道。`--timeout-seconds` が 30 秒上限を上書き |
| risk | **2.00** | 2.33 | 0.25 | P0 2件。うち1件は「是正済み」と報告した箇所 |
| business | 3.50 | 3.50 | 0.15 | 公開面の機能は増えていない |

findings: 統合前 19 件 → 重複排除後 **10 件**（**P0: 2** / P1: 5 / P2: 3 / P3: 0）。

## 結論を一文で

**`GP-001`〜`006` の「全件消化」は成立しない。** 是正そのものが不十分であるだけでなく、
**是正の完了を確認した方法が前回と同じ誤りを繰り返している。**

## 最も重要な所見 — 是正 task が、自分が是正するはずだった欠陥を犯した

`FLW-REV-029` の最重要所見は「**`GP` 消化の確認を source 文字列の照合で済ませた**」であり、
その手当てが `GP-006`（確認を振る舞いの検査に限定する）であった。

今回、`GP-006` を適用したと明記した `tests/test_flow_m2_judgement_quality.py` 自身が、
**公開 API を一度も呼んでいない**。判定式をテスト側で再実装した helper と、内部定数
`_AUDIT_ACTIONS` を照合しているだけである。変異試験で確認した:

```
worktree_operability.verify_receipt の判定を `valid = True`（常に有効と主張）へ改変
→ tests/ 全体 2574 passed / 失敗 0
```

**「receipt を壊せば判定が反転すること」を証明するために書いた test が、判定を常に
真へ固定しても落ちない。** 同じ型の穴がもう1件ある。`UNSUPPORTED` を `BLOCKED` へ
畳む改変（§13.2 が明示的に禁止し、`SI-FLW-084` の中心である区別）を全 2611 test が
検出しない。落ちるのは confirmation の指紋 test 1 件だけで、それは**file が変わったこと**を
検出しているのであって振る舞いの誤りを見ていない。

`FLW-REV-029` は「直した」と「直ったことを確かめた」の差を所見にした。今回は
**「確かめ方を直した」と「確かめ方が直ったことを確かめた」の差**である。

## 手順について

`FLW-REV-029` で確立した「セカンドオピニオンを統合判定より前に実施する」を踏襲した。
今回の P0 2 件はいずれも**外部レビュアーが先に指摘した**ものである。

- `SYN-001`（deadline の前段抜け道）: codex が発見。自己レビューでは child の**監督**は
  数えたが、各 child が deadline を**受け取っているか**を見ていなかった。
- `SYN-002`（test が公開 API を呼んでいない）: codex と agy が**独立に**同一箇所を指摘。

自己レビューが単独で見つけたのは `SYN-004`／`SYN-005`／`SYN-006`／`SYN-008`／`SYN-010`。
**2 回連続で、最も重い所見は自己レビュー単独では出ていない。**

指摘は自己申告として受け取らず、すべて実測で再現してから採用した。
agy は初回が headless の権限制約、2 回目が timeout で応答せず、3 回目に**使い捨て clone**へ
向けて実行した（作業ツリーには触れていない。2026-08-15 の harness 事故を踏まえた措置）。

## P0

### `SYN-001` 公開 operation の deadline に前段の抜け道が残り、`--timeout-seconds` が 30 秒上限を上書きする

`worktree doctor` の child を実測した。

| 呼び出し | child 数 | deadline 無し | 残り 1 件の deadline |
|---|---:|---:|---:|
| 既定 | 4 | **3** | 30.0 秒 |
| `--timeout-seconds 300` | 4 | **3** | **300.0 秒** |

`_legacy_approval_detected()` が `OperationDeadline` の生成より前に
`rev-parse --git-common-dir` ／ `ls-tree` ／ `diff` を起動する。さらに `--timeout-seconds` が
operation deadline そのものになるため、`FLW-NFR-014` の 30 秒 closed terminal result を
利用者が上書きできる。

`FLW-TSK-130` は `_common_dir`／`_head`／`_rederive` を塞いだが preflight を見ておらず、
**`FLW-REV-029:SYN-001`（P0）を `resolved` と判定したのは誤りであった**。本レビューで
`open` へ差し戻した。

### `SYN-002` 判定 API を壊しても全 test が通る

上記「最も重要な所見」のとおり。`GP-006` は**未消化**である。

## P1

- **`SYN-003`** `audit_operation` が `quarantine` を `INDETERMINATE`／`result-indeterminate` へ写し、
  公開契約（`operation-catalog.md`: 外部起因の乖離は `BLOCKED`／`quarantined`／NEXT は空）を破る。
  `result.py` の `quarantined` cause は `FLW-REV-017:SYN-011` で「公開 audit が quarantine へ
  繋がっていることを result から読めない」問題を解くために追加された語彙であり、**本変更は
  その回帰**である。`FLW-TSK-132` が矛盾を1つ直す過程で別の矛盾を作った。
- **`SYN-004`** `UNSUPPORTED` を `BLOCKED` へ畳む改変を全 2611 test が検出しない。
- **`SYN-005`** §13.7 の表（行4 = **実証済み**）と直後の散文（「`実証済み`は依然1件も無い」）が矛盾。
  **`FLW-TSK-131` は `FLW-REV-029:SYN-003`（直した後に他の箇所を確認していない）の是正 task で
  ありながら、同じ誤りを犯した。**
- **`SYN-006`** `FLW-CON-008` の 7観点の閉集合が機械検査で開いている。`一部実証済み`（現に
  §13.7 行1 が使用）や `ほぼ実証済み（未確認）` が substring 一致で**実証済みとして通る**（変異で確認）。
- **`SYN-007`** Linux 限定の裁定が §9.1（:441）と §10（:460）に未反映。
  `test_flow_norm_consistency.py` は固定 4 フレーズの照合であり、言い回し違いを検出できない。

## P2

- **`SYN-008`** §13.7 行3 が「10,000 event の負荷実測は未実施」と書くが、§13.4 は 0.40 秒で
  実測済みと記録している。未実施なのは 100 MiB 規模だけ。証跡を**過小に**書いた例。
- **`SYN-009`** §13.5 の実観測欄が tmpfs／9p を含むが、引用 test が実走するのは ext4 だけ。
  実観測と合成分類を同じ欄に並べている。
- **`SYN-010`** `FLW-TSK-132` の STATE.md が `SYN-006`／`SYN-007` を「`resolved` へ照合した」と
  書いたが、台帳は `tracked` のままであった。

## 差し戻した先行 finding

`FLW-REV-029` の次を `resolved` から `open` へ戻した。**是正が不十分または誤っていた。**

| finding | 差し戻す理由 |
|---|---|
| `SYN-001`（P0） | preflight の 3 child が deadline 外。`--timeout-seconds` が上限を上書き |
| `SYN-002` | 同上。塞いだのは 3 経路だけ |
| `SYN-003` | §9.1／§10 に同種の記述が残る。名指しされた 3 箇所しか直していない |
| `SYN-009` | source 照合 test が残り、新しい test 自身が定数照合である |

## Gate blocking 条件（GP-001〜004）

4 件すべて `basis: verified`、`response: accepted`。

| GP | 内容 |
|---|---|
| GP-001 | deadline を dispatcher 最上流で 1 つ生成し preflight を含む全 child へ配る。`--timeout-seconds` を 30 秒で頭打ちにする |
| GP-002 | 判定 API と platform 写像の test を公開関数・CLI 経路から呼ぶ形へ書き直し、**導入時に変異試験で検出を実証する**。source 照合 test を撤去する |
| GP-003 | audit の code／cause／operator_action を公開契約へ戻す。`INDETERMINATE` は chain を検証できない場合に限る |
| GP-004 | 規範文書の内部矛盾を解消し、表と散文の一致・7観点語彙の閉集合・保証範囲記述を機械検査へ載せる |

`GP-002` は今回の findings の共通原因に対する手当てであり、他の 3 件より優先度が高い。
**`GP-002` を先に消化し、その方法で他の GP の消化を確認すること。**

## carried over 台帳

先行レビューの未解決 P0/P1 **107 件**を `carried_over[]` へ収録した（前回 102 件 +
差し戻し 4 件 + `SYN-006`／`SYN-007` の継続。うち 1 件は前回時点で既に計上済み）。
`SI-FLW-091` の機械検査により欠落が起きないことは保証されているが、個別照合は依然未了である。

## 裁定

`GP-001`〜`004` を消化すること。Promotion Gate は本レビューの判定により通さない。
**`origin/main` へのマージ禁止を継続する**（`decision-2026-08-24-canary-forward-fix.md` の
担保は `GP-001` 完了で解ける約束だったが、その `GP-001` の完了判定自体が誤りであった）。

公開を戻すか前進させるかは人間裁定とする。前回は「案B（前進）」を採ったが、
**前進の根拠であった「結線完了」が成立していなかった**ため、その裁定の前提は失われている。

## Revision History

- 1.0 (2026-08-25) `FLW-TSK-130`〜`132` による GP-001〜006 消化主張を検証し FAIL で記録。
  セカンドオピニオン（codex / antigravity）を統合判定より前に実施
