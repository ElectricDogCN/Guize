# GZ-031 实施交接

当前阶段为 `in_progress`，实施人和集成人为 `/root`，独立审查人为 `/root/independent_review`。实施分支 `chore/GZ-031-bootstrap-v1` 从受验实际主线 `421db3f3c6ce34c4f2bea87413cfd5b0e6360999` 创建。激活提交 `366f87c03d0d2f59e6405c5156cec0785d02027a` 与固定受测提交 `cc26ec1e687352f84dcaf2a5854c924008b45dff` 连续。租约结束于 2026-12-04T11:46:01Z。[任务 #345](https://github.com/ElectricDogCN/Guize/issues/345)

## 输入和交付

- 依赖 GZ-008 固定的 `guize.plugin/v1`、`worker-v1` 和 Worker SDK 1.0.0。控制面按 [ADR-0002](../../adr/0002-modular-monolith-control-plane.md) 使用 Java 17 与 Spring Boot 3。
- 产品文件位于 `backend/guize-bootstrap/`、`services/guize-worker-agent/bootstrap/` 和自身 Evidence。[实际变更路径](changed-files.md)
- W5 集成顺序为 3，共享写入范围为空。[实际登记验收](https://github.com/ElectricDogCN/Guize/actions/runs/45999354149)

## 实际运行

[实施验证记录](test-results/implementation-cc26ec1e.json)保存每项执行命令、结果、制品及日志摘要。Maven clean package、JAR 与三个实际合成进程的回环验证、Worker 固定 SDK 启动和篡改回归均退出 0。首轮工具缓存缺少实际测试所需的 Surefire 提供者。补入 Maven 官方依赖后对固定源码的离线构建已经通过。

目前插件探测使用本机回环和可信发布清单。插件进程与制品均为合成夹具。独立审查定位的关闭竞态已修复，关闭后迟到的就绪事件不能启动探测线程，受控并发回归已通过。Worker 源码和消费契约与已实际验证的前一提交逐字节一致，沿用原回执。生产依赖维护决策单独跟踪于 [#340](https://github.com/ElectricDogCN/Guize/issues/340)。

固定产品源码的独立技术复评已关闭关停竞态，回执 SHA-256 `bd5273fbc72c39ed8a9cd79a231ac7f157d10e5877afb85f5cb56c6b62125756`。

## 交接与回退

审查者核对固定受测树、当前候选只追加本任务证据、启动命令及真实输出，再进入完整官方 CI 和同头审查。集成人在完整 CI 且同头审查通过后普通合入，复验实际主线。未合入的候选可按任务流程撤回。测试仅使用回环临时进程和目录，能够回收后使用同一固定版本复跑。
