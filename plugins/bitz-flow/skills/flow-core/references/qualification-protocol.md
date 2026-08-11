# Qualification Protocol

正式な測定（confirmation）を始める前に、**計測器そのものが測れる状態にあること**を確かめる手順
（`FLW-DSN-015` / `FLW-NFR-011`）。schema の正は `schemas/qualification-manifest-v1.schema.json`。

被測定物の良し悪しを見るのではなく、**harness が正しく観測・分類できるか**を見る。
ここを通さずに confirmation を起動しない。

## 二段階原則

```
qualification（計測器の適格化） → confirmation（正式測定）
```

confirmation は、同じ platform・operation・credential・capability・fixture snapshot・sandbox・
CLI / model binding で qualification が `PASS` した場合にだけ起動できる。
PASS していない状態から confirmation を起動する経路を作らない。

## 3 trial

platform × operation ごとに、次を**各ちょうど1件**実行する。0 件でも 2 件以上でも FAIL。

| trial | 目的 | PASS 条件 |
|---|---|---|
| `Q-NORMAL` | 正常入口 | CLI / event / envelope / schema / raw log / 終了 code が全一致 |
| `Q-REJECT` | 既知拒否 | 構造化 failure code と陽性対照 oracle が 100% 検出 |
| `Q-CORRUPT` | 観測破損 | event 欠落・flush 失敗・schema 矛盾を `blocked` に分類 |

`Q-CORRUPT` は「壊れた観測を壊れたと言えるか」を見る。壊れた入力に対して PASS を返す harness は、
本番でも壊れた測定を PASS と報告する。

## 合格条件

次を**すべて**満たすときだけ `PASS` とする。

- 3 trial すべてが存在する
- 必須 check の **denominator が各 1 以上**
- 検出率 100%
- positive-control 100%
- hazardous event 0 件
- 残存副作用 0 件

`FAIL` にするもの: 欠落 field、未知 enum、**denominator 0**、trial 件数の不一致、
10 分超過、harness 再試行 2 回目。

`BLOCKED` にするもの: 台帳不整合、TTL 超過（境界時刻を含む）、partition、
canary 未検出、未許可 role、保持期限超過。

### 空集合を 100% として扱わない

**測っていないことは「全部通った」ではない。** denominator 0 の check を検出率 100% と数える実装は、
計測器が壊れているときに最も高い点を出す。この一点を守るために、必須 check ID 集合と
positive-control ID 集合は**結果取得より前に**拘束し、schema 側でも `minItems: 1` を課す。

## 実行制約

- **10 分以内**
- **harness 再試行 1 回以内**（超過は延長せず FAIL）
- **TTL 24 時間**。`issued_at` / `completed_at` / `expires_at` は coordinator の
  authoritative clock 由来とし、**trial 開始時**と **confirmation mutation 直前**の2点で再検査する

## 隔離

write の trial は、authoritative coordinator が予約した**推測不能な run ID・owner・lease** を持つ
独立した repo / remote namespace で行う。

- fixture 作成から confirmation mutation 開始まで**同じ lease に拘束**する
- 各 mutation の直前に ref / HEAD を **CAS 再照合**する（TOCTOU の遮断）
- 終了時に **fixture 初期 digest と最終 digest** を比較し、**残存副作用**を検査する

## raw log の保存境界

- 読めるのは **owner と `evaluation-reviewer`** だけ（owner-only permission）
- repo 外の秘密値は **redaction** する。`redaction_version` を manifest に記録する
- **秘密値 canary** を仕込み、書き出した log から検出できることを確認する。
  **未検出は安全ではない** — redaction が効きすぎて観測不能か、log が欠落しているかのどちらかで、
  いずれも Gate 停止事由とする
- **最大 30 日**で削除する。`delete_by` と `delete_owner` を持ち、削除したら
  **削除証跡**（対象 digest・時刻・担当）を残す。証跡の無い削除を認めない
- legal hold は別 record がある場合のみ 30 日を超えられる。自動延長はしない

## credential

manifest が持つのは **credential class**（`none` / `local-only` / `read-scoped` / `write-scoped`）だけである。
値・token・path を書ける field を schema に置かない。

## manifest の必須 field

trial ごとに次を持つ（正は schema）。

credential class、capability、fixture 初期 digest、fixture 最終 digest、sandbox 境界、
CLI identity、model identity、host event-contract、raw-log digest、残存副作用、
必須 check ID 集合、check 結果、positive-control ID 集合、検出された positive-control、
oracle digest、hazardous event。
