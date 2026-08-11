---
implements: FLW-FR-013
depends_on: [FLW-TSK-026]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/sanitize.py, tests/test_flow_m1_sanitize.py
status: pending
---

### 診断出力sanitizer（安全表現への正規化と秘密値・絶対pathの遮断）

- **作業内容**: 失敗診断に載せてよい入力だけを通す sanitizer を `flowlib/sanitize.py` として実装する。

  - 診断へ含めてよいのは**引数名・リポジトリ相対の安全表現・長さ・digest・許容候補**に限る。
    絶対 path、URL の userinfo、token pattern、制御文字は出力しない。
  - 既存の compact 用 escape は「1項目1行を保つ表示層」であり、本 sanitizer は
    「そもそも載せてよいか」を決める入力層として分離する（責務を混ぜない）。
  - Git の生 stderr 本文は許可語彙 cause へ正規化してから扱う（Git read adapter の分類方針に合わせる）。
  - qualification の raw log に埋め込む**秘密値 canary** の検出関数を置き、検出時に Gate を停止できる
    判定を返す。raw log の保存境界（owner と evaluation-reviewer のみ読取、最大 30 日）は
    判定材料として扱い、削除の実行そのものは本タスクの責務外とする。
  - 遮断した事実は可視化する（黙って落とさない）。長さと digest は残してよい。
- **完了条件**: 代表的な秘密値パターン（token 様文字列・URL userinfo・絶対 path・制御文字・
  非 ASCII path の生バイト）が遮断されることをテストで示すこと。canary を含む文字列で検出率 100%、
  含まない文字列で誤検出 0 であること。
  `.venv/bin/pytest -q` が全件 PASS すること。
- **備考**: M0 で検証済みの「raw command / stdout / stderr / environment / credential を出力しない」
  性質を退行させないこと。sanitizer 単体では公開 operation を増やさない。
