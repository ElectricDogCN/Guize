# POC-007 本地播放入口

本目录实现 [local-v1 规格](../../specs/poc/plans/POC-007.yaml) 的回环 TLS、OpenList 与 Range 播放验证。实际实验前固定样本、服务及 TLS 配置、资源和执行窗口。[实施交接](../../evidence/POC-007/handoff.md)

候选样本沿用 POC-003 已验证的 64 MiB 合成文件。先校对本机的实际文件身份，复用字节后为 POC-007 单独批准样本。命令无需将本机路径写入输出。

```bash
python poc/POC-07-public-network/verify_fixture.py /path/to/materialized-synthetic-sample
```

目录中的样本校验只确认实际输入字节。OpenList 挂载、TLS 代理、Range 读回、授权和性能证据随后一起接受正式实验。公网 IPv6、DDNS、Tunnel 和 CDN 保留用于生产验收。

播放入口的 OpenList 读取组件只连接回环地址的已选端口和单一合成对象。入口先完成授权，再把 Range 与 If-Range 交给组件处理。组件在送出响应头之前核对源状态、长度和区间。完整响应与部分响应共用样本摘要作为强 ETag，过期的 If-Range 回退到完整响应。传输每次最多读取 64 KiB，返回实际字节数、SHA-256 和单次读取峰值。缓存隔离、限流及端到端授权在组合实验中复验。

请求证据每条最多 256 个事件。64 MiB 样本按每次读取记事件会超限。读取观察器在实际源传输时，每 1 MiB 连续字节记录一个偏移、长度、摘要及观察时间。它随着实际缓冲增量计算摘要，最后记录不足 1 MiB 的片段。读取源失败时丢弃本次未完成的观察记录。

本地客户端先使用批准的信任材料严格校验 TLS 证书和 `localhost`，再以 64 KiB 缓冲留存解密后的完整 HTTP 响应。采集器记录实际连接提供的证书摘要，并与本地实验固定的自签名证书核对。响应头和响应体从实际连接读出，交给现有 POC 验证器核对。采集器仅连接回环地址上的固定播放入口和 OpenList 样本入口。直接样本请求不带身份，验证实际源返回的状态与字节。

`playback_gateway` 和 `replay_fixture` 是同次本地实验的服务端与采集入口。实验启动器向网关注入已配置的只读 OpenList、TLS 上下文、Grant 校验和固定的缓存区间及限流窗口。网关先校验 Grant 和限流，再查缓存或取源。采集器依次验证 Range、匹配的 If-Range、三类身份拒绝、完整读取、固定窗口限流和直接 OpenList 拒绝。每次保留独立的原始响应和响应体，使用请求 ID、追踪 ID 和实际时间核对网关处理、OpenList 请求与连续读取。大文件及区间摘要增量计算。正式实验在批准的隔离环境运行，保持端口、信任材料、样本和阈值绑定一致。

`run_local_replay.py` 将两部分接到仓库内的单一命令。启动器先准备仅在回环监听的 OpenList 与 `synthetic.bin` 只读挂载，通过标准输入管道交付临时只读凭据。命令行参数固定样本、端口、信任材料、缓存区间和限流窗口。`--preflight` 验证已记录的小样本，默认校验固定的 64 MiB 原件。命令需要一个尚不存在的证据目录，成功后保留 `.http`、`.body` 和 `replay-result.json`。

```bash
python -B poc/POC-07-public-network/run_local_replay.py --help
```

```bash
python -B -m unittest discover -s poc/POC-07-public-network -p 'test_stream_fixture.py'
```
