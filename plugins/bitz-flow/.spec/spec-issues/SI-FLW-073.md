---
id: SI-FLW-073
raised_by: FLW-REV-019（OPS-304 / RSK-204 / RSK-201 / RSK-207）
target: 実行環境ガードの覆域と、承認強度 fail-closed の不全
proposed_change_type: modify
status: open
---
- **目的**: `SI-FLW-069` の対処（PR #294）が**述べた脅威を閉じていない**状態を解消する。

- **発見した事実**（実測）:
  1. **fail-closed が脅威を閉じていない**（`OPS-304` / `RSK-204`）—
     registry が `chmod 644` なら `BLOCKED` になるが、**registry を削除すると apply が `DONE` を
     返し実 worktree が作られる**（無言で `plan-digest` へ降格）。閉じたのは非敵対的な破損だけで、
     コメントが述べる脅威主体は削除もできる。**この経路に回帰テストが1件も無い。**
  2. **`force_ask` はパス正規化で今も迂回できる**（`RSK-201`）—
     `ASK_PATTERNS` が生文字列の正規表現であり、`/./` や重複スラッシュを挟むだけで外れる。
  3. **ガードの覆域が不十分**（`RSK-207`）— 裁定 B は「`chmod` / `mv` によるガード無力化は塞がる」と
     したが、`sed -i scripts/agy_guard.py` のような**書き込み動詞の列挙漏れ**が素通りする。
     動詞を列挙する方式そのものが不十分である。

- **提案する修正**:
  - registry の**不在と削除を区別**する（配備が signed-capability を意図したかを別の印で持つ）か、
    降格を必ず `warnings` / `evidence` へ残す。いずれにせよ**この経路のテストを置く**
  - `ASK_PATTERNS` を生文字列でなく**正規化後のパス**へ適用する
  - ガード保護を動詞の列挙でなく**書き込み経路ベース**の判定にする

- **対象ファイル**: `scripts/agy_guard.py`、`tests/test_agy_guard.py`、
  `flowlib/worktree_runtime.py`、`tests/test_flow_m2_runtime.py`

- **確認観点**: registry 削除・パス正規化変種・書き込み動詞の変種に**陽性対照**を置く。
  正規経路が落ちないことを陰性対照で守る。

- **依存**: 出口条件2と5の判定に関わる。
