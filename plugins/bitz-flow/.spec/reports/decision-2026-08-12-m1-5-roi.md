# M1-5 ROI 判定材料 — evidence 再利用・合成に着手するか

- **日付**: 2026-08-12
- **記録者**: implementation-owner（claude）
- **裁定者**: budget-approver（**未裁定**）
- **対象**: `FLW-DSN-015` の M1-5 区分（ROI 条件付き evidence 再利用・合成）
- **Go 条件**: 予測再実測削減が **1 PR 以上または 3 session 以上**

## M1-5 が実装するもの

1. **compatibility key v1** — 閉集合13要素（scoring rule / runner / adapter / oracle / fixture /
   prompt / skill / result・event schema / 推移的依存 / model identity・date / CLI version /
   host event-contract version / trial 割付）の canonical JSON digest
2. **失効規則** — 共通入力が変われば全 platform 証跡を失効、**platform adapter だけなら当該 platform だけ失効**
3. **ledger 合成** — platform 部分台帳と正本の双方向照合、objective ごとの candidate 選択、
   retry 1回、late-evidence の扱い
4. **復旧運用** — RPO 0 / RTO 4時間の restore 検証
5. **fault fixture 13件** — `M1-FLT-010`〜`015` / `017` / `018` / `021`〜`023` / `028` / `030`

## 算定根拠（M0 の実測データ）

M0 の eval harness（`evals/flow-core/m0-eval/`）を触った commit を、
compatibility key の失効規則に照らして分類した（確定 ref から測定）。

```
harness を触った commit: 18 件
  全platform失効（共通入力: score.py / fixture.py / prompts/ を変更）: 14 件
  単一platform失効（adapter 1つだけを変更）:                            4 件（22%）
```

単一 platform の 4 件:

| commit | 内容 |
|---|---|
| `bebeaaf` | SI-FLW-014 / 015（codex adapter） |
| `c02adee` | 検証予算の再提示（codex adapter） |
| `bf17c8a` | SI-FLW-028 `--base` 意味論（codex adapter） |
| `cccde92` | SI-FLW-019 の裁定記録（codex adapter） |

**合成が無い場合**、この 4 件でも 3 platform 全部を再実測する必要がある。
**合成がある場合**、当該 platform だけ再実測すればよく、1 回あたり **2 platform 分**を省ける。

### 予測削減

M0 の実測規模は 14 ラウンド × 3 platform = **42 platform-run**。
単一 platform 修正 4 回で他 2 platform を省けたとすると **8 platform-run（19%）**の削減。

M1〜M5 の総 session 予算は 88（M1 20 / M2 14 / M3 20 / M4 20 / M5 14）で、
うち検証に充てるのは概ね半分の **約 44 session**。

| 前提 | 予測削減 session |
|---|---|
| M1〜M5 でも M0 と同率（19%）の反復が起きる | **約 8 session** |
| `FLW-DSN-014` の外挿（M0 比 0.6 倍）を適用 | **約 5 session** |
| 単一 platform 修正が M0 の半分しか起きない | **約 2.5 session** |

**Go 条件（3 session 以上）は、上2つの前提では満たす。最も保守的な前提では下回る。**

### 実装費

区分予算は 1 PR / 3 session。M1-1〜M1-4 の実績は各区分 1 session で完了しているため、
**1 PR / 1〜3 session** と見込む。M1 の残予算は 2 PR / 15 session あり、
M1-5（1 PR）と M1-6（1 PR）で使い切る想定。

## 不確実性（正直に述べる）

- M0 は**測定系の構築を含む初回**であり、反復回数が多かった。M1 以降は測定系を再利用するため、
  単一 platform 修正の**絶対回数は減る**可能性が高い。削減量もそれに比例して減る。
- 上の分類は「commit が触ったファイル」による機械分類であり、実際に再実測が必要だったかは
  当時の裁定記録まで遡らないと確定しない。**過大評価の方向に振れうる**。
- 合成そのものにも運用コスト（台帳の整合検査、失効判定の保守）がかかる。これは上の見積もりに
  含めていない。

## No-Go を選んだ場合に起きること

`FLW-DSN-015` の縮退規定より:

- M1-1 core（coordinator / durable / recovery / sanitize）は**維持**する
- M1-5 の合成拡張だけを実装しない
- **M1-6 を「単一 platform の非合成証跡保全 + active manifest 非昇格」へ縮退**する
- 残予算と M1 出口を人間へ再提示する

つまり No-Go は「M1-5 を飛ばす」だけでなく、**M1-6 の 3 platform 正式確認も縮退**させ、
active manifest への昇格を見送ることを意味する。M1 の出口条件
（contract 全行・fault fixture・重複 commit 0）自体は満たせるが、
**3 platform で正式に確認した証跡は残らない**。

## 裁定

- **日付**: 2026-08-12
- **裁定者**: hide（budget-approver として）
- **結果**: **Go — M1-5 に着手する**

中間的な前提（`FLW-DSN-014` の 0.6 倍外挿）で約 5 session の削減となり、Go 条件
（1 PR 以上または 3 session 以上）を満たすと判断された。最も保守的な前提では下回るが、
No-Go は M1-6 を「単一 platform の非合成証跡保全 + active manifest 非昇格」へ縮退させ、
3 platform で正式に確認した証跡が残らないことも考慮された。

### 着手時の条件

- 実装費は **1 PR / 1〜3 session** を上限とする。区分超過は総枠内でも人間へ再提示する
  （`FLW-DSN-014` の停止規則）。
- 合成そのものの運用コスト（台帳の整合検査・失効判定の保守）は本見積もりに含めていない。
  M1-6 完了時に実績を run manifest へ記録し、M2 以降の budget 再校正の材料とする。
