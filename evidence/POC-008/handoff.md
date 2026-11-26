# POC-008 登记交接

## 登记身份

本任务对应 [Issue #298](https://github.com/ElectricDogCN/Guize/issues/298)，基线 `b9d0a3c4d81f57925e733e4ce800bf15694d8af0`。登记分支为 `chore/POC-008-frontend-comparison-reservation`，实现分支为 `chore/POC-008-frontend-comparison`。准确源提交在 [登记分支提交](https://github.com/ElectricDogCN/Guize/commits/chore/POC-008-frontend-comparison-reservation/) 与当前 PR 的检查记录中确定。

协调人 `program-coordinator-agent`，实现人 `task-owner-agent`，独立审核人 `independent-review-agent`，集成人 `integration-agent`。原生登记租约为 `2026-11-26T07:01:36Z` 至 `2026-12-03T07:01:36Z`。集成顺序为 2。

## 范围与输入

- 使用已完成的 GZ-010 与 `POC-PROTOCOL-V1`。固定 [POC-008 计划](../../specs/poc/plans/POC-008.yaml)，沿用 `RES-FRONTEND-COMPARE` 与 `SAMPLE-FRONTEND-SCENARIOS`。资源、样本、工具版本与阈值须在实施实际运行前确认。
- 本次的具体文件列在 [变更清单](changed-files.md)。共享写入声明为 `adr/**` 和 `specs/poc/results-index.yaml`，按同组顺序集成。其他试验可以独立准备。
- 使用等价的合成数据、接口和浏览器执行两方案，覆盖原十项场景和三项测量。独立专用环境保留代码、样本和配置版本、命令、环境、原输出、阈值及结论。正式选型证据须取得实际结果，运行期播放器和模块能力由各自集成阶段验证。

## 验证和限制

登记验证见 [命令](commands.txt)。命令实际退出码和原始输出摘要按精确源提交记录在登记 PR。正式 GitHub CI 和独立源审查的结论随当前 PR 检查归档。当前阶段只有登记元数据，选型结论尚待正式实验。

## 集成与回滚

独立审核人核验依赖、写入范围、租约、已完成用例和官方 CI。集成人对合格源执行普通合并并复验实际主线。实际主线验收后，实现人从该主线开启工作分支，准备等价场景和样本，完成审查后执行试验。

登记未合入时撤回候选。登记合入后经正常任务流程取消并释放自身范围，保留原证据与审查记录。
