---
id: SI-FLW-024
raised_by: ユーザー要望（2026-08-07 セッション）
target: FLW-DSN-008 の未マージ依存節・flow-pr SKILL.md のスタック PR 禁止・discovery/scope.md（MoSCoW）
proposed_change_type: modify
status: open
---
- **目的**: GitHub の **stacked pull requests がネイティブ機能として公開された**という
  外部環境の変化を受け、bitz-flow の「スタック PR 禁止」という現行の立場を再検分し、
  フローとして組み込めるかを裁定する。

- **現状1（bitz-flow の立場 = 明示的な禁止）**:
  - `FLW-DSN-008` L102「stacked PR は作成しない。依存 PR を先に land し、
    最新 default から別 WorkUnit を作る」
  - 同 merge plan の必須証跡 L77「stacked PR でない（head branch を base とする open PR なし）」
  - 診断コードに `stacked-pr` を持つ（= 検出したら止める側の設計）
  - `flow-pr/SKILL.md` L90「未マージ PR のブランチを base にしたスタック PR を安易に作らない」＋例外時手順
  - 根拠は `SI-CORE-020` の実事故（2026-07-13）。上段を `gh pr merge --delete-branch` した際に
    base branch が消え、**下段 PR が retarget されず自動クローズ**され、リベース＋PR 再作成が必要になった。

- **現状2（GitHub 側の事実 / 2026-08-07 時点で確認）**:
  - **2026-07-30、stacked pull requests が public preview で全リポジトリへ段階公開**
    （[GitHub Changelog](https://github.blog/changelog/2026-07-30-stacked-pull-requests-are-now-in-public-preview/)）。
  - CLI は公式 extension `gh extension install github/gh-stack`。github.com / mobile /
    Copilot agents からも扱える。
  - 「最新の ready な PR を merge すると、その下の未マージ層をまとめて1操作で land」でき、
    **部分マージ時は上位層が自動 rebase** される。
  - 「既存の branch protection と required checks はそのまま効く」。
  - **merge queue 対応は数週間かけて順次**。preview 段階で全機能が揃っていない。

- **論点**: 事故の直接原因（base branch 消滅 → retarget 不発）は、GitHub がスタックの順序と
  再ベースを**自分で管理する**ことで構造的に解消される可能性が高い。つまり `SI-CORE-020` の
  禁止根拠は**部分的に無効化された**。一方で v2 の設計前提とは次の点で衝突する。

  | 衝突点 | 内容 |
  |---|---|
  | 外部依存 | `scope.md` の外部前提は「Python 3.10+ / Git / 必要時 `gh`」。`gh-stack` **extension** は新規の外部依存 |
  | passthrough 禁止 | Won't「任意 `gh api` passthrough」。extension 経由の操作も method / field 固定の adapter 化が要る |
  | capability 差 | public preview = 有効・無効・未対応が混在。`FLW-DSN-014` の capability contract 対象になる |
  | squash 契約 | v2 は squash merge と squash subject 契約が前提。stack merge が squash とどう合成されるか changelog に明示がなく**未確認** |
  | 状態機械 | `FLW-DSN-008` は単一 PR の線形状態機械。部分マージ + 自動 rebase は head SHA を外部要因で動かすため、expected head SHA 契約（`FLW-FR-009`）と直接干渉する |
  | merge queue | queue 必須リポジトリでの stack 挙動が順次対応中。`FLW-DSN-008` は queue を別状態として扱う設計 |

- **提案する修正（3案。裁定は人間）**:
  1. **A: 現状維持（禁止を明文で継続）** — 根拠を「事故」から「preview 段階の仕様変動リスク +
     外部依存増 + expected head SHA 契約との干渉」へ**更新**し、`FLW-DSN-008` と
     `flow-pr/SKILL.md` の記述の理由づけだけを差し替える。再評価時期を明記する。
  2. **B: 検出のみ対応（read-only capability）** — `scope.md` の Could に
     「stacked PR の capability 検出と stack 所属の可視化」を置く。stack を**作らない**が、
     他者が作った stack を検出したとき `stacked-pr` で一律ブロックせず、
     状態を正しく報告する。M4 の PR 契約への影響は最小。
  3. **C: フローとして採用** — worktree-first と組み合わせた stack 運用を v2 に組み込む。
     `FLW-DSN-008` の状態機械、`FLW-FR-009` の expected head SHA、`FLW-DSN-012` の
     WorkUnit 写像、`SI-CORE-020` 由来の記述（bitz-sdd `sdd-git` 側含む）を全面改訂し、
     Design Gate を再裁定する。

- **対象ファイル**: `plugins/bitz-flow/.spec/design/FLW-DSN-008.md`、
  `plugins/bitz-flow/.spec/discovery/scope.md`、`plugins/bitz-flow/skills/flow-pr/SKILL.md`、
  案 C の場合は加えて `requirements/FLW-FR-009`、`design/FLW-DSN-012`、`design/FLW-DSN-014`、
  ルート `.spec/spec-issues/SI-CORE-020`（前提が変わった旨の追記）、
  `plugins/bitz-sdd/skills/sdd-git/references/issue-driven-flow.md`。

- **確認観点**:
  - `gh-stack` を入れずに `gh` 標準だけで stack 所属を判定できるか（判定できるなら案 B の
    実装コストは低い。head branch を base とする open PR の照会は既存 preflight で可能）。
  - stack merge と squash merge の合成規則。squash subject 契約が壊れないか。**要実測**。
  - 自動 rebase で head SHA が動いたとき、`FLW-NFR-005` のべき等性・重複副作用防止が保てるか。
  - preview 機能に依存した契約を v2 の安定版入口として案内してよいか（`FLW-DSN-011` の
    規範セット時間軸）。
  - 本リポジトリ自身の運用（AGENTS.md / `pr-unmerged-dependency-no-stacking` の規律）を
    変えるかは**別判断**。bitz-flow の提供機能と BitzSkills の自己運用規約を混同しない。

- **影響推定・ロールバック**: 案 A は文言のみで単独 revert 可能。案 B は Could 追加 + 検出処理で
  局所的。案 C は M4 の PR 契約の中核を書き換えるため Design Gate 再裁定が必須で、
  v2 のスケジュールに直接影響する。

- **依存**: `FLW-DSN-008` は active、`FLW-FR-009` は approved。M0 出口未達のため、
  いずれの案でも着手は M4 以降。ただし**裁定自体は今行える**（M4 の設計に入る前に決めるべき）。

- **予備判定（推薦・裁定ではない）**: **案 B を推薦**（A へのフォールバック可、C は時期尚早）。
  | 判定軸 | 結果 |
  |---|---|
  | 既存要件との矛盾 | 案 C は `FLW-DSN-008` と正面衝突（supersedes 相当の改訂が要る）。案 A / B は矛盾なし |
  | ガードレール抵触 | なし（stack 運用自体は force push・履歴書換えを必須としないが、自動 rebase は Won't「rebase を通常フローに含めない」と**要整理**） |
  | 影響範囲 | 案 A: 文書2件 / 案 B: scope + 検出1箇所 / 案 C: FR・DSN 4件 + 他ワークスペース |
  | 軽量レーン適否 | 案 A のみ軽量レーン可。B / C は要件化が必要 |

  理由: 禁止の根拠だった事故モードは GitHub 側で解消された可能性が高く、「禁止を維持する」
  にしても理由の更新は必要である。一方で public preview（merge queue 対応が未完）の機能を
  v2 の中核契約へ取り込むのは、M0 出口すら未達の現況では過剰なリスクである。
  **stack を作らないが正しく検出・報告する**案 B が、v2 の目的（決定論的な安全判定）を
  損なわずに現実の GitHub と齟齬を起こさない最小の対応になる。preview 卒業（GA）後に
  案 C を改めて起票することを推薦する。
