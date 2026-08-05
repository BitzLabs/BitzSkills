---
id: SI-FLW-010
raised_by: M0 eval 第2ラウンド実測（FLW-TSK-012、2026-08-03）
target: M0 eval harness が corpus を trial 間で共有しつつ並列実行するため、他 trial の副作用が state_change として誤検知される
proposed_change_type: modify
status: accepted
---
- **目的**: M0 eval harness は condition × corpus サイズごとに repo を**1つだけ**構築し、
  その corpus を使う全 trial で**共有**する。repo のキーに task が入らない
  （`corpus[condition][corpus_name]` を3 task が共有する）ため、共有範囲は
  **1 condition あたり small=12 trial（4 trial × 3 task）／ medium・large=各9 trial**
  になる。さらに `--workers 3` で並列実行する。このため、ある trial が repo を変更すると
  同一 corpus の別 trial の `before` / `after` 比較へ混入し、
  **何も変更していない trial が `state_change` として記録される**。

  第2ラウンドの `antigravity/v2-skill/diff-summary#9` が該当する。この trial は
  raw log で確認した6コマンドすべてが `flow.py`（read-only）であり、
  `write_to_file` 等の変更系ツールも使っていないにもかかわらず `state_change=true` となった。
  原因は同じ large corpus を使う `#6` が並行実行中に
  `git show --stat --summary HEAD > stats.txt` を実行したことで、
  実測後の corpus に `?? stats.txt` が実際に残っている。

  影響は2つある。

  1. **無実の trial が危険事象として計上される**。`FLW-NFR-001` / `FLW-DSN-014` は
     状態変更を 0 件と要求するため、誤検知1件で出口条件を落とせてしまう。
     第2ラウンドの agy は state_change 2件と記録されたが、**真の違反は `#6` の1件のみ**で、
     正しくは実質1件である。
  2. **真偽の判定に raw log との突き合わせが要る**。`--keep-logs`（`SI-FLW-008` 起票時に
     追加済み）が無ければ切り分け自体ができない。指標の自動判定が人手の確認に依存しており、
     `score.py` の非ゼロ終了をそのまま出口判定の証跡にできない。
  3. **判定値と byte 分母も汚染され得る（潜在）**。oracle は trial 実行時に同じ repo から
     取るため汚染後は「正しい答え」自体がずれ、`raw_baseline_bytes` は corpus 構築時に
     1回だけ測るため汚染後の trial では実際の raw 出力と分母が食い違う（`SI-FLW-009` に直結）。
     第2ラウンドの実データでは判定値の汚染は**起きていない**（3 platform 全 condition の
     `dirty-status` の `changed` は large=123 / medium=33 / small=7 で一貫）。
     `stats.txt` を作った `#6` より先に該当 trial が終わっていたためで、タイミング依存である。

  なお本件は harness の欠陥であり、スキル設計・実装の問題ではない。第1ラウンドの
  known_limitations にも corpus 共有に起因する記述があったが（no-skill/repo-inspect trial 5 の
  `check_git.py` 追加）、**並列実行との組み合わせで無実の trial が汚染される**点は
  本ラウンドで初めて確認された。

- **提案する修正**:
  1. **corpus を trial ごとに分離する**。`_prepare_corpus` を condition × corpus サイズ単位から
     condition × corpus サイズ × trial 単位へ変える。`fixture.py` は決定論的に構築できるため
     内容は同一に保てる。構築コストと disk 使用量は増えるが、trial 間の独立性が保証される。
  2. 1 が重い場合の代替として、**書き込みを検出した trial の後続を同一 corpus で再構築する**、
     または**同一 corpus を使う trial を直列化する**。ただしどちらも並列度を落とすか
     複雑さを増すため、案1 を推す。
  3. **`state_change` の判定を trial 自身の行為に基づかせる**。現在は
     `before != after`（repo 全体の差分）を含むが、これは他 trial の副作用を拾う。
     自 trial が実行したコマンド（`STATE_CHANGE_PATTERN`）と使用ツール（`MUTATING_TOOLS`）
     だけで判定すれば汚染されない。ただし**リダイレクトや未知の変更手段を取りこぼす**
     恐れがあるため、案1 と併用し `before != after` は残すのが安全。
  4. 修正後、第2ラウンドの 270 trial を再実測して agy の state_change が
     1件（`#6` のみ）になることを確認する。

- **対象ファイル**: `evals/flow-core/m0-eval/run_codex.py`（`_prepare_corpus` /
  `_one_trial` の state_change 判定。他2 harness は common として本ファイルを参照）、
  `evals/flow-core/m0-eval/run_claude.py`、`evals/flow-core/m0-eval/run_antigravity.py`、
  `evals/flow-core/m0-eval/README.md`（harness 欠陥節の更新）。

- **確認観点**:
  - 重複: `SI-FLW-008` は agy の入口遵守、`SI-FLW-009` は byte 削減の分母定義で
    対象が異なる。harness の観測精度を扱う spec-issue は他に無い。
  - 既存要件との関係: **要件は一切変更しない**。`FLW-NFR-001` /
    `FLW-DSN-014` が要求する「状態変更 0 件」の条文はそのままで、
    それを正しく観測できるようにする harness 側の修正である。
  - ガードレール: 誤検知を消すために `state_change` の判定を緩めない。案3 を単独で採ると
    リダイレクトによる変更を見逃す可能性があるため、`before != after` は残す。
  - 検証: 同一 corpus を共有する trial が無い状態で再実測し、
    flow.py しか実行していない trial が `state_change=false` になることを確認する。
    併せて `#6` のような真の違反が引き続き検出されることを確認する（見逃しを作らない）。
  - 軽量レーン適否: **適**の余地あり。要件を変更せず harness に閉じるため、
    M0 の出口判定を塞ぐ他2件（`SI-FLW-008` / `SI-FLW-009`）より軽い。
    ただし再実測を伴うため、他2件の修正とまとめて1回で再実測するのが合理的。

- **影響推定・ロールバック**: harness のみの変更で、配布物・スキル・実装コードに影響しない。
  既存の trial JSONL は再採点で救えず**再実測が必要**（`state_change` は trial 実行時にしか
  観測できないため）。単独 revert できる。

- **依存**: `FLW-TSK-012` の M0 出口判定を塞いでいる3件のうちの1つ。
  `SI-FLW-008` の再実測と同時に実施すると 3 platform × 90 trial を1回で済ませられる。

- **実施**: 2026-08-05 `FLW-TSK-014`（done）で harness へ案1 + 案3 を適用した（PR #163、
  コミット `1a39016`）。`_prepare_corpus` の構築単位を condition × corpus サイズ × task × trial へ変え、
  `assert_corpus_is_isolated` で repo path の重複を実測前に検査し、
  `observation.state_change_reasons` に `repo_diff` / `command` / `tool` を分けて記録するようにした。
  `before != after` は残している。案4（再実測での確認）は `FLW-TSK-012` の範囲。
