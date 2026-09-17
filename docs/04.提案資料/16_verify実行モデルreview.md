# verify実行モデルレビュー

- 状態: Closed（ADR-041でP0・関連P1/P2を裁定・反映済み）
- 実施日: 2026-09-02
- 基準: branch `bitz_next`、HEAD `0097f2839e15a697cea5a8e4cb413a77562201ab`＋未コミット設計
- 規範文書digest: `b292eed96f8d607c49e380bdb500c10a0c896c2e2c41bea415c4fd14aa38aaba`
- 観点: 対象、Context、binding、実行計画、重複排除、結果対応、0件・失敗

## 1. 結論

`(workspaceId, commandName)`をbinding IDとし、全対象のtest pathをまとめて1回だけ実行する方針は、現行の
command名単位簡素化と整合している。command所有workspaceの設定、cwd、timeoutを使用する点も明確である。

ただし、複数対象と引数なしverifyが複数Contextを作るのに、公開結果が単一`contextDigest`しか持たない。
これは「何を検証した結果か」を一意に表せないため、実装開始前のP0である。

## 2. 指摘一覧

| ID | 優先度 | 指摘 | 影響 |
|---|---|---|---|
| FED-VER-001 | P0 | 複数Contextに対して結果の`contextDigest`が1つしかない | verified述語とstale判定が成立しない |
| FED-VER-002 | P1 | targetからContext・statement・binding・結果への対応Schemaがない | どの要求が失敗したか機械追跡できない |
| FED-VER-003 | P1 | `bindingRefs[]`と連合command結果の完全なSchemaがない | adapter間で結果表現が分岐する |
| FED-VER-004 | P1 | 非成功Contextと共有bindingの実行可否が未定義 | blocked対象のtestを実行する実装が生じる |
| FED-VER-005 | P2 | owner側とrequest側へ同じ失敗を反映する件数規則が不足 | 集約件数が二重計上され得る |

## 3. FED-VER-001 Context Digestの基数

[verify仕様 §7](../03.詳細設計/03_操作仕様/03_verify.md#7-引数なし実行)は対象ごとにContextを解決する。
明示複数対象でも、対象ごとに異なる依存閉包を持ち得る。一方、[結果 §8](../03.詳細設計/03_操作仕様/03_verify.md#8-結果)
はtop-levelに`contextDigest`を1つだけ持ち、`verified`を「特定Context Digestに対する述語」と定義する。

連合全体ではworkspace数と対象数だけDigestが増えるため、任意の1件を代表値にすることはできない。
次のどちらかへ統一する必要がある。

1. 全起点を1回のmulti-root Context requestとして解決し、1つのDigestを計算する
2. `targetResults[]`ごとに`contextDigest`を持ち、top-level単一Digestを廃止する

引数なしverifyが対象ごとの非成功を独立継続する現行設計には2が適合する。target ID、Context Digest、statement、
bindingRefs、status、diagnosticsを同じ要素へ置くことを推奨する。

## 4. FED-VER-002 target単位結果

現在の結果は`targets[]`、`statements[]`、`commands[]`が独立配列であり、多対多の対応を復元できない。
command結果の`covers[]`だけでは、同じstatementを起点とする複数targetや、Context解決だけがblockedになったtargetを
表せない。共通結果契約は個別原因を保持するため、`targetResults[]`を正本化すべきである。

推奨最小fieldは`target`、`status`、`contextDigest|null`、`statements[]`、`bindingRefs[]`、`diagnostics[]`である。
Contextを構成できない場合だけDigestをnullとし、その条件を列挙する。

## 5. FED-VER-003 binding Schema

連合仕様は`bindingId: <workspace-id>::<command-name>`とmemberの`bindingRefs[]`を定めるが、結果例とfield表がない。
次を固定する必要がある。

- `bindingId`、`workspaceId`、`name`の必須性
- `bindingRefs`の重複排除と辞書順
- command実体をowner memberへ1回だけ置く規則
- workspace単独連合結果と`--all-workspaces`結果の差
- `covers[]`を連合正規statement IDで返すこと

## 6. FED-VER-004 実行計画への採用条件

全workspaceのContextを先に解決してbinding和集合を作るが、failed/blocked Contextから見つかったbindingを和集合へ
入れるかが定義されていない。非成功target由来のbindingは実行せず、別の通過targetも同じbindingを必要とする場合だけ
実行計画へ残すべきである。command実行後のstatusは通過targetへだけ関連付け、非成功targetの元statusを上書きしない。

## 7. FED-VER-005 件数

横断command失敗をrequest memberとcommand owner memberの両statusへ反映する判断は、原因を隠さない点で妥当である。
ただし、top-level failed workspace数とfailed target数は2つの別指標である。command実体数、target失敗数、
非成功workspace数を分け、同じcommandを合計へ2回加算しない規則が必要である。

## 8. 成立を確認した契約

- binding IDはworkspace IDとcommand名の組である。
- argv/cwdが同じ別名commandと別workspace commandを統合しない。
- 同一bindingのtest pathは所有workspace相対pathで重複排除する。
- test所有workspaceのargv、cwd、timeoutを使う。
- 実行済み集合は連合全体に1つである。
- member対象0件はwarning、連合全体0件はblockedである。
- 1件のcommand失敗後も解決済みの独立bindingを継続する。

## 9. 判定

レビュー時点ではFED-VER-001を解消するまでverify結果Schemaを実装開始不可と判定した。
2026-09-02に[ADR-041](../02.設計書/10_決定記録/ADR-041_verify対象別証跡とreport明示保存の分離.md)で、
target単位Context、`targetResults[]`、全workspace共通binding ID、非成功targetのbinding除外、target／全体statusの分離を
採用し、正本へ反映した。これによりFED-VER-001〜005をClosedとする。
