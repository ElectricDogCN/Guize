# GZ-005 follow-ups

1. Validate this exact reservation source, archive actual results, obtain independent
   review, pass latest CI and merge with expected head before activation.
2. Implement V1 OpenAPI, stable errors and schema-valid HTTP examples within own paths.
3. Exercise schema/ref resolution, write idempotency, permissions, trace IDs, coverage
   and compatibility with meaningful negative cases; independently review content.
4. GZ-012 incorporates these contract checks into language CI before application builds.
5. Complete GZ-005 separately after the reviewed implementation merges and main passes.
