---
id: SI-CORE-035
raised_by: bitz-sdd:SI-SDD-022/023/024の統合設計
target: CORE-FR-004/005の後継化とbitz-sddへの契約移管
proposed_change_type: deprecate
status: accepted
origin: bitz-sdd（SI-SDD-022/023/024からのエスカレーション）
delegated_to: bitz-sdd:SI-SDD-022,bitz-sdd:SI-SDD-023,bitz-sdd:SI-SDD-024
github_issue: https://github.com/BitzLabs/BitzSkills/issues/100
---
- **目的**: ルートworkspace所有のverified契約 CORE-FR-004（採番付きscaffold）と
  CORE-FR-005（status遷移・人間専用flag）が、bitz-sdd固有workspace設立前のlegacy配置に
  残っている。SI-SDD-022/023/024の設計は両契約のgreenをredにし得るため、sub-workspaceから
  直接改訂せず、ルート裁定を経てbitz-sddの後継要件へ移管する。
- **提案する修正**:
  1. SDD-DSN-005のDesign Gate後、bitz-sddに後継要件をscaffoldし、
     CORE-FR-004/005との`supersedes`/`superseded_by`を双方向に記録する。
  2. CORE-FR-005は「人間性をCLIが構造強制する」という過大な契約を廃し、遷移表、
     明示的対話入力、workspace transaction、local lifecycle task前提へ責務を分割する。
  3. CORE-FR-004は単一worktreeのmax+1を維持しつつ、Plan直列化、atomic no-replace、
     target SHA拘束付きmerge gateへ並行採番契約を移す。
  4. 後継要件・テストがgreenになった段階で、人間裁定により旧2要件をdeprecated化する。
- **対象ファイル**: ルート`.spec/requirements/CORE-FR-004.md`、`CORE-FR-005.md`、
  bitz-sddの`.spec/requirements/`、SDD-DSN-005、関連task/test、STATE。
- **確認観点**:
  - 既存要件との矛盾: 意味的変更でgreenをredにし得るためversion bumpではなくsupersedeする。
  - ガードレール: deprecated化とDesign Gateは人間裁定まで実行しない。
  - 影響: `--impact CORE-FR-004/005`は現時点で各2件（既存task 1、test 1）を列挙した。
  - 軽量レーン: 公開CLI、lifecycle、監査event、`.spec`変更protocolに触れるため不可。
- **影響推定・ロールバック**: ルート契約の履歴は削除せずdeprecatedで保持する。後継releaseを
  revertする場合も旧要件を自動でverifiedへ戻さず、人間再裁定で復帰可否を判断する。
- **依存**: bitz-sdd:SI-SDD-022 / SI-SDD-023 / SI-SDD-024、SDD-DSN-005。
- **予備判定（推薦）**: **accept推薦**。所有workspaceを越えたverified契約変更を
  lifecycleのsub→rootエスカレーション規則に従わせ、旧契約と後継契約の二重稼働を防ぐため。
  本issueは2026-07-27のユーザー裁定でaccepted。
- **実施**: 2026-07-27 SDD-DSN-005を承認し、後継SDD-FR-143/144をverified化。
  旧CORE-FR-004/005の相互リンクとdeprecated遷移は、人間専用の対話操作として分離した。
