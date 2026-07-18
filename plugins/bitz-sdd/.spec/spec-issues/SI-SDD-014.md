---
id: SI-SDD-014
raised_by: FLW-FR-001のspec inspect警告振り返り（2026-07-18）
target: monorepoのworkspace外テスト参照を含むトレース集計
proposed_change_type: modify
status: open
---
- **目的**: canonicalな `spec inspect --workspace . plugins/*` では全workspaceを同時に検査するが、
  「テスト/実装からの参照がない要件」の判定は各workspace配下の `tests` / `test` / `src` だけを見る。
  FLW-FR-001はモノレポルートの `tests/test_branch_preflight.py` と `tests/test_worktree_ops.py` から参照され、
  requirementはverified・テストもgreenなのに、bitz-flowのinspection-reportへ未参照警告が残った。
  workspace外に正規配置されたテスト参照をcanonical実行時だけ安全に集約する。
- **提案する修正**:
  1. 複数workspace検査時に全入力rootのtest/src参照をグローバルIDで集約し、所有workspaceの要件へ還流する
  2. 単一workspace検査の既存挙動は維持し、外部テストrootを宣言する設定方式との比較をDesign Gateで行う
  3. reportへ参照元workspaceと相対パスを表示し、偶然の文字列一致・自己参照・生成reportを除外する
  4. root testsがplugin requirementを参照するfixture、同名でないID、幽霊参照、単一実行の回帰テストを追加する
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py`、
  `tests/test_spec_inspect.py`、sdd-coreのartifact/traceability説明、CORE-FR-002 / CORE-FR-016の改訂または
  bitz-sdd後継要件、bitz-sddマニフェスト。
- **確認観点**: canonicalコマンドでFLW-FR-001の警告が解消されること。workspaceを跨いだ幽霊IDを
  正当化しないこと。単一workspace利用者の結果を変えないこと。走査量増加が実用時間内であること。
- **影響推定・ロールバック**: `--impact CORE-FR-002` はルートタスク1件。report判定意味論と
  multi-workspace契約に触れるため通常SDDフロー + Design Gateを推奨。グローバル集約をrevertすれば
  現行のworkspaceローカル判定へ戻る。
- **依存**: CORE-FR-002（spec_inspect）、CORE-FR-016 / SI-CORE-023（monorepo canonical実行）。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。canonical複数workspace実行時の参照解決を完全にする |
| ガードレール抵触 | なし。読み取り専用検査 |
| 影響範囲 | spec_inspectの参照集計・report・回帰テスト |
| 軽量レーン適否 | 不適。検査結果の意味論を変更する |

**推薦: accept**。verified要件に誤解を招く警告が残り、トレース率指標の信頼性を下げるため。
