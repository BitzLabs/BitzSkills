# 裁定記録 — NEXT が提示する snapshot を次の operation が拒否する（SI-FLW-011）

- **日付**: 2026-08-06
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `SI-FLW-011`（`NEXT` が提示する snapshot を次の operation がそのまま受け付けず
  `snapshot-mismatch` になる）
- **裁定の形式**: M0 eval 第3ラウンド（codex-cli 90 trial）の実測と実装調査を提示したうえでの
  対話裁定。記録経路は代行可視化経路（`--on-behalf-of hide --decision-ref` でエージェントが
  status 遷移を実行）。

## 裁定材料

### 症状（再現手順つき）

```text
$ flow.py --format compact git status
OK   git.status snapshot=sha256:6d5b branch=main changed=8
NEXT git.diff-summary base=HEAD snapshot=sha256:6d5b

$ flow.py --format compact git diff-summary --base HEAD --snapshot sha256:6d5b
STALE git.diff-summary cause=snapshot-mismatch stage=validate     （exit 6）
```

`flow.py` が提示した引数を `flow.py` 自身が拒否する。

### 機構

snapshot は「その operation が観測した事実」の fingerprint であり、operation ごとに入力が違う
（`flowlib/cli.py`）。同一 repo・同一時点でも値が一致しない。

| operation | `snapshot_of` の入力 | 実測値 |
|---|---|---|
| `repo.inspect` | `[head, branch, upstream, dirty]` | `sha256:7545` |
| `git.status` | `[branch, items]` | `sha256:5ec3` |
| `git.diff-summary` | `[range, items]` | `sha256:8f18` |

短縮表示（`ABBREV_HEX_DIGITS = 4`）は原因ではない。`digest_matches()` は前方一致で照合するため
短縮形は正しく通る。渡している値が**別 operation の digest** であることが原因である。

### 壊れている箇所は3箇所中2箇所

| 箇所 | NEXT の内容 | 判定 |
|---|---|---|
| `cli.py` L165 `repo.inspect` → `git.status` | `repo.inspect` の snapshot を添付 | ❌ 必ず mismatch |
| `cli.py` L209 `git.status` → `git.diff-summary` | `git.status` の snapshot を添付 | ❌ 必ず mismatch |
| `cli.py` L211 `git.status` → `git.status`（ページング） | `git.status` の snapshot を添付 | ✅ 正しく通る |

同一 operation のページングは実測でも通る。

```text
$ flow.py --format compact git status --limit 8 --snapshot sha256:6d5b
OK git.status snapshot=sha256:6d5b branch=main changed=8     （exit 0）
```

すなわち **`NEXT` に snapshot を載せてよいのは「次も同じ operation」のときだけ**である。

### 実測への影響（第3ラウンド codex-cli 90 trial）

| 指標 | 閾値 | 第2R | 第3R |
|---|---|---|---|
| SFCR | 90%以上 | 100% ✅ | **53.3%** ❌ |
| 必須 field 保持 | 100% | 100% ✅ | **86.7%** ❌ |

v2 30 trial 中 10 trial が exit 6 を受けて `--snapshot` を外して再実行し、`self_retried` として
減点された（`diff-summary` 8 件は L209 経由、`dirty-status` 2 件は L165 経由で、
**壊れた2経路の両方が実際に踏まれている**）。`SI-FLW-012`（出力欠落）の4件を除いても
SFCR は 61.5% で `FLW-NFR-001` の platform 別 90% 要件に届かない。

## 読み取り

1. **エージェントの非遵守ではない。** SKILL.md の指示（`NEXT` の引数をそのまま渡す）に
   忠実に従った結果として失敗している。拒否しているのは dispatcher 側である。
2. **`SI-FLW-008` が原因ではなく、顕在化の契機である。** 欠陥は以前から存在した。
   第2ラウンドで出なかったのは、当時のエージェントが `NEXT` の引数をそのまま使って
   いなかったためにすぎない。agy の入口遵守を改善した修正が codex で後退を招いた形だが、
   直すべきは dispatcher であって SKILL.md ではない。
3. **snapshot の設計思想自体は妥当。** 「自分が観測したものが変わっていないか」を表す値
   としては operation ごとに異なるのが正しい。誤っているのは、その値を別 operation へ
   引き渡している `NEXT` の生成側である。
4. **楽観ロックが本当に効くのはページングである。** 打ち切られた一覧を辿る間に repo が
   変わったことを検出する用途であり、ここは同一 operation なので現状で正しく機能している。

## 裁定

**accept。案1（`NEXT` に snapshot を載せない）を採用する。ただし実装上は
「次の操作が現在の操作と同じときだけ snapshot を載せる」形に精緻化する。**

- `cli.py` L165・L209 の cross-operation な `next_action` から `snapshot` を落とす
- L211（`git.status` → `git.status` のページング）は**残す**
- 楽観ロックを使いたい呼び出し側は、対象 operation を一度読んでからその operation 自身の
  snapshot を渡す経路が引き続き使える

### 裁定の根拠

- 変更が `flowlib/cli.py` の2箇所に局所化でき、単独 revert できる
- `SI-FLW-008` の「`NEXT` の引数はそのまま渡す」規範と矛盾しなくなる。規範側を緩める必要がない
- 楽観ロックの機能を失わない。ページング（唯一 snapshot が意味を持つ場面）は温存される
- v2 は Promotion Gate 前の prerelease であり（`FLW-DSN-011`）、利用者影響がない

### 採らなかった案とその理由

- **案2（operation 横断の repo 状態 digest へ統一）**: `NEXT` の引き渡しを正当化できるが、
  無関係な変更でも `STALE` になる誤検出が増え、全 operation で repo 全体の digest を
  計算するコストが乗る。変更検出の粒度も落ちる。
- **案3（`observed-at=` へ改名）**: 呼び出し側の混同は減るが、「そのまま渡す」規範との
  衝突が残るため対症療法にとどまる。

### 裁定しなかったこと（本裁定の範囲外）

- `FLW-NFR-001` の platform 別閾値の見直しは**行わない**。本件は達成手段の欠陥であり、
  要件を緩める話ではない。
- `STALE` 時の回復経路（`--snapshot` を外して再実行する手順）の契約への明文化は、
  本裁定では扱わない。実測ではエージェントが正しく回復できており、緊急性がないため
  別途扱う。
- `SI-FLW-012`（codex の出力キャプチャ欠落）は対象が測定系であり、独立に裁定する。
- `SI-FLW-006`（診断 cause 語彙の不足）は依然 open のままとする。

## 次アクション

1. `flowlib/cli.py` の L165・L209 から `snapshot` を落とす（L211 は温存）
2. `tests/test_flow_contract.py` に「**`NEXT` が示した引数をそのまま渡すと成功する**」を
   機械検査として追加する。これが本 issue の受け入れ条件であり、回帰の歯止めとなる
3. `flow-core/references/output-contract.md` に snapshot が operation 固有であることと、
   `NEXT` が snapshot を載せる条件を明記する
4. M0 eval を再実測し、codex-cli の SFCR が 90% 以上へ回復することを確認する
   （agy の既達水準を落とさないこと）
5. 既存要件の条文は変更しない（`FLW-NFR-001` / `FLW-FR-004`）。EARS の意味は変わらない

## 備考

本欠陥は M0 eval が捕捉した。エージェントが指示に忠実に従うほど失敗する契約であったため、
`SI-FLW-008` で入口遵守を強化するまで表面化しなかった。**eval の価値が示された事例**として
記録する。
