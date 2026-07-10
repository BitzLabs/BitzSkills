# Rules: Assumption Validation (validate-assumptions)

`/product:validate-assumptions`の参照。検証駆動設計（validation-driven design）の中核：もっともらしい戦略を、反証可能な賭けのセットに変換し、それぞれに最も安価なテストと停止ルールを設ける。

## Classify every assumption (desirability / viability / feasibility)

- **Desirability** — 顧客はそれを望んでいるか？（問題は現実であり、上位にランク付けされている。解決策は代替案よりも好まれる）
- **Viability** — それはお金を稼ぐか？（支払う意思、価格、CAC、チャネル、ユニットエコノミクス）
- **Feasibility** — 私たちはそれを構築し、運用できるか？（主要な技術的、データ的、規制上のリスク）

## Rank by collapse impact (Riskiest Assumption Test)

各前提条件について、「もしこれが間違っていたら、戦略のどれくらいが崩壊するか？」と問う。最も危険で、不確実性の最も高い前提条件を**最初に、かつ最も安価に**検証する — MVPの後ではなく、前に。

## Test catalog (cheapest credible test per assumption)

| Test | Validates | Cost |
|------|-----------|------|
| カスタマー / スイッチインタビュー | desirability、Jobs-to-be-Done (ジョブ理論) | low |
| スモークテスト / フェイクドアランディングページ | 需要（サインアップ / クリック率） | low |
| コンシェルジュMVP | desirability + 配信 | medium |
| Wizard-of-Oz | バックエンドを構築せずにdesirabilityを検証 | medium |
| **事前販売 / 関心表明書 (letter of intent)** | **viability — 最も強いシグナル** | medium |
| Van Westendorp PSM (4つの質問：高すぎる / 高い / 安い / 安すぎる) | 許容可能な価格帯 | low |

## Kill / pivot threshold (mandatory per top assumption)

テストを実行する**前**に閾値を設定する。例：「ランディングページのサインアップ率が5%未満の場合、需要の前提条件を却下し、フェーズ1を再検討する。」 事前にコミットされた閾値のないテストは検証ではない。

## Price is an assumption, not arithmetic

`LTV:CAC ≥ 3`はスプレッドシートを検証するものであり、市場を検証するものではない。ビジョン/スコープ/収益から`TBD-assumption`の価格/CAC値を引き出し、計算によってではなく、事前販売やVan Westendorpを用いてそれらを検証する。

## Go / No-Go verdict

- **No-Go** — 崩壊に直結する重要な前提条件が未検証であり、かつ定義されたテスト+閾値が欠如している場合。
- **Go** — それ以外の場合。トラッキングのために、未解決の前提条件をリストアップする。

判定結果と`open_assumptions`を`work/pipeline-progress.json` → `gates`に書き込む。証拠が届くにつれて再実行する — ゲートは再検討されることを意図している。

## ID convention

前提条件 → `ASM-`、アップストリーム列（`VIS-`/`SCP-`/`NSM-`/revenue）を伴う。変更時に`adapt-change`がゲートを再び開くことができるように、すべてのノードを`work/traceability.json`に追加する。

## Sources

- Bland & Osterwalder — "Testing Business Ideas" (Strategyzer)
- Intercom — Riskiest Assumption Test
- Van Westendorp — Price Sensitivity Meter
