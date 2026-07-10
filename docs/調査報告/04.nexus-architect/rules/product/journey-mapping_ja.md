# ルール: Customer Journey Mapping (カスタマージャーニーマッピング) (map-journey)

`/product:map-journey` のリファレンス。各 **プライマリペルソナ** のジャーニーを、ペルソナのジョブとそのままの感情に基づいて、理想化されたマーケティングファネルではなく **ステージ × レイヤー** のグリッドとしてマッピングする。

## ステージ (列)

デフォルトのエンドツーエンドのスパイン（プロダクトに合わせて適応させる）：

Awareness → Consideration → Purchase/Sign-up → Onboarding → Usage → Renewal/Retention → Advocacy

各ペルソナには独自のステージセットがある場合があり、最低でもプライマリペルソナごとに1つのマップを作成する。

## レイヤー (行) — すべてのステージについて

- **Touchpoints / channels (タッチポイント / チャネル)** — インタラクションが発生する場所（ウェブ、アプリ、メール、営業、サポート）
- **Actions** — ジョブを進めるためにペルソナが何をするか
- **Thoughts & emotions** — 可能な限り **そのまま（verbatim）** （引用）で捉え、さらに感情曲線（高/中/低）を描いて落ち込みを視覚化する
- **Pain points** — 摩擦、離脱リスク、満たされていない期待
- **Opportunities** — プロダクトがどのようにペインを取り除くか、またはゲインを増幅できるか

## Moments of Truth (真実の瞬間: MoT)

ジャーニーに沿った決定的な瞬間にフラグを立てる：

- **ZMOT** (Zero) — Touchpoints に到達する前の購入前リサーチ
- **FMOT** (First) — 最初の直接的な遭遇 / 第一印象
- **SMOT** (Second) — 約束を確認する、または破る実際の使用体験
- (Optional) **UMOT** — ユーザーが体験を共有する → Advocacy につながる

MoT において感情曲線が落ち込む場所にマークをつける — これらが最もレバレッジの高い修正ポイントである。

## 規律

- マップが地に足のついたものになるように、すべての Pain/Opportunity を `JOB-`/`PER-` ID に紐付ける。
- 感情をでっち上げない。検証されるまでは想定されるエントリに **[proto]** のマークをつける。
- マッピングの出力は優先順位付けされた **opportunities** のリストであり、見栄えの良い図ではない。

## ID規約

各ジャーニー（ペルソナごと）と注目すべき各 opportunity には `JNY-xxx` ID を付与する。上流の `PER-`/`JOB-` 参照とともに `work/traceability.json` に追記する。Opportunities は `design-positioning`（タッチポイント）、そして後に `define-features` へとつながる。

## 情報源

- Nielsen Norman Group — Journey Mapping 101 (stages × lanes)
- P&G / Google — Moments of Truth (FMOT/SMOT) and ZMOT
