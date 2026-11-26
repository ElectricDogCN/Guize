# 登记结果

固定源与实际合并主线分别记录检查命令和退出码。

## Workflow 与 Activity 契约首批验证

Windows 原生与 Ubuntu WSL 均校验了工程基线十个 Workflow 及同一合成策略，策略 SHA-256 为 `d18f99947887ea2e1e46b84dc1717d27101132abd55d66bde2586ebc87078cc0`。两处各六项离线检查通过，覆盖合法配置、类型替换、遗漏或超时的心跳、错误的截止时间、无限重试、超大的退避值、业务拒绝重试及 YAML 和 JSON 重复字段。[契约与运行边界](../../../contracts/workflows/v1/README.md)

```bash
python -B specs/contracts/runtime/check_workflow_contract.py specs/contracts/runtime/fixtures/workflow-policy-v1.json
python -B -m unittest discover -s specs/contracts/runtime -p test_workflow_contract.py
```

## 四类契约实施验证

Windows 原生与 Ubuntu WSL 各通过 28 项离线单元及组合检查。规范化重放保留已完成结果，仅返回尚未调度且依赖就绪的步骤。重复读取同一快照结果相同，取消停止新派发，执行完毕后转入 TASK 对账。Policy 用例核对版本与摘要、批准范围、决策上下文、资源预算和 P0 优先级。插件用例覆盖能力包兼容、插件缺席、局部故障及输出权限。组合用例由策略 P0 建议推进到已锁定 AV1 能力包与 Worker 领取，并核对现有 TASK 接受事件。

两个环境独立构建并重新解包的 Worker 参考 SDK `1.0.0` 均为 37,742 字节，SHA-256 为 `debb66b4a493abd8ba21fdaa5725372aba04e108fe2028d843fa8ffff66f8f04`。解包副本各执行同一份 40 个协议用例，结果一致。用例 SHA-256 为 `2bfe772731446f04719ad2b490443741ee0266a28970755a8c404d41cf06ac8b`，协议 Schema SHA-256 为 `45cac8900d332fa4aebed0c300d8aba19df7551046ef042d4a00cabd7867ad65`。SHA-256 取仓库 LF 字节。[Worker 运行边界](../../../contracts/workers/v1/README.md)

预审发现 Worker 校验对内部状态旗标使用了通用真值判断。修订后 TASK 内部快照使用明确的布尔、期限、状态、预算和进度类型。两套环境的依赖组合对时区格式的支持不同，参考实现现统一要求明确时区和最多六位小数秒。新增用例覆盖缺失或无效的授权状态、节点会话状态、预留状态、续租期限、时间及产物字节数。

PR 审查发现初次领取租约需显式短于或等于资源预留期限。修订后该期限约束在开始和运行中统一生效，续租仍取审批、任务和资源三个期限的最早值。用例分别验证期限相同可领取，以及资源预留仍有效但会先于执行租约结束时拒绝领取。

```bash
python -B -m unittest discover -s specs/contracts/runtime -p 'test_*.py'
python -B specs/contracts/runtime/check_workflow_contract.py specs/contracts/runtime/fixtures/workflow-policy-v1.json --replay specs/contracts/runtime/fixtures/workflow-replay-v1.json
```

复现 SDK 时使用 [构建入口](../../../specs/contracts/runtime/build_worker_sdk.py) 写入空临时目录，将 ZIP 解包后直接执行包内的 `check_worker_contract.py`，并传入原始 [协议用例](../../../specs/contracts/runtime/fixtures/worker-conformance-v1.json)。结果限于合成输入和参考实现。Temporal 真实历史回放、LiteFlow 部署、Android Worker、实体设备以及远端发布证明由对应集成任务验证。
