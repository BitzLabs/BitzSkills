---
implements: FLW-CON-002
depends_on: [FLW-TSK-059]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-016.md, tests/test_m2_spec_consistency.py, plugins/bitz-flow/.spec/tasks/FLW-TSK-060.md
status: done
---

### guard identityとworktree CASを確定

- **作業内容**: SI-FLW-048の裁定に従い、実在targetをdev+ino、不在pathを最寄り実在祖先identity＋相対pathへ収束させ、content CASをGit porcelain v2出力digestへ委譲する。
- **検証**: path非依存key、祖先遡り、instance分離、porcelain v2・untracked・racily-clean契約を機械検証する。
