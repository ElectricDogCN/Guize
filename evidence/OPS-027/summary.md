# OPS-027 正常审查

实现合并 `ba5f5a086cecc2a595b16f4e34da0cd85d60e237`（PR #249）。当前基线 `93eb6e99955404ec1ece78041bd73fa0355b5d80` 的前置阶段已通过独立审查、七项本地检查及完整官方 [源验证](https://github.com/ElectricDogCN/Guize/actions/runs/45342264511)、[主线验证](https://github.com/ElectricDogCN/Guize/actions/runs/45344539699)。本候选需要自身的完整官方源验证和实际主线验收。

原实现的[固定源 CI](https://github.com/ElectricDogCN/Guize/actions/runs/44445532521)和[实际主线 CI](https://github.com/ElectricDogCN/Guize/actions/runs/44449302925)均已独立验证通过 1,078 项，实际实现主线的 224 项 POC 校验器用例亦全部通过。归档 PR #261 保留本次冻结恢复五项验证原件。

## 原实现的独立 POC 校验器验证

固定源 `773791f95b7a82c7b8047989065e0007f29fd8eb` 和实际实现主线 `ba5f5a086cecc2a595b16f4e34da0cd85d60e237` 分别完整执行 224 项，均退出 0，零失败、错误或跳过。以下命令将实际解释器及输出路径写成可移植形式。

```bash
python -B -m pytest -v -ra -n 2 --dist=load -p no:cacheprovider --color=no specs/poc/test_program.py --junitxml=standalone-poc.xml
```

| 执行版本 | 原始日志 SHA-256 | JUnit SHA-256 |
| --- | --- | --- |
| 固定源 | `3fc26553363b3cf9ada8c581f442db38a3420e253ec292466b6b44f13da27ee1` | `c326356ff60778878344d765c16d7eceff245e1edd08ae67eb673200ea9046ea` |
| 实际实现主线 | `8b135eb59d1e96bacec11c5a7487f7c3dc22bdfd9f4d01bd279c534154744f11` | `4d7ec20c4dc18bfe60f772d74569bacc6ff13599280eecec34206cb68500aff7` |

该结果用于 OPS-027 实现审查。POC-003 和 POC-005 的正式验证各自需要当前版本的运行结果。

## 可查阅的运行记录

下表提供完整测试输出和 JUnit 的公开副本。测试输出以 gzip 压缩，解压后的字节只替换了五处本机路径。JUnit 只替换了主机名。公开副本保留实际源码、全部测试条目和结果。上表的 SHA-256 对应保留供独立审查的原件。

| 执行版本 | 记录 | 公开副本 SHA-256 |
| --- | --- | --- |
| 固定源 | [pytest](test-results/standalone-224/source-pytest.txt.gz) | `9e6a17a4f63e840c1783d1b662bf4a64f4e21c2f393d8140a20b6cb634d0b50b` |
| 固定源 | [junit](test-results/standalone-224/source-junit.xml) | `98c9fd25332a87ea532be3709efc4ec60aacb9e5f89f4532b73952a2aa6c2b42` |
| 实际实现主线 | [pytest](test-results/standalone-224/main-pytest.txt.gz) | `204337dedf70348cd901dba0a2fd630b2c42401b3008a468f779568a11f81c40` |
| 实际实现主线 | [junit](test-results/standalone-224/main-junit.xml) | `9a8b65e9d3a141d524a9ff89fe82236d5cfd77654b281c7cba91efd201c7853e` |

## 历史开发状态

<!-- Development-only diagnostic: original151 + two new compatibility cases + eleven key-reuse cases =14, actual zeroFES. Fixed-source/full224 and official1078 still pending. See evidence/OPS-027/local-origin-compatibility-v1/development-diagnostic.json. -->
OPS-027 NEEDS_REVIEW. Minimal mapped IPv6 fullhex canonical compatibility code after independently accepted prospective Own metadata 1868291c2eb04755469efd9b8bf2e31b4cee22ed. Original222 tests retained;2new tests,224 total. Development/fixedsource/fullCI results UNEXECUTED. Original994 failed/interrupted and1058 cancellations retained. No public source/main/thaw/currentPOC qualification.


## OPS-027 正式结项

Status: COMPLETED

OPS-027 的结项实现为 PR-268，实际合并 `5d4bfd1e70fbe9e161a64cbaabfe561044161ded`。范围恢复的实际主线 `409789aa12d9d6e76ce8855ef8559215b6d7903d`。 交付检查记录见 [实现实际主线 CI](https://github.com/ElectricDogCN/Guize/actions/runs/45413642714) · [范围恢复实际主线 CI](https://github.com/ElectricDogCN/Guize/actions/runs/45421862729)。正式结项候选待自己的完整源和实际主线 CI。
