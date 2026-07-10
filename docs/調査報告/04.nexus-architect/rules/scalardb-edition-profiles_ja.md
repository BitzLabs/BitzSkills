# ScalarDB Edition Profiles

## エディションの比較

| 機能 | OSS | Enterprise Standard | Enterprise Premium |
|---------|-----|--------------------|--------------------|
| Consensus Commit (コンセンサスコミット) | あり | あり | あり |
| JDBC互換DB | あり | あり | あり |
| NoSQLサポート | Cassandra, DynamoDB, CosmosDB | 同上 | 同上 |
| Two-Phase Commit (二相コミット) | あり | あり | あり |
| ScalarDB Cluster | なし | あり | あり |
| SQLインターフェース | なし | あり | あり |
| GraphQL | なし | あり | あり |
| Spring Data統合 | 基本 | 完全 | 完全 |
| ScalarDB Analytics | なし | なし | あり |
| マルチリージョン | なし | なし | あり |
| SLA | コミュニティ | 営業時間内 | 24/7 |
| サポート | コミュニティ | 営業時間内 | 24/7 |

## デプロイメントモード

### Core (OSS)
- アプリケーションに組み込まれる
- ライブラリとして直接使用される
- gRPCサーバーは不要である

### Cluster (Enterprise)
- 独立したgRPCサーバークラスターである
- Kubernetes上にデプロイされる
- アプリケーションはgRPCクライアント経由で接続する
- 水平スケーリングをサポートする

## 選定基準

| 要件 | 推奨エディション |
|-------------|---------------------|
| 単一DBのトランザクション | OSS |
| 複数DBのトランザクション | OSS または Enterprise |
| SQLインターフェースが必要 | Enterprise Standard以上 |
| 分析クエリが必要 | Enterprise Premium |
| 99.99%のSLA | Enterprise Premium |
| 5つ以上のサービスにまたがるTwo-Phase Commit | Enterprise Standard以上 (Clusterを推奨) |
