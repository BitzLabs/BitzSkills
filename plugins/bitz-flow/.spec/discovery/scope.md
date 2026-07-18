---
id: FLW-DSC-003
title: "bitz-flow スコープ（制約 → MoSCoW → In/Out-of-Scope 境界）"
status: draft
version: 1.0
updated: 2026-07-18
owner: hide
---

# スコープ（制約 → MoSCoW → In/Out-of-Scope 境界）

> 切り出し discovery。sdd-git から転記した機能セットを MoSCoW で追認しつつ、SDD 非依存化に伴う
> 帯域を明示する。Out-of-Scope（Won't）リストがスコープクリープに対する主ガード。
> **SDD 連携（Implements 突合・`.spec/tasks` 分解）の規定の正は bitz-sdd 側に残す**のが最重要の境界。

## 制約の棚卸し（最初にやる）

| 種別 | 制約 |
|---|---|
| 技術 | 各スキルはフォルダ単位で自己完結（他スキルの references を相対参照しない。連携はスキル名の言及） |
| 技術 | 失敗時復元はガードレール準拠のみ（`git reset --hard` / `git push --force` / `git clean -f` を規定しない） |
| 技術 | SDD 連携の正は bitz-sdd（sdd-implement / sdd-core parallel-git.md）にある。bitz-flow は接続点のみ持つ |
| 技術 | Git / GitHub（`git worktree` / `gh` CLI）に依存。ホスティングは GitHub を主対象とする |
| 組織 | メンテナは実質1名（作者 hide）。運用・保守コストは1人分に収める |
| プロセス | 開発は sdd-core 準拠（ドッグフーディング）。適用する bitz-sdd はリリース済み版に固定（PROJECT.md） |
| 法規制 | Agent Skills オープン標準／OSS ライセンス準拠。特段の追加規制なし |

**スコープ項目は上記制約に違反してはならない。** 違反するものは Won't に落とす。

## MoSCoW（帯域分け）

sdd-git から転記した機能を追認しつつ、SDD 非依存化の帯を分ける。判定基準:
「これ以外を全部出荷したら成功指標（FLW-DSC-002）を達成できるか?」

| 帯 | 項目 | 根拠 |
|---|---|---|
| **Must** | flow-core（フロー選択・コミット規約・失敗時復元） | フローの入口。単独開発でもこれだけで完結。SDD 非依存の核 |
| **Must** | flow-worktree（1エージェント=1worktree=1ブランチの並列運用） | 並列開発の物理分離。エージェント運用の中核価値 |
| **Must** | flow-pr（Issue 駆動 + Draft PR + squash merge + 未マージ依存の原則） | チーム・別リポジトリ開発の要。SI-CORE-020 の事故防止規約を含む |
| **Must** | SDD 非依存で単体完結すること | 存在意義。bitz-sdd 無しで機能する条件。ガードレール G3 と表裏 |
| **Should** | 各スキルの「bitz-sdd 併用節」（Implements フッター・`.spec/tasks` 連携の接続点） | 併用時の価値を繋ぐが、規定の**正は bitz-sdd 側**に置き二重化しない |
| **Should** | 各スキルの references による progressive disclosure | 品質保守に効くが機能の本質ではない |
| **Could** | SI-CORE-010: sdd-git の委譲ポインタ化（二重規定の解消） | 転記直後は sdd-git が併存。委譲化は磨き込み。未着手（open） |
| **Won't（今回は）** | Git フローそのものの正規定を bitz-flow に一元化（SDD 側の parallel-git.md を吸収） | SDD 連携の正は bitz-sdd に残す。吸収は境界違反 |
| **Won't（今回は）** | GitHub 以外のホスティング（GitLab / Bitbucket）固有フローの網羅 | GitHub を主対象に絞る。他は将来 `TBD` |
| **Won't（今回は）** | CI/CD パイプライン自体の構築・デプロイ自動化 | フロー規約に徹する。デプロイ・運用は sdd-ops 等の管轄 |
| **Won't（今回は）** | `git reset --hard` / `--force` / checkpoint 巻き戻しの規定 | ガードレールと衝突。復元は worktree 破棄→再投入に一本化 |
| **Won't（今回は）** | 要件・タスク・テスト設計（各 sdd-* の管轄） | フロー実行手段に徹する。仕様の正は `.spec/`（bitz-sdd） |

## In-Scope / Out-of-Scope 境界（必須）

| 区分 | 内容 |
|---|---|
| **In-Scope** | 状況別フロー選択 / worktree 並列運用（作成・マージバック・破棄） / Conventional Commits + Implements フッター規約 / Issue 駆動 Draft PR + squash merge / 未マージ依存の原則 / 失敗時の破棄→再投入 / bitz-sdd 併用時の接続点提示 |
| **Out-of-Scope（Won't）** | SDD 連携の正規定の吸収 / GitHub 以外のホスティング網羅 / CI/CD・デプロイ構築 / 破壊的巻き戻しの規定 / 要件・タスク・テスト・インフラ設計（各 sdd-* の管轄） |

**Won't を名指しすることがスコープクリープを止める。** 特に「SDD 連携の正の吸収」と
「破壊的巻き戻しの規定」は要望が来やすいが、前者は bitz-sdd との境界を、後者はガードレールを壊すため
明示的に除外する。
