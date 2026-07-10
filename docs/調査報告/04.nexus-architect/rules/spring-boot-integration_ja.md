# Spring Boot + ScalarDB Integration Guide

## Gradle Dependencies

```groovy
dependencies {
    implementation 'com.scalar-labs:scalardb:3.17.0'
    implementation 'com.scalar-labs:scalardb-sql-spring-data:3.17.0'  // Enterprise
    implementation 'org.springframework.boot:spring-boot-starter:3.2.0'
}
```

## ScalarDB Property Configuration

```properties
# Storage configuration
scalar.db.storage=jdbc
scalar.db.contact_points=jdbc:postgresql://localhost:5432/scalardb
scalar.db.username=postgres
scalar.db.password=postgres

# Transaction manager
scalar.db.transaction_manager=consensus-commit

# Default namespace
scalar.db.default_namespace_name=app

# Cluster connection (Enterprise)
scalar.db.transaction_manager=cluster
scalar.db.contact_points=indirect:lb.scalardb-cluster.svc.cluster.local
```

## Spring Data Integration Pattern

```java
@Configuration
public class ScalarDbConfig {
    @Bean
    public TransactionFactory transactionFactory() {
        return TransactionFactory.create("scalardb.properties");
    }

    @Bean
    public DistributedTransactionManager transactionManager(TransactionFactory factory) {
        return factory.getTransactionManager();
    }
}
```

## Transaction Annotations

ScalarDBはSpringの`@Transactional`と直接統合されないため、明示的な transaction management pattern (トランザクション管理パターン) を使用する：

```java
@Service
public class OrderService {
    private final DistributedTransactionManager manager;

    public void placeOrder(OrderRequest request) {
        DistributedTransaction tx = manager.begin();
        try {
            // Business logic
            tx.commit();
        } catch (CommitConflictException e) {
            tx.rollback();
            throw new RetryableException(e);
        }
    }
}
```
