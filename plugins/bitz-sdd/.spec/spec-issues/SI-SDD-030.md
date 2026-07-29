---
id: SI-SDD-030
raised_by: SI-SDD-016 実装後の振り返り（2026-07-29）
target: 検証証跡と verification_method の突合欠落
proposed_change_type: modify
status: accepted
---
- **目的**: SDD-FR-153 の証跡検査は `exit_code` と件数、参照切れ、記録時 commit は見るが、
  **証跡が要件の宣言した検証手段で得られたものかを一切見ない**。`command_id` は自由文字列であり、
  `benchmark` を宣言した要件に `--command-id pytest` の実行証跡を紐づけても検査を通る。
  実測でも `benchmark` 宣言の要件が 1 件あるが、その証跡が本当にベンチマークかを機械は判定できない。
  宣言（verification_method）と実測（証跡）の突合が 1 段欠けており、証跡機構が
  「実行した事実」は担保しても「宣言どおりの検証をした事実」は担保していない。
- **提案する修正**:
  1. 証跡へ検証手段の宣言（`method` 等）を持たせ、対象要件の `verification_method` と
     一致することを `spec_inspect` が検査する。不一致は FAIL とする
  2. `benchmark` / `load-test` の証跡には、要件本文が必須とする数値閾値との突合を求めるか、
     少なくとも閾値と実測値を証跡へ記録することを Design Gate で裁定する
     （verification.md は両者に「数値閾値の明記が必須」と定めているが、実測値の記録先が無い）
  3. 1 実行が複数要件を覆うとき、要件ごとに検証手段が異なる場合の扱いを定義する
     （現状 `requirements` は単なる配列で、手段の異なる要件を同一実行へ束ねられてしまう）
  4. 既存の証跡（現時点で 1 件）への移行方針を定める。schema は未リリースのため
     破壊的変更が許容できるうちに確定する
- **対象ファイル**: `skills/sdd-test/scripts/spec_verify.py`、`skills/sdd-core/scripts/spec_inspect.py`、
  `skills/sdd-core/references/verification.md`、`skills/sdd-test/SKILL.md`、
  SDD-FR-151 / SDD-FR-153 の改訂または後継要件、関連テスト、bitz-sdd マニフェスト。
- **確認観点**: 宣言と証跡の手段が食い違う場合に FAIL すること。`manual-check` 要件を
  巻き込まないこと（SI-SDD-029 の範囲）。`counts` が解析できないツールでも突合が成立すること。
  schema 変更が既存証跡を読めなくする場合、移行手順が示されること。
- **影響推定・ロールバック**: 証跡 schema（公開契約）の変更を伴うため軽量レーン不可・Design Gate 必須。
  schema は導入直後で利用実績が 1 件のみのため、破壊的変更のコストは今が最小。
  問題時は突合検査だけを無効化して schema は残せる。
- **依存**: SDD-FR-151（証跡の記録）、SDD-FR-153（証跡の構造検証）、
  `verification.md` の verification_method 統制語彙。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。SDD-FR-151 / 153 を強化する方向で、除外の判断は変えない |
| ガードレール抵触 | なし。記録項目の追加は SDD-FR-152 の許可リスト方式を維持する |
| 影響範囲 | sdd-test（証跡生成）、sdd-core（証跡検査・検証契約）、テスト |
| 軽量レーン適否 | 不適。証跡 schema は公開契約であり Design Gate 必須 |

**推薦: accept**。ただし**着手は早いほど安い**。schema の利用実績が 1 件のうちに直せば移行が不要で、
証跡が各ワークスペースに蓄積してからでは破壊的変更のコストが跳ね上がる。
SI-SDD-028 / 029 より規模は小さいが、時間依存のコストがあるため優先度は下げないこと。
