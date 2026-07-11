# env-register テストケース

対応要件: ENV-FR-006(S1/S2/S3/S5) / ENV-FR-004(S2) / ENV-CON-003
（.spec/specs/bitz-env/test-spec.md B節のシナリオ ENVFR006-S1〜S3, S5, ENVFR004-S2 に対応）

## TC-01: 契約準拠アダプタの登録（ENVFR006-S1）
- **種別**: 正常系
- **入力プロンプト**: bitz-collab-example という協調アダプタを入れたので登録して
- **前提条件**: sandbox に模擬アダプタ（plugin.json の metadata.collab に agent と
  skills: {delegate: ex-delegate, review: ex-review} を宣言）と、マーカー区間を含む CLAUDE.md がある
- **アサーション**:
  - [ ] 能力宣言（collab.agent と delegate 相当スキル）の契約チェックを行っている
  - [ ] ユーザー確認のうえ .claude/bitz-env.local.md に登録している
  - [ ] レジストリに役割→実スキル名の routes（delegate: ex-delegate 等）が記録されている
  - [ ] CLAUDE.md のマーカー区間内の協調アダプタ行だけが更新され、区間外は不変
  - [ ] 書き出し先はすべて sandbox 配下（ENVCON003-A1）
- **期待成果物**: sandbox/.claude/bitz-env.local.md（routes 付きエントリ）、更新された sandbox/CLAUDE.md

## TC-02: 非準拠アダプタの拒否（ENVFR006-S2）
- **種別**: エッジケース
- **入力プロンプト**: この my-tool プラグインも委譲先として登録して
- **前提条件**: sandbox の模擬プラグイン my-tool は metadata.collab を持たず delegate 相当スキルも無い
- **アサーション**:
  - [ ] 非準拠の理由（能力宣言なし・delegate 役割なし）を具体的に報告している
  - [ ] レジストリに登録していない
- **期待成果物**: なし（レジストリ変更なし）

## TC-03: スキル名の衝突解決（ENVFR006-S3）
- **種別**: エッジケース
- **入力プロンプト**: second-adapter も登録して
- **前提条件**: レジストリに既登録アダプタ（routes.delegate: ex-delegate, priority: 1）があり、
  新規 second-adapter の宣言も実スキル名 ex-delegate を使っている
- **アサーション**:
  - [ ] 衝突（役割・スキル名・双方のアダプタ名）をユーザーに報告している
  - [ ] 後発側にアダプタ名プレフィックスの名前空間化を適用して登録している
  - [ ] priority で優先順を明示し、既登録アダプタの priority を変更していない
- **期待成果物**: 衝突解決済みの sandbox/.claude/bitz-env.local.md

## TC-04: マーカー区間なしの CLAUDE.md（ENVFR004-S2）
- **種別**: エッジケース
- **入力プロンプト**: アダプタを登録して委譲マトリクスも更新して
- **前提条件**: sandbox の CLAUDE.md にマーカー区間が無い（env-init 未実行相当）。準拠アダプタあり
- **アサーション**:
  - [ ] env-init の実行を先に案内している
  - [ ] CLAUDE.md にマーカー区間を勝手に新設していない（CLAUDE.md が不変）
- **期待成果物**: なし（CLAUDE.md 不変）

## TC-05: アンインストール済みアダプタの棚卸し（ENVFR006-S5）
- **種別**: エッジケース
- **入力プロンプト**: レジストリを最新の状態に更新して
- **前提条件**: レジストリに登録済みだが実体（プラグイン）が存在しないアダプタが1件ある
- **アサーション**:
  - [ ] 実体が無いことを検出して報告している
  - [ ] ユーザー確認のうえでエントリを削除している（確認前に消していない）
- **期待成果物**: 棚卸し後の sandbox/.claude/bitz-env.local.md

## TC-06: 発動判定
- **種別**: 発動判定
- **入力プロンプト**: (a) gemini 連携のプラグインを入れたから委譲先に追加して (b) このプラグインの marketplace.json に登録して
- **前提条件**: description のみで判定（本文は読まない）
- **アサーション**:
  - [ ] (a) は「このスキルを使う」と判定する
  - [ ] (b) はリポジトリのプラグイン登録（add-plugin の管轄）として「使わない」と判定する
- **期待成果物**: なし
