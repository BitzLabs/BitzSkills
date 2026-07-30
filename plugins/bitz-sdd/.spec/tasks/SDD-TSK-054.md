---
implements: SDD-FR-165
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/references/parallel-git.md
status: done
---

### 共有作業ツリー節・測定値の出典規律・権限マトリクス行を追記する

- **作業内容**:
  1. 「共有作業ツリー（複数セッションが同一リポジトリを見る場合）」節を追加。
     稼働中作業の把握（`git worktree list`）、既定ブランチのリモート追跡からの明示的な
     ブランチ生成、広いパス指定でステージしない、コミット直前のステージ内容確認の4点を規定。
     単一セッション・単一 worktree では不要であることを冒頭に明記する。
  2. 「測定値は確定した ref から読む」節を追加。`git show <ref>:<path>` 等の利用と、
     測定の出典となる ref の併記を求める。
  3. 権限マトリクスへ「他セッションの作業中ファイル」の読み取り／変更の2行を追加し、
     機械強制（`boundary:` 逸脱検査）が本書の範囲外であることを末尾へ明記する。
- **検証**: manual-check。`parallel-git.md` の目視で受入基準5項を確認。あわせて
  `spec_inspect.py --workspace . plugins/*` と `release_check.py`、pytest 全スイートが PASS。
- **備考**: 提案4（機械強制）は裁定Kにより範囲外。bitz-flow への Git 運用移管後に所有者を裁定する。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
