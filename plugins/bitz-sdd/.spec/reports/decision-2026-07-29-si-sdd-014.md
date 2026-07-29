# 設計裁定記録 — SI-SDD-014 トレース参照判定の正確化（Design Gate）

- **日付**: 2026-07-29
- **対象ワークスペース**: `plugins/bitz-sdd`
- **裁定者（人間）**: hide
- **裁定の形式**: セッション内の対話裁定。現状調査（誤警告 97 件の内訳と原因の3分解）を提示し、
  設計論点3点をそれぞれ選択肢化して裁定を得た
- **代行実行者（エージェント）**: claude-code
- **前提**: SI-SDD-014 は `.spec/reports/decision-2026-07-29-open-spec-issues.md` の裁定で
  accepted 済み。本記録はその実装に必要な Design Gate の裁定

## 現状（実測）

canonical 実行 `spec inspect --workspace . plugins/*` の
「テスト/実装からの参照がない要件（approved以降）」は **97 件**を警告している。

| ワークスペース | 警告数 |
|---|---|
| BitzSkills（root） | 20 |
| bitz-sdd | 54 |
| bitz-env | 19 |
| bitz-flow | 2 |
| bitz-ddd | 2 |
| plugin-creator / skill-creator | 0 |

verification_method の内訳: manual-check 51 / example-test 27 / unit-test 18 / benchmark 1。

原因は独立した3つに分解できる:

1. **参照走査が workspace 配下に閉じている** — `scan_refs()` の走査対象は
   `.spec/specs` / `.spec/tasks` / `tests` / `test` / `src` で、いずれも workspace root からの
   相対。本モノリポのテストは**すべてリポジトリルートの `tests/`** にあり、
   プラグイン workspace（`plugins/*`）には `tests/` も `src/` も存在しない
2. **実装コードの置き場が `src` 決め打ちと合わない** — プラグインの実装は
   `skills/*/scripts/`（bitz-sdd / bitz-flow）、`scripts/`・`hooks/`（bitz-env）にあり、
   `src` に該当しない。FLW-FR-001 は `skills/flow-pr/scripts/branch_preflight.py` の
   docstring から参照されているのに拾われていない
3. **manual-check 要件はテスト参照が原理的に存在しない** — 51 件が該当。
   検証手段が「SKILL.md の目視確認」「skill-validator チェックリスト通過」等であり、
   テストコードから ID 参照されることはない

## 設計裁定

### 論点1: workspace 外テスト参照の集約方式 → **案A（canonical 実行時のグローバル集約）**

複数 workspace を同時指定したときに限り、全入力 root の test/src 参照をグローバル ID で
集約し、その ID を所有する workspace の判定へ還流する。

- 採用理由: 宣言のメンテが不要で、canonical コマンドを使うだけで正しくなる。
  **単一 workspace 実行の挙動を一切変えない**ため既存利用者に影響がない
- 案B（`.spec/PROJECT.md` に `external_test_roots` を宣言）を採らない理由:
  6 workspace 分の宣言メンテが必要なうえ、workspace が外部の相対パスを持つことになり
  「各 workspace は独立した BitzSDD プロジェクト」という自己完結性を壊す。
  モノリポの物理配置を仕様ファイルに焼き付けると、ディレクトリ移動のたびに仕様が壊れる
- 案A+B の両建てを採らない理由: 同じ結論に至る経路が2つになり、
  どちらで解決したかによって単一実行と canonical 実行の結果が食い違う条件が増える

**誤検知の抑制**: 集約は厳格な ID パターン（`ID_RE`）の一致に限る。自己参照の除外
（ファイル名 stem と一致する ID を数えない）と生成レポートの除外（`inspection-report.md`）は
既存の `scan_refs()` の挙動をそのまま踏襲する。

### 論点2: 実装コードの走査対象 → **コード拡張子のみ対象に追加**

`skills/*/scripts/`・`scripts/`・`hooks/` を走査対象に加える。ただし**コード拡張子に限定**し、
`SKILL.md` などの Markdown は「実装からの参照」として数えない。

- 採用理由: 「テスト/実装からの参照」という指標の意味論は
  「その要件を実現するコード、または検証するテストが実在すること」。
  実装コードが `src/` にあるか `skills/*/scripts/` にあるかは配置の都合にすぎない
- SKILL.md を含めない理由: スキル本体は要件 ID を解説目的で多数言及するため、
  含めると「言及があるだけで実装済みと見なす」ことになり、指標が空洞化する。
  スキル記述で担保される要件は verification_method が manual-check であり、論点3で扱う

### 論点3: manual-check 要件の扱い → **別セクションへ分離して報告**

「テスト/実装からの参照がない要件」を2つの見出しに分ける:

- **自動検証要件の未参照**（unit-test / example-test / benchmark / pbt / load-test /
  sast / dep-audit）— 真のトレース欠落。従来どおり警告する
- **manual-check 要件の未参照** — 検証記録で担保される旨を添えて別掲する

- 採用理由: 情報を捨てずに誤警告を消せる。「manual-check なのに検証記録すら無い」状態は
  別掲リストを見れば分かるため、完全除外より検出力が高い
- 完全除外を採らない理由: `verification_method` を manual-check にするだけで
  トレース指標から消えられる抜け道を作らないため

## 追加裁定（実装中に判明した論点）— 追加走査対象と幽霊参照判定

論点2を実装したところ、走査対象へ加えた実装コードの docstring 内の使用例が
幽霊参照として検出され、canonical 実行が FAIL した:

```
bitz-flow: TSK-042      ← skills/flow-core/scripts/commit_lint.py   （コミットメッセージの例示）
bitz-sdd:  CORE-TSK-001 ← skills/sdd-core/scripts/spec_scaffold.py  （使用例）
bitz-sdd:  FR-012       ← skills/sdd-core/scripts/spec_inspect.py   （--impact FR-012 の例示）
```

**裁定: 追加走査対象からの参照は未参照判定にだけ使い、幽霊参照判定の入力にはしない。**

- 採用理由: 実装コードの docstring・`--help` 出力・エラーメッセージには使用例としての
  ID が自然に登場する。これを幽霊参照として扱うと、ツールのヘルプを書くたびに
  検査が壊れる。一方で実装コード内の ID の綴りは機能に影響しないため、
  そこでタイポを検出する価値は低い
- 例示 ID をプレースホルダへ書き換える案を採らない理由: 具体例を書けなくなり
  ヘルプの質が下がる。検査の都合でドキュメントの表現を制約するのは本末転倒
- WARN 別掲案を採らない理由: 幽霊参照の報告経路が2系統に分かれ、
  「FAIL する幽霊」と「しない幽霊」の区別を利用者が覚える必要が生じる

従来の走査対象（`.spec/specs`・`.spec/tasks`・`tests`・`test`・`src`）における
幽霊参照の検出は一切変更しない。SDD-FR-147 を 1.0 → 1.1 へ改訂して反映する。

## 影響と非影響

- **判定への影響なし**: 本節の警告はいずれも `ok = not problems and not ghosts and not orphans`
  に含まれず、PASS / FAIL 判定を変えない。既存の green を red にしない
- **単一 workspace 実行**: 論点1の集約は複数 workspace 指定時のみ作動する。
  論点2の走査対象拡張は単一実行にも効くが、参照を**増やす**方向のみで警告は減る
- **走査量**: 追加対象は `skills/*/scripts`・`scripts`・`hooks` のコードファイルのみ。
  本リポジトリ全体で数十ファイル規模であり、実用時間内に収まる

## 要件化の方針

3つの論点は独立して revert 可能な機能変更のため、要件も3件に分けて起票する
（既存 SDD-FR-133 / 134 の粒度に合わせる）。いずれも `spec_inspect.py` の
参照集計・レポート表示に閉じた追加変更であり、既存 EARS 節の意味は変更しない。

## 残余リスク

- グローバル集約は「ある workspace のテストが他 workspace の要件 ID を文字列として含む」
  ことをもって参照と見なす。ID の綴りが正しければ意図しないファイルでも参照と数えるが、
  これは単一 workspace 内の既存挙動と同じ性質であり、新たなリスクではない
- 走査対象の追加により、実装コード内のコメントで要件 ID に言及しただけの箇所も
  参照と数える。「参照がある ≠ 実装されている」という指標の限界は従来どおり残る
- manual-check の別掲リストは警告として残るが、件数が多い（51 件）ため
  レポートが長くなる。件数の可視化は保ちつつ表示形式は実装時に調整する
