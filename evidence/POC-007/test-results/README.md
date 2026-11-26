# 测试结果

登记基线已通过本地七项及官方 1,090 项测试，独立终验接受。[实际主线 CI #1168](https://github.com/ElectricDogCN/Guize/actions/runs/45851386217)

## 运行环境预检

- Windows 原生 OpenList v4.2.6 与记录的二进制摘要一致。使用一次性目录和随机生成的测试管理员凭据启动，验证回环监听属于该进程，健康接口返回 HTTP 200 和 `pong`。预检没有挂载来源。进程及临时数据已回收。
- Python 3.12.4 与 OpenSSL 3.0.14 使用临时证书在回环地址完成 TLS 1.3 握手。客户端验证证书与 `localhost`，读回 20 字节。进程及临时证书已回收。
- [样本校验器](../../../poc/POC-07-public-network/verify_fixture.py) 读取本机原件，返回 `SAMPLE-RANGE-LARGEFILE`、67,108,864 字节及 SHA-256 `9a30d2bb1a4f1eabcb41baa5b6518628411ba8ac668fc1e7085983261aa5f419`，与 POC-003 的原始合格样本完全一致。三字节错误样本退出 1。正式运行需要本任务的样本批准。

正式实验将从真实 TLS 播放入口请求 OpenList 里已挂载的相同合成样本，并记录 Range、授权、限流、流式读取及回收结果。
