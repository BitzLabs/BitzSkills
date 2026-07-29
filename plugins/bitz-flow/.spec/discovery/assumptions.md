---
id: FLW-DSC-006
title: "bitz-flow v2 仮説検証ゲート"
status: draft
version: 2.0
updated: 2026-07-29
owner: hide
---

# bitz-flow v2 仮説検証ゲート

## 仮説表

| ID | 分類 | 仮説 | 崩壊影響 | 状態 | テストと事前閾値 |
|---|---|---|---|---|---|
| H-F1 | Feasibility | 1つのdispatcherへ集約すると3プラットフォームで同じCLI契約を使える | クリティカル | 未検証 | M0でplatform×task各10trial。各SFCR 90%またはparity 100%未満ならM1へ進まない |
| H-D1 | Desirability | 生コマンド例を通常経路から除くとscript実行率が上がる | クリティカル | 未検証 | skillあり/なし比較。SFCR 90%未満、または改善幅20pt未満ならskill構成を再検討 |
| H-F2 | Feasibility | Python標準ライブラリで必要なGit / gh出力を安全にparseできる | 高 | 部分支持 | status/diff/log/Issue/PR/releaseのgolden fixture。必須field保持100%未満なら対象操作を縮小 |
| H-F3 | Feasibility | byte上限と段階取得でtokenを減らしつつ判断を保てる | 高 | 未検証 | 必須field保持100%かつ対象操作のmedian byte削減が目標未達ならschemaを再設計 |
| H-D2 | Desirability | 単独作業でもworktree-firstの利点が作成コストを上回る | 高 | 部分支持 | 本リポジトリで連続10作業を運用。例外率30%以上なら単独作業の既定を再検討 |
| H-V1 | Viability | 2スキル + 1dispatcherは現行4スキルより保守しやすい | 高 | 未検証 | workflow追加時の変更ファイル数、重複関数、skill参照逸脱を比較。重複が増えるなら分割を再検討 |
| H-F4 | Feasibility | `.spec`とGitHub IssueをSSOT競合なしに双方向接続できる | クリティカル | 部分支持 | accepted spec-issue→parent Issue、task→sub-issueをfixture化。重複・リンク切れ0件 |
| H-F5 | Feasibility | PR / releaseを段階化すれば中断後に副作用なく再開できる | クリティカル | 部分支持 | 各段階へ故障注入。Issue/PR/release重複0件、stale head merge 0件 |
| H-V2 | Viability | GitHubのIssue type / sub-issue / dependency / Projects差異をcapability検出で吸収できる | 中 | 部分支持 | 高水準ghとallowlist固定endpointのfixture。権限不足を機能欠如と誤判定したらM3を停止 |

## 崩壊クリティカル仮説

1. **H-F1 / H-D1**: 単一dispatcherがモデル横断の実行率を改善しなければ、v2の主目的を満たさない。
2. **H-F4**: SDD接続が二重SSOTを作るなら、GitHub連携を分離しなければならない。
3. **H-F5**: 外部状態変更を冪等に再開できなければ、PR / release のapply機能は出荷しない。

すべてテストと kill / pivot 条件を定義済みであり、未検証であること自体は Discovery Gate の
No-Go 条件に当たらない。ただし実装 milestone ごとに閾値を満たさなければ後続を止める。

## Discovery Gate 提示

- **裁定**: Go（条件付き）
- **条件**:
  1. 公開契約の最初の成果物をM0のresult schema、終了コード、read-only 3操作にする。
  2. M0でcross-model evalを行い、script実行率が改善しなければM1以降へ進まない。
  3. MCP、Rust化、プラットフォーム固有hook、透過proxyは将来候補を含め実装対象外とする。
  4. `.spec` status をGitHubから変更しない。
  5. destructive discard とrelease publishは明示的な人間承認を残す。
- **裁定者**: hide（人間）
- **裁定日**: 2026-07-29
- **設計移行**: 許可

上記条件を設計の制約として維持し、基本設計・詳細設計へ進む。
