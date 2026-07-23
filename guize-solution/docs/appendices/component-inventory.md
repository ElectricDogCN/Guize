# 组件清单 / Component Inventory

| 领域 | 组件 | 用途 | V1 状态 | 备注 |
|---|---|---|---|---|
| Control | Java 17 | 控制面运行时 | 冻结 | 版本固定于构建 |
| Control | Spring Boot 3 | 模块化单体 | 冻结 | 具体 3.x 待兼容核验 |
| Rules | LiteFlow | 轻量决策编排 | 冻结 | 不运行长任务 |
| Workflow | Temporal | 长任务 | 冻结 | 自托管、PostgreSQL |
| Database | PostgreSQL | 权威数据 | 冻结 | 独立数据库/Schema |
| Cache | Redis | 会话、限流、短期协调 | 冻结 | 非唯一正确性保障 |
| HTTP Cache | Apache Traffic Server | Range/Slice | 冻结 | POC |
| Secrets | OpenBao/Vault abstraction | Secrets | 冻结 | 业务库只存引用 |
| Search | OpenSearch | 全文、聚合、混合 | 冻结 | 可重建 |
| Vector | Milvus | 多向量 | 冻结 | 可重建 |
| Media | FFmpeg/ffprobe | 媒体处理 | 冻结 | 版本和构建参数固定 |
| Media | Intel Arc A380 | 边缘媒体 | 待 POC | ESXi 直通 |
| AI | FastAPI services | AI 能力 | 冻结 | 逻辑独立 |
| Observability | Prometheus | 指标 | 冻结 | |
| Observability | Grafana | 可视化 | 冻结 | |
| Observability | Loki | 日志 | 冻结 | |
| Observability | OpenTelemetry | Trace | 冻结 | |
| Alerting | Alertmanager | 告警治理 | 冻结 | |
| Player | Shaka Player candidate | HLS/DASH | 待 POC | 独立 SDK |
| Frontend | Vue/React candidate | Console/UI | 待 POC | 最终单主框架 |
| Deploy | Docker Compose | 首期部署 | 冻结 | |
| Deploy | Ansible | 远程部署 | 冻结 | |
| Deploy | Go / guizectl | Bundle Builder | 冻结 | |
| Supply chain | Huawei SWR | 镜像仓库 | 冻结 | |
| Supply chain | Cosign | 签名验签 | 冻结 | |
