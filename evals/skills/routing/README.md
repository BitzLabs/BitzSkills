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

2026-10-06に保存計画の外部領域への継続的な新規保存が明示承認された。
承認範囲と初期有限条件は `held-out-collection.json` に固定した。
`audit_held_out.py` は指定領域の集合を読み、件数・hash・集計だけを出力する。
スキーマ診断に非公開本文が含まれる場合も、例外の文字列やtracebackを出さない。

```text
python -B evals/skills/routing/audit_held_out.py --cases /home/hide/BitzLabs/BitzSkills-private-evals/core-sdd-quality-20261006/cases.json
```

初期集合12件は機械検査を通過したが、独立検分で公開ケースとの意味重複P2が2件あり停止した。
当該集合で一次評価を行わず、原ケース・失敗記録を非公開で保持する。
[停止結果](../results/2026-10-06-held-out-collection-stopped/report.md)を後続成功へ置換しない。

`host.py` は固定manifestのhashと全package資源を照合してから、stdio MCPで
`list_resources` と `read_resource` だけを提供する。モデルに渡す情報は6スキルの
名前・説明・版・相対パスとpackage資源本文に限定する。case/正解/集合controlは渡さない。
読取りごとにhashと実結果をログへ記録する。未登録パス・絶対パス・symlink・改変を拒否し、
CLI・shell・試験・ファイル変更のtoolは提供しない。既存ログを再利用せず新規0600で作成する。

```text
python -B evals/skills/routing/host.py --snapshot <固定snapshot> --manifest-sha256 <固定hash> --log <新規host.jsonl>
```

これは資源ホストの準備で、発火実測ではない。`host-preparation.json` の別有限予算で独立検分する。
非公開入力を含む測定のログは承認済み非公開領域へ保存し、公開しない。
後続runnerは出力領域・有限台帳・停止条件を検査し、モデルのshell等を無効化した状態で接続する。

後続保持集合0.2.0の条件は `held-out-collection-v0.2.json` に固定する。
製品候補は変えず、旧停止集合を除外照合へ束縛し、新規子領域・IDs SE-900〜911へ保存する。
`novelty.json` は全46公開ケース・旧12件の照合範囲、各新ケースの因果前提、
近い公開/旧ケース、決定に関係する差を `novelty.schema.json` に沿って非公開で記録する。
監査は固定製品資源・旧集合hash・文字列正規化衝突・比較証拠のケースhash束縛と全件対応を検査する。
診断に非公開本文が含まれても公開出力はerrorTypeだけとする。

```text
python -B evals/skills/routing/audit_held_out.py --collection novelty --cases /home/hide/BitzLabs/BitzSkills-private-evals/core-sdd-quality-20261006/collection-02/cases.json
```

機械検査の通過は比較証拠の構造・束縛の確認で、`semanticNovelty=requires_independent_review`を返す。
比較欄を埋めただけでは新規性を認定しない。初回準備source `3d98bf72` は公開JSONの追加と
公開46件の変化を拒否できず独立P2で停止した。旧準備枠1を消費済みとして保持し、
是正コードの別確定refを `held-out-novelty-preparation-v0.2.1.json` の新準備独立1枠で検分する。
公開入力のファイル一覧をケース読取り前に固定し、件数も照合する。生成1・ケース独立1の
未消費枠は準備通過後だけ起動し、一次0・retry0で元の停止記録を保持する。

0.2の作成は保存前のHEAD一致ガードで停止した。結果記録commitによるHEADの移動を、
確定source内容の変化と取り違えた停止であり、ケースは保存されなかった。原枠と失敗を保持する。
後続0.3は別版・別IDs・collection-03への別新規保存とし、生成1/ケース検分1を新予算へ固定する。
`source_guard.py --source <確定40桁commit>` はcontractのsourceFilesをref blobと照合する。
HEADは観測値だけで、対象内容を変えない結果記録のcommitで停止しない。
候補・入力・除外hashと比較の検査は引き続き必須で、内容変更は拒否する。

```text
python -B evals/skills/routing/source_guard.py --source <確定commit>
python -B evals/skills/routing/audit_held_out.py --collection fixed-ref --cases /home/hide/BitzLabs/BitzSkills-private-evals/core-sdd-quality-20261006/collection-03/cases.json
```
