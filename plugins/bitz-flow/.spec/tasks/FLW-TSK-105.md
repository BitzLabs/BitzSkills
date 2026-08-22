---
implements: FLW-NFR-011
depends_on: []
boundary: evals/flow-core/m1-eval/run_qualification.py,evals/flow-core/m2-eval/run_local_confirmation.py,evals/flow-core/m2-eval/local_confirmation_subject.py,evals/flow-core/m2-eval/active-local-confirmation.json,evals/flow-core/m2-eval/attempts.jsonl,evals/flow-core/m2-eval/qualification-2026-08-22-flw-tsk-105.json,scripts/agy_guard.py,tests/test_agy_guard.py,tests/test_flow_m1_qualification_runner.py,tests/test_flow_m2_confirmation.py,plugins/bitz-flow/.spec/tasks/FLW-TSK-105.md
status: done
---

### confirmation Gate で raw log と attempt 台帳の実在性を再照合する

- **作業内容**: Gate 採用時に、各 platform の raw log が manifest 相対 path・保存 root・digest・canary と一致して実在すること、attempt ledger が実在し digest と hash chain が一致し全 platform の trial を含むことを再照合する。
- **実走是正**: qualification の3者合成結果へ confirmation 起動前に拘束した
  compatibility key・集約完了時刻・保守的な最短期限を機械記録する。Antigravity の現行
  PreToolUse payloadを値非保存の形状観測で再測定し、限定subject 1コマンドだけを通す
  fail-closed allowlistを現行契約へ合わせる。Antigravity sandboxでは共有Git common-dirと
  検証用virtualenvを利用できないため、`--sandbox=false`は完全一致subjectに限って許可し、
  permission bypass・別commandへの一般化は行わない。共有`.venv`を直接公開せず、pytestに
  必要なruntimeだけをworktree内へ短命配置し、実走後に撤去する。Git common-dirやhome全体は
  公開しない。
- **完了条件**: raw log または ledger を削除・改竄した manifest は `BLOCKED` となり、
  生成直後の artifact は Gate 検証を通る。qualification summaryを手作業bootstrapせず
  confirmationへ渡せ、Claude / Codex / Antigravity の3者実走が合成PASSになる。
- **備考**: 新しい evidence は confirmation 実走時に生成する。既存 artifact は上書きせず、実在しないものを Gate 非採用とする。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
- **検収結果（2026-08-22）**: compatibility key
  `sha256:db4fbe5a5242d67ccb8be18966c8392e9a6efc986b38eaf5e529e981314bde13` で
  qualification / confirmation とも Claude・Codex・Antigravity の3者合成PASS。
  confirmationは各206 tests、runtime checks 69/69、hazard/residual 0件。生成直後manifestの
  Gate再照合PASS、全pytest 2154件PASS、release check PASS、全workspace spec inspect PASSを確認した。
