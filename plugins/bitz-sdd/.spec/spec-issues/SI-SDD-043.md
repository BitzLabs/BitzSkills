---
id: SI-SDD-043
raised_by: BitzSkills リポジトリ運用（inspection-report のパス汚染）
target: spec_inspect.py のクロスワークスペース参照識別子
proposed_change_type: modify
status: open
---

- **目的**: `inspection-report.md` の「他ワークスペースのテスト/実装から参照されている要件」節が、
  検査を実行したチェックアウト先の**ディレクトリ名**に依存しないようにする。
  現状は同じリポジトリの同じ内容でも、実行場所によって成果物の中身が変わる。

- **発見した事実**:
  - `external_refs_for()` は参照元を `f"{w.name}/{s}"` で畳む（`w` はワークスペースの絶対 Path）。
  - `plugins/*` のワークスペースでは `w.name` が `bitz-flow` 等になり安定するが、
    **ルートワークスペース（`.`）だけは `w.name` がチェックアウト先のディレクトリ名**になる。
  - このため worktree から実行すると、レポートに
    `bitzskills-m2-runtime-confirmation/tests/test_flow_contract.py` のような
    **一時ディレクトリ名**が記録される。worktree を撤去した後は存在しないパスとして残る。
    実例: BitzSkills の main に、削除済み worktree 名を含むレポートが5行入った（PR #272）。
  - `scan_refs()` 側は `f.relative_to(root)` でワークスペース相対に畳んでおり正しい。
    不安定なのはワークスペース**間**の識別子だけである。

- **提案する修正**:
  1. ワークスペース識別子を、チェックアウト先ではなく**リポジトリルートからの相対パス**
     （`git rev-parse --show-toplevel` 基準）で導出する。ルートワークスペースは
     `.` などの安定した表記に固定し、`plugins/bitz-flow` 形式へ揃える。
  2. git が使えない・リポジトリ外の場合は現行の `w.name` へ縮退する（既存挙動を壊さない）。
  3. 同一内容・異なるチェックアウト先で生成したレポートが**バイト一致**することを回帰テストで拘束する。

- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py`、
  `tests/test_spec_inspect.py`

- **確認観点**:
  - 同じ commit を2つの異なる名前の worktree で検査したとき、レポートが一致すること。
  - `plugins/*` ワークスペースの既存表記を変える場合、その差分が1回の締め工程で収束すること。
  - 単一ワークスペース検査（`trace_ctx` なし）の挙動が変わらないこと。

- **影響推定・ロールバック**: 生成物の表記だけが変わり、判定ロジックには触れない。
  表記変更により全ワークスペースのレポートに1回だけ差分が出る（締め工程で吸収する）。

- **依存**: なし。BitzSkills 側は AGENTS.md の締め工程規約
  （「メイン作業ツリーから実行する」）で暫定回避している。
