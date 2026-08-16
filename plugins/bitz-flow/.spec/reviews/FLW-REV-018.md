---
id: FLW-REV-018
title: "M2 Exit 最終状態レビュー（GP-005）"
status: active
version: 1.0
updated: 2026-08-16
owner: hide
decision: CONDITIONAL_PASS
---

# M2 Exit 最終状態レビュー（GP-005）

- **review_id**: FLW-REV-018
- **対象**: 是正がすべて入った最終状態 `bcc1525`（PR #281 / #284 / #282 / #286 / #287 /
  #289 / #290 / #291 / #292）
- **判定**: **CONDITIONAL_PASS**
- **集計スコア**: **3.60 / 5.00**（前回 3.13、**+0.47**）
- **測定重み**: **1.00**（5観点すべてを測定。`FLW-REV-016` 以来はじめて欠測が無い）
- **実施方式**: 観点ごとに独立エージェントを**順次1体ずつ**起動した
  （個票は `individual/flw-rev-018-*.json`）

## なぜこのレビューが必要だったか

`FLW-REV-017` は CONDITIONAL_PASS 3.13 で終わったが、**4観点が是正前後の異なる commit を
見ていた**。最終状態を独立に評価した観点は1つも無く、critical 4件が「解消済み」なのは
司令塔の作業であって独立の検分を経ていなかった。これが `GP-005` である。

本レビューは**5観点すべてが同一 commit（`bcc1525`）を見る**。

## 観点別スコア

| 観点 | 今回 | 前回 | 差 | 重み |
|---|---:|---:|---:|---:|
| operations | **4.00** | 3.60 | +0.40 | 0.20 |
| business | **3.85** | 3.20※ | +0.65 | 0.15 |
| consistency | **3.70** | 3.00 | +0.70 | 0.15 |
| data-integrity | **3.65** | 3.25 | +0.40 | 0.25 |
| risk | **3.00** | 2.70 | +0.30 | 0.25 |

※ business は `FLW-REV-017` で欠測のため `FLW-REV-016` との比較。

findings: 統合前76件 → 重複排除後16件（P0: 1 / P1: 11 / P2: 3 / P3: 1）。

推移は **2.85 → 3.13 → 3.60**。全観点が上昇した。

## 独立レビューが司令塔の報告を訂正した

PR #292 の完了報告で司令塔は「**M2 出口条件は 8/8 が PASS**」と述べた。
**この報告は否定された。** 5観点の集計では次のとおりである。

| # | 出口条件 | 判定 | 根拠 |
|---|---|---|---|
| 1 | repo identity衝突0 | **PASS** | 重複 create の `BLOCKED` を実測（data-integrity） |
| 2 | repo外rootの単回capability | **条件付き** | 単回性を担保する nonce ledger が crash に耐えない（`SYN-007`） |
| 3 | `M2-FLT-*` 全件 | **PASS** | 欠番0（operations / business） |
| 4 | enum三者照合 | **未達** | PR #292 が `ORPHAN` を閉集合の外へ入れた**新規の回帰**（`SYN-005`） |
| 5 | 公開dispatcher経由 in-band検証 | **条件付き** | 注入 fixture 依存、実 mutation 1種（全観点一致） |
| 6 | operation外変更のaudit検出・quarantine接続 | **未達** | 5観点中4観点が「PASS と言えない」（`SYN-001`〜`004`） |
| 7 | 3platform confirmation | **条件付き** | 実走は PASS だが証跡が実走を指さず、TTL 時限故障がある（`SYN-010` / `011`） |
| 8 | reconnaissance entry必須 | **PASS** | `M2-FLT-045`〜`047` / `051`（operations / business） |

**PASS 3項目・条件付き 3項目・未達 2項目。**

条件6の未達は、`FLW-REV-017` の読み方そのものが誤っていたことを意味する。
同レビューは条件6を「検出は成立、接続語彙が未整備」と読み `SI-FLW-066` で語彙を接続したが、
**独立レビューは検出そのものが成立していないと判定した** — ground truth の receipt chain が
無検証で偽装でき（`SYN-001`）、外部削除と無許可コミットを検出せず（`SYN-002`）、
解除区分は定数（`SYN-004`）である。

## 是正は本物だった — 独立の追試で確認された

否定ばかりではない。前回 critical / major とされた指摘のうち、次は**独立レビュアが
自分で再現を試みたうえで解消と判定**した。

| 前回の指摘 | 追試の方法 | 結果 |
|---|---|---|
| ガード迂回（`FLW-REV-017:SYN-001`） | 前回 allow を得た8形すべてを guard へ再投入 | **解消**。権限昇格は閉じた |
| receipt payload の欠落（`DIN-202`） | create を実走させ receipt の中身を確認 | **解消**。`target` が `record_digest` の対象に入る |
| 例外貫通（`DIN-101`） | monkeypatch でなく実 receipt 破損で再現 | **解消**。`PARTIAL` を返し nonce が収束 |
| 指紋の被覆不足（`DIN-301`） | HEAD で `compatibility_key` を再計算 | **解消**。`result.py` の変更を捉えて manifest が再発行 |
| 既定 renderer の `KeyError`（`RVC-101`） | 実 repo で既定形式を描画 | **解消**。traceback なし |
| SKILL.md と catalog の矛盾（`RVC-301`） | 記述の突合 | **解消**。二重定義を削除 |
| 承認由来の偽装（`OPS-303`）・Gate 時 TTL（`OPS-402`） | コードと証跡の確認 | **解消** |

`codex` の timeout についても、attempt 台帳の時刻から
「失敗 record は前 record から 240.1秒（`timeout=240` に一致）、再試行は 12.5秒」が確認され、
**「計測環境の性質」という切り分けは実質的に裏づけられた**。
`FLW-REV-017` の「恒常欠陥の隠蔽」という評価は取り下げられている。

## Gate Precondition

| GP | 判定 | 要点 |
|---|---|---|
| `GP-001` | partially-discharged | 公開経路は実機再現できたが、注入 fixture 依存・実 mutation 1種・署名モード未通過 |
| `GP-002` | **discharged** | HEAD 再計算の指紋が manifest と一致し、失効の伝播を実証 |
| `GP-003` | **discharged** | 実破損条件での追試に耐えた |
| `GP-004` | partially-discharged | 5観点すべてが partially。台帳と manifest の接続、比率 field、指紋の次元が不足 |
| `GP-005` | **discharged** | 本レビューが最終状態を単一 commit で独立に検分した |
| `GP-006` | open（agenda・新規） | M3 予算と M2 残債の計上。是正では閉じず人間の裁定を要する |

## 期限のある1件 — TTL 時限故障

`SYN-010`（`SI-FLW-070`）は**時刻に縛られる**。コミット済み qualification が
**2026-08-17T07:45:25Z に失効**し、`--verify-for-gate` の exit 0 を主張するテストが CI にある。
**コード変更が無くても、時刻が過ぎるだけで全ブランチが赤になる。**
他の条件と独立に先行処置してよい。

## CONDITIONAL_PASS の通過条件

- [ ] `SYN-001`（receipt chain の無検証。**critical**）を解消する — `SI-FLW-067`
- [ ] M2 出口条件6（audit 検出・quarantine 接続）を成立させる — `SI-FLW-067`
- [ ] M2 出口条件4（enum 三者照合）の回帰を解消する — `SI-FLW-067`
- [ ] `SYN-010`（TTL 時限故障）を期限内に処置する — `SI-FLW-070`
- [ ] `GP-006`（M3 予算と M2 残債の計上）を人間が裁定する

起票した spec-issue は `SI-FLW-067`〜`071` の5件である。

## 予算の経過

| 枠 | 承認 | 実績 |
|---|---|---|
| 第1次（2026-08-15） | 4 PR / 13 session | 4 PR / 8 session で自動停止 |
| 第2次（2026-08-16） | 5 PR / 15 session（本体3＋予備2） | 本 PR で **5 PR / 11 session（枠を使い切り）** |

第2次予算はこの PR で**使い切る**。付帯条件により、ここで自動停止する。

## 人間への裁定依頼

1. **Completion Gate は保留を継続する。** 出口条件のうち2項目が未達であり、
   うち条件4は**是正 PR（#292）が持ち込んだ回帰**である。
2. **通過条件5件への追加予算**（第3次）を裁定する。第2次枠は使い切った。
   なお `SYN-010`（TTL 時限故障）は期限があるため、予算裁定と独立に先行処置する余地がある。
3. **`GP-006`** — M3 予算へ、移送された破壊系 worktree と M2 残債3件を計上するかを裁定する。

`write_target: remote` は M3 まで `UNSUPPORTED` を維持する方針に変更はない。
