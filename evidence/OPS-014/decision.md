# OPS-014：metadata profiling 416 正文修复决定草案

状态：事前合同决定草案；尚未登记、冻结或修改两条合同路径。仅在 OPS-013 的实际 Completion 主线完整接受并释放 high 容量后，办理唯一后继 OPS-014 的独立原始预留。

## 问题与依据

实际 Windows OpenList 10k 的授权越界 Range 请求返回416、`Content-Range: bytes */4096`，并返回33字节错误解释。原始响应保留在已接受 OPS-013 授权声明绑定的 `unsatisfiable-response.bin` 中；该声明的原始登记、来源及摘要继续使用原件。

当前 `specs/poc/check_program.py` 的 `validate_qualified_metadata_profiles` 在 supported/unsatisfiable 分支要求空正文，与 HTTP 错误解释正文不兼容。现有测试的空正文是合法样例，不能代表416唯一合法的内容。

[RFC 9110 §15.5](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5) 建议非 HEAD 的4xx响应包含错误解释；[§15.5.17](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.5.17) 定义416及越界范围的 Content-Range 语义，没有规定诊断正文必须为空。这里采纳的合同决定是：授权的 supported/unsatisfiable 探测可以保留空正文或有界非空诊断正文，且必须验证实际字节的完整长度及摘要。

## 精确变更

- 仅修复 metadata profiling 的 supported/unsatisfiable 分支：继续要求实际请求为 `bytes=<当前对象大小>-`、状态416、Content-Range 精确为 `bytes */<当前对象大小>`。
- 该分支不再将正文与固定空字节比较。诊断正文不采用提供方专用字符串、语言、编码或33字节长度白名单，也不裁剪、替换或重写原响应。
- 保留现有每份响应不超过65536字节的有限读取条件、选中槽与产物类型、source/object/version、真实 UTC 窗口、响应实际长度/摘要，以及其余记录绑定检查。这是原有有限上限，不是新放大的预算。
- bounded/206 继续逐字节匹配实际对象前两字节和精确 Content-Range；完整读取及 ignored/200 继续匹配完整已批准探测对象。unsupported 的既有状态/正文/头部语义保持，不把416错误归类为 unsupported。
- 不修改 storage outcomes 的416规则、权限拒绝规则、原13项测量、任何 Schema、阈值、样本/资源、工作流、所有权或其他任务。

写入仅限原始不可变授权中的两条精确路径：`specs/poc/check_program.py`、`specs/poc/test_program.py`。Own Task/Evidence 和正常治理阶段元数据仍按原规则维护。

## 验证结果必须分别证明什么

1. 保留既有测试和断言，先以真实33字节原件的内容建立会被旧合同拒绝的回归；测试中的请求身份与时点仍是明确标识的合成夹具，不冒充重跑真实10k。
2. 新合同接受真实诊断内容及另一种有界诊断内容，旧空正文仍接受；使用 local-v1 与 production 的既有 schema/夹具消费方式，不能只证明某一分支。
3. 非空诊断正文下，分别篡改请求 Range、状态码、Content-Range、对象版本、UTC、响应摘要或响应长度，仍须拒绝。超过原65536字节上限仍拒绝。
4. 既有 supported/206 精确字节、ignored/200 与 unsupported 分类的正反例保持；不能通过改弱旧断言让真实33字节例子变绿。
5. 合法登记与真实 GZ-021 冻结之后才实施。固定修复源执行对应治理检查器、完整 `tests/governance`、`make verify` 和 POC 专项，保留实际命令、源提交、原始日志、零失败/错误/跳过的非空 JUnit，并完成同头 CI 与独立审查。
6. 实际修复合入冻结主线后，以真实 validatedCommit 的检查原件办理独立 metadata-only 解冻；普通 POC 只能在实际解冻后的新源继续验证。原 Windows10k失败保留；新实验仍需自己的输入、环境和窗口批准。

## 顺序与退出

OPS-013 实际 Completion 主线完整接受 → OPS-014 独立 metadata-only 原始预留 → 真实主线接受 → 单独记录针对已完成 GZ-021 的冻结事件 → 冻结主线接受 → 两文件最小修复与完整验证 → 修复主线接受 → 独立解冻及实际主线接受 → POC-005 同步新基线并按批准窗口复验。

任何原始授权、两文件旧 Git 字节、登记身份/租约/容量、冻结事件或完整验证不匹配时，不进入下一步。草案审查不授予未登记实现或实验权限。
