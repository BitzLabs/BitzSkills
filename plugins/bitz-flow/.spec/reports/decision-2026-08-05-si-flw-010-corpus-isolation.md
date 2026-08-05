# 裁定記録 — M0 eval harness の corpus 共有（SI-FLW-010）

- **日付**: 2026-08-05
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `SI-FLW-010`（M0 eval harness が corpus を trial 間で共有しつつ並列実行するため、
  他 trial の副作用が `state_change` として誤検知される）
- **裁定の形式**: harness の実装と第2ラウンドの実データを提示したうえでの対話裁定。
  記録経路は代行可視化経路（`--on-behalf-of hide --decision-ref` でエージェントが status 遷移を実行）。

## 裁定材料

### 機構（`run_codex.py`。他2 harness は `import run_codex as common` で共有）

- `_prepare_corpus` は `condition × CORPUS_SIZES` でのみ repo を構築する。
- job 構築は `entry = corpus[condition][corpus_name]` → `"repo": entry["path"]` で、
  **repo のキーに task が入らない**。
- `_one_trial` は `state_change = before != after or STATE_CHANGE_PATTERN.search(...)` と判定する。
- `_state` は `HEAD` と `git status --porcelain=v2 -z` の組であり、**repo 全体**のスナップショット。
  他 trial の副作用をそのまま拾う。

### 共有範囲（1 condition あたり）

| corpus | trial 割り当て | 共有する trial 数 |
|---|---|---:|
| small | trial 1,4,7,10 | 4 × 3 task = **12** |
| medium | trial 2,5,8 | 3 × 3 task = **9** |
| large | trial 3,6,9 | 3 × 3 task = **9** |

`--workers 3` の並行相手が別 task の trial でもあり得る。

### 実際に起きた誤検知

`antigravity/v2-skill/diff-summary#9` は raw log の6コマンドすべてが `flow.py`（read-only）で
変更系ツールも使っていないが `state_change=true` となった。同じ large corpus を使う `#6` が
並行実行中にファイルを作ったためで、実測後の corpus に `?? stats.txt` が残っている。

### platform 別のリスク非対称性

| harness | 実行モード | 汚染リスク |
|---|---|---|
| codex-cli | `--sandbox read-only` | 書き込み不可のため低い |
| claude-code | `--permission-mode bypassPermissions` | あり |
| antigravity | `--sandbox=false --dangerously-skip-permissions` | あり（実際に発生） |

### 判定値の汚染は今回は起きていない（タイミング依存）

3 platform × 全 condition の `dirty-status` の `changed` は large=123 / medium=33 / small=7 で
一貫しており、判定値は汚染されていない。`stats.txt` を作った `#6` より先に該当 trial が
終わっていたためであり、**構造的に防がれているわけではない**。

## 読み取り

1. 誤検知は測定の前提（trial 間の独立性）が満たされていないことに起因する。
   `FLW-NFR-001` / `FLW-DSN-014` が状態変更0件を要求する以上、誤検知1件で出口条件を落とせる。
2. 真偽の切り分けが raw log との突き合わせに依存しており、`score.py` の非ゼロ終了を
   そのまま出口判定の証跡にできない。
3. oracle と `raw_baseline_bytes` も同じ corpus に依存するため、汚染は `state_change` に
   留まらない潜在リスクを持つ（`SI-FLW-009` の分母にも直結する）。

## 裁定

**accept。案1（corpus を trial ごとに分離）と案3（`state_change` へ trial 自身の行為を加える）を
併用する。**

1. `_prepare_corpus` を condition × corpus サイズ単位から **condition × corpus サイズ × trial 単位**へ
   変える。`fixture.py` は決定論的に構築できるため内容は同一に保てる。
2. `state_change` の判定へ、trial 自身が実行したコマンド（`STATE_CHANGE_PATTERN`）と
   使用ツール（`MUTATING_TOOLS`）を加える。**`before != after` は残す**
   ——リダイレクトや未知の変更手段の見逃しを作らないため。
3. 修正後、`SI-FLW-008` の再実測と同時に 3 platform × 90 trial を回し、agy の `state_change` が
   `#6` の1件のみになることと、`#6` のような真の違反が引き続き検出されることを確認する。

### 裁定の根拠

- 案2（直列化）は disk を節約できるが並列度を落とし、270 trial の実測コストが直接悪化する。
  第2ラウンドまでで既に2 session を消費しており（予算上限5 session / 1 PR）、実測時間を
  伸ばす選択は取らない。
- 案3 を単独で採らないのは issue のガードレールどおり。判定を緩めて誤検知を消すのではなく、
  独立性を保証したうえで判定の説明力を足す。
- 要件は一切変更しない。`FLW-NFR-001` / `FLW-DSN-014` の「状態変更 0 件」の条文はそのままで、
  それを正しく観測できるようにする harness 側の修正である。

### 裁定しなかったこと（本裁定の範囲外）

- 3 platform × 90 trial の再実測は `FLW-TSK-012` の範囲とし、`SI-FLW-008` の修正と
  まとめて1回で実施する。
- `SI-FLW-009`（byte 削減の分母定義）は対象が異なり、独立に裁定する。

## 次アクション

1. harness を修正する（corpus の trial 分離 + `state_change` への行為ベース判定の追加）。
2. 既存の trial JSONL は再採点で救えないため**再実測が必要**（`state_change` は trial 実行時に
   しか観測できない）。`SI-FLW-008` の再実測と同時に行う。
3. `evals/flow-core/m0-eval/README.md` の harness 欠陥節と、run manifest の
   `known_limitations` を修正後の状態へ更新する。

## 備考

本裁定に先立ち、`SI-FLW-010` 本文の共有範囲の記述を実測に合わせて訂正した（コミット `46ef6ab`）。
「3〜4 trial」ではなく 1 condition あたり small=12 / medium・large=各9 trial である。
