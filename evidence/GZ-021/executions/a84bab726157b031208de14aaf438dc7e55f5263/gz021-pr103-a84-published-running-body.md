本地 V1 采用异构 AV1 Worker、HLS 切片缓存与播放优先调度；先使用 Android 虚拟机和本地 OpenList，百度生产接入后置。本 PR 建立这一路线的协议、验收和证据校验基线。

当前正式源 `a84bab726157b031208de14aaf438dc7e55f5263`，tree `af8310494b96a6e4261a8a1e2b5109c6cbf8aab7`，唯一父提交 `8ddb9717005133ffdbc987883a79720ab32f84ff`；base/main 仍为 `d7f1ab8f727ce3879408653736b972e21bb45b7a`。

修复了已确认的七处问题：配置坏类型导致原146回归报错、嵌套 retention UTC 解析、六项业务恢复时间的实际事件绑定、生产 A380 编码身份及遥测、访问控制与拒绝返回字节、Range 切片与缓存恢复实际字节、AI 质量/用量/检索/策略结果绑定。新增165–172合成回归，保留其余163个原测试方法；原121保留七组数值案例及有效完整基线，调整为数值域单元检查，新增172检查完整实际结果。旧 schema 完整前缀、冻结计划/manifest/metadata和35个反例保留。

58个增量路径已完成独立内容审查，并核对发布后的 Git LF 字节。内容接受证明 `gz021-independent-a84bab7-actual-source-content-binding.json` SHA256 `5cd3755e185441fde7b563cf1a65d8a186703bd872fdafb1d2f497ed8233a3fc`。Windows 与 Linux 测试副本均已更新到同一正式源。

本地完整20项检查 session24551 已通过前17项，172项POC回归仍在运行，但已观察到原146一项ERROR；完整异常栈和总结果须等待该进程终止。后续本地工程测试637项尚未执行。[同源 CI705](https://github.com/ElectricDogCN/Guize/actions/runs/38469620584) run38469620584/job115545001014已完成并报告success；官方原始日志确认637项/1572.40s/无跳过，checkout `740247f21e3d9e4e3d8072811b31b3b687b4ce47`为相同tree及[D7,a84]父序的合成提交。连接器和公开API均返回steps=[]，因此原28步骤逐项通过条件尚不能证明，完整CI接受仍为false。观察证明 `gz021-a84bab7-ci705-log-observation-not-full-ci-acceptance.json` SHA256 `3ef183e0087eff098159f89b37fa1c861c516fb730614841e6d1e8248c572d1d`；不能据CI success合并。

独立单项复现确认原146这次是新测试辅助程序回归：POC007 sync_capture_reviews 在validator之前将故意损坏的TLS布尔配置当字典读取，TypeError。实际a84单项1/25.980s/Exit1及3树前后一致干净已保留。在独立detached a84候选中仅加三行dict/两个origin字符串守卫，全部172方法/断言、validator/schema/计划/metadata不变。有限内容审查通过；146/151/165/170四项107.295s/Exit0通过。候选尚未发布，不能代替正式源完整回归。完整源执行、正式验收和最终合并批准仍为false。

父源8ddb的真实失败保留：本地18项已执行、前17项通过，164项POC回归中原146一项ERROR，后续工程测试未执行；其CI704独立通过28步骤/637项，不能抵消本地失败。35份父源执行记录及16份候选增量原始日志已归档，含首次增量失败及修复后的通过结果，没有合并计算成一次成功执行。

Docker与Android15/API35虚拟机启动已验证。实际AV1编码、Worker、平台运行时和真实POC尚未完成；合成证据回归不能替代真实运行。GZ021正常Review/Completion及实际main接受完成后，继续运行时开发与完整V1集成测试。
