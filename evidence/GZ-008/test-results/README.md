# 登记结果

固定源与实际合并主线分别记录检查命令和退出码。

## Workflow 与 Activity 契约首批验证

Windows 原生与 Ubuntu WSL 均校验了工程基线十个 Workflow 及同一合成策略，策略 SHA-256 为 `d18f99947887ea2e1e46b84dc1717d27101132abd55d66bde2586ebc87078cc0`。两处各六项离线检查通过，覆盖合法配置、类型替换、遗漏或超时的心跳、错误的截止时间、无限重试、超大的退避值、业务拒绝重试及 YAML 和 JSON 重复字段。[契约与运行边界](../../../contracts/workflows/v1/README.md)

```bash
python -B specs/contracts/runtime/check_workflow_contract.py specs/contracts/runtime/fixtures/workflow-policy-v1.json
python -B -m unittest discover -s specs/contracts/runtime -p test_workflow_contract.py
```

后续结合 Policy、Worker 和 Plugin 契约验证部署配置、真实执行和跨端一致性。
