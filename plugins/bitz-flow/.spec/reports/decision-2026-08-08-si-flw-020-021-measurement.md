# 裁定記録 — M0 eval 測定系の是正（SI-FLW-020 / SI-FLW-021 / SI-FLW-017）

- **日付**: 2026-08-08
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `SI-FLW-020`（`exit_code` 計装が3 runner で非等価）、`SI-FLW-021`（Decision Parity が
  corpus をまたいで比較）、`SI-FLW-017`（採点対象の選択規則。本裁定で `SI-FLW-020` へ統合）
- **裁定の形式**: 2026-08-08 のセッションで、open 9 件を性質別（測定系 / 被測定物 / 新規スコープ）に
  提示し、hide が**測定系の是正を先行トラックとして選択**した対話裁定。
  記録経路は代行可視化経路（`--on-behalf-of hide --decision-ref` でエージェントが status 遷移を実行）。
- **裁定材料**: `.spec/reports/analysis-2026-08-07-m0-measurement-system.md`（全10ラウンド再解析）、
  `.spec/reviews/FLW-REV-006.md`（判定 FAIL・スコア 2.42・P0 3 件）

## 前提 — 判定されているのは被測定物ではなく計測器である

`FLW-REV-006` は M0 eval **測定系**に対する多観点レビューであり、判定は **FAIL**（2.42）である。
「測定系が現状のままでは M0 出口の合否を根拠づけられない」という結論であり、
第10ラウンドの数値の良し悪し以前の問題として扱う。

M0 eval 期の spec-issue の内訳は、再解析で次のとおり更新された。

| 種別 | 件数 | ID |
|---|---:|---|
| **測定系（harness・採点規則）** | **9** | 007, 009, 010, 012, 014, 017, 020, 021, （計装の不均一は未起票） |
| 被測定物（dispatcher の契約） | 3 | 006, 011, 015 |
| 被測定物（SKILL.md の誘導） | 4 | 008, 013, 016, 018 |

**測定系が被測定物の 1.3 倍**である。個別に潰しても同じ場所から再発しているため、
本裁定では 3 件を1つの変更セットで扱う。

## 裁定1 — `SI-FLW-020`: accept（案1・案2・案3 を採る）

### 材料

`exit_code` の実体が runner ごとに違う。

| runner | 実体 | `flow.py` の exit 2 を捕捉 |
|---|---|---|
| codex-cli | Codex event の `item.exit_code`（実値） | ○ |
| claude-code | `1 if item["is_error"] else 0`（Bash tool の error flag） | ○ |
| **antigravity** | 出力に `error` / `failed` / `exit code: 1` を含むかの**文字列判定** | **×** |

`flow.py` の失敗行は `INVALID_INPUT git.diff-summary cause=invalid-ref stage=inspect`（実 exit 2）
であり、どの marker にも一致しない。結果として agy は **v2 条件の 242 回の呼出で一度も
非ゼロ exit を記録していない**一方、byte 長で同定すると `diff-summary` だけで **38 回
`INVALID_INPUT` を受けている**。計測器が沈黙して失敗する経路である。

この 1 field の上に採点規則（`_task_output` の成功判定）と `self_retried`（SFCR の減点要因）が
乗っているため、**platform 間で等価でない基準で採点していた**。`self_retried` は agy で
構造的に永久 false であり、agy の SFCR は過大評価されている。

### 裁定

**accept。** `SI-FLW-020` の案1（result code を出力から読む）・案2（`exit_code_source` を記録）・
案3（agy のヒューリスティックを撤去し `None` とする）をすべて採る。案4（marker 文字列の強化）は
提案どおり**採らない** — result code の語彙が増えるたびに harness 側の文字列一覧が腐り、
`SI-FLW-019` の「実装が事実上の仕様」を再生産するため。

採点は `exit_code` ではなく **result code**（compact 出力の先頭 token / JSON の `code`）で行う。
これは `result-v1.schema.json` の `code` enum であり、**platform の event contract に依存せず読める**。

歯止め: harness の成功／失敗の分類が schema の enum を網羅しなくなったら、黙って誤分類せず
`SystemExit` で落とす（`tests/test_m0_eval_scoring.py` が機械検証する）。

## 裁定2 — `SI-FLW-021`: accept（案1・案2・案3 を採る）

### 材料

`decision_parity` が **corpus をまたいで判定を比較していた**。trial は small / medium / large の
3 corpus に散っており、`dirty-status` の判定は corpus ごとに `changed=8` / `34` / `124` と
**当然に異なる**。そのため同一 platform 内でも「判定が揺れている」と数えられていた。

`FLW-DSN-014` の出口条件「Cross-model Decision Parity 100%」は、**初回ラウンドから一度も
達成可能でなかった**。合格していた 1/3 は `repo-inspect` だけで、この task の判定が corpus に
依存しないためたまたま素通りしていた。

**この欠陥は数値の悪化を伴わなかった。** 10 ラウンドすべてで同じ FAIL 行を出力し続けながら、
どの spec-issue にも起票されていない。他の未達に紛れて**恒常的な FAIL 行が背景化**していた。

### 裁定

**accept。** 案1（グループ化キーへ corpus を加える）・案2（corpus 名を持たない trial を除外し
件数を明示）・案3（実測 platform が2種未満なら「未実測」とする）をすべて採る。

`score.py` の docstring は既に「同じ fixture・同じ task で3platform の判定が一致した割合」と
書いており、**実装が docstring に追いついていなかっただけ**である。

### 再採点（再実測なし）

確定済みの trial 記録を修正後の規則で再採点した。

| ラウンド | 旧（task 単位） | 新（task × corpus 単位） |
|---|---:|---:|
| r7 | 1/3 = **33%** ❌ | 9/9 = **100%** ✅ |
| r8 | 1/3 = **33%** ❌ | 9/9 = **100%** ✅ |
| r10 | 1/3 = **33%** ❌ | 9/9 = **100%** ✅ |

`SI-FLW-021` の主張どおり、**実際のパリティは全ラウンドで 100%** である。
この再採点は `tests/test_m0_eval_scoring.py::test_recorded_rounds_reach_full_parity_after_fix`
が記録から機械検証する。負の対照（同一 fixture 上で判定を人工的に食い違わせると 100% を割る）も
同ファイルで検証しており、修正が「常に 100% を返す」ものでないことを確かめている。

## 裁定3 — `SI-FLW-017`: reject（`SI-FLW-020` へ統合）

`SI-FLW-017` が指摘した**事象**（正解を得たあとの探索的な失敗呼出が採点対象になる）は実在し、
`SI-FLW-020` の裁定で解消する。しかし `SI-FLW-017` が提案した**修正**は採れない。

- 推奨案1「`exit_code == 0` の一致を優先し、成功が無ければ従来どおり最後を採る」は、
  **agy では全ての `exit_code` が 0** であるため選択結果が現行と一切変わらない。
  欠陥が観測された当の platform で無効である。
- 記述にも誤りがある。「第10ラウンドで表面化」「第8Rはたまたま失敗呼出が先に来ていた」は
  不正確で、順序依存の露出は **r7 と r10 の 2 ラウンド**であり、r8 は `INVALID_INPUT` 呼出が
  7 件あったものの採点対象にはならなかった。

**reject する。** 提案の修正が機能しないためであり、事象を否定するものではない。
同一の事象は `SI-FLW-020` が result code ベースの選択規則で解消する。
`SI-FLW-014` の歯止め（成功 result が1件も無い trial は引き続き不合格）は維持する
— 「成功を優先して選ぶ」ことが「失敗をなかったことにする」にならないようにする。

## 併せて是正したこと — `FLW-DSN-014` が裁定に追随していなかった（再解析の発見4）

| 出典 | status の byte 削減閾値 | 分母 |
|---|---|---|
| `FLW-DSN-014` 本文（v1.4） | **70%** | no-skill でエージェントが実際に消費した出力（`SI-FLW-007`） |
| `FLW-NFR-008`（2026-08-05 裁定） | **40%** | 固定 baseline `git status` 長形式 |
| `score.py` の実装 | **40%** | 同上 |

`implements:` は `FLW-NFR-008` へ更新済みだが**本文が旧のまま**で、SSOT と宣言された設計文書が
要件と実装の双方に矛盾していた。`FLW-DSN-014` を v1.5 とし、本文を `FLW-NFR-008` へ追随させた。

さらに `FLW-DSN-014` へ **「測定量の定義」節**を新設した。`SI-FLW-019` の原因1
「測定量の定義が仕様に無く、実装が事実上の仕様になっている」への直接の手当てであり、
trial の「答え」・呼出の成否・`--help` の扱い・自己再試行・Parity の比較単位を設計側で固定する。

## 裁定しなかったこと（本裁定の範囲外）

- **`SI-FLW-019`（`FLW-DSN-014` の設計不足の恒久化）は未裁定のまま**。本裁定は 019 の原因1 に
  対する部分的な手当て（測定量の定義を設計へ明記）にとどまり、案2（proxy 乖離条件の洗い出し）と
  案3（harness 自己診断）は別途裁定する。案3 には「**常に FAIL している条件**の検出」を
  含める必要がある（`SI-FLW-021` は数値の悪化を伴わなかったため）
- **計装の不均一（再解析の発見3）は本裁定では扱わない**。`empty_output_positions` /
  `task_output_missing` / `help_invocations` が `run_codex.py` にしか無く、`SI-FLW-012` /
  `SI-FLW-014` の歯止めが codex-cli でしか効いていない。`SI-FLW-025` として別途起票する
- **`SI-FLW-018`（claude-code の生 git 直行）は未裁定**。測定系を是正すると第10ラウンドの
  不合格はこの 1 事象に収束するため、次のトラックとして扱う
- **閾値そのものは変更しない**。Parity 100% / SFCR 90% / Invocation 95% は据え置く
- **配布側 `plugins/bitz-flow/skills/flow-core/SKILL.md` は変更しない**（本裁定は harness と
  設計文書に閉じる）。プラグインの version も bump しない — 配布物に変更が無いため

## 影響推定・ロールバック

変更は harness（`evals/flow-core/m0-eval/`）・回帰テスト・設計文書に閉じ、**配布物と v2 fixture に
影響しない**。単独 revert できる。

**過去ラウンドの判定は変わる。** どのラウンドをどの規則で採点したかは
`evals/flow-core/m0-eval/README.md` の「採点規則」節に表として明記した。

- Parity は `score.py` だけで再採点でき、r7 / r8 / r10 は 33% → **100%**
- 採点対象の選択と `self_retried` は runner が trial 記録を作る時点で確定するため、
  **再実測しないと確定値は得られない**。agy の SFCR は**下がる可能性がある**
  （過大評価の是正であって退行ではない）

## 次アクション

1. `SI-FLW-025`（計装の不均一）を起票する
2. `SI-FLW-018` を裁定し、claude-code の生 git 直行への対策を入れる
3. 上記を反映したうえで**第11ラウンドを再実測**し、本裁定の確認観点を確定させる
   - agy の必須 field 保持が r7 / r10 相当の条件で 100% へ戻ること
   - agy の `self_retried` が非ゼロになること（下がる方向に動くことの確認）
   - claude-code / codex-cli の既達水準を落とさないこと
   - `exit_code_source` が3 runner すべてで記録されること
4. `SI-FLW-019` の案2・案3 を裁定して恒久化する
