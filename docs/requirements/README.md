# Guize V1 需求实施基线

> GZ-004 / `REQ-V1` + `NFR-V1` + `ACCEPTANCE-TRACE-V1`

## 1. 权威层级

本目录不是第二套产品需求。冲突时始终按以下顺序解释：

1. `specs/requirements/product-requirements.md` — **APPROVED / FROZEN** 产品权威；
2. 已批准 ADR、设计与 `specs/requirements/requirements-index.yaml`；
3. 本目录的派生、机器可读实施基线；
4. 下游 Task、代码或 Agent 推断。

GZ-004 的职责是把已批准范围收敛为可验证输入，而不是扩展范围。新增/删除产品能力或关键边界变化必须另走需求/ADR 审批。

## 2. 文件与合同

| 文件 | 合同/用途 | 主要消费者 |
|---|---|---|
| `specs/requirements/v1/requirements.yaml` | `REQ-V1`：十项冻结需求、别名、范围、非目标、模块、工作包、验收、阻断和下游任务 | GZ-005～GZ-009、GZ-011、后续实现 |
| `specs/requirements/v1/nfr.yaml` | `NFR-V1`：安全、隐私、性能、容量、可用性、恢复、可观测、兼容、维护、供应链 | 契约设计、POC、GZ-011、Release |
| `specs/acceptance/requirements/acceptance.yaml` | Requirement-level 成功/失败/权限/完整性/恢复/生产门禁场景 | GZ-011、E2E/Release |
| `specs/requirements/v1/traceability.yaml` | `ACCEPTANCE-TRACE-V1`：Requirement → Module → WP → Acceptance → POC/Blocker → Task → 当前合同 | 所有下游 Agent |
| `*.schema.yaml` | 严格 JSON Schema 2020-12 合同 | CI / Reviewer |
| `specs/requirements/v1/validate.py` | 结构、跨文件语义与负向用例校验 | CI / Implementer / Reviewer |

## 3. Requirement 语义

`requirements.yaml` 必须且只能包含 `REQ-V1-0001～REQ-V1-0010`。`aliases`、`moduleIds`、`workPackages`、`acceptanceIds`、`blockers`、`nextTasks` 与既有 `requirements-index.yaml` 做 exact-set 对齐。

`statement`、`scope` 和 `nonGoals` 只收敛已批准需求/设计，不能覆盖产品权威。

## 4. NFR 与 `MEASUREMENT_REQUIRED`

NFR 使用三种测量状态：

- `FROZEN_CONSTRAINT`：仓库已经明确批准/记录的产品或环境约束，例如约 700TB 来源规模、至少 500GB 本地安全空间、单物理宿主机、ESXi 6.7、V1 无对外 Beta；
- `DESIGN_TARGET`：设计必须满足的定性目标，仍需后续 Evidence；
- `MEASUREMENT_REQUIRED`：吞吐、时延、首帧、AI 质量、搜索相关性、文件数量分布、并发、RPO/RTO 等尚无批准实测结果的指标。

`MEASUREMENT_REQUIRED` 必须 `value: null` 并声明 `verificationOwners`。POC/GZ-011 测量并审批前，禁止把这些项目写成“已达到”、PASS 或生产 SLA。

设计文档中出现的恢复目标范围仍是待验证设计目标；GZ-004 不把它们升级为实测承诺。

## 5. Acceptance 语义

每个 Requirement 至少覆盖：

- `success`：批准能力成功路径；
- `failure`：关键依赖/输入/运行时失败路径；
- `production_gate`：V1 无对外 Beta 的生产退出门禁。

按需求还强制 `permission`、`data_integrity` 和/或 `recovery`。场景使用结构化 Given/When/Then，并复用既有 Acceptance ID，不建立第二套 ID 体系。

## 6. Traceability 语义

`traceability.yaml` 对每项需求保存 exact-set 关系：

```text
Requirement
→ Module
→ Work Package
→ Acceptance
→ POC / Other Blocker
→ downstream Task
→ REQ-V1 / NFR-V1 / ACCEPTANCE-TRACE-V1
```

这里 `producedContracts` 只表示 GZ-004 当前产出的三个基线合同。OpenAPI、Event Payload、DDL、Temporal/LiteFlow/Worker/Plugin 等业务机器契约仍由 GZ-005～GZ-008 冻结。

## 7. 下游使用规则

- **GZ-005 OpenAPI**：消费 `REQ-V1`、`NFR-V1`，不能重新解释产品范围；
- **GZ-006 Event**：使用 Requirement/Acceptance 事件边界，不得提前声称 Event Contract 已冻结；
- **GZ-007 Data**：从批准 Requirement/Contract 推导 DDL，不允许无 Migration 数据行为；
- **GZ-008 Runtime**：冻结 Workflow/Policy/Worker/Plugin 运行时契约；
- **GZ-009 UI**：页面/Action/API/权限/状态/错误映射不得创建第二套业务规则；
- **GZ-011 Acceptance**：将 `MEASUREMENT_REQUIRED` 转化为 Golden Dataset、测量脚本和经批准阈值。

POC-01～10 的执行结果仍是独立 Evidence；本目录只记录它们对 Requirement/NFR 的阻断或验证责任。

## 8. 明确未冻结内容

GZ-004 完成后，以下内容仍不等于完成：

- OpenAPI / Error Catalog；
- Domain Event Payload；
- PostgreSQL/Flyway DDL；
- Temporal/LiteFlow/Worker/Plugin 运行时契约；
- POC-01～10 的任何实验结果；
- 未测量性能、容量、质量、RPO/RTO 数值；
- 业务代码、部署和生产发布。

## 9. 验证

从仓库根目录执行：

```bash
python specs/requirements/v1/validate.py
python specs/requirements/v1/validate.py --negative-fixtures
```

正常校验检查 Schema、ID/alias 唯一性、索引 exact-set、模块/Task/POC/Blocker 引用、Acceptance 双向关系、场景覆盖、Traceability 对称性和 NFR 测量策略。

负向校验必须证明至少以下错误会被拒绝：重复 alias、未知模块、缺失需求、不对称追踪、`MEASUREMENT_REQUIRED` 下伪造数值、伪造 POC PASS。
