# Rules: Success Metrics (define-success-metrics)

`/product:define-success-metrics`のためのリファレンスである。vision (ビジョン) の「勝利の定義」を、下流の優先順位付け（RICEのImpact、MoSCoW、positioning (ポジショニング)）のアンカーとなる単一の測定可能な形に変換する。

## North Star Metric (NSM)

プロダクトが顧客に提供するcore value (コアバリュー) を捉える単一の指標である。以下の条件を満たさなければならない:

1. **Lead revenue, not lag it.** NSMは*leading indicator (先行指標)*である — それを改善することで、将来の収益やretention (リテンション) が確実に引き上げられるべきである。収益自体はlagging output (遅行的な結果) であり、決してNSMにはならない。
2. **Express customer-received value**, 顧客の言葉で測定される（例：「ログイン数」ではなく「ワークフローを完了した週間のアクティブなチーム数」）。
3. **Be movable by the team** プロダクトの作業を通じてチームが動かせるものであり、定期的なcadence (ケイデンス) で追跡可能であること。

Anti-patterns (アンチパターン): vanity metrics (虚栄の指標)（単なるサインアップ数、ページビュー数）、純粋な収益、またはチームが影響を与えられないあらゆるもの。

## Input metrics (インプット指標) (3–5)

NSMは、チームが直接行動を起こすことができる少数のinput metricsのセットによって駆動される。一般的な分解: **breadth (広さ) × depth (深さ) × frequency (頻度) × efficiency (効率)**（例：アクティブユーザー数 × ユーザーあたりのアクション数 × 使用頻度 × 成功率）。各input metricは、プロダクトの作業で引くことができるレバーにマッピングされるべきである。

## Mapping frameworks (use one as a lens)

- **AARRR (Pirate Metrics)** — Acquisition (獲得) → Activation (活性化) → Retention (継続) → Referral (紹介) → Revenue (収益)。NSMとinput metricsをこのファネルに配置し、戦略がどの段階に賭けているかを明らかにすること。
- **HEART (Google)** — Happiness (幸福度)、Engagement (エンゲージメント)、Adoption (採用)、Retention (継続)、Task success (タスクの成功)。選択した各次元について、Goals (目標) → Signals (シグナル) → Metrics (指標) を定義すること。UX（User Experience）重視のプロダクトに有用である。

プロダクトに適合するフレームワークを選択すること。両方を機械的に埋めないこと。

## Targets & guardrails (目標とガードレール)

各指標について以下を記録すること: **definition (定義)**、**measurement method/source (測定方法/ソース)**、**target value (目標値)**、および **guardrail (ガードレール)**（NSMを最適化する際に悪化させてはならない対抗指標 — 例：retentionやサポート負荷を犠牲にしてengagementを成長させてはならない）。信頼できるソースのない目標は、Open Questions (未解決の質問) において `TBD` とマークすること — 決してでっち上げないこと。

## ID convention (IDの規則)

North Starには `NSM-001` が付与される。各input metricとguardrailには、それが寄与する `VIS-` 要素を参照するUpstream (上流) カラムとともに、独自の `NSM-xxx` が付与される。すべての `NSM-` ノードを `work/traceability.json` に追記すること。下流のスキル（`define-scope`、`design-revenue`、`define-features`、`design-positioning`）は、Impactを指標に結びつける際にこれらのIDを引用する。

## Sources (情報源)

- Sean Ellis / Amplitude — "North Star Metric" framework
- Dave McClure — "AARRR: Startup Metrics for Pirates"
- Google — "HEART framework" (Rodden, Hutchinson, Fu)
