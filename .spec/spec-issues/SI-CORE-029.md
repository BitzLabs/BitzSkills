---
id: SI-CORE-029
raised_by: 開発フロー振り返り（2026-07-18 セッション、SI-CORE-007 実装サイクルの実地観察）
target: AGENTS.md コミット・PR 規約（version bump の位置規定が実態と乖離）
proposed_change_type: modify
status: accepted
---
- **目的**: AGENTS.md の「1 PR = 1 関心事」節は「version bump は PR の最終コミットに含める」と
  規定しているが、実態はテスト先行フロー（red コミット → green 実装コミット → status 遷移
  chore コミット）が定着し、bump は実装（green）コミットに同梱される運用が続いている
  （実例: PR #45 / #47 / #52）。規約と実態の乖離を放置すると、規約側が形骸化する。
- **提案する修正**: AGENTS.md の当該規定を実態に合わせて緩和する:
  「version bump は PR 内のコミットに含める（推奨: 実装コミットと同一コミット。
  bump 単独の後付けコミットでもよい）」。bump を PR に含め忘れないことが本質であり、
  位置は問わないことを明確化する。
- **対象ファイル**: `AGENTS.md`（コミット・PR 規約節の1文）。
- **確認観点**: release_check / spec_inspect PASS。CI の pr-title 検査には影響しない
  （コミット位置の規定は機械検査対象外＝ナラティブのみの変更）。
- **影響推定・ロールバック**: 規約文言1文の変更。revert で戻る。
- **依存**: なし。
- **実施**: 2026-07-18 CORE-CON-010 / CORE-TSK-020 として要件化・実装。
  version bump は同一 PR に含め、実装コミット同梱を推奨しつつ位置を固定しない規約へ更新。
