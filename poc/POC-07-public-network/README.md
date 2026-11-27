# POC-007 本地播放入口

本目录实现 [local-v1 规格](../../specs/poc/plans/POC-007.yaml) 的回环 TLS、OpenList 与 Range 播放验证。实际实验前固定样本、服务及 TLS 配置、资源和执行窗口。[实施交接](../../evidence/POC-007/handoff.md)

候选样本沿用 POC-003 已验证的 64 MiB 合成文件。先校对本机的实际文件身份，复用字节后为 POC-007 单独批准样本。命令无需将本机路径写入输出。

```bash
python poc/POC-07-public-network/verify_fixture.py /path/to/materialized-synthetic-sample
```

目录中的样本校验只确认实际输入字节。OpenList 挂载、TLS 代理、Range 读回、授权和性能证据随后一起接受正式实验。公网 IPv6、DDNS、Tunnel 和 CDN 保留用于生产验收。

播放入口的 OpenList 读取组件只连接回环地址的已选端口和单一合成对象。入口先完成授权，再把 Range 与 If-Range 交给组件处理。组件在送出响应头之前核对源状态、长度和区间。完整响应与部分响应共用样本摘要作为强 ETag，过期的 If-Range 回退到完整响应。传输每次最多读取 64 KiB，返回实际字节数、SHA-256 和单次读取峰值。缓存隔离、限流及端到端授权在组合实验中复验。

请求证据每条最多 256 个事件。64 MiB 样本按每次读取记事件会超限。读取观察器在实际源传输时，每 1 MiB 连续字节记录一个偏移、长度、摘要及观察时间。它随着实际缓冲增量计算摘要，最后记录不足 1 MiB 的片段。读取源失败时丢弃本次未完成的观察记录。

回环请求超过采集大小上限时，采集器失败退出，保留已写入的片段、实际发出请求和首次收到响应的 UTC 时间。失败诊断只记录时间和字节数，供复核限流试验是否落在固定窗口内。

本地客户端先使用批准的信任材料严格校验 TLS 证书和 `localhost`，再以 64 KiB 缓冲留存解密后的完整 HTTP 响应。采集器记录实际连接提供的证书摘要，并与本地实验固定的自签名证书核对。响应头和响应体从实际连接读出，交给现有 POC 验证器核对。采集器仅连接回环地址上的固定播放入口和 OpenList 样本入口。直接样本请求不带身份，验证实际源返回的状态与字节。

`playback_gateway` 和 `replay_fixture` 是同次本地实验的服务端与采集入口。实验启动器向网关注入已配置的只读 OpenList、TLS 上下文、Grant 校验和固定的缓存区间及限流窗口。网关先校验 Grant 和限流，再查缓存或取源。采集器依次验证 Range、匹配的 If-Range、三类身份拒绝、完整读取、固定窗口限流和直接 OpenList 拒绝。每次保留独立的原始响应和响应体，使用请求 ID、追踪 ID 和实际时间核对网关处理、OpenList 请求与连续读取。大文件及区间摘要增量计算。正式实验在批准的隔离环境运行，保持端口、信任材料、样本和阈值绑定一致。

`run_local_replay.py` 将两部分接到仓库内的单一命令。启动器先准备仅在回环监听的 OpenList 与 `synthetic.bin` 只读挂载，通过标准输入管道交付临时只读凭据。命令行参数固定样本、端口、信任材料、缓存区间和限流窗口。`--preflight` 验证已记录的小样本，默认校验固定的 64 MiB 原件。命令需要一个尚不存在的证据目录，成功后保留 `.http`、`.body` 和 `replay-result.json`。

```bash
python -B poc/POC-07-public-network/run_local_replay.py --help
```

管理与产物使用独立的 [本地验证入口](run_local_resource_replay.py)。准备回环 OpenList 的只读管理接口和独立产物挂载，经标准输入传入 JSON 的 `management` 与 `worker` 两项临时身份。传入已批准的小型 `output.bin` 样本。命令以源端口和样本路径启动回环网关，先验证管理身份或有期限的样本 Grant，再读取对应真实 OpenList 路径。验证器记录授权读回、普通身份的明确 HTTP 拒绝及实际源读取次数。验证范围为本地应用边界预检。

使用 `--evidence-dir` 指定新目录，保留两次普通身份请求的实际 HTTP 拒绝、独立响应体及 `resource-replay.json`。回执核对请求和追踪编号、回环连接、网关实测判定时间及响应摘要。在临时目录校验 HTTP 403 与空响应体后才移入留证目录。

正式采集准备使用 [同窗口采集入口](run_local_access_replay.py)。一个已准备的回环 OpenList 同时挂载播放和产物样本。固定播放及受控入口端口，经标准输入传入 `playback`、`management`、`worker` 的临时身份。两个采集器分别保留原件，最后写入记录实际执行窗口和两个回执摘要的 `access-replay.json`。该回执用于组装正式结果及审核材料。

使用 `--grant-schedule` 读取固定的播放授权时间。JSON 包含 `grantValidFrom`、`grantValidUntil` 和 `expiredAt`，均使用 UTC。开始时当前授权须有效，过期授权须已失效。回执保存实际采用的授权与身份引用，供独立审查核对。

逐请求记录保存实际采集进程号、请求开始时间及单次接收峰值。TLS 播放响应还保存严格校验过的主机名。请求开始时间在握手完成后采集，并用于核对网关判定的顺序。输出不含发出的授权头。

使用 `--native-transport` 时，每个 TLS 播放请求由独立的请求进程启动严格验证的 TLS 客户端。回执保留实际命令、TLS 进程和退出状态。TLS 客户端的标准输出与留存 JSON 按字节核对，响应从同一个 TLS 客户端读回。本地单证书模式要求已验证的对端证书精确匹配批准的回环证书。

该选项也为直接来源、管理、Worker 产物三条回环 HTTP 请求记录实际独立命令、PID 和目标。组合入口将这些回执写入同一实验窗口的两份结果文件。单独运行资源入口时，使用该选项需同时传入 `--evidence-dir`。

组合入口可同时传入 `--transport-context`，将预先固定的资源、路径、受测版本、样本和 ACL 信息写入逐次限流回执和 `access-outcome.json`。报告引用九次实际请求及五次限流回执，绑定命令、响应和授权事件，并为播放用例绑定独立 TLS 握手。管理和产物入口的拒绝时间取自网关。OpenList 的直接拒绝用客户端实测到达时间记录。正式运行时从仓库根目录传入相对 `--output` 和 `--certificate`，使原始命令、响应和公开实验信任证书直接对应证据引用。采集器要求该段限流使用已预热的缓存。

同一选项还生成 `raw-artifacts.json`，记录正式访问结果依赖的原件、类型、字节数和 SHA-256。它包含组合命令回执、被选中的访问与 TLS 证据和公开实验信任证书，可将两个清单字段用于组装执行记录。

使用 `assemble_access_execution.py` 将采集目录与本次实际执行元数据合成执行记录。元数据使用 [执行记录模板](../../specs/poc/templates/execution-record.yaml) 的身份、资源、环境、实际命令、样本和批准引用。组装器从采集原件补齐实际窗口、原件和测量，并以仓库原件及访问验证器重读对应文件。结果批准和正式索引由独立审核后提交。

```bash
python -B poc/POC-07-public-network/assemble_access_execution.py \
  evidence/POC-007/profiles/local-v1/v1/capture \
  /path/to/execution-metadata.json \
  evidence/POC-007/profiles/local-v1/v1/execution.json
```

```bash
python -B poc/POC-07-public-network/run_local_resource_replay.py --help
```

```bash
python -B -m unittest discover -s poc/POC-07-public-network -p 'test_stream_fixture.py'
```
