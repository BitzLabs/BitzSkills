---
implements: FLW-NFR-014
depends_on: [FLW-TSK-106]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_platform.py,plugins/bitz-flow/skills/flow-core/references/worktree-v2-platform-support.json,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/platform-evidence-v2.schema.json,tests/test_flow_m2_platform_adapter.py,tests/test_flow_m2_contract_v2.py,evals/flow-core/m2-eval/qualification-2026-08-23-flw-tsk-111.json,evals/flow-core/m2-eval/active-local-confirmation.json,evals/flow-core/m2-eval/raw/claude.log,evals/flow-core/m2-eval/raw/codex.log,evals/flow-core/m2-eval/raw/antigravity.log,plugins/bitz-flow/skills/flow-core/SKILL.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json,.claude-plugin/marketplace.json
status: done
---

### local filesystem platform adapterを固定する

- **作業内容**: Linux、macOS、Windowsのowner、非追随walk、native component、resource identity、
  case semantics、OS lock、file/directory durability、child監督のclosed evidenceを返す。
  - コード同梱static allowlistとsemantic self-testの両方でsupportを判定する。
  - network/unknown filesystemをsupportedへ格上げしない。
  - support profile署名、外部profile更新、policy result選択を実装しない。
- **完了条件**: 3platform local fixtureが同じlogical evidenceを返し、case collision、symlink/reparse point、
  owner/lock/durability不明、network filesystemを安全側へ停止する。
- **見積り**: 単独の実装PR 2とし、3 sessionを上限とする。
- **実行判定**: pure contract後に開始し、platform差異を推測で補完しない。
  実装PR 2のrelease integration ownerとしてplugin/skillをpatch bumpする。
