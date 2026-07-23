# 23. 官方资料核验 / Official Source References

核验日期：2026-07-21。以下资料用于确认方案中主要组件的能力边界。具体生产版本必须在实施时重新核验、固定并通过兼容测试。

## Spring

- Spring Boot System Requirements  
  https://docs.spring.io/spring-boot/system-requirements.html
- Spring Framework Reference  
  https://docs.spring.io/spring-framework/reference/index.html

说明：当前官方 Spring Boot 文档仍以 Java 17 作为最低 Java 基线之一。归泽冻结 Java 17 + Spring Boot 3，但具体 3.x 版本需在实施阶段按支持周期选择。

## Temporal

- Self-hosted guide  
  https://docs.temporal.io/self-hosted-guide
- Deployment guidance  
  https://docs.temporal.io/self-hosted-guide/deployment
- Persistence  
  https://docs.temporal.io/temporal-service/persistence
- Visibility  
  https://docs.temporal.io/visibility
- Server upgrade  
  https://docs.temporal.io/self-hosted-guide/upgrade-server
- Archival  
  https://docs.temporal.io/self-hosted-guide/archival

说明：

- 自托管 Temporal 是关键控制与持久化组件，不应暴露公网；
- PostgreSQL 可作为持久化和 Visibility 的选项，实际版本需匹配 Temporal；
- Server 与数据库 Schema 升级必须按官方顺序执行；
- 本地开发可使用开发服务器，但生产不得使用嵌入式/开发模式替代正式部署。

## LiteFlow

- 官方站点  
  https://liteflow.cc/

说明：LiteFlow 官方定位为组件式规则引擎。归泽只用于同步决策和轻量编排，不用于 FFmpeg、ASR、备份等长时间任务。

## Apache Traffic Server

- Cache Range Requests  
  https://docs.trafficserver.apache.org/en/latest/admin-guide/plugins/cache_range_requests.en.html
- Slice Plugin  
  https://docs.trafficserver.apache.org/en/latest/admin-guide/plugins/slice.en.html
- Cache Storage  
  https://docs.trafficserver.apache.org/en/latest/admin-guide/storage/index.en.html
- Plugins  
  https://docs.trafficserver.apache.org/admin-guide/plugins/index.en.html

说明：ATS 提供 HTTP 缓存、Range 缓存和 Slice 插件能力。归泽仍需通过 POC 验证大文件、权限缓存键、源版本变化和磁盘行为。

## OpenSearch

- Hybrid Search  
  https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/index/
- Vector Search  
  https://docs.opensearch.org/latest/vector-search/
- Concepts  
  https://docs.opensearch.org/latest/vector-search/getting-started/concepts/

说明：OpenSearch 支持关键词、向量及混合搜索。归泽仍将 PostgreSQL 作为权威数据源，OpenSearch 索引可重建。

## Milvus

- Overview  
  https://milvus.io/docs/overview.md
- Hybrid Search  
  https://milvus.io/docs/hybrid_search_with_milvus.md
- Reranking  
  https://milvus.io/docs/reranking.md

说明：Milvus 支持密集、稀疏、多向量和混合搜索及重排。归泽主要用其保存文本、图像和多模态向量。

## OpenBao

- What is OpenBao  
  https://openbao.org/docs/what-is-openbao/
- Secrets Engines  
  https://openbao.org/docs/secrets/
- KV v2  
  https://openbao.org/docs/secrets/kv/kv-v2/

说明：OpenBao 提供身份驱动的 Secrets 和加密管理。归泽通过抽象接口接入 OpenBao/Vault，业务数据库只保存引用。

## Shaka Player

- API Documentation  
  https://shaka-player-demo.appspot.com/docs/api/
- Manifest Parser  
  https://shaka-player-demo.appspot.com/docs/api/shaka.extern.ManifestParser.html

说明：官方 API 包含 DASH 和 HLS 解析器。归泽播放器仍需通过 Vue/React POC 和浏览器兼容测试决定最终封装。

## Sigstore / Cosign

- Signing Containers  
  https://docs.sigstore.dev/cosign/signing/signing_with_containers/
- Verifying Signatures  
  https://docs.sigstore.dev/cosign/verifying/verify/
- CI Quickstart  
  https://docs.sigstore.dev/quickstart/quickstart-ci/
- SBOM Signing  
  https://docs.sigstore.dev/cosign/signing/other_types/

说明：Cosign 可签名并验证容器和其他制品。归泽将镜像 Digest、签名、SBOM 和部署验签作为生产门禁。

## Prometheus / Alertmanager

- Prometheus Overview  
  https://prometheus.io/docs/introduction/overview/
- Alertmanager  
  https://prometheus.io/docs/alerting/latest/alertmanager/
- Alerting Overview  
  https://prometheus.io/docs/alerting/latest/overview/
- Alerting Practices  
  https://prometheus.io/docs/practices/alerting/

说明：Alertmanager 提供聚合、路由、静默和抑制。归泽使用多渠道告警并要求每个高等级告警有可操作 Runbook。

## 华为云 SWR

华为云官方文档入口需在账号区域和部署区域确定后重新核验。实施阶段必须验证：

- 私有仓库；
- OCI Digest；
- 漏洞扫描能力；
- Cosign/OCI Artifact 兼容；
- 跨区域恢复；
- 权限和审计；
- 离线导出。

本方案不把仓库提供方的权限等同于制品完整性，仍强制 Digest 和签名校验。
