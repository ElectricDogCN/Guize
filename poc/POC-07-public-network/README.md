# POC-007 本地播放入口

本目录实现 [local-v1 规格](../../specs/poc/plans/POC-007.yaml) 的回环 TLS、OpenList 与 Range 播放验证。实际实验前固定样本、服务及 TLS 配置、资源和执行窗口。[实施交接](../../evidence/POC-007/handoff.md)

候选样本沿用 POC-003 已验证的 64 MiB 合成文件。先校对本机的实际文件身份，复用字节后为 POC-007 单独批准样本。命令无需将本机路径写入输出。

```bash
python poc/POC-07-public-network/verify_fixture.py /path/to/materialized-synthetic-sample
```

目录中的样本校验只确认实际输入字节。OpenList 挂载、TLS 代理、Range 读回、授权和性能证据随后一起接受正式实验。公网 IPv6、DDNS、Tunnel 和 CDN 保留用于生产验收。

播放入口的 OpenList 读取组件只连接回环地址的已选端口和单一合成对象。入口先完成授权，再把 Range 与 If-Range 交给组件处理。组件在送出响应头之前核对源状态、长度和区间。完整响应与部分响应共用样本摘要作为强 ETag，过期的 If-Range 回退到完整响应。传输每次最多读取 64 KiB，返回实际字节数、SHA-256 和单次读取峰值。缓存隔离、限流及端到端授权在组合实验中复验。

请求证据每条最多 256 个事件。64 MiB 样本按每次读取记事件会超限。读取观察器在实际源传输时，每 1 MiB 连续字节记录一个偏移、长度、摘要及观察时间。它随着实际缓冲增量计算摘要，最后记录不足 1 MiB 的片段。读取源失败时丢弃本次未完成的观察记录。

```bash
python -B -m unittest discover -s poc/POC-07-public-network -p 'test_stream_fixture.py'
```
