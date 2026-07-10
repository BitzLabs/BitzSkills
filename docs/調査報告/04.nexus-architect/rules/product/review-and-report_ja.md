# Rules: Review & Report (review, report)

Phase Rのためのリファレンスである。`review`は蓄積されたアーティファクトに対して4つのレンズを適用し、`report`はすべてを1つのHTML成果物に統合し、検証ステータスを冒頭に配置する。

## review — four lenses (apply in order)

1. **Consistency** — 欠落/破損したID参照、ドキュメント間の矛盾、用語のドリフト（同じ概念が異なる名前で呼ばれること）。ファイル全体で`VIS-`/`NSM-`/`SCP-`/`FEAT-`/`ENT-`/`CTX-`/`API-`/`NFR-`の使用状況をクロスチェックする。
2. **Traceability** — `work/traceability.json`はドキュメントと一致しているか？すべてのノードは`VIS-`/`NSM-`ルートへの有効なUpstreamチェーンを持っている必要がある。孤立したノード（Upstreamなし）やダングリング参照（存在しないUpstream ID）にフラグを立てる。
3. **Extensibility** — ドメインの境界とAPIの階層化は、将来の可能性のある機能を吸収できるか？現在の画面の周囲に引かれた境界、UIに公開されたシステムAPI、低い再利用性（1 Process → 1 Experience）、および過剰設計された汎用サブドメイン（Generic subdomains）にフラグを立てる。
4. **Strategy (product lens)** — ビジョンは選択されたスコープと一貫しているか？ユニットエコノミクスは健全か（LTV:CAC、回収期間）？差別化は持続可能か（Delighterは劣化する）？表面的な問題ではなく、目標と作業の不一致を表面化させる。

各発見事項について、**lens、severity (blocker / major / minor)、location (file + ID)、および具体的な修正案**を記録する。出力は、散文的な賞賛ではなく、実行可能なリストである。

## report — consolidated HTML

すべての`reports/**/*.md`を`report/full-report.html`にマージする（Mermaid図をインラインでレンダリングする）。

**必須要件: 先頭（デザインコンテンツの前）に「Key Assumptions & Validation Status」を配置すること。**これは以下を集約する:

- `work/pipeline-progress.json` → `gates.validate-assumptions`からのゲート判定（go / no-go）
- テストされていない / オープンな前提条件（パスしたテストがない`ASM-`）と、それらのキル/ピボットの閾値
- アーティファクト全体のすべての`TBD`および`TBD-assumption`
- `work/context.md`で収集されたOpen Questions

これにより、何が決定事項であり、何が依然として賭けであるかについて、読者を誠実に保つ。これに続いて、パイプライン順にフェーズごとのセクションを設け、それぞれをソースファイルにリンクさせる。自己完結型（インラインCSS）を維持し、Mermaidランタイム以外の外部アセットを使用しないこと。

## Discipline

- **「合格」を捏造してはならない。**アーティファクトが不足している場合や、判定が`no-go`である場合は、レポートで目立つようにその旨を記載する。
- `review`は**パイプラインの途中で再実行可能**である — 存在するものであれば何でも機能する（最小限: `map-journey`）。

## Sources

- Google SRE / DDD context-mapping (extensibility lens)
- Amazon Working Backwards — assumptions-first framing (report header)
