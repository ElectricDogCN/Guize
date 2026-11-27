# OPS-035 登记原生验证

本地受测提交 ed5be64905dbfa4f699789a481f3fdccb2ba90f0，单父 cb51148e41e8b420a5c58fb928d5bc84bdacb89c，树 a9e1b0df4a186368cdabcb19786ef0b5c74e580a。
固定受测提交上 14 项本地原生控制均退出 0，具体命令见 [commands.txt](../commands.txt)。本地原始回执的 SHA-256 为 c346811d3101c28d68a2a51a6263e203963876ebe408be314cd08b98d94c3657。各命令使用固定受测提交，Windows 运行环境使用 PYTHONUTF8=1。

第一次 Windows 执行未启用 UTF-8，Git 中文输出解码失败。启用后，原 Task 文本中仓库根路径 AGENTS.md 缺少反引号，转换检查未识别该声明。修订 Task 的 Markdown 表示后在上述新固定提交重跑 14 个原生入口。四条声明、授权意图、租约和五条保护路径的字节及范围保持一致。

| 检查 | 退出码 | 秒 | 原日志 SHA-256 |
| --- | --- | --- | --- |
| diff | 0 | 0.08 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| task | 0 | 0.19 | 7960affd4a900659eb4a363a2a5225ed5c0796900792db6076f9e45644987f8d |
| schemas | 0 | 6.2 | 50aecf49f71334dd7f96647bd572aef132984fed442d5dfd6f0144bc9c23b94c |
| integrity | 0 | 36.83 | dc09f34dad1a757af897139c06557b21cf371e781cb03b7eef1d1d79cdcbffc0 |
| history | 0 | 17.81 | ab563592ea208c08543e10cef22ed42c55ffc7ce4f4982abd9d973af5a31aaac |
| transitions | 0 | 19.94 | a47bd31eb521bfb475c2f4e34bf0be688108877835a7a58542c3077c6cb0b2d4 |
| lifecycle-guards | 0 | 31.72 | 993bed1818cf230ec0845ab2eb26fe979b4a4a425fe2d9550a7f3553bfa462c3 |
| program-gate | 0 | 30.7 | 95c8521c4932ec5b76c9bb47641e21e424d648fa0e40b34e8609633159debd45 |
| coordination-gate | 0 | 0.75 | 18ba928761b092b75171d36d7db682845d47a23ef70a6269b56c5154f8c71621 |
| finalization | 0 | 0.67 | 07fbfdac3e338a6bbf960e2763c0990dd80b7bfc114dc244325cb9a6640ec65d |
| scope | 0 | 0.12 | 5f4bc77acf6cb94a50168d7b49d155abafbd56a26357f4e4687861b80e3a81d7 |
| evidence | 0 | 0.09 | d65fc4d535e2f7fbdcbe6a08c36ee1053be37930a0c5cad6a2a7bd6eb695713e |
| readiness | 0 | 122.62 | 632121dca7108a89e032a1c8203500807b9a69a0d4d2ac0b73a1b4df2ae5d7ef |
| markdown | 0 | 0.53 | 7332fd2fe281175a43cd0f47f3616f07c0f220d44a2a7a83f05cee117e6f3acd |

后继证据候选和实际主线分别按完整官方 CI 及独立审查验收。

## 实施固定代码源

2737a57b6c50b334ff3790ef8db793a6e090e771 的 15 项本地检查全部通过。固定回执 SHA-256 为 a9253b822d17997e319d963cfe44b47ff7a9e19edee4bda1f2665396e50e0deb。
本地收集 1,105 项，逐项核对包含实际登记主线的 1,101 项与全部原有 1,078 项，新增四项定向回归均执行通过。
另以 OPS-018、027 原始登记 Git 对象对照已批准绑定及无效范围，结果和拒绝诊断分别相同。

| 检查 | 退出码 | 秒 | 原日志 SHA-256 |
| --- | --- | --- | --- |
| diff | 0 | 0.08 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| task | 0 | 0.19 | 7960affd4a900659eb4a363a2a5225ed5c0796900792db6076f9e45644987f8d |
| schemas | 0 | 6.53 | 50aecf49f71334dd7f96647bd572aef132984fed442d5dfd6f0144bc9c23b94c |
| integrity | 0 | 35.45 | 9c1f1072a600c261b03c3e0e7d35dc8f8fa028b9dfd653dbd511cad54856c998 |
| history | 0 | 21.38 | 6459856a9db3a2f02e9b3817b81a8560706864f7a6cabf03cf4dffd809f36da0 |
| transitions | 0 | 18.45 | a47bd31eb521bfb475c2f4e34bf0be688108877835a7a58542c3077c6cb0b2d4 |
| lifecycle | 0 | 30.83 | a13c4d828ae3b76e66a1113a432f311d500344ca3ffaadb09662caeaed0f5f74 |
| program-gate | 0 | 30.62 | f82053b5644facfd1c56b95586a9ed25d17f3b673da1544cf699f34ec2b78228 |
| coordination | 0 | 78.45 | 642363ebef5e5daecdaa1062ffdb129e1a18cbd8d37e2f62bc20922c008c72c1 |
| finalization | 0 | 0.67 | 07fbfdac3e338a6bbf960e2763c0990dd80b7bfc114dc244325cb9a6640ec65d |
| effective-scope | 0 | 78.05 | 928bbf304632d4b44b3b728e008c3926790b06996f7002d94cb227c6e4d4fc1d |
| evidence | 0 | 0.09 | d65fc4d535e2f7fbdcbe6a08c36ee1053be37930a0c5cad6a2a7bd6eb695713e |
| readiness | 0 | 123.22 | 632121dca7108a89e032a1c8203500807b9a69a0d4d2ac0b73a1b4df2ae5d7ef |
| markdown | 0 | 0.61 | 7332fd2fe281175a43cd0f47f3616f07c0f220d44a2a7a83f05cee117e6f3acd |
| source-dependency-regressions | 0 | 7.42 | cb37da4abf05ef0989ffdbf033ea3454275bc6e7a8b1c86ec5a96458a4e79e88 |
