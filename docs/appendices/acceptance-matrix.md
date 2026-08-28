# 验收矩阵 / Acceptance Matrix

| ID | 验收场景 | 预期 |
|---|---|---|
| AC-001 | 同一文件多来源 | 单 Asset，多 SourceObject |
| AC-002 | 文件改名 | 不创建新 AssetVersion |
| AC-003 | 内容变化 | 创建新 AssetVersion |
| AC-004 | 单来源删除 | Asset 仍可用 |
| AC-005 | 所有来源删除但有副本 | 可恢复状态 |
| AC-006 | ATS 命中 | 不创建正式 Replica |
| AC-007 | 缓存提升 | 完整哈希、扫描、验证 |
| AC-008 | 水位低于 500GB | 阻止非必要任务 |
| AC-009 | 匿名播放 | 无源凭据泄漏 |
| AC-010 | 无权搜索 | 不泄漏标题/摘要 |
| AC-011 | Worker 离线 | Lease 后重调度 |
| AC-012 | Temporal 重启 | Workflow 恢复 |
| AC-013 | AI Prompt 更新 | 固定样本回归 |
| AC-014 | OpenSearch 丢失 | 可重建并降级 |
| AC-015 | PostgreSQL 恢复 | 权限、资产、任务一致 |
| AC-016 | 镜像篡改 | 部署验签失败 |
| AC-017 | 管理员密码登录 | 异常检测和审计 |
| AC-018 | 恢复密钥日常使用 | 被拒绝 |
| AC-019 | AList/OpenList | 仅 WebDAV 兼容插件 |
| AC-020 | 中英文 API 文档 | 机器标识唯一、说明双语 |
