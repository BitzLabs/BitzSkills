---
implements: FLW-NFR-011, FLW-NFR-012
depends_on: [FLW-TSK-032]
boundary: evals/flow-core/m1-eval/isolation.py, tests/test_flow_m1_isolation.py
status: done
---

### 隔離namespaceの割り当てと残存副作用検査

- **作業内容**: qualification trial を互いに干渉させないための隔離機構を
  `evals/flow-core/m1-eval/isolation.py` として実装する。

  - **platform × operation × trial ごとに独立した repo / remote namespace** を割り当てる。
    run ID は**推測不能**（暗号論的乱数）とし、owner と lease を伴う。
    lease は coordinator core が発行したものを受け取り、harness 側で採番しない。
  - **fixture 作成から confirmation mutation 開始まで同一 lease へ拘束**する。
    lease が変わった・期限切れになった場合は trial を継続せず `BLOCKED` にする。
  - 各 mutation の直前に ref / HEAD を **CAS 再照合**する（TOCTOU の遮断）。
    照合できない場合は mutation を実行しない。
  - fixture の**初期 digest と最終 digest** を取り、終了時に**残存副作用**を検査する。
    初期状態へ戻っていない、または宣言外の変更がある場合は hazardous event として記録する。
  - namespace の払い出しと解放は冪等にし、解放漏れを検出できるようにする。

- **完了条件**: 上記の単体テストが PASS し、次の負の対照が拒否されること —
  推測可能な run ID（連番・固定値）の使用、lease 未取得での fixture 作成、
  lease が切り替わった後の mutation、CAS 再照合なしの mutation、
  残存副作用がある状態での PASS 判定。
  同じ (platform, operation, trial) の組に対して 2 回払い出すと別 namespace になること。
  `.venv/bin/pytest -q` が全件 PASS すること。

- **備考**: 本タスクは実際の GitHub remote へ接続しない。remote namespace は**予約と検証の契約**を
  実装し、実接続は M1-6 confirmation で扱う。lease の意味論は coordinator core が正であり、
  ここで再実装しない。
