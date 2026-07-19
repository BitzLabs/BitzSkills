---
id: SI-ENV-025
raised_by: ENV-FR-012 救済フローの実地試行（2026-07-19 本リポジトリへの stamp 後付け）
target: plugins/bitz-env/skills/env-update/SKILL.md 手順4（書き込み前の承認フロー）
proposed_change_type: modify
status: accepted
---
- **目的**: env-update の dry-run（手順4）は rollback 用バックアップ先の提示を求めるが、
  **書き込み対象が git 管理下かどうかの確認手順が無い**。ENV-FR-012 救済フローの実地試行
  （本リポジトリへの stamp 後付け）で、レジストリ `.claude/bitz-env.local.md` が
  `.gitignore`（`.claude/*.local.md`）対象の git 管理外であるにもかかわらず
  「rollback 手段は git」と誤提示し、手順5.1 が規定する git 管理外向けの `.bak`
  バックアップ取得もスキップされた。手順4 の提示内容と手順5.1 の分岐が実行時に
  接続されておらず、判定の根拠確認が暗黙になっているのが原因。
- **提案する修正**:
  1. 手順4 に明示ステップを追加する: 変換対象ファイルごとに git 管理状態を
     `git ls-files` / `git check-ignore` 等で**実際に確認**し、その結果に応じた
     rollback 手段（git 管理下 = git / 管理外 = `.bak` 取得）を dry-run で提示する
     （推測や既定値での提示を禁止する）。
  2. レジストリ `.claude/bitz-env.local.md` は env-init の既定で gitignore 対象
     （ローカルファイル）になる旨を手順4 か注記に明記し、「リポジトリ内 = git 管理下」
     という誤推定を防ぐ。
  3. migration-runbook.md に同趣旨の記述があれば同期する。
- **対象ファイル**: `plugins/bitz-env/skills/env-update/SKILL.md`（手順4・手順5.1 の接続）、
  必要に応じて `references/migration-runbook.md`。マニフェスト bump。
- **確認観点**:
  - dry-run の提示に対象ファイルごとの git 管理状態と対応する rollback 手段が含まれること
  - git 管理外の対象へ書き込む際、承認後の適用で `.bak` バックアップが必ず取得されること
  - gitignore されたレジストリを持つ環境（本リポジトリ相当）で誤提示が再発しないこと
- **影響推定・ロールバック**: SKILL.md の手順追記が中心で契約（レジストリ書式・
  CORE-CON-008/009）には触れない。単独 revert 可能。
- **依存**: ENV-FR-011 / ENV-FR-012（手順4・5 の現行規定）。関連: SI-ENV-024（発見元の実地試行）。
- **実施**: 2026-07-19 ENV-FR-013 起票 → ENV-TSK-016 で SKILL.md 手順4・5.1 の接続と
  migration-runbook.md 同期を実装、合成フィクスチャ検証 G1〜G4 PASS
  （`evals/env-update/dryrun-rollback/`）で verified。
- **予備判定（推薦・裁定は人間）**: **accept を推薦**。実地試行で実際に発生した提示誤りで、
  再現条件（gitignore されたレジストリ）は env-init の既定配置そのものであり全展開先で起こりうる。
  既存要件との矛盾なし（ENV-FR-011/012 の安全原則をむしろ強化）。ガードレール抵触なし。
  契約に触れない手順の明確化のため**軽量レーン適用可**（Design Gate 不要）。
