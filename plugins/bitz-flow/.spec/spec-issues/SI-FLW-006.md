---
id: SI-FLW-006
raised_by: FLW-REV-002 P0およびシステムエンジニアリングレビュー（2026-07-29）
target: bitz-flow v1 verified要件からv2後継契約へのsupersede・切替管理
proposed_change_type: modify
status: open
---
- **目的**: bitz-flow v2の破壊的再設計に際し、現行active/verifiedのv1契約を先に壊さず、
  v2後継契約の検証・Promotion Gate完了後に安全にsupersedeする切替手順を確立する。
  FLW-REV-002は、FLW-FR-001/002とFLW-DSN-001が旧`flow-pr`/`flow-worktree`/旧scriptを正とする一方、
  v2 draftが単一dispatcherと旧入口削除を規定し、適用時点がないことをP0とした。
- **提案する修正**:
  1. v1-current、v2-proposed、v2-approved、v2-currentの規範setと適用期間を定義する
  2. v2 Promotion Gate完了まではFLW-FR-001/002と現行skills/scriptsを現在の正として維持する
  3. Design Gate後にv1の安全不変条件を引き継ぐv2後継FR/CONを新IDで起票し、
     `supersedes`候補を明記する。旧要件のEARS本文は変更しない
  4. v2後継要件がverified/promotedとなり、bitz-sdd等の利用側参照更新とmigration検証が
     greenになった後だけ、人間裁定で旧要件をdeprecated化して`superseded_by`を記録する
  5. 旧skill名・旧script名の参照をdoctor/pre-migration検査で列挙し、旧→新action対応表、
     major version、更新順、旧版復帰手順をmigration noteへ残す
  6. pointer skillや互換shimは恒久経路として残さず、切替前はv1、切替後はv2へ正を一意化する
  7. SI-FLW-002〜005はopenのまま自動採用せず、各Issueのaccept/reject裁定とv2への継承先を別途記録する
- **対象ファイル**: `plugins/bitz-flow/.spec/requirements/FLW-FR-001.md`・`FLW-FR-002.md`
  （将来の人間裁定時のみstatus/superseded_by）、`.spec/design/FLW-DSN-001.md`、
  v2移行設計候補`FLW-DSN-011.md`、v2後継要件・検証仕様、現行/v2 skills/scripts、
  3manifest、README/migration note。bitz-sdd側の参照更新は本Issueから直接変更せず、
  必要時にルート経由の別Issueへ委託する。
- **確認観点**:
  - v2完成前にv1の正規フローが消えないこと
  - 同一時点で安定版入口がv1/v2の2つにならないこと
  - 旧verified要件を直接改訂せず、「緑を赤にし得る」変更を新IDへ継承すること
  - 後継テストgreen前に旧テストを削除せずtombstone手順へ従うこと
  - v2失敗時にmanifest/version固定でv1へ戻せること
  - repo外worktree、merge、discard、release publishの承認境界を移行で弱めないこと
- **影響推定・ロールバック**:
  - `FLW-FR-001`: ルート`tests/test_branch_preflight.py`、bitz-flowのtest-spec + 3task、
    bitz-sddのtrace test-specの計6件
  - `FLW-FR-002`: bitz-flow `FLW-TSK-004`、bitz-sddのtrace test-specの計2件
  - 合計8件が機械列挙された。要件supersedeと公開CLI/skill削除を伴うため軽量レーン不可、
    通常フロー + Design Gate + Promotion Gateが必要
  - 切替前はv2 draftをrevertしてv1-currentを維持する。切替後は直前v1 plugin versionへ固定し、
    v2が作成したGit/GitHub成果物を自動削除しない
- **依存**: FLW-REV-002、v2 Design Gate、FLW-FR-001/002、SI-FLW-002〜005の人間裁定。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | 現行要件とv2は意味的に競合。後継IDによるsupersedeが必要 |
| ガードレール抵触 | なし。人間専用status遷移と安全境界を維持する |
| 影響範囲 | bitz-flow契約・skills/scripts・manifestと下流参照。機械列挙は8件 |
| 軽量レーン適否 | 不可。破壊的公開契約変更と要件supersedeを伴う |

**推薦: accept**。v1を即時廃止せず、v2を検証してから一意に切り替えるための必須移行契約である。
