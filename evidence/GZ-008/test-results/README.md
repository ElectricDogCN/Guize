# 登记结果

固定源与实际合并主线分别记录检查命令和退出码。

## Workflow 与 Activity 契约首批验证

Windows 原生与 Ubuntu WSL 均校验了工程基线十个 Workflow 及同一合成策略，策略 SHA-256 为 `d18f99947887ea2e1e46b84dc1717d27101132abd55d66bde2586ebc87078cc0`。两处各六项离线检查通过，覆盖合法配置、类型替换、遗漏或超时的心跳、错误的截止时间、无限重试、超大的退避值、业务拒绝重试及 YAML 和 JSON 重复字段。[契约与运行边界](../../../contracts/workflows/v1/README.md)

```bash
python -B specs/contracts/runtime/check_workflow_contract.py specs/contracts/runtime/fixtures/workflow-policy-v1.json
python -B -m unittest discover -s specs/contracts/runtime -p test_workflow_contract.py
```

## 四类契约实施验证

Windows 原生与 Ubuntu WSL 各通过 26 项离线单元及组合检查。规范化重放保留已完成结果，仅返回尚未调度且依赖就绪的步骤。重复读取同一快照结果相同，取消停止新派发，执行完毕后转入 TASK 对账。Policy 用例核对版本与摘要、批准范围、决策上下文、资源预算和 P0 优先级。插件用例覆盖能力包兼容、插件缺席、局部故障及输出权限。组合用例由策略 P0 建议推进到已锁定 AV1 能力包与 Worker 领取，并核对现有 TASK 接受事件。

两个环境独立构建并重新解包的 Worker 参考 SDK `1.0.0` 均为 32,456 字节，SHA-256 为 `f91a958b388af672e2e978de4786ba2691274a791df04229949f92fe6e2e11ad`。解包副本各执行同一份 32 个协议用例，结果一致。用例 SHA-256 为 `fcd0fd57d929b711e1179c26c690727b66ac8e933216d4e465c6ea20e7f26362`，协议 Schema SHA-256 为 `0567c0aca3d306233e0ff8205f8afb7a5d19297485bfcee797682088f22c0dce`。SHA-256 取仓库 LF 字节。[Worker 运行边界](../../../contracts/workers/v1/README.md)

```bash
python -B -m unittest discover -s specs/contracts/runtime -p 'test_*.py'
python -B specs/contracts/runtime/check_workflow_contract.py specs/contracts/runtime/fixtures/workflow-policy-v1.json --replay specs/contracts/runtime/fixtures/workflow-replay-v1.json
```

复现 SDK 时使用 [构建入口](../../../specs/contracts/runtime/build_worker_sdk.py) 写入空临时目录，将 ZIP 解包后直接执行包内的 `check_worker_contract.py`，并传入原始 [协议用例](../../../specs/contracts/runtime/fixtures/worker-conformance-v1.json)。结果限于合成输入和参考实现。Temporal 真实历史回放、LiteFlow 部署、Android Worker、实体设备以及远端发布证明由对应集成任务验证。
