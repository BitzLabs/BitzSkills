# ルール: Naming Frameworks (ネーミングフレームワーク) (name-product)

`/product:name-product` のリファレンス。ハウススタイルは **acronym (頭字語)** の名前である：短く、ラテン文字の名前で、**すべての文字が英単語の頭文字**になっており、その名前を展開するとプロダクトの価値を述べるフレーズになる。

## 厳格な制約

名前 `L1 L2 … Ln` について、英単語 `W1 W2 … Wn` が存在し、`initial(Wi) == Li` となり、`W1 … Wn` がプロダクトを説明する一貫したフレーズとして読めなければならない。許容される2つの読み方：

- **Acronym** — 名前が単語として発音される（NEXUS、SCALAR、RADAR）。推奨：最もブランド化しやすい。
- **Initialism** — 名前が文字ごとに発音される（SDK、ATM）。短く適切な場合に許可される。

「backronym (バクロニム)」は同じ対象を逆向きに構築したものである — 先に文字列を選び、それに単語を合わせる。ここでは両方の方向性が正当である。成果物はプロセスではなく*結果*で判断される。

## 2つの構築の方向性 — これらを反復する

1. **Forward (頭文字優先)**: プロダクトの価値を表す単語を選ぶ → その頭文字を取る → それらを発音可能な文字列に並べ替えてみる。最初のアプローチで良い単語が得られることは稀である。シード（種）として使用する。
2. **Backward (文字列優先 / backronym)**: ドメインの響きに合う発音可能な文字列を選び、そこから word bank (単語バンク) の1文字につき1つの英単語を当てはめる。音と意味の両方を最も制御しやすい。`--seed=<word>` を指定すると、与えられたベース単語に対してこの方向性を強制する。

**word bank** を維持する：ビジョン/価値観/ポジショニングの各テーマキーワードについて、強力な英単語をリストアップし、頭文字でインデックスを作成する。展開はこの word bank から組み立てられるため、すべての単語はスロットを埋めるためにでっち上げられたものではなく、実際のプロダクトの価値に追跡可能である。

## ネーミング品質基準 (すべての候補をスコアリングする)

Marty Neumeier の7つのテストを適応：

1. **Distinctiveness (独自性)** — カテゴリ内で際立っているか。競合他社のコピーに近いものではないか。
2. **Brevity (簡潔さ)** — 短いか。Acronym スタイルの場合は3音節以下。長い展開は問題ない。*名前*が短いこと。
3. **Appropriateness (適切さ)** — プロダクトに合っているか、ただし一般的なカテゴリの説明ではないか。展開がその領域のあらゆるプロダクト（「高速で信頼性が高く効率的な…」）を説明できる場合、このテストには不合格となる。
4. **Easy spelling & pronunciation (スペルと発音のしやすさ)** — 明らかな読み方が1つあるか。曖昧な母音や黙字（サイレントレター）がないか。
5. **Likability / extendability (好感度 / 拡張性)** — 口に出して言いやすいか。最初の機能を超えて成長する余地があるか。
6. **Protectability (保護可能性)** — *確認可能*であり、推測ではないか。以下を参照。

各文字の展開が強引な候補（文字を満たすためにテーマ外の単語が押し込まれている）や、フレーズとして無意味な候補は、文字列自体が魅力的であっても拒否する。

## 利用可能性を決して捏造しない

名前、ドメイン、商標、またはハンドル名が利用可能であると明言してはならない。具体的なチェック項目を外部検証のための **Open Questions (未解決の質問)** としてリストアップする：商標クラス、`.com` および関連する TLD、アプリストア名、ソーシャルハンドル、既知の競合との衝突。利用可能性は人間/レジストリのルックアップによってクリアされるものであり、この Skill によってクリアされることは決してない。

## ID規約

各候補と最終的な推奨には `NAM-xxx` ID が付与され、展開がエンコードする価値を示す `VIS-`/`POS-` ID を引用する Upstream 列が追加される。すべての `NAM-` ノードを `work/traceability.json` に追記する。

## 作業例 (例示であり、コピーするためのテンプレートではない)

```
Candidate: NEXUS  (acronym, 2 syllables)
  N — Next-generation     (theme: innovation      ← VIS-003)
  E — Extensible          (theme: platform growth ← VIS-005)
  X — eXchange            (theme: interoperability← POS-002)
  U — Unified             (theme: consolidation   ← VIS-001)
  S — System              (theme: category        ← VIS-001)
  Reads as: "a next-generation, extensible exchange that unifies the system."
```

## 情報源

- Marty Neumeier — "The Brand Gap" / "Brand" naming criteria
- Alina Wheeler — "Designing Brand Identity" (name types: acronym, descriptive, invented)
