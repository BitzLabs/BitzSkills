# 製品6スキルの発火評価準備

旧 `candidates/six-skill` の6本文は、製品pluginsの本文とは異なる。
旧候補・protocol・原測定は保持し、製品本文の結果として扱わない。
`prepare.py` は確定commitのGit blobから製品6本文とpackage資源を取得し、
名前・description・版・取得先・全資源hashのmanifestを作る。
作業ツリーの未コミット差分を取り込まず、symlink・保護対象・不正パスを拒否する。

出力先はこのrepoの `.venv` 配下に限定し、既存または中断した出力を再利用しない。
これは資源の準備だけで、モデル起動・CLI操作・品質認定は行わない。

```text
python -B evals/skills/routing/prepare.py --ref <確定commit> --output <repo>/.venv/<新規snapshot名>
```

次は製品本文を固定した状態で、別文脈の保持ケースを生成・検分し、集合hashを確定する。
公開canaryと保持ケースの新測定は、その後に別の有限contractへ固定する。
原 `run_model.py` はprototype候補を読むため、そのまま製品本文の測定へ流用しない。
モデルへ渡す資源と操作を制限し、発火分類だけを行動実証へ変換しない。

[保持ケースの保存計画](held-out-storage-plan.md)の外部保存領域は明示承認後だけ作成する。
公開資源snapshotの所在と、非公開ケース/軌跡の所在は区別する。
