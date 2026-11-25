# Domain Event contract checks

本目录包含离线检查器、正向样例和回归用例。正式目录与 Schema 位于 `contracts/events`。GZ-006 以 [Issue #128](https://github.com/ElectricDogCN/Guize/issues/128) 和登记 [PR #279](https://github.com/ElectricDogCN/Guize/pull/279) 为范围依据。样例均使用合成标识。

```bash
python specs/contracts/events/check_contract.py
python specs/contracts/events/test_contract.py
```

使用 `requirements.lock.txt` 中的固定依赖。命令验证全部登记版本的样例、聚合身份、时间和有效 Schema 兼容。要验证与历史目录的兼容，可执行 `python specs/contracts/events/check_contract.py --previous-root PATH`。既有版本的 Schema 和语义不可变，公共 Envelope 参与比较，各版本的其余定义保留在自身 Schema 中。

与现有模块的生产和消费关系见 `specs/designs/module-ownership.yaml`。领域事件记录控制面已提交的事实，受控执行、事务和真实端侧验证由相关运行任务交付。
