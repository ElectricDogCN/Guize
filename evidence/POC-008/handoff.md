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

## 实验输入准备

固定登记主线 `b97135ac94360828e9d29562be593551e231ab30` 已独立接受。[登记 PR #304](https://github.com/ElectricDogCN/Guize/pull/304) · [实际主线 CI #1149](https://github.com/ElectricDogCN/Guize/actions/runs/45775450522)

工作分支 `chore/POC-008-frontend-comparison` 进入实施，原角色、租约、范围和集成顺序保持。固定实验输入引用 POC-PROTOCOL-V1 和既有 POC-008 计划。当前源码及证据在 [任务工作分支](https://github.com/ElectricDogCN/Guize/commits/chore/POC-008-frontend-comparison/) 的固定提交记录。共享 ADR 和结果索引没有写入，后续仍按原顺序集成。

- `poc/POC-08-frontend-framework/README.md` 的 Git 对象为 `035f777f8189afab0824660ae70e7943208993b1`。
- `poc/POC-08-frontend-framework/fixtures.mjs` 的 Git 对象为 `7c5bcfe2e3980596328164960a1ba7eba7b93ce4`。
- `poc/POC-08-frontend-framework/fixtures.test.mjs` 的 Git 对象为 `6e8af83699bfca1f9065303497f24703771f92ec`。
- `poc/POC-08-frontend-framework/scenarios.json` 的 Git 对象为 `d39ce8d5cab0f7800f18b4a8af02dc3a2d76e916`。

[命令与退出码](commands.txt) 记录小用例实测。后继分别实现同一套场景的两个原型，固定依赖、环境、样本摘要和阈值并完成独立审核，再执行十三项正式测量。记录原始输出、可复现命令、结论适用范围和回退。数据均为合成输入。未发布时撤回工作候选，正式发布后按冻结样本版本和实验回退流程处理自身范围。

## 原型阶段交接

React 和 Vue 各自构建独立输出，从同一份固定样本运行十个场景。本地浏览器读回共 64 个动作，20 份原始记录逐一通过对应 JSON Schema。两份本地编译记录都包含四个实际输出，并逐一核验字节和 SHA-256。

这些试跑验证原型、动作驱动与原始输出结构。正式比较将采用已锁定的资源、样本、框架与浏览器版本、独立的评估角色和共同实验窗口。在正式归档中保留完整编译输出、两类传输的回连记录、DOM 读回、三项维护准则和结论依据。

在已登记的工作分支先固定原型和采集工具的受测提交与树，独立复核资源配置、样本、执行窗口、阈值及评估角色后再执行正式实验。React 和 Vue 在同一固定环境构建、运行和评分。受测源码与正式证据可以在同一个 PR 接受正式审查和完整官方 CI，证据提交保留受测提交的祖先关系。若实测无法区分，两套原型继续保留结果并沿用现有基线。[浏览器驱动](https://github.com/ElectricDogCN/Guize/commit/ad14847356b3184428171658bd11eca7dd26d059) · [编译记录工具](https://github.com/ElectricDogCN/Guize/commit/e5e681ea15744f46d41d142b6fa3f8ba20fe0753)
