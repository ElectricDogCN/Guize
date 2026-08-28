# CI Workflow 规划

建议拆分为：

- `java-ci.yml`
- `python-ci.yml`
- `go-ci.yml`
- `frontend-ci.yml`
- `contract-ci.yml`
- `security-ci.yml`
- `container-release.yml`
- `deployment-bundle.yml`
- `docs-ci.yml`

正式实现时使用可复用 Workflow，并固定 Action 版本或 SHA。
