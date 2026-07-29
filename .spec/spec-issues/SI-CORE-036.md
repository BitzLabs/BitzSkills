---
id: SI-CORE-036
raised_by: SI-SDD-026 実装時の実事故（bump_version.py が --help を無視して bump を実行）
target: 全リポジトリスクリプトの引数解析（argparse への統一と未知引数の拒否）
proposed_change_type: new
status: accepted
---
- **目的**: 副作用のあるスクリプトが、ユーザーが安全のために付けたフラグを黙って無視して
  変更を実行する。`scripts/bump_version.py` は `sys.argv[1]` でしか `-h` / `--help` を見ておらず、
  `sys.argv[3]` 以降を一切検査しない:

  ```python
  if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
      sys.exit(__doc__)
  name = sys.argv[1]
  part = sys.argv[2] if len(sys.argv) > 2 else "patch"
  ```

  このため `python3 scripts/bump_version.py bitz-sdd minor --help` は help を表示せず
  **bump を実行する**。実際に SI-SDD-026 の実装中にこれで意図しない bump（3.2.0 → 3.3.0）が
  走り、3マニフェストを手で戻す事故が起きた。`--dry-run` は未実装のため、安全確認のつもりで
  そのフラグを付けた場合も同様に変更が適用される。

  問題の質は「タイプミスを飲み込む」ではなく、**破壊的操作を持つツールが安全側の意図表明を
  無視して実行する**こと。ガードレールが「事前確認が必要」としている操作の手前で、
  ユーザーの確認動作そのものが空振りする。

- **提案する修正**:
  1. `scripts/bump_version.py` の手書き `sys.argv` 解析を **`argparse` へ置き換える**。
     未知フラグは argparse の既定動作で自動的に拒否され、`--help` は位置に関わらず効く。
     あわせて `--dry-run`（差分を表示して書き込まない）を追加する。
  2. 全スクリプトの引数解析を棚卸しし、「**未知引数を受理して処理を続行しない**」ことを
     リポジトリ共通の契約として要件化する（下記「棚卸し結果」が現状のベースライン）。
  3. 引数を取らない no-arg スクリプト（`release_check.py`）も、余分な引数を黙認せず
     エラー終了させる。読み取り専用で実害は無いが、「フラグが効いた」という誤認を作らないため。
  4. stdin JSON で駆動する hook スクリプト（`agy_guard.py` / `env_guard.py`）は
     CLI 引数を取らない設計のため対象外とするか、同様に余分な引数を拒否するかを裁定する。

- **棚卸し結果（2026-07-29 時点。全17ファイル）**:

  | 分類 | スクリプト | 現状 |
  |---|---|---|
  | **手書き `sys.argv`（要修正）** | `scripts/bump_version.py` | 未知引数を黙認し **mutation を実行**。実害発生済み |
  | no-arg（要裁定） | `scripts/release_check.py` | `--bogus-flag` を黙認して正常終了（読み取り専用） |
  | stdin hook（対象外候補） | `scripts/agy_guard.py`, `plugins/bitz-env/scripts/env_guard.py` | stdin JSON 駆動。CLI 引数を取らない |
  | ディスパッチャ | `scripts/spec` | `argv[0]` を `TOOLS` と照合し、残りを委譲先へ転送。委譲先が argparse で検査 |
  | argparse 済み（現状維持） | `commit_lint.py`, `branch_preflight.py`, `pr_helper.py`, `worktree_ops.py`, `spec_inspect.py`, `spec_scaffold.py`, `spec_status.py`, `spec_update.py`, `docs_inspect.py`, `migrate_docs.py`, `sdd_sync.py`, `sdd_report.py` | 未知引数を拒否（実証済み） |
  | ライブラリ（CLI なし） | `spec_labels.py`×2, `spec_trace.py`, `spec_transaction.py` | `__main__` を持たない |

  実証:

  ```
  $ python3 plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py . --bogus-flag
  spec_status.py: error: unrecognized arguments: --bogus-flag

  $ python3 scripts/release_check.py --bogus-flag
  結果: PASS（全チェック合格）        # 黙認
  ```

  `parse_known_args` / `argparse.REMAINDER`（未知引数を意図的に通す書き方）は
  リポジトリ内に1件も無い。つまり修正対象は実質 `bump_version.py` 1件で、
  残りは**契約として明文化し回帰を防ぐ**ことが主眼になる。

- **対象ファイル**: `scripts/bump_version.py`（argparse 化 + `--dry-run`）、
  `scripts/release_check.py`（余分な引数の拒否）、
  `tests/`（未知引数を渡したとき非ゼロ終了し副作用が無いことの回帰テスト）、
  ルート `.spec/requirements/`（CLI 契約の要件化。CORE-CON 系が妥当か CORE-FR 系かは裁定時に決める）、
  `AGENTS.md`「定型手順」節（`--dry-run` を案内に追加するかは裁定次第）。

- **確認観点**:
  - 既存要件との矛盾: なし。既存の CLI 契約要件を変更せず**追加**で足りる見込み
  - 後方互換: `bump_version.py` の既存の呼び出し形（`<plugin名> [major|minor|patch]`）は
    argparse 化後も同一に保つ。`scripts/bump_version.py <name>` の part 既定値 `patch` も維持する
  - 誤検知: 引数を取らないスクリプトを厳格化すると、既存の呼び出し側（CI・フック・
    ドキュメントの例）が余分な引数を渡していないかの確認が要る
  - hook スクリプトの扱い: `agy_guard.py` / `env_guard.py` は Claude / Antigravity の
    フック契約で起動されるため、プラットフォーム側が引数を付けて呼ぶ可能性を確認してから
    厳格化する（付けて呼ばれる場合、厳格化すると**フックが壊れる**）
  - ガードレール: 本 issue の裁定は人間専権
  - 軽量レーン: `bump_version.py` の argparse 化のみなら軽量レーン適だが、
    「未知引数を拒否する」を全スクリプトの共通契約として要件化するなら不適

- **影響推定・ロールバック**: 修正対象は実質1〜2ファイルで、いずれも副作用は
  「これまで黙って通っていた呼び出しがエラーになる」方向のみ。既存の正しい呼び出しは影響を受けない。
  ロールバックは当該コミットの revert で足り、成果物への破壊的変更を伴わない。
  hook スクリプトを厳格化対象に含める場合のみ、プラットフォーム側の起動形に依存するため
  影響範囲が広がる（上記「確認観点」で先に確認する）。

- **依存**: なし（SI-SDD-026 の実装中に発見されたが、機能的な依存関係は無い）。

- **予備判定（推薦）**: **accept 推薦**。破壊的操作を持つツールがユーザーの安全側の
  意図表明（`--help` / `--dry-run`）を無視して実行するのは、ガードレール規律の前提を
  崩す。実害が既に1件発生しており、修正コストは小さく後方互換も保てる。
  ただし hook スクリプトの厳格化はプラットフォーム側の起動形を確認するまで含めない。
