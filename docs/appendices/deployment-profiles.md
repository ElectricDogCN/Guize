# 部署 Profile 附录

## 正式 Profile

```text
single-node-demo
control-plane
edge-media-a380
ai-worker-nvidia
av1-worker-ada
cpu-worker
search-node
observability-node
single-site-full
distributed-full
custom
```

## Profile 结构

```yaml
apiVersion: guize.io/v1
kind: DeploymentProfile
metadata:
  name: edge-media-a380
  version: 1.0.0
spec:
  runtime: docker-compose
  requirements:
    architecture: amd64
    cpuCores: 8
    memoryGiB: 16
    gpu:
      vendor: intel
      capabilities:
        - AV1_ENCODE
        - H264_ENCODE
    workspaceGiB: 100
  services:
    - guize-worker-agent
    - guize-media-service
  optionalServices:
    - guize-thumbnail-service
  security:
    signatureRequired: true
    secretsRequired:
      - worker-registration
```

## 校验结果

- `PASS`：满足；
- `WARN`：可强制继续，记录风险；
- `BLOCK`：不可绕过的兼容、安全或数据风险。

## BLOCK 示例

- 架构不兼容；
- 必需 GPU 不存在；
- Secret 缺失；
- 镜像签名失败；
- Digest 不一致；
- 数据库版本不兼容；
- 安全水位不足；
- 配置 Schema 无效。
