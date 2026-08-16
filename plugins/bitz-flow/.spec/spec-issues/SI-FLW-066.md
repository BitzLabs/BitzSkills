---
id: SI-FLW-066
raised_by: FLW-REV-017 consistency（RVC-201 / RVC-103 / RVC-102）
target: 是正PRのタスク追跡と、覆った宣言・operation-catalog の追随
proposed_change_type: modify
status: open
---

- **目的**: `FLW-REV-017` が指摘したトレーサビリティの断絶を解消する。
  本 issue は**裁定待ち**であり、実施は後続の予算裁定に従う。

- **発見した事実**:
  1. **是正 PR に対応するタスクが無い**（`FLW-REV-017:SYN-008` / `RVC-201`）。
     `SI-FLW-063` / `SI-FLW-064` に対応する task が存在せず（tasks は `FLW-TSK-086` 止まり）、
     PR #289 + #290 の変更21ファイル中4件がどの boundary にも属さない。
     `FLW-TSK-086` の boundary は `SI-FLW-059` の成果物を指したままである。
     `spec_inspect` はこの規律を検査しないため PASS してしまう。
  2. **覆った宣言が残置**（`FLW-REV-017:SYN-009` / `RVC-103`）。
     `SI-FLW-064` で覆った「operation 外の変更検出は行わない…
     `data.external_change_detection` で不可を宣言する」が
     `FLW-TSK-086`（status: implementing）に規範として残っている。
     STATE.md 側は訂正済みでタスクだけ漏れた。該当 field はコードから消えている。
  3. **catalog 未追随**（`RVC-102`）。`worktree.audit` の新しい振る舞い
     （`BLOCKED` / `external_changes` / receipt 突合）が operation-catalog へ反映されておらず、
     契約の正が再びコードだけになっている。11 field 契約の未適用も残存する。

- **提案する修正**:
  1. `SI-FLW-063` / `SI-FLW-064` / `SI-FLW-065` に対応するタスクを起こし、boundary を実体へ合わせる。
  2. `FLW-TSK-086` から覆った宣言を削除する。
  3. operation-catalog を audit の新しい振る舞いへ追随させる。
  4. 「PR の変更ファイルがいずれかの task boundary に属すること」を機械検査できるか検討する
     （`spec_inspect` の対象外である現状が、この断絶を見えなくしている）。

- **対象ファイル**: `plugins/bitz-flow/.spec/tasks/`、
  `plugins/bitz-flow/skills/flow-core/references/operation-catalog.md`、
  `plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py`（4 を採る場合）

- **確認観点**:
  - 是正 PR の全変更ファイルがいずれかの task boundary に属すること。
  - 覆った宣言が文書のどこにも残っていないこと。
  - catalog がコードの振る舞いと一致すること。

- **影響推定・ロールバック**: `.spec/` と catalog に閉じる。4 を採る場合は bitz-sdd 側の変更となる。

- **依存**: なし。`SI-FLW-063` / `064` / `065` の後始末に当たる。
