# POC-007 本地播放入口

本目录实现 [local-v1 规格](../../specs/poc/plans/POC-007.yaml) 的回环 TLS、OpenList 与 Range 播放验证。实际实验前固定样本、服务及 TLS 配置、资源和执行窗口。[实施交接](../../evidence/POC-007/handoff.md)

候选样本沿用 POC-003 已验证的 64 MiB 合成文件。先校对本机的实际文件身份，复用字节后为 POC-007 单独批准样本。命令无需将本机路径写入输出。

```bash
python poc/POC-07-public-network/verify_fixture.py /path/to/materialized-synthetic-sample
```

目录中的样本校验只确认实际输入字节。OpenList 挂载、TLS 代理、Range 读回、授权和性能证据随后一起接受正式实验。公网 IPv6、DDNS、Tunnel 和 CDN 保留用于生产验收。
