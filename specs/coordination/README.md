# Guize 多 Agent Program Plan 与活动任务登记

本目录包含两个不同层次的事实源，禁止混用：

- `program-plan.yaml`：唯一机器可读 Program 入口，保留冻结 V1 及显式固定的 `AGENT-EDGE-104` 后续范围，描述 Task、Wave、依赖、风险、Requirement、Module、输出路径、契约生产/消费、POC 和发布阻断项。
- `active-work.yaml`：当前已预留或正在执行的少量任务登记，描述固定 base SHA、角色、租约、独占/共享路径、handoff 和集成顺序。

二者都不是产品需求或业务契约。发生范围冲突时，仍按 `AGENTS.md` 的权威顺序处理。

## 文件

| 文件 | 作用 |
|---|---|
| `program-plan.yaml` | canonical Program 与固定范围边界 |
| `program-plan.schema.yaml` | Program Plan 结构契约 |
| `active-work.yaml` | 当前活动任务 Registry |
| `active-work.schema.yaml` | Registry 结构契约 |
| `planning-revision.schema.yaml` | 已登记任务的原始精确计划修订声明 |

旧 `work-package-plan.yaml` 已被 Program Plan 替代，不得重新创建第二份后续任务计划。

## 从计划到合并

```text
Program Plan 中任务可启动
→ Coordinator 检查依赖/Wave/外部 blocker
→ Issue + Task Spec + Evidence
→ reservation PR 写入 active-work
→ reservation Gate/Review/Merge
→ Implementer 从 reservation 后最新 main 创建登记分支
→ Implement + Tests + Evidence + Handoff
→ Independent Review
→ Integrator 检查契约/迁移/行为冲突
→ Integration PR Merge
→ Registry 完成/释放
→ Program Plan 状态更新
```

非治理紧急修复若不在 Program Plan 中，必须先用独立高风险治理任务修订 Program Plan，不能只创建 Issue 后直接开工。

## 启动条件

一个任务只有同时满足以下条件才可 reservation：

1. `program-plan.yaml` 中存在唯一 Task ID；
2. `dependsOn` 已完成或输出已冻结为机器契约；
3. 所属 scope 的 Wave 静态占用与路径冲突有效，且全局活动和 high-risk 容量未超限；
4. external blocker 不禁止该任务；
5. Requirement、Module、output/shared path 和 contract producer/consumer 与计划一致；
6. high/critical 任务具有独立 Implementer 与 Reviewer；
7. Task Spec、Registry、Issue 和 branch name 使用同一任务定义。
8. 若位于 `planningBaselines` 的消费者根或其后续依赖闭包，基线任务必须已在实际集成基线中完成，并具有正常登记、实现、独立 Review 与 Completion 的可达提交证据；冻结契约不能替代此完成条件。

## 两阶段协议

1. Coordinator 创建 Issue、schemaVersion 2 Task Spec 和 Evidence；
2. 通过独立 reservation PR 把任务写入 `active-work.yaml`；
3. reservation PR 合并后，Implementer 从最新 `main` 创建实现分支；
4. 实现阶段把登记状态改为 `in_progress`，不得改变已审查角色和路径而不修订 reservation；
5. Reviewer 只审查，不在同一高风险任务中兼任 Implementer；
6. Integrator 复核依赖、公共契约、Migration、行为冲突和 Handoff；
7. 合并后通过治理提交把 Registry 标记完成或释放，并同步 Program Plan 状态；
8. 过期、取消或阻塞登记由 Coordinator 通过独立治理 PR 清理。

GZ-003 是机制 bootstrap，列入 `policy.bootstrapTasks`；GZ-014 通过真实 reservation 验证并扩展该机制。

## 路径与公共契约

- `exclusivePaths` 与其他活动任务的独占或共享路径重叠时失败；
- `sharedPaths` 只有在 `coordinationGroup` 相同、双方都声明 shared 且 `integrationOrder` 不同时允许重叠；
- “无共享范围”必须单独写为 `- 无。`，不得在同一 bullet 中混入反引号路径；
- 不允许使用 `**` 预占整个仓库；
- `module-ownership.yaml` 中每个公共 Contract Namespace 只有一个 owner；
- consumer 只能依赖已合并 producer Task 或冻结契约；
- shared writer 必须显式登记，不能因为多个 Agent 都能提交文件而推断为允许共同写入。

## 并行上限

- Program Plan 和 Registry 默认最多 3 个并行任务；
- 默认最多 1 个 high/critical 风险任务；
- critical 任务单独一个 Wave；
- 未冻结共同机器契约前，不并行实现同一契约的多个消费者；
- 审查者只能按可实际处理的容量放行任务，不能为追求并发填满上限。

## 验证

```bash
python scripts/check-schemas.py
python scripts/check-project-readiness.py
python scripts/check-agent-coordination.py
python scripts/check-agent-coordination.py --task GZ-XXX
```

`python scripts/check-project-readiness.py --strict-ready` 用于最终生产就绪检查；在机器契约、实现或外部 GitHub Ruleset 未完成时应失败。

## 原始 v1 计划修订声明

规划权限来自实际 `main` 第一父历史上最终 metadata-only reserved 登记快照的 `evidence/<TASK-ID>/planning-revision.json`。声明绑定 `schemaVersion: 1`、登记任务和登记主线第一父 SHA。审查期未合入的早期草稿不是原始权限；真正登记之后，声明的 Git 字节必须保持不变。

旧 `schemaVersion: 1` 声明的 `targets` 仍只支持三个闭合类型：新增完整 `planned` Task、修改声明字段内的完整未启动 `planned` Task，以及新增精确 planning baseline。修改目标同时保存完整 before/after、原定义规范 JSON 的 SHA-256 和精确 `allowedFields`。不得加入目标状态、Issue、Task Spec、租约、政策、恢复信息、完成账本或未声明的计划变更。所有目标必须一次完整应用；不能分批授权、拓宽路径或用字符串 SHA 代替可达历史。

执行者须已独立登记为 high 风险、声明 `MOD-GOV`、持有精确独占 Program 路径与有效租约，处于 `in_progress`/`integration` 的 implementer/integrator 阶段。Foundation 的所有 claims 仍须是治理所有权范围的子集；普通需求规划任务可声明其实际业务模块及已经审查的精确业务文档路径，保持既有模块所有权规则。登记、Scope、容量、独立角色和最新实际 main 检查均不豁免。

Foundation 后续范围修订须先在实际集成基线的第一父历史中完成独立 reserved/coordinator 元数据登记：只改自身 Registry/Task/Evidence，绑定该节点的真实第一父，保留原始声明、Program、账本、稳定身份与租约。实现提交自行追加 claim、未合入 sibling 或晚于实现基线的修订均不赋予执行权限。

共享校验器 `scripts/program-planning-revision.py` 完整认证后，三个既有检查器仅投影声明的未来定义；任何无效认证都不隐藏变更。原 schema、依赖 DAG、POC 镜像、Wave、契约覆盖、最终发布闭合、冻结与完成后限制继续执行。历史检查按实际引入节点认证，恢复过的最终文件不能掩盖中途的违规。

普通定义和 baseline 的实际 Git 两端均未变时，分类回调不生成任何投影或规划权限；相关生命周期继续由原门禁处理。消费者按真实 Registry、Task Spec 身份和代码 diff 识别，实际消费者准入仍校验完整图和 producer 完成历史。仅已 completed、Registry 中不存在、Program/完整 Task/Own Evidence/账本均未变的历史 CLI 上下文不会替代唯一真正执行者；其他错误上下文继续拒绝。Git 数据缓存只绑定规范仓库路径、完整不可变 commit SHA 和路径，解析结果返回深拷贝；引用别名每次重新解析，租约、时间、权限和准入结论均不缓存。

## 固定 AGENT-EDGE-104 范围与独立声明

`scopeBoundary` 仅承载一个固定扩展：`v1TaskIds` 精确保留原27项成员，`v1FinalTask` 固定为 `GZ-020`；`agentEdge104` 的 ID、Issue104、planner GZ-022 与需求/索引路径均固定。旧计划没有此字段仍可读取；新增范围不能迁出 V1 成员、缩减原十项需求/十二验收或生产门禁，也不能改变旧 POC、历史账本、公共政策或原始声明。

`agentEdge104.state` 只有 `planning` 和 `defined`。`planning` 的成员精确仅 GZ-022、最终任务为 null，只允许该普通规划任务按正常登记流程承接文档；不能启动业务或宣称范围完成。`defined` 必须包含 GZ-022、完整业务成员及非空业务最终任务；共享校验器验证最终任务属于本范围、严格传递覆盖全部成员，且实际依赖/契约/baseline图无环。声明没有 `completed` 状态；最终任务与全部实际交付完成后，才按真实执行和正常 Completion 判定范围接受。

Program 的旧 `$defs/task`、`reqId` 和旧 v1 声明的根、`plannedTask`、target 与相对 `$ref` 语义保持。新增 `$defs/edgeTask` 复制相同23个闭合字段，仅接受 `REQ-EDGE-104-####`；Task 不增加 scope、repository 或任意权限字段。Program tasks 以旧 task/edgeTask 的 `oneOf` 区分，既有 V1、Foundation 和 GZ-022 的治理 REQ-V1 归属不变。Registry 只允许旧 REQ-V1 或这一固定 EDGE 格式；实际 scope 成员及 Task/Registry 的精确身份仍须由共享准入校验。

两个新增声明只从 `planning-revision.schema.yaml` 的独立片段入口验证，不能送入或扩展旧 v1 根：

- `https://guize.local/schemas/planning-revision.schema.yaml#/$defs/agentEdge104FirstUse`：认证 OPS-011 / Issue108 原始 `evidence/OPS-011/agent-edge-104-first-use.json`。三个 target 次序精确为 `add-fixed-scope-boundary`、新增完整 planned GZ-022、增加仅 POC-003/POC-005 根的 BASELINE-GZ-022。原 Git 字节、真实 reservationParent 和完整事务不变；声明本身不是安装或执行证明。
- `https://guize.local/schemas/planning-revision.schema.yaml#/$defs/agentEdge104Definition`：GZ-022 的独立原始定义声明为 schemaVersion2，kind `agent-edge-104-definition`，固定 taskId/scopeId/Program 路径，绑定真实 Issue 与 reservationParent。targets 必须有一次 `define-fixed-scope`、新增完整 planned EDGE Task，以及明确列出的旧闭合 editTask / 可选 addBaseline；全量事务一次应用，仍认证 canonical reserved 第一父历史中的原始声明、角色、claims、有效租约和所有消费者未启动。

`define-fixed-scope` 精确只有 `kind`、`id`、`before`、`after`：id 为 AGENT-EDGE-104，before 是完整 planning 对象、after 是完整 defined 对象；共享实现只写 `scopeBoundary.agentEdge104`，不接受 path，也不能改 v1TaskIds/v1FinalTask。原 first-use 的 `add-fixed-scope-boundary` 仍只有 kind/path/before/after，path 固定为 scopeBoundary。加载片段时须在 registry 注册完整 Program 和 Planning Schema 资源及原 `$id`，保留相对引用；不能裁下片段丢失资源解析上下文，也不能改旧 ref 来间接扩大 v1 权限。

正式 EDGE 需求仅由固定的 `specs/requirements/agent-edge-104.md`、独立 `agent-edge-104.yaml` 与 `specs/acceptance/agent-edge-104.yaml` 承载。需求索引根为 schemaVersion1/scopeId/sourceIssue/requirements，逐项闭合字段为 id/title/requirementPath/moduleIds/taskIds/acceptanceIds；验收索引根为 schemaVersion1/scopeId/sourceIssue/acceptances，逐项为 id/title/requirementIds/taskIds/verification/evidencePath。原始 v2 定义声明必须同时包含完整 typed `requirementIndex` 与 `acceptanceIndex` catalog 对象，以及闭合 `requirementDocument` 对象：path 固定为 `specs/requirements/agent-edge-104.md`，content 保存完整非空规范正文。两个目录使用同资源的 `edgeRequirementCatalog` / `edgeAcceptanceCatalog` 闭合定义；不接受只列路径或事后补填摘要。首次定义引入时，认证 canonical GZ-022 原始登记声明，将两个目录与同一实际 Git ref 中固定文件精确比较，并将规范正文按 UTF-8 编码后与该 ref 的 Markdown Git blob 逐字节比较，不规范化换行或 Unicode。声明应按规范 Git 文件字节准备，不能混入 Windows 工作区换行。此后目录与正文同样冻结：即使只有任一 catalog 或 Markdown 正文变化而 Program 未变，也必须在分类器的 early return 前认证原始不可变 v2 和实际引入节点，不能以保留标题锚点绕过正文比较。新 Task 的直接 REQ/AC 与索引 taskIds 精确双向对应、真实 module 由承接 Task 覆盖；旧 V1 index 和 legacy module requirementIds 不混入 EDGE。最终任务覆盖本范围全部需求/验收，不能靠未映射的依赖结果充数。

Wave 编号只在所属 scope 内表达顺序和静态容量/冲突；固定扩展复用现有 Wave，不另建并发池。跨 scope 的数字先后不能替代或阻断实际 DAG，真实 dependsOn、公共契约和 planning baseline 完成仍严格。全局最多3个活动任务、1个 high/critical、critical 独占及真实 lease 路径互斥保持。无论 scope 是否 defined，每个 EDGE 业务任务启动都额外要求 `completed_producer(GZ-022)` 的真实普通登记/实现/独立 Review/Completion 历史；不能仅凭状态、BASELINE 名字或 planner 已写好文档放行，也不对 OPS-011 Foundation套用该普通 producer 判据。

跨仓运行时由其仓库自己的 Task、claims、构建与发布承接。主仓 Task 只写本仓已登记路径，不使用 `../` claim 或推导 Android CI 权限；GZ-008 版本化 Worker 制品/兼容契约和主仓 owned artifact-lock 绑定远端真实提交、Task/完成证据及不可变制品摘要。主仓联合验收消费固定组合；新仓 bootstrap、应用交付、各仓 CI 与系统联合接受分别记录，不能互相替代。GZ-022 只冻结需求/DAG/接口，不能据此宣称八项 runtime、正式 POC 或完整 V1 已通过。

## Planning baseline 与消费者

`planningBaselines` 是可选的闭合记录列表，每项只有 `id`、`taskId` 和非空唯一 `requiredBy`。旧计划不含此字段仍然有效。producer 与消费者须存在，不能自依赖、重复或与普通依赖共同成环。创建时，producer 和全部消费者闭包必须未启动、无 Task Spec、无 Lease/Completion；已有 baseline 不得删除、缩小、替换或静默修改。

基线 producer 的完成必须已经存在于接受的集成基线，具备真实主线登记、非元数据实现、独立 Review 和独立 Completion 的历史。伪造 completed/ledger、非祖先或同一 PR 完成 producer 并启动 consumer 都不能放行。显式 Task 启动和没有 `--task` 的代码变更都检查实际代码 owner；声明外的消费者输出代码也不能绕开门禁。producer 完成后，消费者仍须满足所有普通准入条件。

Readiness 从实际 Git 第一父历史认证 baseline 的完整原始事务及后续不可变记录，只对 producer 与仍 planned、无 Task Spec/Lease/Completion 的消费者闭包识别前后串行关系。该关系仅解除这两个未并行执行任务的未来输出冲突；已启动消费者、无关任务冲突、共享写入顺序、容量、高风险/critical、模块所有权、DAG、Wave 和 POC 镜像规则全部保留。Program 与身份输入必须绑定实际 Git 快照，原始声明在当前 HEAD 中仍须字节一致；无 baseline 的旧计划沿用原检查。

每个 baseline 保留创建提交中的消费者依赖闭包；producer 尚未在实际主线完成时，后续计划修订不得缩小这个集合。baseline 的消费者到 producer 的语义依赖同样检查已知 Wave 和阶段顺序。原始声明的字节检查覆盖登记后的中间历史，即使最终恢复原字节也不能抹去违规修改；没有 Program 定义变化的节点也必须执行声明审计。缓存只保存完整提交 SHA 绑定的不可变数据，不能保存准入、租约或完成判断。

既有 baseline 的规划交易如果扩大消费者闭包，新增成员在交易前后必须保持未启动（交易新增的 Task 可在 before 中不存在）。检查逐交易 before/after 的差集，不能把历史上已经合法加入的成员在后续正常启动时再次当作新成员。普通规划任务只可登记精确 docs/、adr/、specs/ 文件及 poc/README.md；specs 中的已登记业务 Schema、校验器和相应回归文件仍允许。运行时目录、治理 scripts/tests 与通配符不属于普通规划例外，自身 Evidence 仍按普通元数据规则管理。

OPS-009 首次使用只执行原始三目标：新增 planned GZ-021、给 planned GZ-020 尾追加 GZ-021 依赖，以及新增 BASELINE-GZ-021。十个消费者根经既有图覆盖二十三个未启动任务；POC 依赖镜像和 GZ-020 的生产最终义务保持。原始登记到机制合入之间的暂停派发与失败关闭顺序记录于 OPS-009 Handoff/PR86；这项 Coordinator 排序不表示登记 PR 已安装持续机器阻断。发布和合并首次使用之前，必须再核全部消费者未启动；已启动则停止首次使用，保留真实身份与原始声明，按既有合法生命周期作具体恢复决定。

## 实现合并提交与 Completion 身份

Completion 的 `mergeCommit` 必须指向已登记、已审查、已集成的最后实现版本；激活、Review、纯 Task/Evidence 提交和空提交不能替代实现身份。Git 提交说明必须同时包含精确 Task ID 和真实 PR 的 `#<number>`。实现 source 的说明含这些标识不能替代实际合并提交自身的说明。

Integrator 在合并已通过最新源测试与独立审查的实现 PR 时，显式设置提交标题，例如 `Merge PR #123: OPS-009 <本次交付目的>`；数字必须来自当前真实 PR，不能照抄示例。通过 GitHub merge 接口时设置 `commit_title`，并在实际合并后读取新的 merge SHA 和完整 Git message。保留真实父提交、Tree 和通过检查的 source；不重写既有主线历史。

合入后，在真实 main 上以本次实际 Task、PR 和 merge SHA 运行现有两个身份检查，再办理正常 Completion：

```bash
python - TASK-ID PR-N ACTUAL-MERGE-SHA <<'PY'
import importlib.util
import sys
task, reference, merge = sys.argv[1:]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
integrity = load("identity_integrity", "scripts/check-program-plan-integrity.py")
history = load("identity_history", "scripts/check-program-plan-history.py")
errors = integrity.commit_identity_errors(".", merge, task, reference, "Actual implementation")
history.validate_commit(".", merge, task, reference, "Actual implementation", errors)
assert not errors, errors
print("PASS: actual implementation commit identifies Task and PR and is reachable")
PY
```

这项预检使用现有检查函数，只核对实际 Git 身份；它不替代完整 Scope/历史/生命周期检查、非空治理测试、最新 CI、独立 Review 或真实主线验收。失败时保留原始日志并停止 Completion，在原有效登记和精确授权范围内完成必要的前向修复后重新交付，不能改写历史提交、使用元数据身份或放宽断言冒充完成。
