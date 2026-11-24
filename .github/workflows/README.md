# CI 工作流

`Governance Gate / Governance Checks` 是统一的合并检查。治理脚本和三组正确性测试并行执行，每个作业的上限为 30 分钟。

- 治理脚本继续检查任务、范围、历史、冻结、协调、证据、Schema 和敏感信息。
- 三组测试从同一个提交的完整 pytest 清单进行确定性划分。同一文件只落入一组，保留两个 worker 和按文件分发。每组校验 JUnit 中的实际用例身份并执行跳过审计。pytest 严格判定 `xfail` 标记，意外通过会让分片失败。
- 汇总作业要求所有前置作业实际成功，并校验三份回执来自同一提交、同一工作流尝试，完整清单中的每项用例恰好出现一次。缺回执、重复用例、取消和失败均阻断。重新验证时使用整轮工作流重跑。

历史快照检出速度、负载、规模和资源消耗等指标使用专用环境采集。名称含 `Performance` 的治理回归仍按实际断言归类。权限、等价性和回退行为等正确性断言保留在官方检查中。性能证据按被测提交留存，详见[专用容器](../../scripts/ci-performance/README.md)。

## 后续工作流

- `java-ci.yml`
- `python-ci.yml`
- `go-ci.yml`
- `frontend-ci.yml`
- `contract-ci.yml`
- `security-ci.yml`
- `container-release.yml`
- `deployment-bundle.yml`
- `docs-ci.yml`

正式实现时使用可复用 Workflow，并固定 Action 版本或 SHA。
