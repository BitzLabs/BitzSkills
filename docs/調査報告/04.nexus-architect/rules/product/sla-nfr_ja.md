# Rules: SLA & Non-Functional Requirements (design-sla, define-nfr)

quality layer (品質レイヤー) のためのリファレンスである。`design-sla`はcustomer expectations (顧客の期待) からservice-level targets (サービスレベル目標) を設定する。`define-nfr`はそれらの目標を測定可能なnon-functional requirements (非機能要件) へと変換する。すべてのNFRはSLOにtrace back (遡及) しなければならない。

## SLI / SLO / SLA (Google SRE)

- **SLI** (Indicator) — service health (サービスの健全性) の測定されたシグナル（例：リクエストの成功率、p99のlatency (レイテンシ)、freshness (鮮度)）。*何を*、そして*どのように*測定するかを定義すること。
- **SLO** (Objective) — window (ウィンドウ) 全体にわたるSLIの内部目標（例：30日間で99.9%の成功）。チームはSLOに対して運用を行う。
- **SLA** (Agreement) — consequences (結果・ペナルティ) を伴う、外部に対して約束されたレベル。**SLO = SLA − buffer (バッファ)**: 常に外部への約束よりも内部の目標を厳しく設定すること。

順序: SLIを導出する → （positioning/benefitからの）**customer expectation**に合致するSLOを設定する → 安全のためのbufferを設けた上でSLAを明記する。service criticality (サービスの重要度)（critical / standard / best-effort）によってTier (ティア) 分けを行うこと。

## Error budget (エラーバジェット)

`error budget = 1 − SLO`（例：99.9% → 0.1%の許容されるunavailability (ダウンタイム)）。error budgetはリスクと速度のトレードオフを支配する: 予算が残っているうちはリリースに費やし、枯渇した場合はリスクを伴う変更を凍結すること。
各クリティカルなサービスに対して、予算とポリシーを明記すること。

## NFR categories (define-nfr)

それぞれについて、数値（または`TBD`）と**その導出元となるSLO**を提示すること:

- **Availability** — windowあたりの稼働率（%）（availability SLOから）
- **Latency** — key operation (主要な操作) ごとのp95 / p99の応答時間
- **Throughput** — 単位時間あたりの持続的/ピーク時のリクエストまたはジョブ
- **Error rate** — 許容される最大失敗リクエスト率
- **Durability** — data-loss tolerance (データ損失の許容度)（例：11 nines（イレブンナイン））
- **RPO** (Recovery Point Objective) — max acceptable data loss window (許容される最大のデータ損失ウィンドウ)
- **RTO** (Recovery Time Objective) — max acceptable downtime to recover (復旧までに許容される最大のダウンタイム)
- (必要に応じて) scalability (スケーラビリティ)、security (セキュリティ)、compliance (コンプライアンス)、observability (オブザーバビリティ) の目標

## Discipline (規律)

- **すべてのNFRはSLOにtrace backする**: SLOの根拠がないNFRは疑わしいものである。
- 信頼できる根拠が存在しない場合、**数値は`TBD`としてもよい** — assumption (前提条件) を記録し、でっち上げないこと。
- 切りの良い数字に合わせるのではなく、**customer expectationとcriticality**に合わせて目標を設定すること。

## ID convention & handoff (IDの規則と引き継ぎ)

agreement (合意) レイヤーには`SLA-`/`SLO-`を、requirements (要件) には`NFR-`を使用すること。Upstream (上流) である`FEAT-`/`POS-`/`CTX-`（および`SLO-`→`NFR-`）の参照とともに `work/traceability.json` に追記すること。`NFR-`のセットは、architectのnon-functional inputs (非機能インプット)（design.md §1.3）→ `/architect:define-requirements` へとマッピングされる。

## Sources (情報源)

- Google — "Site Reliability Engineering" (SLI/SLO/SLA, error budgets)
- ISO/IEC 25010 — software product quality characteristics (NFR taxonomy)
