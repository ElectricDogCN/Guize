# 控制面启动骨架

使用 Java 17 构建并启动独立控制面。默认在回环地址提供 Actuator 健康检查。空配置启动无需插件进程。

```bash
mvn -f backend/guize-bootstrap/pom.xml package
java -jar backend/guize-bootstrap/target/guize-bootstrap-0.1.0-SNAPSHOT.jar
```

`/actuator/health/readiness` 用于确认控制面可用。可选插件通过本机独立探测完成注册。配置存在时，应用在开始服务后调用仓库中 GZ-008 的清单和制品核验。启动参数 `--guize.bootstrap.repository-root=<归泽仓库>`、`--guize.bootstrap.plugin-directory=<本地验证目录>` 和 `--guize.bootstrap.python=<Python 3.11 解释器>` 分别指定核验源码、制品目录和执行环境。Python 依赖沿用仓库的 `requirements-governance.txt`。

验证目录包含 GZ-008 的 `release-lock.json`、已由发布验证流程提供的 `inventory.json`、对应制品和 `probes.json`。后者将插件标识映射到本机回环端口。符合契约并声明回环权限的外部服务通过清单的 `healthEndpoint` 供客户端探测，清单未指定时使用 `/health`。应答包含 `status: READY` 和实际可用的 `capabilities`。探测超时由 `guize.bootstrap.probe-timeout-millis` 设置，默认 1 秒。

发布来源与制品摘要通过 GZ-008 约定的可信输入验证。只有通过有效探测的声明能力才进入状态快照。失败或迟到的服务不影响控制面及其他插件。在受控环境中可用 Spring Actuator 的 `management.endpoint.health.show-details=always` 检查插件快照。

打包后可在回环环境运行真实进程对照。

```bash
python backend/guize-bootstrap/test_plugin_startup.py test --java /path/to/java --jar backend/guize-bootstrap/target/guize-bootstrap-0.1.0-SNAPSHOT.jar
```
