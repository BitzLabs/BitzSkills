---
implements: SDD-FR-164
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-docs/scripts/sdd_sync.py, plugins/bitz-sdd/skills/sdd-docs/SKILL.md, tests/test_sdd_sync.py
status: done
---

### 同期の新旧判定をナノ秒精度へ揃え lock 不参加を明記する

- **作業内容**:
  1. `get_mtime()` の戻り値を `st_mtime`（float 秒）から `st_mtime_ns`（整数ナノ秒）へ変更し、
     不在時の番兵を `0.0` から `0` へ揃える。`format_mtime()` は ns を秒へ割って表示する
     （表示は秒精度のまま）。
  2. `do_pull` / `do_push` / `do_diff` の比較・番兵判定を整数へ揃える。
  3. 回帰テスト4件を追加 — float 秒では消える ns 差で pull / push が同期すること、
     同期直後の mtime が ns 単位で同値で逆方向同期が起きないこと、`diff` が同条件を
     「pullが必要」と判定すること。ns 粒度を持たない FS では `pytest.skip` する。
  4. lock 不参加を設計判断として `sdd-docs/SKILL.md` に明記し、適用範囲（変更 CLI と
     同時実行しない）と残余リスク（lost update）を記す。
- **検証**:
  - `pytest` 全スイート PASS。
  - 修正前スクリプト（`origin/main`）との比較実測: `docs` が `base_ns`、`spec` が
    `base_ns + 1` の状態で pull すると、修正前は `UP-TO-DATE` を表示して**古い本文を残し**、
    修正後は同期される。前提（FS が ns を保持し、float 秒では同値になること）は
    テスト内でアサートした。
- **備考**: mutation lock 参加は追加裁定（2026-07-30）により本タスクの範囲外。共有 Python
  コードの配置が V4 の未裁定論点1（配布単位）であるため、そこで裁定するまで実装しない。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
