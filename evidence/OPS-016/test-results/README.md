# OPS-016 当前验证边界

旧脚本下三项新增正例已在隔离开发副本实际失败：两POC增量正例及真实0976/PR157历史，均为同一complete registered implementation拒绝；child实际wait1，pytest3failed/48deselected/0error，符合复现预期。这不是测试通过。原始日志/JUnit/方法/结果无损保留于regression-red索引。

修复后固定源15项及完整同头CI尚未执行；不预填PASS。真实source、argv、PID/wait及退出码由后续固定源原始日志绑定。

首候选424c123固定源检查实际diff退出0、Task退出1（缺5项规范章节标题），余13项未执行；原件见source424-doc-failure索引。当前只前向补正Own Task章节与该失败Evidence，两代码文件保持。新候选的15项尚待，不继承失败源的门禁结论。

源971首10项实际退出0，第11scope退出1，后4未执行。原件见source971-scope-failure。独立审查另确认祖先424无效Task会在Completion重审：旧两源/分支/工作目录/恢复包全部保留，新候选从实际accepted263独立起步，未导入坏历史；精确复用两个实现文件，Own允许范围逐行列原两代码路径与OwnEvidence，正常生命周期metadata继续接受原scope子校验，无checker/claim/阈值放宽。新源15项尚待。

新author未提交诊断中Task格式通过，scope因本地longpaths配置及metadata未提交而拒绝；只补持久化本地Git配置，并以Windows extended-length路径核实foreign长路径Git字节未变。普通Python长路径open的诊断失败也保留，未删除文件。该诊断不作固定源门禁。负面旧源审查及说明见prior-source-assessments；新候选需完整15项，代码字节不变。

新有效历史源f65固定源首11项实际退出0（含历史/协调/scope），第12 Evidence因follow-ups.md缺任务ID退出1，readiness/docs/51专项未执行。原结果/失败日志/方法/候选见sourcef65-evidence-failure，首11完整raw按索引引用原生目录保留。当前只前向补Own后续文档ID/命令说明及本失败档案；Task与两代码字节保持有效原样，不继承失败源15资格。
