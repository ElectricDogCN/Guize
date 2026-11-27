# OPS-034 登记测试

此前隔离演练通过，正式登记证据以固定源实际检查及完整官方 CI 为准。

## 规划实施实际主线

实施 [PR #342](https://github.com/ElectricDogCN/Guize/pull/342) 已普通合入 `74d653e0d1bf723382b8879f746973371216443e`。实际双父与文件树匹配固定受审预览。官方 #1208/#1209 的 1,101 个用例逐项一致，实际最长作业 1018 秒。Windows 原生实际主线 14 项本地检查通过，取得独立终验。[实际主线 CI](https://github.com/ElectricDogCN/Guize/actions/runs/45974551103) · [独立终验原件](../implementation-main-74d653e0/independent-review.original.json) · [本地检查公开摘要](../implementation-main-74d653e0/actual-main-controls.summary.json)

## OPS-034 已验收的实际 Review

OPS-034 的实施合并为 `74d653e0d1bf723382b8879f746973371216443e`，已接受的正式 Review 主线为 `032143c287fd1e107c7316fa9e1e9ded77d120f5`。完整官方 #1211 的 1,101 项与固定源逐项一致，最长作业 826 秒。14 项 Windows 原生检查通过，独立终验接受。[实际官方 CI](https://github.com/ElectricDogCN/Guize/actions/runs/45981969539)

Status: PASS
