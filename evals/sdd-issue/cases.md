# 発動判定テストケース: sdd-issue

sdd-issue の発動判定は sdd-plan と合同で実施した（同一のスキル一覧・同一セッションで
ルーティング全体を検証するため）。ケース定義・実行ログの実体は
`evals/sdd-plan/`（cases.md の T6〜T8、runs/1〜2）を参照。

- 直接関連ケース: T6 / T7（sdd-issue が発動すべき発話）、T8（sdd-core に譲るべき発話）
- 結果: 2回独立実行で全件期待どおり（誤爆・取りこぼしなし）。詳細は evals/sdd-plan/runs/。
