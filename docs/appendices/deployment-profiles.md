# 部署 Profile 附录

## 验收配置与部署配置分离

GZ-021 的验收绑定 revision 1 只允许下列两种配置，并由需求/NFR/追踪/验收四份 schemaVersion 2 机器文档及需求索引一致绑定。它们不新增或改写下方既有 DeploymentProfile 机器契约枚举，也不等同于媒体编码配置版本。

| 验收配置 | 里程碑 | 需求与验收 | 生产声明 |
| --- | --- | --- | --- |
| `local-v1` version 1 | GZ-018，GZ-019 之后 | 全十需求、原十二验收；真实本地组件与可控故障 | 本地结果不能满足生产释放 |
| `production` version 1 | GZ-020 | 原全量生产验收 | 必须另满足实测资源、容量、来源、公网、安全、恢复与发布门禁 |

本地以 OpenList 模拟来源/存储入口，Windows/Linux 工作进程先形成实际编码闭环；Android 按真实能力和热/电源/网络限制准入。分片尝试和节点身份使用不同租约；不把临时 HLS 缓存计作正式副本。生产 700TB、500GB、ESXi 6.7 等原约束及百度云接入义务保留；本地实测水位、单机多进程、软件编码和协议沙箱结果必须标明范围。

验收配置必须显式选择并绑定版本与实际执行环境。未知 ID/版本、错误里程碑/范围、文件间漂移，以及用本地标签声明生产通过均拒绝。规格校验通过只证明声明一致，不授予 POC 或发布结果。

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
