# OPS-004 Test results

Current implementation source 751dc3db960420f64641c4edd935f7669d026c85; actual CI branch environment. 351 passed in 325.18s (0:05:25); 351 nonempty JUnit cases, no failure/error/skip. Full 15-check raw output: test-results/implementation-ci-env-751dc3d/; only bounded capacity coordination/make remain FAIL.

Registration history: registration-59dcba7/ and first failed registration-first-2931cf2/. Real registration CI: registration-remote-590/. Implementation 2da30c0 has one Issue-binding failure; implementation-local-6cb4c67/ has local 350 PASS but CI environment reproduction fails in ops004-ci-env-reproduction-6cb.txt/xml. All retained without relabeling. reproduced-activation-346c9b6/ records the original blocking defect.

## 前向返工范围登记

Current phase: metadata-only review -> blocked; actual base 62d4ef826e0be1acb2839c3f04fe62d1894f9585.

Completion源c5bf真实前4项退出0，history退出1，其余本地检查NOT_EXECUTED。Gate598实际349 passed/2 failed（239.73s），原始见test-results/completion-first-c5bf/。history误把最新Registry.baseSha当首次Reservation基线，与合法Review基线刷新冲突；另一个失败是待测Completion尚无合法完成/PASS证据。当前不声称PASS。只登记自身blocked状态和精确追加history及对应test范围，代码不变、Lease不变、GZ005/政策/Ledger/旧完成不变。新范围实现必须在本登记合入后的独立PR，且再次完整验证/独立审查。
