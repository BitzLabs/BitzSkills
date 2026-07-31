"""bitz-flow の内部ライブラリ。

``flow.py`` だけが public executable であり、``flowlib`` を直接呼ぶことは公開契約外
（FLW-DSN-004）。スキルはフォルダ単位でコピーされるため、本パッケージは
プラグインマニフェスト等のスキル外ファイルを読まない（CORE-CON-004 の自己完結）。

``__version__`` は result envelope の ``audit.tool_version`` として公開する値であり、
プラグインの3マニフェストの version と同じ値に保つ（bump は同じ変更セットで行う）。
"""

__version__ = "0.4.0"
