# 15. 可观测性与运维 / Observability and Operations

## 1. 技术栈

- Prometheus；
- Grafana；
- Loki；
- OpenTelemetry Collector；
- Alertmanager；
- Node Exporter；
- cAdvisor；
- PostgreSQL Exporter；
- Blackbox Exporter；
- ATS 指标适配；
- Worker 指标。

## 2. 统一关联

所有请求、任务、事件和 Workflow 关联：

```text
traceId
requestId
taskId
workflowId
assetId
versionId
workerId
```

日志不得输出 Secret、Token、签名 URL 全文或敏感内容。

## 3. 指标域

### 平台

- API RPS；
- 延迟；
- 错误率；
- 活跃用户；
- 认证失败；
- DB 连接；
- Outbox 积压。

### 数据源

- 健康；
- 请求；
- 延迟；
- 429；
- 5xx；
- 配额；
- 扫描进度；
- 变化数量；
- 回源字节。

### ATS

- 对象命中率；
- 字节命中率；
- Range/Slice；
- 回源；
- 源站延迟；
- 淘汰；
- 磁盘；
- 错误。

### 存储

- ZFS 健康；
- 数据集容量；
- 500GB 水位；
- 增长；
- 预计写满时间；
- 缓存；
- 正式副本；
- 备份；
- SMART。

### 播放

- 首帧；
- 缓冲；
- 码率；
- ABR 切换；
- 失败；
- 临时转码等待；
- 匿名流量；
- 完成率。

### 媒体/AI

- 队列；
- 等待时间；
- FPS；
- GPU；
- 显存；
- ASR 实时倍率；
- Token；
- 费用；
- 质量；
- 人工退回；
- 低置信度。

## 4. 日志

结构化 JSON：

```json
{
  "timestamp": "...",
  "level": "INFO",
  "service": "guize-control",
  "traceId": "...",
  "taskId": "...",
  "message": "Task dispatched",
  "fields": {}
}
```

底层英文日志，Console 提供中文解释。

## 5. Trace

OpenTelemetry 覆盖：

- Gateway；
- Java 控制面；
- Connector；
- Python 能力；
- Temporal Activity；
- OpenSearch/Milvus；
- 对象存储。

大文件字节流不做逐块高开销 Trace，采用采样和指标。

## 6. 告警渠道

- 配置中心；
- Email；
- Telegram；
- 企业微信；
- Critical 多渠道。

## 7. 告警分级

| 级别 | 示例 | 动作 |
|---|---|---|
| Info | 扫描完成 | Console |
| Warning | 水位 80%、源站慢 | Console + Email |
| High | 备份失败、数据库异常 | Email + IM |
| Critical | 水位接近 500GB、存储降级 | 多渠道 |
| Emergency | 数据丢失/入侵 | 持续提醒直至确认 |

## 8. 告警治理

- 聚合；
- 去重；
- 静默；
- 维护窗口；
- 抑制；
- 根因关联；
- 升级；
- 确认；
- 处理记录；
- Runbook。

避免对无行动价值的指标告警。

## 9. AI 运维助手

输入：

- 指标；
- 日志；
- Trace；
- 配置版本；
- 最近发布；
- 容量趋势。

输出：

- 现象；
- 影响；
- 原因候选；
- 证据；
- 风险；
- 建议；
- 验证；
- 回滚。

AI 只能执行只读检查和低风险验证，不自动执行生产高风险修改。

## 10. SLO

初期建立：

- 核心 API；
- 播放授权；
- ATS；
- 首帧；
- 数据源同步；
- 任务排队；
- 数据库备份；
- 安全扫描。

物理单点导致的长时间故障必须在 SLO 报告中明确，不通过排除统计掩盖。

## 11. 容量预测

至少预测：

- ZFS；
- 缓存；
- 正式副本；
- 衍生物；
- PostgreSQL；
- OpenSearch；
- Milvus；
- 日志；
- 备份；
- 月度流量；
- GPU 队列；
- AI 费用。
