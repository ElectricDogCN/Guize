# ADR-0016：边缘运行时与产品 Agent 的规划及交付边界

- Status: Proposed — 本规划经 GZ-022 独立审查和正常合入后接受；运行时按后续任务分别验收
- Date: 2026-10-22
- Task: [GZ-022 / #114](https://github.com/ElectricDogCN/Guize/issues/114)；本文不分配后续实现租约或跨仓写权限

## Context

ADR-0015 已将异构 AV1 执行与平台权威状态分离。后续还需让同一批手机和 PC 承接结构分析、离线 OCR 与产品 Agent 调用，避免为每种能力另建任务状态、权限和容量池。Android 的构建、系统权限、生命周期和升级渠道不同于平台后端，直接并入全部运行时会放大工具链和发布耦合；过早拆出 AI/Agent 仓又会增加未形成使用方的协议与发布负担。

本文的工作节点指 Android 或 Windows/Linux 执行设备，区别于现有术语表的 LiteFlow Node；产品 Agent 指用户任务的计划与工具选择能力，区别于开发和审查所用的 Agent Harness。这些区分不创建新的机器字段或越过既有契约版本。

## Decision

保留 ElectricDogCN/Guize 的资产、版本、IAM/POLICY、统一任务、计划和结果接受权威。公共执行协议先在主仓按既有契约所有权定义，再由独立任务建设 `guize-edge-runtime`；Android 与 Windows/Linux 消费同版协议，节点只在授权 attempt、数据范围和资源预算内执行。MOD-TASK 负责持久计划与派发，MOD-WORKER 负责工作节点，MOD-AI 提供受约束产品 Agent，MOD-EDGE 仍负责网关与 ATS。节点及能力包不直接修改业务数据库，Agent 不放宽权限、质量或预算。

依赖先为公共协议→节点→共用资源约束。AV1/HLS 消费 GZ-016 媒体基础；六帧闭环消费 GZ-011/013 基础，在固定授权视频和六个采样点上返回实际解码图像与可校验元数据。离线 OCR 后接六帧及 POC-009/GZ-011 的独立质量基线；产品 Agent 消费已验证工具；最后以 GZ-018 交接及全部交付形成非空最终联合验收。编码、分析与 OCR 共用容量账本，播放预留和资源硬约束先行；过期观测、已取消或旧尝试不得取得执行或发布权。规划完成不能替代上述运行验证。

首批使用 OnePlus 8T（KB2000）、Android VM 和闲置 Windows/Linux 设备，不以 root、GPU/NPU、持续后台或手机实时 AV1 为前置保证。VM 验证可重复协议与故障路径，温升、后台生命周期及持续吞吐分别留给真实环境。来源/存储先采用本地 OpenList/WebDAV，百度生产接入后置；本地结果不替代原生产义务。

各仓分别登记 Task、路径权限和 Evidence，通过不可变协议/SDK、节点、能力包制品交接；系统锁定平台提交、版本、摘要/签名、兼容矩阵和真实联合验收证据。发布遵循服务端兼容→协议制品→节点灰度→按能力启用；恢复先停新派发、处理活动尝试，再禁用问题能力并恢复上个已接受组合，不能把新检查点强交旧节点。`guize-ai-services` 待独立依赖/发布需求明确后建立，通用 Agent 运行时仓继续后置。

## Consequences

这一边界降低平台与设备工具链的耦合，同时增加跨仓兼容、签名制品、固定组合验收及恢复的责任。保留一个平台权威和共用资源约束，避免各能力或仓库各自宣布成功、重复预留同一设备或复制高风险名额。GZ-022 只完成正式规划；后续任务各自获得合法权限并以真实制品、设备、样本、命令和结果证明能力，原 V1、十 POC、GZ-020 及已完成历史不变。

参考：[系统架构](../docs/03-system-architecture.md)、[路线图](../docs/20-roadmap-and-wbs.md)、[仓库规划](../docs/22-repository-and-directory-plan.md)、[ADR-0015](0015-heterogeneous-av1-workers-and-local-storage-validation.md)。
