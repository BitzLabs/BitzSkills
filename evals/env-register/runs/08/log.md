# run 08 — TC-03（スキル名の衝突解決）

- ケースID: TC-03
- モード: スキルあり（env-register SKILL.md を読了して遂行）
- 実行日時: 2026-07-12

## 手順の記録

1. 入力プロンプト「second-adapter も登録して」を受領。
2. `plugins/second-adapter/plugin.json` を確認。`metadata.collab.agent: second-adapter-agent`、
   `metadata.collab.skills.delegate: ex-delegate` を宣言しており、契約準拠（collab.agent あり、
   delegate 役割スキルあり）と判定。
3. `.claude/bitz-env.local.md` を確認。既登録の `first-adapter`（priority: 1,
   routes.delegate: ex-delegate）がある。
4. SKILL.md「#### 名前衝突の検出と解決」に従い、new 側 second-adapter の
   routes.delegate（`ex-delegate`）が既登録 first-adapter の routes.delegate（`ex-delegate`）と
   重複していることを検出した。
5. 衝突内容（役割: delegate、スキル名: ex-delegate、双方のアダプタ名: first-adapter / second-adapter）を
   ユーザーに報告（シミュレート）: 「second-adapter の delegate 役割の実スキル ex-delegate が、
   既登録の first-adapter と重複しています。後発の second-adapter 側に名前空間化を適用し、
   `second-adapter-delegate` として登録します。よろしいですか」→ ユーザーは承認した（シミュレート）。
6. 後発アダプタ（second-adapter）の該当ルートに、SKILL.md の例（`<adapter名>-<role>`）に従い
   `second-adapter-delegate` の名前空間化を適用。priority は既登録 first-adapter（1）より低い
   優先度として `2` を設定。**first-adapter の priority: 1 は変更していない**。
7. `.claude/bitz-env.local.md` に second-adapter セクションを追記。
8. SKILL.md「3. 委譲マトリクスの更新」に従い、CLAUDE.md のマーカー区間内「協調アダプタ」行を
   レジストリ全体（first-adapter + second-adapter）の routes から再生成した。区間外・他の行には
   触れていない。
9. 報告（シミュレート）: 「second-adapter を登録しました（priority: 2、
   delegate: second-adapter-delegate として名前空間化）。first-adapter の設定（priority: 1）は
   変更していません。CLAUDE.md の協調アダプタ行を更新しました」。

## アサーション結果

- [x] ✅ 衝突（役割・スキル名・双方のアダプタ名）をユーザーに報告している
      証拠: 上記5のシミュレート報告（delegate 役割・ex-delegate・first-adapter/second-adapter を明示）
- [x] ✅ 後発側にアダプタ名プレフィックスの名前空間化を適用して登録している
      証拠: `sandbox/.claude/bitz-env.local.md` の second-adapter エントリ
      `routes.delegate: second-adapter-delegate`（SKILL.md の命名例 `<adapter>-<role>` に準拠）
- [x] ✅ priority で優先順を明示し、既登録アダプタの priority を変更していない
      証拠: `sandbox/.claude/bitz-env.local.md` で first-adapter は `priority: 1` のまま、
      second-adapter は `priority: 2` として追記（`diff original/.claude sandbox/.claude` で確認）

## その他確認

- CLAUDE.md の変更はマーカー区間内（5〜35行目）の「協調アダプタ」行1箇所のみ
  （`diff -u 08/original/CLAUDE.md 08/sandbox/CLAUDE.md` で該当行番号26のみの差分を確認済み）。
- 書き出し先はすべて sandbox 配下（`.claude/bitz-env.local.md`, `CLAUDE.md`）。

## 気づき

- SKILL.md の名前空間化の命名規則の例は「`bitz-collab-example-delegate`」＝
  `<アダプタ名>-<役割名>` の形式で、実スキル名（`ex-delegate`）とは無関係に
  「アダプタ名+役割名」で命名する読み方をした。だが実スキル名を活かした
  `<アダプタ名>-<実スキル名>`（例: `second-adapter-ex-delegate`）という読み方も文面上は排除できず、
  曖昧さが残る。SKILL.md 側で命名規則を厳密化（役割名ベースか実スキル名ベースか）すると
  実装のブレを防げる。
- ベースライン（run03）は衝突検知の手順自体を持たず、同一スキル名で重複登録してしまっていた。
  スキルにより衝突検知・報告・名前空間化・priority 明示のすべてが機械的に遂行できることを確認した。
