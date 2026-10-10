# V1 control-plane contract

Entry: `contracts/openapi/common/openapi.yaml` (OAS 3.1.1 / API 1.0.0).
Module Path Items use local references. Shared DTOs, stable errors and illustrative
serialized HTTP fixtures live in `contracts/openapi/common/`.
`coverage.yaml` binds the actual operation inventory to the assigned frozen requirements;
`semantics.md` specifies permission, replay, approval, content and concurrency boundaries.
These are a contract candidate until independent review and integration finish.

Use Python 3.12 in a separate environment. This task's tool environment is independent
of the existing governance environment; no governance dependencies or scripts change.
All tool dependencies are pinned with wheel hashes in requirements.lock.txt for
Linux x86_64 / CPython 3.12. These are validation tools, not production dependencies.

```bash
python -m pip install --require-hashes -r specs/contracts/openapi/requirements.lock.txt
python -m openapi_spec_validator contracts/openapi/common/openapi.yaml
python specs/contracts/openapi/check_contract.py --base-ref origin/main
python -m pytest specs/contracts/openapi/test_contract.py -q
```

For this first baseline only, use the actual pre-API integration base:

```bash
python specs/contracts/openapi/check_contract.py --base-ref 429a6566d81f128cb618c524ee8dc22faba1c0a4 --initial-baseline
```

After the baseline has merged, compare to the real target main base without the
initial flag. Missing baseline then fails closed. The optional `--bundle /tmp/guize-openapi.yaml`
writes a resolved artifact outside canonical source; it never replaces the checked-in
multi-file source. External/escaping references and duplicate YAML keys are rejected.
Reference siblings may carry descriptive annotations only. Assertion siblings fail
closed rather than replacing the constraints of the referenced schema.

Approval proposals include the complete protected request. The reference validator
resolves its operation, validates its body and recomputes the bound RFC 8785 digest.
The server must independently derive the authorized action, targets and revisions,
persist the verified immutable intent and present that intent to the approver.
Execution must recompute and compare the actual request. The hashing helper is not
an authentication, authorization or approval service.

Passkey registration and authentication use separate typed WebAuthn options. Binary
JSON fields require canonical unpadded Base64url. Fixtures contain synthetic bytes,
not valid attestations or signatures; browser and server cryptographic verification
remain downstream integration work.

The HTTP samples are actual serialized CRLF request/response pairs parsed against
the corresponding paths, required headers, content lengths, typed bodies, trace IDs
and response schemas. Credentials/grants are deliberately invalid example placeholders.
They prove contract consistency, not server execution, cryptographic validity or
end-to-end behavior. No application server exists in this task's scope.

Meaningful negative cases exercise malformed data, source secret leakage inputs,
client ACL injection, public expensive playback, generated-thumbnail identity,
missing approvals/idempotency/trace, broken refs, SSE and API compatibility, and
HTTP wire boundaries. GZ-012 wires these exact checks into language CI and adds real
DTO/consumer checks before business implementation. GZ-013+ provides runtime/E2E proof.

Primary tool/format references: [OpenAPI 3.1.1](https://spec.openapis.org/oas/v3.1.1.html),
[validator documentation](https://openapi-spec-validator.readthedocs.io/en/latest/),
[pinned validator release](https://pypi.org/project/openapi-spec-validator/0.9.0/).
Canonicalization: [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785),
[rfc8785 0.1.4 license](https://github.com/trailofbits/rfc8785.py/blob/v0.1.4/LICENSE).
WebAuthn JSON options: [W3C Recommendation, 25 August 2026](https://www.w3.org/TR/2026/REC-webauthn-3-20260825/).
The selected standard is pinned for compatibility; it is not claimed to be the latest.
