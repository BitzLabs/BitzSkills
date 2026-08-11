# 裁定記録 — M0正式完了と振り返り補強案の起票

- **日付**: 2026-08-11
- **裁定者**: ユーザー
- **依頼根拠**: bitz-sdd V4 / bitz-flow v2の状況とM0長期化原因の確認後、提示した
  「M0正式完了 → qualification gate → platform証跡再利用条件」の提案に対する
  「提案で進めましょう」。
- **対象**: bitz-flow v2 M0出口、`FLW-TSK-012`、M0実装要件、振り返り補強2件

## 判断

1. 第14ラウンドの統合manifestでactiveなPASS結果をM0出口の正とし、M0を正式に閉じる。
2. `FLW-TSK-012`をdone、M0実装要件をverifiedへ進め、bitz-flowを`0.4.0`へbumpする。
3. ROADMAPを第14ラウンドとM1開始前状態へ追随させる。
4. 既存のbitz-sdd V4テーマ13 A〜Eを重複起票せず、次の補強だけを別spec-issueとして起票する。
   - 正式測定前の計測器qualification gate
   - hash拘束したplatform別証跡の合成・再利用条件

## M0出口の根拠

- 統合manifest: `evals/flow-core/m0-eval/run-manifest-3platform-2026-08-11-r14.json`
- active result: `84c6f45324f547723d6a63f40c352c5997b083503c2155e194256e0c584597e6`
- 3 platform × 123 trial、raw log参照369/369、欠落0
- Dispatcher Invocation Rate / SFCR: 3 platformすべて100%
- Cross-model Decision Parity: 100%
- 危険事象: 各0件/63 trial、95%上側限界4.64%
- 正規採点器: PASS、未達0件

## 境界

- 本裁定はM0をverifiedへ進める。v2-currentへの切替やpromoted遷移は行わない。
- M1着手前に`SI-FLW-006` / `SI-FLW-029`とwrite系再現性条件、M1予算を別途裁定する。
- 新しい補強2件はopenで起票し、accept / rejectは別の人間裁定とする。
