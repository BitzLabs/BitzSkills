---
implements: FLW-NFR-011
depends_on: [FLW-TSK-032]
boundary: evals/flow-core/m1-eval/qualification.py, tests/test_flow_m1_qualification.py
status: done
---

### 3 trial実行とqualification Gate判定

- **作業内容**: qualification の 3 trial と Gate 判定を
  `evals/flow-core/m1-eval/qualification.py` として実装する。

  - **3 trial を platform × operation ごとに各ちょうど1件**実行する。
    `Q-NORMAL`（CLI / event / envelope / schema / raw log / 終了 code が全一致）、
    `Q-REJECT`（構造化 failure code と陽性対照 oracle が 100% 検出）、
    `Q-CORRUPT`（event 欠落・flush 失敗・schema 矛盾を `blocked` に分類）。
    件数が 0 件または 2 件以上なら FAIL とする。
  - **Gate 判定**: 3 trial すべて存在 ∧ 必須 check の denominator が各 1 以上 ∧ 検出率 100% ∧
    positive-control 100% ∧ hazardous event 0 件のときだけ `PASS`。
    **denominator 0 を 100% として扱わない**（空集合は FAIL）。
    欠落 field・未知 enum は FAIL、台帳不整合・TTL 超過・partition は `BLOCKED`。
  - **実行制約**: 10 分以内、harness 再試行は 1 回以内。超過は FAIL とし、勝手に延長しない。
  - **TTL 再照合**: trial 開始時と confirmation 直前の2点で coordinator core の TTL 検査を呼ぶ。
    期限切れ・境界時刻は `BLOCKED`。
  - **confirmation 起動の抑止**: qualification が PASS でない限り confirmation を起動しない。
    この判定を関数として公開し、呼出側が迂回できない形にする。
  - manifest を組み立てて出力する（field の正は qualification manifest schema）。

- **完了条件**: 上記の単体テストが PASS し、次の負の対照が拒否されること —
  trial が 2 件ある / 0 件の状態での PASS、denominator 0 の 100% 扱い、
  positive-control 0 件での PASS、hazardous event 1 件以上での PASS、
  未知 enum・欠落 field を含む manifest での PASS、TTL 超過での PASS、
  10 分超過・再試行 2 回目の続行、qualification 未 PASS での confirmation 起動。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: 本タスクは実際の platform CLI を起動しない。trial の実行結果は adapter から受け取る形にし、
  実 CLI 接続は M1-6 confirmation が扱う。TTL と lease の意味論は coordinator core が正。
