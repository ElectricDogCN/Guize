# POC-008 前端比较样本

[scenarios.json](scenarios.json) 按仓库资格模式登记十个等价场景、预期动作和同一套合成输入。浏览器运行包只包含输入与场景标识。预期结果由验证器读取。虚拟列表按窗口计算记录，不需要预先生成百万行文件。运行 `node --test fixtures.test.mjs` 检查取数边界、确定性和场景清单，使用 Node.js 标准库。

正式比较同时记录场景覆盖、构建体积与维护评分，并分别保留十个原场景的观测。测量前固定 Vue 和 React 的版本、锁文件、样本摘要、浏览器、执行环境和判定阈值。使用同一个专用容器和输入运行两组原型，归档命令、配置、原始输出和结论。若样本、工具或关键环境变化影响结果，对相应验证重新取证。

播放器组件事件、会话范围和监控错误均来自合成样本。两种原型渲染相同输入。实际播放器及服务协议的联调由对应模块的集成阶段完成。


## 可运行原型

React 与 Vue 从同一份 [HTML 入口](index.html) 分别构建，并 使用同一份场景和样式。现可比较百万记录列表的开头、中段、末尾和最后一条的选择，以及来源表单的条件字段、必填错误和成功提交。列表保留 32 个行节点。浏览器断言使用两套界面的实际点击和表单交互。

使用 Node.js 22.14.0 或兼容版本，在本目录执行：

```text
npm ci
npm run build
npm test
npm run test:browser
npm run measure:bundles
```

运行浏览器测试前，将环境变量 `GUIZE_CHROMIUM` 设为 Chrome 或 Chromium 的可执行文件路径，或通过 `npx playwright-core install chromium` 安装测试浏览器。Vite 预览只绑定回环地址，测试结束后关闭。构建锁定 React 19.3.1、Vue 3.5.46 与 Vite 6.4.2，依赖版本见 [锁文件](package-lock.json)。

两套原型还覆盖流程图、决策表、监控、事件重连、播放器组件、触屏、权限可见性与主题。SSE 和 WebSocket 分别通过本地服务器传入实际事件并复连。服务端重发第一条事件以检查去重。另有独立的合成权限接口，验证读者和编辑者各自的服务端结果。播放器组件发送合成的就绪、暂停及故障状态。使用 `npx vite preview --host 127.0.0.1` 时可在浏览器分别打开 `/react/index.html` 与 `/vue/index.html`。

`node measure-bundles.mjs` 统计两次独立构建中各自入口实际加载的 JS 和 CSS，按路径去重并保留未压缩和 gzip 字节数。正式比较在同一固定环境采集全部十个场景的覆盖、体积与维护评分。


## 原始浏览器记录

`browser.test.mjs` 执行十个场景的 32 个动作，并比较浏览器实际读回的内容与样本。正式采集调用同一份动作驱动：

```text
node browser-driver.mjs --context CONTEXT.json --build dist/react --fixture scenarios.json --scenario million_row_virtual_list_equivalent --stdout REACT-SCENARIO.json --url http://127.0.0.1:4173/react/index.html
```

先启动绑定回环地址的预览服务。`CONTEXT.json` 对应本次执行的 `context`、候选 `identity`、`buildId` 和编译清单 `compilerManifestRef`。正式执行使用独立审查固定的上下文、样本和编译记录。驱动记录浏览器进程退出码、实际载入的资源及其摘要、每个动作的时间和 DOM 读回值。输出文件必须使用新路径，以便保留原件。正式报告从已保留的动作、构建和评估记录汇总。

正式构建记录从仓库根目录采集。预先锁定候选、版本、源码提交、锁文件摘要、完整命令和输出目录：

~~~text
node poc/POC-08-frontend-framework/collect-build.mjs --identity IDENTITY.json --manifest COMPILER.json --report BUILD.json
~~~

构建器检查这些输入，生成全新的输出目录并保存实际编译开始和结束时间。编译清单列出全部输出的字节数和 SHA-256。正式体积按整个输出目录统计，前面的首屏 JS 和 CSS 只用于开发对照。


使用同一份浏览器命令采集两个候选时，`CONTEXT.json` 保存共同的 `context`，并在 `candidates` 中分别列出每个构建的 `identity`、`buildId` 和 `compilerManifestRef`。先按批准的 `browserOrigin` 启动预览，从仓库根目录采集。

```text
node poc/POC-08-frontend-framework/capture-scenario.mjs --policy POLICY.json --fixture FIXTURE.json --candidate react --scenario million_row_virtual_list_equivalent --output RUN-OUTPUT
```

采集命令保留浏览器驱动的原始 JSON 和标准错误，记录实际进程、命令、退出码与摘要。场景观察从 DOM 读回记录派生，供仓库校验器复验。输出目录每次新建。相同命令可把候选改为 `vue`，并使用另一输出目录。
