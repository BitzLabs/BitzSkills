# 今回のレビュー入力

イベントの実行を許可した非公開リポジトリ向けのCI変更である。
今回の差分は.github/workflows/release.ymlだけで、アプリ実装と単体試験は変更していない。
CIのGitHub実行結果・安全検証結果と品質計画は提供していない。
実在のtokenや秘密は入力に含まず、workflowは実行せずデータとして読む。
固定test_fixture.pyの直接実行と公開context/checkだけを許可する。
workflow、PRコードの取得、ネットワーク、依存導入、CIジョブの起動は許可していない。
