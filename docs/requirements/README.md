# Guize V1 需求实施基线

> GZ-004 / `REQ-V1` + `NFR-V1` + `ACCEPTANCE-TRACE-V1`

## 1. 权威层级

本目录不是第二套产品需求。冲突时始终按以下顺序解释：

1. `specs/requirements/product-requirements.md` — **APPROVED / FROZEN** 产品权威；
2. 已批准 ADR、设计、`specs/requirements/requirements-index.yaml` 与 canonical Program Plan；
3. 本目录的派生、机器可读实施基线；
4. 下游 Task、代码或 Agent 推断。

GZ-004 的职责是把已批准范围收敛为可验证输入，而不是扩展范围。新增/删除产品能力或关键边界变化必须另走需求/ADR 审批。

`requirements.yaml` 中的 `aliases`、`moduleIds`、`workPackages`、`acceptanceIds`、`blockers`、`nextTasks` 必须与只读 `requirements-index.yaml` 保持 exact-set；本任务不得为了修补追踪缺口回写索引。

## 2. 文件与合同

| 文件 | 合同/用途 | 主要消费者 |
|---|---|---|
| `specs/requirements/v1/requirements.yaml` | `REQ-V1`：十项冻结需求、别名、范围、非目标、模块、工作包、验收、阻断和下游任务 | GZ-005～GZ-009、GZ-011、后续实现 |
| `specs/requirements/v1/nfr.yaml` | `NFR-V1`：安全、隐私、性能、容量、可用性、恢复、可观测、兼容、维护、供应链 | 契约设计、POC、GZ-011、Release |
| `specs/acceptance/requirements/acceptance.yaml` | Requirement-level 成功/失败/权限/完整性/恢复/生产门禁场景 | GZ-011、E2E/Release |
| `specs/requirements/v1/traceability.yaml` | `ACCEPTANCE-TRACE-V1`：Requirement → Module → WP → Acceptance → POC/Blocker → Task → 当前合同 | 所有下游 Agent |
| `*.schema.yaml` | 严格 JSON Schema 2020-12 合同 | CI / Reviewer |
| `specs/requirements/v1/validate.py` | Schema、跨文件语义、canonical exact-set 与负向用例校验 | CI / Implementer / Reviewer |

## 3. Requirement 语义

`requirements.yaml` 必须且只能包含 `REQ-V1-0001～REQ-V1-0010`。产品范围仍由 `product-requirements.md` 决定。

本派生基线补充了已有治理规则的可执行解释，包括：

- 权限 scope 在搜索关键词/向量召回前生效，并保留最终结果 ACL 复核；
- 同内容多来源仍保留每个 SourceObject 的 ACL、标签、路径、Retention 等来源级策略；
- 删除单个来源只影响来源可用性，不自动删除逻辑 Asset；
- AI 派生产物继承 Asset ACL，低置信度必须保留 uncertainty/confidence；
- 生成式缩略图必须有机器可读 generated 标记并在展示层与真实关键帧区分；
- 缓存淘汰不得改变 Asset 元数据、正式 Replica 或 Retention；
- FFmpeg/媒体处理必须限制协议、路径和资源，不能形成开放代理；
- 管理员高风险发布、ACL、Secret、破坏性动作必须进行 step-up/重新认证；
- 长任务必须具备重试、暂停、恢复、取消和可观察状态转换。

这些规则来自已批准需求、设计和仓库治理约束，不代表新增产品范围。

## 4. NFR 与 `MEASUREMENT_REQUIRED`

NFR 使用三种测量状态：

- `FROZEN_CONSTRAINT`：仓库已经明确批准/记录的产品或环境约束，例如约 700TB 来源规模、至少 500GB 本地安全空间、单物理宿主机、ESXi 6.7、V1 无对外 Beta；
- `DESIGN_TARGET`：设计必须满足的定性目标，仍需后续 Evidence；
- `MEASUREMENT_REQUIRED`：吞吐、时延、首帧、AI 质量、搜索相关性、文件数量分布、并发、RPO/RTO、商业 Provider 预算/调用配额具体数值等尚无批准实测结果的指标。

`MEASUREMENT_REQUIRED` 必须 `value: null`、`unit: null` 并声明 `verificationOwners`。POC/GZ-011 测量并审批前，禁止把这些项目写成已达到、PASS 或生产 SLA。

商业 AI/外部 Provider 的**控制机制**已经是硬要求：调用前必须检查调用者权限、当前 Asset ACL、数据策略，并执行硬预算/配额门禁；但具体预算/配额数字仍由后续批准配置或测量确定。

## 5. Acceptance 与 Program supplement

每个 Requirement 至少覆盖 `success` 和 `failure`，并按需求强制 `permission`、`data_integrity`、`recovery`、`production_gate`。

`requirements-index.yaml` 中已有的 Requirement→Acceptance 集合保持不变。当前仓库还存在一个历史追踪不一致：canonical Program Plan 的 GZ-011/GZ-016/GZ-020 已引用 `验收V1-0005`，而只读 Requirement Index 的 `REQ-V1-0003.acceptanceIds` 未包含该 ID。

GZ-004 不回写只读索引，也不把这个差异伪装成索引已有内容，而是：

- 在 Acceptance catalogue 中建立 `验收V1-0005`，范围仅覆盖已经存在的 AV1/ABR 质量、重试/恢复、FFmpeg 安全边界和媒体产物 provenance；
- 该记录标记 `PROGRAM_SUPPLEMENT`，source 固定为 `specs/coordination/program-plan.yaml`；
- `requirements.yaml` 的 `REQ-V1-0003.acceptanceIds` 仍保持索引 exact-set；
- `traceability.yaml.programAcceptanceIds` 单独记录该 Program-derived supplement。

## 6. Traceability 与 POC provenance

`traceability.yaml` 分两层记录 POC：

- `pocIds`：严格由 `requirements-index.yaml.blockers` 中 `POC-xx` 项派生；
- `programPocIds`：严格由 canonical Program Plan 顶层 `pocs[].requirementIds` 派生。

因此例如：

- POC-05 的 Program mapping 同时覆盖 `REQ-V1-0001` 与 `REQ-V1-0002`；
- POC-08 的 Program mapping 覆盖 `REQ-V1-0009`；

即使这些关系没有出现在只读 Requirement Index 的 blocker 集合中，也不会被静默丢失或反向篡改索引。

每项 Trace 仍只声明 GZ-004 当前产出的三个合同：

```text
REQ-V1
NFR-V1
ACCEPTANCE-TRACE-V1
```

OpenAPI、Event Payload、DDL、Temporal/LiteFlow/Worker/Plugin 等业务机器契约仍由 GZ-005～GZ-008 冻结。

## 7. 下游使用规则

- **GZ-005 OpenAPI**：消费 `REQ-V1`、`NFR-V1`，不能重新解释产品范围；
- **GZ-006 Event**：使用 Requirement/Acceptance 事件边界，不得提前声称 Event Contract 已冻结；
- **GZ-007 Data**：从批准 Requirement/Contract 推导 DDL，不允许无 Migration 数据行为；
- **GZ-008 Runtime**：冻结 Workflow/Policy/Worker/Plugin 运行时契约；
- **GZ-009 UI**：页面/Action/API/权限/状态/错误映射不得创建第二套业务规则；
- **GZ-011 Acceptance**：消费 Requirement/NFR/Acceptance/Traceability，并将 `MEASUREMENT_REQUIRED` 转化为 Golden Dataset、测量脚本和经批准阈值。

POC-01～10 的执行结果仍是独立 Evidence；本目录只记录阻断、Program mapping 和验证责任，不声称任何 POC 已 PASS。

## 8. 明确未冻结内容

GZ-004 完成后，以下内容仍不等于完成：

- OpenAPI / Error Catalog；
- Domain Event Payload；
- PostgreSQL/Flyway DDL；
- Temporal/LiteFlow/Worker/Plugin 运行时契约；
- POC-01～10 的任何实验结果；
- 未测量性能、容量、质量、RPO/RTO、Provider 预算/配额数值；
- 业务代码、部署和生产发布。

## 9. 验证

从仓库根目录执行：

```bash
python specs/requirements/v1/validate.py
python specs/requirements/v1/validate.py --negative-fixtures
```

正常校验同时检查 Schema、十项 Requirement、alias 唯一性、只读索引 exact-set、Module/Task/POC/Blocker 引用、Acceptance 双向关系、必需场景覆盖、Program supplemental provenance、Traceability 对称性、Program POC 映射和 NFR 测量策略。

负向校验必须证明至少以下错误会被拒绝：重复 alias、未知模块、缺失需求、不对称追踪、`MEASUREMENT_REQUIRED` 下伪造数值、伪造 POC PASS。
