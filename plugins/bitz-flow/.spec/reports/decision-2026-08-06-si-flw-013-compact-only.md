# 裁定記録 — antigravity の `--format json` 再取得（SI-FLW-013）

- **日付**: 2026-08-06
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `SI-FLW-013`（antigravity だけが compact 誘導に従わず `--format json` を再取得して
  byte 削減が未達になる）
- **裁定の形式**: M0 第3ラウンド（antigravity）と第6ラウンド（claude-code / codex-cli）の
  実測データを提示したうえでの対話裁定。記録経路は代行可視化経路
  （`--on-behalf-of hide --decision-ref` でエージェントが status 遷移を実行）。

## 裁定材料

### 症状

antigravity だけが、compact で取得した直後に**同じ operation を `--format json` で取り直す**。

```text
flow.py git status                 → 239 B
flow.py --format json git status   → 3004 B（約12.6倍）
```

`_task_output` は最後の該当実行を採点対象にするため、再取得した JSON が採点値になる。

### 閾値の問題ではない

第3ラウンドの v2 `dirty-status` 10 trial の内訳。

| 挙動 | 件数 | 削減率 |
|---|---:|---:|
| compact のみ | 3 | +44.8〜58.4% |
| **`--format json` で再取得** | **4** | **−406〜−428%** |
| `--limit` で全件取得（large corpus） | 3 | +37.0% |

`--format json` の再取得だけを解消した場合の median を実データで再計算すると **44.8%** となり、
閾値 40% を**超える**。

```text
+37.0% +37.0% +37.0% +44.8% +44.8% +44.8% +58.4% +58.4% +58.4% +58.4%
                            ↑ median = 44.8%
```

すなわち `--limit` による全件取得（打ち切りを見て残りを取りに行く**正当な**挙動。
`silent_truncation` は 0 件で打ち切りは可視化されている）は、単独では閾値を割らない。

### platform 差である

同一の v2 SKILL.md を読んでいるにもかかわらず、`--format json` を実際に実行したのは
antigravity だけである。

| platform | v2 trial 数 | `--format json` を実行した trial |
|---|---:|---:|
| claude-code（第6R） | 30 | **0** |
| codex-cli（第6R） | 30 | **0** |
| antigravity（第3R） | 30 | **4**（すべて `dirty-status`） |

第1ラウンドで「機械処理には `--format json`」という誘導は既に是正済みであり、現行文面は
「compact のまま読む。`--format json` は result を別のプログラムへ渡すときだけ使う」と
書いている。**書いてあるのに agy にだけ効いていない**。

## 読み取り

1. **閾値（`FLW-NFR-008` の 40%）を見直す必要はない。** 未達は測定条件でも renderer の
   性能でもなく、agy の挙動に起因する。
2. **`SI-FLW-008` と同じ構図である。** agy は「読んでも拘束されない」傾向があり、
   同じ手法（禁止形の単文へ寄せる）が効く見込みがある。
3. **選択肢を提示していること自体が誘因である。** M0 の read-only では、エージェントが自分で
   読んで判断するため JSON が要る場面が存在しない。使わない選択肢を本文に書く必要がない。
4. `--limit` による全件取得は**抑止してはならない**。打ち切りを見て残りを取りに行くのは
   正当な判断であり、これを止める文面は情報の欠落を招く。

## 裁定

**accept。案1（`--format json` の記述を本文から落とす）と案2（禁止形の単文へ寄せる）を併用する。**

適用した変更は次のとおり。

| 箇所 | 変更 |
|---|---|
| 使用法の行 | `[--format compact\|json]` を削除し、形式の選択肢を見せない |
| 出力の読み方 | 「既定の `--format compact` は」→「result は」。形式への言及を落とす |
| 読み方の規範 | 「`--format json` は…に使う」を削除し、**「同じ operation を、出力形式を変えて呼び直してはならない」**を禁止形の単文で追加 |
| truncation | 「残りが要るなら `--limit` で取り直してよい」を明記し、正当なページングを抑止しない |

案3（dispatcher 側で警告を出す）は**採らない**。dispatcher は状態を持たないため
「compact で取得済みか」を判定できず、実装コストが高いうえ M0 の read-only 契約にも合わない。

### 裁定の根拠

- 変更が `evals/flow-core/fixtures/v2-skill/SKILL.md` に閉じ、稼働中の v1 と配布物へ影響しない
  （`FLW-DSN-011` により v2 は Promotion Gate まで fixture 扱い）。単独 revert できる
- `FLW-DSN-010`（未達時は文章を長くするのではなく description・入口名・命名・next action を直す）
  に沿う。文章量はむしろ減っている
- `SI-FLW-008` の裁定方針（共通文面で効く言い回しを優先し、platform 別の文面分岐は最後の手段）
  を踏襲する。本件も platform 分岐を行わない

### 裁定しなかったこと（本裁定の範囲外）

- **`FLW-NFR-008` の閾値 40% は変更しない。** 本件は挙動の問題であり閾値の問題ではない。
- `--limit` による全件取得の扱いは変更しない（引き続き許容する）。
- claude-code の必須 field 保持 96.7%（1 trial のツール未実行）と codex-cli の母数 9/10 は
  対象が異なり、独立に扱う。前者は再現性の確認、後者は trial 数を増やすことで対処する
  （`FLW-DSN-014` が harness 再実行を別 trial と規定しており仕様変更にあたらない）。

## 次アクション

1. v2 fixture SKILL.md へ案1＋案2 を適用する
2. antigravity を再実測し、`--format json` の再取得が 0 件になること、`dirty-status` の
   byte 削減 median が 40% 以上へ回復することを確認する
3. **claude-code / codex-cli も同じ fixture で再実測する。**共通 fixture を変更したため、
   既達水準を落としていないことを確認する必要がある
4. codex-cli は `--trials` を増やして測定可能 10 件を確保する
5. 既存要件の条文は変更しない（`FLW-NFR-001` / `FLW-NFR-008`）

## 備考

本 issue は「閾値が正当なページングを減点している」という当初の読みを訂正するものである。
第3ラウンド時点の分析は `--format json` の影響を分離しておらず、`--limit` の 37.0% だけを見て
閾値の妥当性を疑っていた。**要件を疑う前に、まず自分の分析の分解能を疑うべき事例**として記録する。
