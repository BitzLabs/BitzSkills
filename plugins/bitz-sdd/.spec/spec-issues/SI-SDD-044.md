---
id: SI-SDD-044
raised_by: FLW-REV-018（OPS-105 / BIZ-101）
target: spec_verify.py の検証証跡が参照する commit の到達可能性
proposed_change_type: modify
status: open
---
- **目的**: `spec_verify record` が記録する検証証跡の `commit` が、マージ後の履歴に
  存在しない状態を解消する。**bitz-flow 固有ではなく、squash merge を採るすべての
  ワークスペースに共通する構造的欠陥**である。

- **発見した事実**（`FLW-REV-018` の独立レビューで複数観点が別経路から指摘）:
  - `.spec/verification/*.json` は実行時の `HEAD` の SHA を記録する
  - 本リポジトリの PR は **squash merge** であり、マージ時に新しい commit が作られる
  - そのため記録された commit は main の祖先にならず、**裁定者が証跡を確定 ref へ
    突き合わせられない**
  - bitz-flow の4件だけでなく、**M0 期の証跡も同じ状態**である（今回持ち込んだ欠陥ではない）
  - `.spec/verification/*.json` は「green 判定の正」と運用上定めているため、
    到達不能な commit を指す証跡はその役割を果たせない

- **提案する修正**（いずれを採るかは裁定で選ぶ）:
  1. commit ではなく**検査対象ファイル群の tree digest** で紐づける
     （マージ方式に依存せず、内容が同じなら同じ値になる）
  2. 記録後にマージ先 commit を追記できる後追い更新経路を用意する
  3. 現行のまま残し、`dirty` と同様に**到達可能性を示す field** を足して
     裁定者が自分で判断できるようにする

- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-test/scripts/spec_verify.py`、
  同スキルの `references/`、証跡の契約を定める `.spec/` 側の文書

- **確認観点**: squash merge 後に証跡が確定 ref から辿れること。
  既存の証跡（M0 期を含む）を壊さない移行経路があること。

- **影響推定・ロールバック**: 証跡の schema が変わる場合は既存ファイルの読み替えが要る。
  読み取り側（`spec_inspect` の証跡カウント）との整合を確認する。

- **依存**: bitz-flow の Completion Gate は「証跡を確定 ref へ突き合わせられること」を
  裁定材料にするため、本件の解決が前提となる。
