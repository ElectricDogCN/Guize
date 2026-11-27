# Worker 启动校验

在 Python 3.11 或更高版本中安装本目录的依赖，使用 GZ-008 的固定 SDK 启动兼容性校验。

```bash
python -m pip install -r services/guize-worker-agent/bootstrap/requirements.txt
python specs/contracts/runtime/build_worker_sdk.py worker-sdk-v1.zip
python services/guize-worker-agent/bootstrap/bootstrap.py --sdk worker-sdk-v1.zip
python services/guize-worker-agent/bootstrap/test_bootstrap.py
```

通过时输出 `worker-v1`、SDK 版本、摘要及实际通过的向量数。摘要不匹配时退出 1。校验使用 SDK 中的原始实现，可以在仓库外运行。成功表示启动环境满足协议要求，任务领取和媒体执行由后续 Worker 接入处理。
