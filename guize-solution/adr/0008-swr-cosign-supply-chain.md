# ADR-0008 SWR + Digest + Cosign

- Status: Accepted
- Date: 2026-07-21

## Decision
华为云 SWR 为主镜像仓库；生产使用 OCI Digest，镜像和离线包签名，部署强制验签，高危漏洞阻断。

## Consequences
CI 和离线部署需要签名、SBOM 和密钥管理。
