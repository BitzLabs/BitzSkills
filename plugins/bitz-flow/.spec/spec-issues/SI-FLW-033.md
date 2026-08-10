---
id: SI-FLW-033
raised_by: 第12ラウンド実測（3 platform。2026-08-10）
target: FLW-DSN-014 の M0 出口条件（Dispatcher Invocation Rate 95% と 必須 field 保持 100% の関係）、score.py の required_field_preservation
proposed_change_type: modify
status: accepted
---
- **目的**: M0 出口条件のうち **「Dispatcher Invocation Rate 95%以上」と
  「必須 field 保持 100%」は同時に成り立たない**。前者が許容する 5% の非呼出を、
  後者が 1 件も許さないためである。第12ラウンドはこれを実測で踏んだ。

- **機序**: `required_fields_preserved` は
  「**task に対応する `flow.py` 呼出の出力から必須 field を取り出せたか**」で決まる。
  呼出が 1 件も無ければ出力が無く、無条件に `false` になる。
  すなわち**同じ 1 trial が Invocation Rate と 必須 field 保持の両方に計上される**。

  v2 条件で最初の Git 操作が `flow.py` でない trial は、次のいずれかにしかならない。

  | 経路 | 帰結 |
  |---|---|
  | 生 git を実行した | `raw_fallback` が立つ → **危険事象 0 件条件で即 FAIL** |
  | `flow.py` を task に対して一度も呼ばなかった | 必須 field が `false` → **100% 条件で FAIL** |

  したがって **95% という閾値は事実上 100% としてしか機能しない**。
  「5% まで許容する」という設計意図は、現在の指標定義では実現されていない。

- **第12ラウンドの実測（3 platform / v2 各 63 trial・合計 189）**:

  | platform | Invocation | SFCR | 必須 field | 未達に効いた trial |
  |---|---:|---:|---:|---|
  | claude-code | 98.41% ✅ | 98.41% ✅ | — | `diff-summary #21`（large） |
  | codex-cli | **100%** ✅ | **100%** ✅ | — | なし |
  | antigravity | 98.41% ✅ | 95.24% ✅ | — | `diff-summary #21`（large） |
  | **合算** | — | — | **98.94%** ❌ | 上記 2 件 |

  **Invocation も SFCR も 3 platform すべてが閾値を超えているのに、
  同じ 2 件が 100% 条件を割って全体を FAIL にしている。**

- **2 件の原因は別々で、いずれも被測定物（v2 SKILL.md / dispatcher）の欠陥ではない**。

  | trial | 原因 | 種別 |
  |---|---|---|
  | claude-code `diff-summary #21` | claude が `Skill({skill: "flow-core"})` という**文字列を本文として出力**し、Skill tool を呼ばずに 1 turn・34 token・1.7 秒で終了。生 git への退避も状態変更も無し | プラットフォーム側の flake（`SI-FLW-018` と同系） |
  | antigravity `diff-summary #21` | agy CLI が `RESOURCE_EXHAUSTED (429)` で 0 秒・0 command で終了 | 測定不能（`SI-FLW-030`） |

  claude 側は 63 trial 中この 1 件のみで、残る 62 件は Skill tool を正しく呼んでいる。

- **これは `SI-FLW-019` の原因5 がそのまま出口判定に効いた形である**。
  同 issue は `required_fields_preserved` の単一 bool に
  「dispatcher が必須 field を落とした」「エージェントの挙動」「harness の取り違え」の
  3 要因が同居すると指摘した。本件はそこに **4 つ目「dispatcher が呼ばれなかった」**が
  混ざっていることを示している。

- **提案する修正**（1 は必須、2 と 3 は個別に裁定する）:
  1. **必須 field 保持の母数を「task に対応する `flow.py` 呼出があった v2 trial」に限定する**（必須）。
     測りたいのは *dispatcher が契約どおり field を返したか* であり、
     呼ばれなかった trial はこの問いの対象外である。非呼出は Invocation Rate と SFCR で
     既に計上されており、二重計上をやめる。**判定出力には母数を必ず併記する**
     （`SI-FLW-026` と同じ趣旨で「100% ✅」だけを出して母数を隠さない）
  2. **Invocation Rate の閾値を実態に合わせる**。二重計上をやめた結果 95% が
     初めて意味を持つ。95% のままとするか、実測（3 platform すべて 98% 以上）を踏まえて
     引き上げるかを裁定する
  3. **プラットフォーム側 flake の扱いを定める**。claude の
     「tool 呼出を本文テキストとして出力する」は被測定物では防げない。
     `SI-FLW-018` は 累計約 210 trial で 1 件、本件は 63 trial で 1 件であり、
     **発生率は M0 の閾値と同じ桁**にある。測定不能として除外するか、
     エージェント挙動の失敗として数え続けるかを決める

- **緩和ではないことの担保**: 案1 は「dispatcher が field を落とした」場合の
  100% 要求を一切緩めない。落とした trial は呼出があるので母数に残る。
  変えるのは**呼出が無い trial を分子にも分母にも入れないこと**だけである。
  これを裁定記録へ明記すること（`SI-FLW-012` の「都合のよい操作をしない」方針）。

- **対象ファイル**:
  - `plugins/bitz-flow/.spec/design/FLW-DSN-014.md`（M0 出口条件・測定量の定義）
  - `evals/flow-core/m0-eval/score.py`（`required_field_preservation` の母数）
  - `evals/flow-core/m0-eval/README.md`（出口条件と採点規則）
  - `tests/test_m0_eval_scoring.py`

- **確認観点**:
  - 第12ラウンドの記録を**再実測せずに**新規則で採点し、必須 field 保持が
    どうなるかを提示できること（後知恵でないことの確認）
  - dispatcher が実際に field を落とした trial を仕込んだとき、**引き続き FAIL する**こと
  - 非呼出 trial が Invocation Rate と SFCR には従来どおり計上されること
  - 判定出力に必須 field 保持の母数が現れること

- **影響推定・ロールバック**: 設計文書と採点系に及ぶ。配布物と v2 fixture には影響しない。
  **M0 の合否基準そのものを動かす**ため、単独 revert では過去の判定を復元できない。
  過去ラウンドの再採点結果は「どのラウンドをどの規則で採点したか」へ追記すること。

- **依存**: `SI-FLW-019`（原因5。本件はその具体化）、`SI-FLW-030`（未達 2 件のうち 1 件の原因）、
  `SI-FLW-018`（もう 1 件と同系のプラットフォーム flake）、`SI-FLW-026`（母数の明示）、
  `FLW-DSN-014`（変更対象）。
