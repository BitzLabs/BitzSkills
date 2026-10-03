# 実行と状態の条件

正本はBitzSkills 2系の `docs/02.設計書/03_SDD-flow.md`、公開操作仕様、SPECモデルである。
この参照は利用手順であり、規範の状態遷移や結果Schemaを上書きしない。

## 結果とcontextの照合

同じリポジトリ・ワークスペースで公開設定から所有者を確認する。
単一ワークスペースではローカルID、複合では所有者が確認できた `workspaceId::localId` と公開の範囲指定を使う。
異なる所有者の起点を一つのリクエストへ詰めない。

JSONはschemaVersion 1.0、要求したoperationと対象・範囲であることを確認する。
終了コードはpassed／passed_with_warningsが0、failedが1、blockedが2、errorが3。
引数不正は4で結果JSONがない場合がある。組合せが矛盾する結果を成功と解釈しない。
Core 1.0には警告を昇格する--strictはない。警告はそのまま説明する。

implement contextは完全解決とdigestが必要で、提示された文書だけから完全性を推定しない。
digest再照合には、元の起点、purpose、範囲、解決・提示オプションを保ち、--expect-digestを加える。
CTX-STALE-001なら再取得・変更理由の確認・必要なレビュー・実装前checkへ戻る。
digestはSPEC本文、関係、テスト対応、登録argvテンプレート等を含むが、コードとテストのファイル内容、
Git履歴、安全設定は含まない。一致しても並行変更の差分と実行条件の確認が必要である。

## 完全フローと要求変更

interpret contextで目的・意味・受入条件・互換性をレビューし、人間の承認を記録する。
新規・編集REQ／TECHはレビュー後にapprovedへ変更し、対象checkを通してからimplement contextへ進む。
既存approvedの意味変更は差分と影響を先に示す。事前承認が必要なリポジトリでは承認を待ち、
許可後は同じ変更作業で先にdraftまたはoutdatedへ戻す。変更後も再レビューと承認を省略しない。
設計レビューはimplement contextの後、書込み前に行い、依存・境界・異常系・検証方法を確認する。
Coreは承認・レビューを保存しない。記録は許可されたGit／PR等へ残す。

TASKはopenが起点で、addressesの規範文、requiresの先行TASKがすべてdoneであること、changesの境界を確認する。
1系のimplements／depends_on／boundaryというTASK項目を持ち込まない。
要求のimplementsやtestsは2系SPECモデルに従って扱う。

## 完了と並行・複合作業

完了には、対象規範文、書込み直前のdigest一致、前後check、verify、必須テストの成功、
未テストMUSTが0件、省略・未実証事項の表示、人間による最終差分の確認、Gitへの記録が必要である。
TASKは人手レビュー後にdoneへ変更し、最終の対象checkを通す。状態変更だけで過去の証拠を現在の証拠へ置き換えない。

複合ワークスペースでは共通要求のinterpretレビューを先に行い、各メンバーにTASKを分け、
各所有者でimplement context、前check、実装、後check、verifyを実行する。
横断到達先と所有境界を人間が確認した後、統合前に同じGitリポジトリのルート／ルートワークスペースを
発見できる場所から `bitz check --all-workspaces --base <統合先先端>` と `bitz verify --all-workspaces` を実行する。
全メンバーの実行安全性を確認する。集約通過は各メンバーの人手レビューの代わりにならない。

並行ブランチを統合先へマージ／リベースした後は `bitz check --full --base <統合先先端>` を実行する。
同一ワークスペースのID重複は人間が未使用IDへ改番し、ファイル名・関係・covers・addressesも更新する。
別ワークスペースの同名ローカルIDを改番しない。再check通過後に通常のレビューと、許可された統合操作を行う。
