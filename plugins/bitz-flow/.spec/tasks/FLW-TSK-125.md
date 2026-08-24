---
implements: FLW-NFR-014
depends_on: [FLW-TSK-124]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_platform.py,tests/test_flow_m2_probe_evidence.py,tests/test_flow_m2_platform_probe.py,plugins/bitz-flow/.spec/design/FLW-DSN-017.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
---

### symlinkとmount単位のcase/fs種別をprobeで実証する

`FLW-REV-028:GP-006`／`GP-008`（いずれもP1）。セカンドオピニオン（codex／agy）の指摘を
実測で確認したもの。**probeが検証していない性質を主張している**点で共通する。

- **実測した欠陥**:
  - `GP-006`: probeは`Path.resolve()`／`os.stat()`／`os.path.isdir()`でsymlinkを追跡する
    一方、`non_follow_walk`は`O_NOFOLLOW`等の**属性存在だけ**でTrueにする。
    symlink経由の0700ディレクトリが`SUPPORTED`／`non_follow_walk=True`を返すことを実測した。
    §1.2は「非symlink/reparse-pointのlocal filesystem namespace」を信頼すると規定する。
  - `GP-008`: `_case_semantics`は**絶対path全体**をswapcaseして存在確認するため、
    mount単位のcase semanticsを測れない。誤って`sensitive`と判定すると`collision_key`が
    case aliasを畳めず、同一資源への競合が直列化されない。
    `_linux_filesystem_type`は`/proc/self/mountinfo`で`st_dev`が一致する**最初の**
    エントリを返すため、bind mountや重ねマウントで親マウントの種別を返す。
- **作業内容**:
  - `non_follow_walk`を**実証**へ変える。root からtargetまでcomponent単位に`lstat`し、
    経路上にsymlinkがあれば False とする。API可用性の検査は維持する。
  - `_case_semantics`をmount局所の判定へ変える。**対象entry名だけ**をswapcaseして
    同一parent内で引き、存在した場合は`(st_dev, st_ino)`一致で同一entryか確認する。
    判定材料が無い場合はNoneを返し不支持へ閉じる（推測しない）。
  - `_linux_filesystem_type`をmount pointの**最長一致**へ変える。mountinfoの
    8進escape（`\040`等）を解く。
- **完了条件**:
  - symlink経由のrootが`non-follow-walk-unavailable`で不支持になること（実測）。
  - 同一entryを指さない同名別entryを`insensitive`と誤判定しないこと。
  - bind mountで最下層のfilesystem種別を返すこと。
  - 判定不能を`supported`へ格上げしないこと。
- **見積り**: 実装PR 1本・1 session。
- **実行判定**: probeはread-onlyを維持する（対象filesystemへ書き込まない）。
