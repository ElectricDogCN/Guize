# 06. API 与事件契约 / API and Event Contracts

## 1. 契约原则

- 外部和内部 API 均版本化；
- URL 使用 `/api/v1`；
- 字段、枚举和错误码使用英文唯一机器标识；
- 所有 OpenAPI 内容提供中英文说明；
- 长任务立即返回 `taskId`；
- 每个写操作支持幂等；
- 每个响应包含 `traceId`；
- 破坏性变更增加主版本或兼容层；
- 契约文件进入 Git 并执行兼容性测试。

## 2. 通用响应

成功：

```json
{
  "code": "SUCCESS",
  "message": "操作成功。",
  "data": {},
  "traceId": "01J..."
}
```

失败：

```json
{
  "code": "ASSET_ACCESS_DENIED",
  "message": "无权访问该资产。",
  "details": {
    "assetId": "ast_..."
  },
  "traceId": "01J..."
}
```

客户端通过 `Accept-Language` 选择 `message`，不得依赖 `message` 判断错误类型。

## 3. 资源命名

示例：

```text
/api/v1/data-sources
/api/v1/assets
/api/v1/assets/{assetId}/versions
/api/v1/assets/{assetId}/renditions
/api/v1/tasks
/api/v1/policies
/api/v1/workers
/api/v1/deployment-profiles
```

## 4. 长任务

创建：

```http
POST /api/v1/assets/{assetId}/transcode
Idempotency-Key: 77a...
```

响应：

```json
{
  "code": "ACCEPTED",
  "message": "任务已创建。",
  "data": {
    "taskId": "tsk_...",
    "status": "QUEUED",
    "statusUrl": "/api/v1/tasks/tsk_..."
  },
  "traceId": "01J..."
}
```

任务操作：

```text
POST /api/v1/tasks/{id}:pause
POST /api/v1/tasks/{id}:resume
POST /api/v1/tasks/{id}:cancel
POST /api/v1/tasks/{id}:retry
PATCH /api/v1/tasks/{id}/priority
GET /api/v1/tasks/{id}/events
```

## 5. 任务状态

```text
CREATED
QUEUED
DISPATCHING
RUNNING
PAUSING
PAUSED
WAITING_RESOURCE
WAITING_BUDGET
WAITING_APPROVAL
RETRYING
SUCCEEDED
PARTIAL_SUCCESS
FAILED
CANCELLED
```

状态变更必须符合状态机，禁止任意跳转。

## 6. SSE

用于：

- AI 流式结果；
- ASR 分段结果；
- 任务事件；
- 配置助手；
- 只读日志流。

事件格式：

```text
event: task.progress
id: 284
data: {"taskId":"tsk_...","progress":42,"stage":"TRANSCODING"}
```

支持 `Last-Event-ID` 恢复。SSE 仅传递状态和小型结果，不传递媒体正文。

## 7. WebSocket

用于：

- 管理端实时任务；
- Worker 在线状态；
- 告警推送；
- 播放质量指标；
- 临时转码会话。

WebSocket 会话必须鉴权、限流、心跳和断线恢复。

## 8. Webhook

Webhook 配置包括：

```text
endpoint
secretReference
eventTypes
retryPolicy
timeout
enabled
```

发送内容必须签名，消费者必须幂等。失败进入重试和死信视图。

## 9. 事件 Envelope

```json
{
  "eventId": "evt_...",
  "eventType": "asset.version.created",
  "eventVersion": 1,
  "aggregateType": "Asset",
  "aggregateId": "ast_...",
  "occurredAt": "2026-07-21T00:00:00Z",
  "producer": "guize-control",
  "traceId": "01J...",
  "payload": {}
}
```

## 10. Outbox

业务事务中同时写入：

- 业务表；
- Outbox 记录。

Dispatcher 读取后发布给：

- OpenSearch 索引器；
- Milvus 索引器；
- 通知服务；
- 审计派生处理；
- 推荐特征处理。

消费者按 `eventId` 去重，不能假设 exactly-once。

## 11. API 双语扩展

OpenAPI 使用：

```yaml
title: Asset ID
description: Unique identifier of the logical asset.
x-i18n:
  zh-CN:
    title: 资产 ID
    description: 逻辑资产的唯一标识。
  en-US:
    title: Asset ID
    description: Unique identifier of the logical asset.
```

开发者门户展示双语，不生成中文字段副本。

## 12. 兼容策略

- 新增可选字段：兼容；
- 新增枚举：客户端必须容忍未知枚举；
- 删除/重命名字段：破坏性；
- 改变字段语义：破坏性；
- 调整错误码：破坏性；
- 改变默认行为：需弃用通知和兼容期；
- Event payload 变化：增加 `eventVersion`。

## 13. 错误码域

```text
AUTH_*
ACCESS_*
SOURCE_*
ASSET_*
CACHE_*
STORAGE_*
MEDIA_*
AI_*
SEARCH_*
TASK_*
POLICY_*
DEPLOYMENT_*
SECURITY_*
BACKUP_*
INTERNAL_*
```

错误码必须有：

- 中英文说明；
- HTTP 状态；
- 是否可重试；
- 建议动作；
- 告警级别；
- 文档链接。

## 14. 契约门禁

每个 PR 检查：

- OpenAPI 语法；
- 破坏性变化；
- 示例可执行；
- 中英文说明完整；
- DTO 与 Schema 一致；
- Consumer-driven contract；
- Event Schema；
- 幂等和错误码；
- Trace ID；
- 权限声明。
