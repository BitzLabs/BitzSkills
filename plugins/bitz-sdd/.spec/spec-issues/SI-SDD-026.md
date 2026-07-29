---
id: SI-SDD-026
raised_by: BitzSkills root workspace（CORE要件26件の無記録promotion事故）
target: SDD-FR-143（監査chain検査の適用範囲）/ spec_inspect.py audit_state
proposed_change_type: bump
status: accepted
origin: BitzSkills（ルートworkspaceでの実事故からのエスカレーション）
---
- **目的**: `spec update` を通さず frontmatter の `status` を直接書き換えた遷移を、
  `spec inspect` が一切検出できない。SDD-FR-143 は「inspectはschema・event ID一意性・
  表示行との対応・遷移連鎖を検査すること」を要求し、`audit_state()` は最終eventと
  現frontmatterの一致まで照合するが、この照合は **STATEに1件以上eventがあるartifactにしか
  適用されない**（`spec_inspect.py` の `events_by_artifact` に載らないIDは走査対象外）。
  結果、eventが1件も無いartifactは status を何に書き換えても PASS する。
  実際にルートworkspaceで CORE-CON-001..010 / CORE-FR-001..017 / CORE-NFR-001 の26件が
  `verified` → `promoted` へ手編集で遷移し、Promotion Gate の裁定記録もSTATE遷移記録も
  無いまま `spec inspect` と `release_check.py` の両方が PASS して main へマージされた
  （事故そのものは revert 済み）。人間裁定必須遷移をCLIで構造強制した SDD-FR-143 の保証が、
  「CLIを使わない」だけで無効化される。
- **提案する修正**:
  1. `audit_state()` に「frontmatterのstatusが、対応eventの無いartifactで
     初期状態から動いている」ケースの検出を追加する。ただし全 non-draft artifact への
     一律要求は既存資産をほぼ全件fail させるため（下記「影響推定」）、
     **監査baselineの明示宣言**とセットで設計する。
  2. baseline の与え方（要設計・案）:
     - 案A（推奨）: workspace の `.spec/PROJECT.md` に監査開始点（コミットSHA または日付）を
       宣言し、**その時点以降にstatus行が変更されたartifactにのみ**event必須を課す。
       git履歴で判定するため既存資産の一括マーキングが不要。
     - 案B: 既存artifactへ一度だけ `audit_baseline: pre-transaction` 等のマーカーを付与し、
       マーカーもeventも無いartifactを `audit-corruption` とする。git非依存だが全件更新が要る。
  3. 検出範囲は最低限、**人間裁定必須遷移の到達状態**（`approved` / `promoted` / `deprecated`）に
     絞ってもよい。これらは権限マトリクス上エージェント単独では到達できないため、
     証跡不在＝規律違反と断定できる。
  4. `spec update` 側は変更不要（拒否ロジックは正しく機能している）。欠けているのは
     「CLIを迂回した事実の事後検出」だけ。
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py`（`audit_state()`）、
  `plugins/bitz-sdd/.spec/requirements/SDD-FR-143.md`（EARS節の追加＝bump）、
  `plugins/bitz-sdd/tests/test_spec_inspect.py`、
  案Aなら `plugins/bitz-sdd/skills/sdd-core/assets/PROJECT.md` と
  `references/lifecycle.md`（監査baselineの記法）。
- **確認観点**:
  - 既存要件との矛盾: SDD-FR-143 の既存EARS節は変更せず**追加**で足りるか（追加なら bump、
    既存節の意味が変わるなら supersede へ切り替える）。
  - 誤検知: 監査機構導入以前に作られた要件を violation として報告しないこと。
    baseline 宣言が無いworkspaceでは fail-closed ではなく**従来どおり無検査**とするか、
    警告に留めるかを裁定する必要がある（SDD-FR-144 の fail-closed 方針とは前提が異なる）。
  - git非依存性: 案Aは `spec inspect` に git 依存を持ち込む。`integration_preflight()` が
    すでに git を呼んでいる前例はあるが、通常の inspect 経路を git 必須にしてはならない。
  - ガードレール: 本issueの裁定（accepted / rejected 化）と SDD-FR-143 の bump は人間専権。
  - 軽量レーン: 公開CLIの判定結果と監査契約に触れるため不可。
- **影響推定・ロールバック**: 現時点で構造化eventを持つartifactは
  ルート2件（CORE-FR-004 / CORE-FR-005）と bitz-sdd 5件のみ。
  non-draft かつ event 記録の無い要件は root 26件・bitz-sdd 56件・bitz-env 19件・
  bitz-ddd 2件・bitz-flow 2件（計105件）にのぼり、一律要求すれば全workspaceが即FAILする。
  したがって baseline 設計を伴わない実装は不可。ロールバックは検査追加分の revert で足り、
  既存artifactへの破壊的変更を伴わない設計を選ぶこと。
  なお CORE-FR-011 は STATE に人間可読の表示行はあるが構造化eventが無く、
  正規CLI経由の遷移と手編集の中間状態にある。baseline 設計時の実例として扱える。
- **依存**: SDD-FR-143（bump対象）、SDD-FR-144（fail-closed方針との整合）、
  `references/lifecycle.md` の権限マトリクス。
- **予備判定（推薦）**: **accept推薦**。「人間裁定必須遷移をCLIが構造強制する」という
  SDD-FR-143 の中核価値が、CLIを迂回した場合に事後検出すらできず、実際に本リポジトリで
  無記録のpromotionがCI含む全ゲートを通過した実績があるため。ただし実装は baseline 設計の
  裁定が前提で、それ無しに検査だけ追加してはならない。
- **実施**: 2026-07-29 案A（`.spec/PROJECT.md` の `audit_baseline` 宣言によるgitベース監査）で
  SDD-FR-143 を 2.1 bump し、`spec_inspect.py` の `audit_baseline_gap()` を実装・検証した。
  未宣言workspaceは無検査（git非呼出）、baseline解決不能はWARN、検出範囲は人間裁定必須の
  到達状態のみ。判定は「未記録の到達状態」（baseline時点のstatus vs 記録済みeventの始点、
  eventが無ければ現status）の突き合わせで行う。設計裁定は
  `.spec/reports/decision-2026-07-29-si-sdd-026.md`。bitz-sdd 3.2.0。
