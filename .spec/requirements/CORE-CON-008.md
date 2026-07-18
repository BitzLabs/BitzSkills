---
id: CORE-CON-008
version: 1.0
status: verified
domain: governance
priority: medium
origin: SI-CORE-006
verification_method: manual-check
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-CON-008 共通ライフサイクルスキル標準 init/doctor/update/uninstall

- **説明**: 全プラグインに共通するライフサイクル操作は標準スキル名
  `<plugin名>:init` / `doctor` / `update` / `uninstall` として制定する。
  最小契約は init=初期設定と依存確認、doctor=環境診断（読み取り専用）、
  update=バージョン更新と依存再確認、uninstall=痕跡を残さない撤去とする。
  この4操作に該当しない独自スキルは従来の命名規則を維持してよい。
  先行実装の bitz-env は `env-destroy` を `env-uninstall` へ改名し本標準に合わせる
  （2026-07-13 人間裁定。改名に伴う bitz-env 側の参照・ドキュメント更新は本要件の実装で
  bitz-env ワークスペースへ委任する）。
- **受入基準 (EARS)**:
  - WHEN プラグインが init/doctor/update/uninstall 相当のライフサイクル操作を提供する THEN その操作は `<plugin名>:init` / `doctor` / `update` / `uninstall` の標準名で命名されていること SHALL
  - THE plugin-creator は各標準スキルの最小契約（責務・入出力・雛形）を reference として提供すること SHALL
  - WHEN bitz-env の `env-destroy` を本標準に合わせて改名する THEN 改名後のスキル名は `env-uninstall` であり、旧名への参照が残っていないこと SHALL
- **検証手段**: plugin-creator の reference 追加を目視確認 + release_check / spec_inspect PASS
  （規定のみで既存スキルの動作変更ゼロ）。bitz-env 側の改名は
  `grep -rn "env-destroy" plugins/bitz-env` がゼロ件であることで確認する。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票。SI-CORE-006 の内容を反映）
  - 1.0 (2026-07-18) 人間裁定により approved 化（チャット指示）
  - 1.0 (2026-07-18) implementing 遷移（CORE-TSK-014・ENV-TSK-013 投入）
  - 1.0 (2026-07-18) verified 遷移（CORE-TSK-014・ENV-TSK-013 done、release_check PASS、
    spec_inspect --workspace . plugins/* 全6ワークスペース PASS、pytest 158 green）
