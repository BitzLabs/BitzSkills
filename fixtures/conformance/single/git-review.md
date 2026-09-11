# Git基準版・状態遷移fixtureレビュー

2026-09-11。SINGLE-027〜031の5件について実入力、base/current、完全期待JSON、副作用期待値を固定する。
Coreの状態比較・変更保護を実装した結果ではない。

## 単一原因と期待結果

最小設定を共通にし、manifestでbase commitを作成した後、変更を1種類だけ適用する。
公開操作は`check --full --base HEAD --format json`。対象選択件数の論点を分離するためfullを明示する。

| ID | HEAD → current | index | Diagnostic / status / exit | 完全検査文書 / 規範文 |
|---|---|---|---|---|
| SINGLE-027 | done TASK → open TASK | baseのまま | SPEC-STATE-TRANSITION-001 / failed / 1 | 1 / 0 |
| SINGLE-028 | 設定だけ → done TASKを新規作成 | baseのまま | なし / passed / 0 | 1 / 0 |
| SINGLE-029 | approved TECH → 文書を削除 | baseのまま | SPEC-STATE-TRANSITION-001 / failed / 1 | 0 / 0 |
| SINGLE-030 | TECH-001.md → TECH-001-renamed.md | renameをstage | なし / passed / 0 | 1 / 0 |
| SINGLE-031 | approved REQのtitle・対応H1を変更 | baseのまま | SPEC-SAFETY-APPROVED-001 / failed / 1 | 1 / 1 |

027はFrontmatter statusだけを変える。done→openは禁止遷移だが、現在のopen自体は合法な語彙である。
TASKはrequires、addresses、changesを持たず、明示TASK境界検査も要求しない。
028は同じdone TASKをbaseに置かず、新規fileとして作成する。新規文書の現在語彙だけを検査し、
架空のopen状態からの遷移を要求しないことを確認する。
029は規範文なしTECHを使い、削除されたstatementへの参照切れを混ぜない。
030は正規file名のslugだけを変える。Frontmatter ID・title・本文のbyte列を保ち、
管理済みSPEC削除として扱わない。Git rename推定の結果を同一性の根拠にしない。
031はFrontmatter titleを変更し、H1も同期する。statusはapproved、規範文は同じである。
titleは意味変更対象なので保護に失敗するが、H1不一致、規範文不正、状態遷移不正は生じない。

## 結果と副作用の選択

全件revision.dirtyはtrue。baseとcommitは同じHEADを指す代表値であり、既存normalizerだけで比較する。
029以外の文書は構文検査を完了し、registryのcontinueにより非成功でも完全検査件数を保持する。
029はcurrent文書0件でもbaseの管理済みSPEC削除を診断する。

- 非成功のDiagnosticは1件、error / failed、file source、workspaceId root。
- 027はTASK-001.mdのkey status、031はREQ-001.mdのkey titleを指す。
- 029はbaseに存在したTECH-001.mdを指す。currentにないpathをsourceに使い、line/column/keyは省略する。
- summaryは各expected JSONの固定文字列。evidence、specRefs、suggestedActionは付加しない。
- source位置・任意fieldの選択は今回固定した期待値であり、既存Coreから取得したものではない。

before/afterはsetup後、Core実行直前と直後の状態を表す。beforeをHEADのclean treeと混同しない。
既存の未stage更新、新規未追跡file、削除、staged renameをそのまま保持するread-only期待値を固定する。
repoの全path・byte hash・実行bit、Git status/index、HOME・cache・TMPDIRを比較する。
Coreが変更をstage、commit、修復したり、report/cacheを新規作成したりすることを許可しない。

根拠は[文書・状態仕様 §6・§8・§9](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)、
[check仕様 §5・§7・§9](../../../docs/03.詳細設計/03_操作仕様/02_check.md)、
[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[適合fixture仕様](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)である。

## 準備検証

git_fixtures.pyはbase入力とchangesのbyte列、manifest、完全期待JSON、Frontmatter、副作用Schemaを確認する。
各fixtureを独立した2つのrepositoryへsetupし、固定snapshotに加えてGitから読み出したHEADとindexの
path集合・各blobをレビュー済みbase/currentと照合する。worktreeのfile集合・byte列も直接照合する。
これはGit状態の準備確認であり、Coreの遷移判定や意味変更判定を実装するものではない。

回帰試験では失敗の成功化、dirtyの消去、削除文書の件数加算、renameのstage省略、診断code取り違え、
実行後Git差分の消去を拒否する。また実repositoryへ誤ったstage/commitを行い、HEAD/index照合が拒否することを確認する。
Core出力、副作用、実際の遷移判定はGate Bで受け入れる。

[保護対象外変更の5件](exempt-review.md)を追加し、50/311件を準備済み、実fixture残261件とする。golden Digest、残fixtureの副作用期待値、
fresh checkoutからの全Gate A検証は未完了であり、Gate AはBlockedを維持する。
