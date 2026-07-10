# ルール: Personas & Jobs-to-be-Done (ペルソナとジョブ理論) (generate-persona)

`/product:generate-persona` のリファレンス。人口統計（デモグラフィック）ではなく、**Jobs-to-be-Done (ジョブ理論)** を中心にペルソナを構築する。AI が生成したペルソナは、実際の証拠が到着した際にリサーチベースのペルソナに昇格されるための **scaffold (足場)**（プロトペルソナ）であり、ユーザーと対話することの代わりにはならない。

## Jobs-to-be-Done (JTBD)

人々はある状況下で進捗を得るためにプロダクトを「雇用（hire）」する。ユーザーの属性ではなく、ジョブを捉える。

- **Job Story format**: *[状況] のとき、[期待する結果] を得ることができるように、[動機] したい。*
- ジョブの3つの次元を網羅する：**functional (機能的)**（タスク）、**emotional (感情的)**（どのように感じたいか）、**social (社会的)**（どのように見られたいか）。
- ジョブはソリューションに依存せず、安定的である。機能はそうではない。ペルソナをジョブに固定することで、プロダクトのピボットを乗り越えられるようにする。

各ジョブストーリーには `JOB-xxx` ID を付与する。

## ペルソナカード

各ペルソナについて、以下を記録する：

- **Name / archetype** および1行の要約（役割であり、決して「全員」ではない）
- **Context & behaviors** — 見栄えだけの人口統計ではなく、関連する状況
- **Jobs (JTBD)** — このペルソナが追求する `JOB-` ID
- **Pains** — ジョブを完了する上での障害、摩擦、リスク
- **Gains** — 望まれる結果と利益
- **Verbatim quote** — ユーザー自身の言葉で（リサーチから、または **[proto / unvalidated]** とマークする）

各ペルソナには `PER-xxx` ID を付与する。

## プロト vs リサーチベース (確信度について正直であること)

- **Proto-persona** — 仮説/デスクリサーチから組み立てられる。検証されていないすべての主張に **[proto]** をマークする。AI は scaffold 作りには優れているが、*感情的な妥当性* には弱い — でっち上げた感情や引用を事実として提示してはならない。
- **Research-based** — インタビュー/データ（`--input`）に裏付けられている。仮説を引用された証拠に置き換えることで、Proto-persona から Research-based へと昇格させる。

**人口統計や引用を決して捏造してはならない。** 不明な点は Open Questions で `TBD` とする。リサーチデータが存在する場合は、生成よりも常にそちらを優先する。

## 優先順位付け

**プライマリペルソナ**（プロダクトが最適化される対象）と、セカンダリ/サーブド/アンチペルソナを特定する。下流の Skill（`map-journey`、`define-features`）は、まずプライマリに焦点を当てる。

## ID規約

ジョブストーリーには `JOB-`、ペルソナカードには `PER-` を使用する。上流の `VIS-`（ターゲットグループ）参照とともに `work/traceability.json` に追記する。

## 情報源

- Clayton Christensen / Tony Ulwick — Jobs-to-be-Done
- Alan Cooper — personas (primary/secondary/served/negative)
- Roman Pichler / Jeff Gothelf — proto-personas
