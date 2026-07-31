# 裁定記録 — bitz-flow ROADMAP 未裁定論点7件

- **日付**: 2026-07-31
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `plugins/bitz-flow/.spec/ROADMAP.md` が洗い出した未裁定論点1〜7
- **裁定の形式**: 対話で提示した選択肢に対する明示選択。エージェントは選択結果を
  ROADMAP と成果物へ反映する（新たな裁定を行わない）。
- **前提**: 2026-07-29 の Design Gate 裁定
  （`.spec/reports/decision-2026-07-29-bitz-flow-v2-design-gate.md`）は有効なまま。

## 裁定

### 1. v2 の version 番号 — 1.0.0 カットオーバー

- M0〜M5 は `0.4.0` 以降の minor / patch で prerelease として進める。この間 v1 が正であり、
  v2 script を安定版入口として案内しない。
- Promotion Gate と**同一の変更セット**で `1.0.0` へ上げ、v2-current へ切り替える。
- 同じ変更セットで bitz-sdd の依存宣言を `bitz-flow>=0.2` から `bitz-flow>=1.0` へ更新する。
- prerelease 識別子（`1.0.0-alpha.1` 等）は採用しない。`scripts/bump_version.py` が
  `\d+\.\d+\.\d+` しか受理せず、`release_check.py` の `parse_version` が
  `re.findall(r"\d+")` でプレリリースを誤順序比較するため、採用にはルート側の
  ツール改修が前提になる。この改修は行わない。

### 2. 要件の承認単位 — 一括承認

- v2 の FR / NFR / CON を一度に approved とする。分割・段階承認は行わない。
- 実装の先走りは承認単位ではなく milestone ゲートで防ぐ。approved 後も
  **M0 スコープだけをタスク分解**し、M0 出口条件を満たすまで M1 を開始しない。
- `spec inspect` の「実装待ち要件（approved だが implements するタスクがない — WARN）」に
  M1 以降の要件が M5 まで並ぶことを**許容する**。これは「承認済みだが未着手」という
  事実の可視化であり、FAIL ではない。
- M0 の実測で M1 以降の受入基準を変更する必要が生じた場合は、`lifecycle.md` の
  「緑を赤にし得るか」基準で人間が bump / supersede を裁定する。

### 3. cross-host GitHub create — スコープ境界として受入れ

- 分散 lock は v2 で実装しない。`FLW-CON-004` の縮退契約
  （plan への非保証表示、証明できなければ `UNSUPPORTED`、marker を lock として扱わない、
  重複検出時は `BLOCKED` で自動 close / delete / edit をしない）をそのまま承認する。
- 同一 host の並行実行は `FLW-NFR-006` の直列化と `FLW-DSN-012` の `concurrency_key` で扱う。
  現運用（1マシン + worktree 並列）ではこの経路だけで足りる。
- 「単一 coordinator であることの証明手段」は **M3 着手時の設計判断**へ委譲する。
  M3 / M4 canary で重複割当0件・marker 重複0件を実測し、1件でも出れば当該 milestone の
  Promotion Gate を停止する。

### 4. Should 機能の昇格 — 1.0.0 到達後に個別昇格

- v2 完成条件は Must のみとする。GitHub Projects、branch protection 読取 / merge 待機、
  merge queue、component mode の CHANGELOG / release notes、`flow.py explain <code>` は
  M0〜M5 の予算に含めない。
- 昇格は Promotion Gate 後に spec-issue → 要件化を経て `1.1.0` 以降で個別に行う。
  順序は実需要順とし、本裁定では固定しない。
- 根拠: いずれも Must 側に安全な代替がある（branch protection は読取不能なら merge を
  `BLOCKED`、merge queue は queue 投入 `UNSUPPORTED`、Projects は無効化して `DEGRADED`、
  CHANGELOG は repository mode で出荷可能）。`FLW-DSN-014` の
  「Must 出口を満たした後に個別昇格する」と一致する。

### 5. release publish の有効化条件 — 7 fixture + canary publish 1件

M5 前半（`changelog-apply` / `tag-create` / `tag-push` / `draft`）から後半（`publish` 有効化）へ
進む入口条件を、次のとおり fixture 名まで固定する。要求水準の追加も緩和も行わない。

- unit fault fixture 7件が green: pagination、PR 重複、CHANGELOG atomicity、tag 応答喪失、
  draft 重複、target 不一致、publish 承認
- canary repo で draft 10件 + prerelease publish 1件を実測し、誤 tag・誤 publish・
  notes 不一致が各0件
- publish は v2 完成条件に含めたままとする（`FLW-DSN-014` 縮退規則4 のとおり黙って除外しない）

### 6. Design Gate の GatePassage — 遡及起票

- `FLW-GATE-001`（`gate: design`、`date: 2026-07-29`、`arbiter: hide`）を起票し、
  `scope` に SI-FLW-002〜005 と FLW-DSN-000 / 002〜014 の18件、
  `confirmed_decision_refs` に 2026-07-29 の裁定記録を記載する。
- 目的は滞留の解消。spec-issue の `open → accepted` は promoted 状態を持たないため、
  Promotion Gate を待っても自動では検分済みにならない。
- `lifecycle.md` は遡及追加を**要求していない**が、禁止もしていない。裁定日・裁定者・対象・
  裁定記録がすべて実在するため、記録の真正性を損なわずに写せる。
- draft → approved には `--gate-passage` は不要（必須なのは verified → promoted のみ）。

### 7. `sdd-git` の廃止 — V4 で後継化

- bitz-flow フェーズ7（v1 撤去）に `sdd-git` の削除を**含めない**。
- `CORE-FR-016`（promoted。2026-07-13 裁定で「縮退維持・完全廃止はしない」）の後継化は
  bitz-sdd V4 Charter で行う。SDD 固有の接続点（Implements フッター書式、
  `.spec/tasks` の並列投入条件、失敗時 worktree 破棄復元）の移設先は、bitz-sdd ROADMAP
  未裁定論点18「SDD・flow 直接接続の所有者」と一体で裁定する。
- 理由: root / bitz-sdd 名前空間の要件変更を bitz-flow V2 の milestone 予算に乗せない。
  移設先の判断は V2 Promotion Gate 後の確定した operation catalog を入力にしたほうが正確。

## 反映先

| 裁定 | 反映先 |
|---|---|
| 1, 2, 3, 4, 5, 7 | `plugins/bitz-flow/.spec/ROADMAP.md`（未裁定論点 → 裁定済みへ移動） |
| 6 | `plugins/bitz-flow/.spec/gates/FLW-GATE-001.md`（新規） |
| 1 の依存更新 | フェーズ7 で bitz-sdd の3マニフェスト `metadata.dependencies` |
| 7 | `plugins/bitz-sdd/.spec/ROADMAP.md` 未裁定論点17 の入力（本裁定では bitz-sdd 側を変更しない） |

## 次工程

v2 の draft 要件を一括で approved へ進める（裁定2）。承認後は M0 スコープだけをタスク分解する。
