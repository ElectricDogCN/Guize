# POC-005 本地百万文件实测退出报告

受测提交为 `be8a16ad0fcaeb64e5b169e6137fedfb91fe5ae6`，原始执行的证据提交为 `37d6024e787262dddebf084aaccd9661b93c7a0e`。
运行窗口为 2026-11-25T08:21:18.086597Z 至 2026-11-25T08:32:00.843432Z，总耗时 642.757 秒。

## 原 13 项测量

| 指标 | 实测结果 | 单位 |
| --- | ---: | --- |
| `file_count` | 1000000 | files |
| `directory_count` | 500 | directories |
| `directory_depth_max` | 12 | levels |
| `average_file_size` | 1792.0 | bytes |
| `source_api_quota` | 6000.0 | requests_per_minute |
| `source_change_frequency` | 17982.504701292746 | changes_per_hour |
| `enumeration_rate` | 3926.048386087165 | objects/s |
| `incremental_scan_cost` | 0.017023402 | s |
| `memory_peak` | 26.44140625 | MiB |
| `filename_characteristics_profiled` | true | boolean |
| `provider_characteristics_profiled` | true | boolean |
| `range_support_profiled` | true | boolean |
| `etag_behavior_profiled` | true | boolean |

## 五项退出条件

1. 固定层级覆盖 1,000,000 个文件和 500 个目录，最大深度 12，平均文件大小 1792 字节。本地适配器上限为每分钟 6000 次请求。
2. 实测创建、更新和删除各一次。三次变化的观测跨度为 0.600584 秒，每小时变化数按此受控窗口折算。
3. 固定层级中 442 个父路径有直接子项，最大直接扇出为 2,273。规模计算使用固定输入清单、实测深度及变化窗口，原始清单引用及校验值可从执行记录查证。
4. 扫描器枚举耗时 254.836391 秒，平均 3926.05 个对象每秒。三次变化的增量阶段耗时 0.01702340 秒，扫描器峰值内存为 26.44 MiB。
5. 文件名、路径和 OpenList 来源特征有对应的原始观测。五次 Range 和 ETag 探测状态依次为 200、200、206、416、200。ETag 在未变更时保持稳定，受控更新后发生变化。

## 来源遍历

| 遍历 | 页数 | 对象数 | 请求跨度（秒） |
| --- | ---: | ---: | ---: |
| 1 | 1,385 | 1,000,500 | 156.256685 |
| 2 | 1,385 | 1,000,500 | 137.373398 |

来源遍历和扫描器枚举各自计时。适用范围限于本次隔离环境、OpenList 配置、固定合成样本和本地适配器。

## 清理与证据

扫描控制器和 OpenList 均完成实际退出并返回 0。实验记录选取 11,224 份原始材料，共 582,042,601 字节。另在隔离实验盘保留 10 个数据库文件，逻辑总长为 3,169,824,768 字节。

已逐项核对三次受控文件变更。合成样本保留本次创建、更新和删除后的状态。

[原始执行记录](execution-candidate.json) · [证据清单](evidence-delivery-inventory.json) · [统计依据](local-v1-exit-observations.json)
