# Domain Events V1

本目录定义归泽 V1 的领域事件。机器标识、字段和枚举只有一套英文名称；以下中文说明与后面的英文说明使用同一份目录和 Schema。

控制面所属业务模块在同一个 PostgreSQL 事务中提交业务状态和 Outbox。Worker 与 Connector 通过运行时协议报告结果，由控制面校验后发布权威事件；它们不能直接更新核心数据库或自行发布业务事实。事件可重复、乱序投递，消费者以 `(consumerId,eventId)` 去重，把可事务化的业务副作用与处理标记一并提交；外部副作用使用幂等操作或新的持久 Outbox。聚合修订号用于避免应用过期状态，事件 ID 不等于任务 SSE 游标。

Payload 结构或语义变化必须增加 `eventVersion`，并保留已发布旧版本。消费者明确支持每个版本或经测试的适配器；未知版本保留并隔离，不能自动当作 V1 执行。来源变化不等于内容变化，来源删除不等于删除逻辑资产。收到事件也不代表获得资源访问权限：来源、媒体、AI、索引的读取与展示必须重新检查权威资产权限和安全状态。

完整缓存和副本校验事件必须绑定权威版本、完整字节数、完整哈希、回读时间及留存测量记录；上传完成、切片命中或校验器通过均不能代替物理验证。完整缓存不等于正式副本或备份。媒体和 AI 发布需要已准入结果与可追溯输入、工具、模型、Prompt、流水线和参数；置信度与进度必须是有限数值，生成缩略图不得冒充真实帧，任务进度不得替代成功状态。策略事件仅引用经审批的不可变版本，不携带可执行规则。下面的验证命令只证明契约与兼容规则，不证明实际 Outbox、Worker、播放、OpenList 或完整 V1 运行验收。

`catalog.json` registers event type/version, business producer, consumers, aggregate identity, revision, payload schema, compatibility and idempotency. The common Envelope remains the established platform Envelope. Each registered schema additionally binds the concrete type/version/producer, required payload and aggregate type.

| Event | Aggregate | Business producer |
| --- | --- | --- |
| source.object.observed | SourceObject | MOD-SOURCE |
| source.object.deleted | SourceObject | MOD-SOURCE |
| asset.created | Asset | MOD-ASSET |
| asset.version.created | Asset | MOD-ASSET |
| cache.complete.verified | CacheEntry | MOD-STORAGE |
| replica.verified | Replica | MOD-STORAGE |
| rendition.published | Rendition | MOD-MEDIA |
| artifact.published | DerivedArtifact | MOD-AI |
| task.status.changed | Task | MOD-TASK |
| policy.published | PolicyDefinition | MOD-POLICY |

The deployed producer name is `guize-control`; a Worker or Connector reports results through its versioned service contract. It does not publish authoritative domain events or update core tables directly. The owning business module validates the operation and writes its business state and Outbox row in the same PostgreSQL transaction.

## 执行、取消和资源事件

新增事件由 MOD-TASK 通过控制面发布，当前授权订阅模块为 MOD-AUDIT 和 MOD-OBS。执行节点按任务协议上报，任务模块校验并提交已发生的业务事实。

| 事件 | 聚合 | 记录的事实 |
| --- | --- | --- |
| `task.plan.accepted` | TaskPlan | 固化计划版本和计划摘要。 |
| `task.step.ready` | TaskStep | 记录满足依赖与策略条件的已就绪步骤。 |
| `task.attempt.leased` | TaskAttempt | 绑定尝试、节点、输入版本、摘要、fencing 和失效时刻。 |
| `task.attempt.cancellation.requested` | TaskAttempt | 记录取消意图以及目标 fencing。 |
| `task.attempt.cancelled` | TaskAttempt | 记录控制面确认的取消结果。 |
| `task.attempt.result.accepted` | TaskAttempt | 记录已通过租约、fencing、取消和产物校验的唯一结果。 |
| `task.attempt.capability.bound` | TaskAttempt | 记录被选用的能力版本和执行协议版本。 |
| `task.resource.reserved` | TaskResourceReservation | 记录具体尝试的独立资源预留、数量和期限。 |
| `task.resource.released` | TaskResourceReservation | 释放精确预留，绑定同一尝试和 fencing。 |

同一逻辑步骤上的 fencing 递增。控制面只有在租约有效、尝试与最新 fencing 对应、取消状态允许且输入和产物摘要匹配时，才通过事务或条件写接受业务结果。取消请求和取消结果各自记录。样例中先取消一个尝试，再以更高 fencing 接受同一步骤的另一次尝试。重放释放事件以预留 ID 和修订号去重，同一尝试的旧 fencing 不作用于新预留。

资源种类定义计量单位。编解码器与执行槽按个数计，内存和临时存储按字节计，系统执行预算按秒计。契约校验覆盖结构、聚合身份、时间及版本。运行时的单次接受、资源公平和恢复由后续实现及其用例验证。

## Delivery and idempotency

Delivery is at least once. An Outbox dispatcher can redeliver after a crash. It must preserve the original `eventId` and contents; retry does not create a new fact. Consumers enforce a unique `(consumerId,eventId)` processed identity. For transactional effects, business changes and the processed marker commit together. External effects require an idempotent operation or another durable Outbox; a consumer must not perform an irreversible effect before recording processing state. A domain event ID is independent of the numeric cursor used by the Task SSE API.

Every payload carries the owning aggregate's `revision`. Consumers must reject stale effects and tolerate redelivery and reordering; no global ordering is assumed. Rebuildable views may refresh from authoritative state rather than blindly applying a stale snapshot. A failed or unknown event is retained for diagnosis/replay and does not acknowledge successful business processing. Schema validation does not implement a dispatcher, database transaction or deduplication store.

## Version compatibility

Payload shape or semantic changes increment `eventVersion`, including optional field additions, consistent with the established event compatibility policy. Old schemas remain immutable and registered. During rolling upgrades, old and new versions can coexist. Consumers explicitly register and test supported versions or an explicit adapter; there is no implicit fallback from an unknown version to V1. Unsupported versions are retained/quarantined without business side effects. `compare_versions` rejects removing or mutating an existing schema or its semantic/identity rules. Adding a consumer does not alter the payload version.

## Identity, permissions and evidence

`aggregateId` must equal the registered payload aggregate key. `asset.version.created` belongs to the Asset aggregate: `versionNumber` identifies content while `revision` identifies aggregate mutation. A source move/rename alone does not create a content version. Source deletion requires retained confirmed deletion evidence and changes source availability; it never authorizes deleting the Asset.

Events remain on the authenticated internal bus. They contain bounded identifiers and provenance, not credentials, raw media, executable policy text or derived content. Receipt is not an access grant. Consumers resolve the current authoritative Asset ACL and security state before exposing source, media, AI or indexed information; derived outputs inherit the parent Asset's permissions. Snapshot visibility never overrides current authorization.

Complete-cache and replica events require matching full hashes, a retained measurement identity and a completed verification time. The storage application must bind that measurement to the pinned authoritative version, full length and readback before committing the event. Upload alone, ATS/HLS slice hits, a matching hash-shaped string or this validator's green result cannot prove those physical measurements. Complete cache does not become a formal replica/backup. `failureDomainId` must represent the real failure domain and a single event does not prove recovery redundancy.

Rendition publication requires admitted quality, input/output hashes and encoder/profile provenance; HLS publication additionally needs verified manifest, segments and decoder measurements in the media application. Artifact publication preserves model/prompt/pipeline/parameters, uncertainty and generated-thumbnail truth. A published policy points to an approved immutable version and hash; it does not embed executable rules. Task progress never substitutes for authoritative workflow state, output admission or lease fencing.

## Validation

Run from the repository root:

```text
python specs/contracts/events/check_contract.py
python specs/contracts/events/test_contract.py
python specs/contracts/events/check_contract.py --event specs/contracts/events/examples/asset.created-v1.json
python specs/contracts/events/check_contract.py --previous-root PATH_TO_PREVIOUS_CHECKOUT
```

The validator resolves registered local schemas offline using JSON Schema Draft 2020-12, checks formats and cross-field identity/hash/time rules, and produces no business side effects. Confidence and progress must be finite numbers; the JSON reader rejects nonstandard NaN/Infinity constants rather than treating them as valid JSON. The tests cover positive examples, required fields, unknown versions, source/asset separation, full verification, publication provenance, generated-thumbnail truth, task bounds and version coexistence/immutability. These contract checks do not establish Worker encoding, actual Outbox/deduplication transactions, HLS playback, OpenList operation or full V1 acceptance.
