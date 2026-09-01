# GZ-010 Reservation Assumptions

Task: GZ-010

- GZ-014 is completed and remains the Program/Harness foundation.
- GZ-004 is completed; its late Completion Evidence findings were repaired by PR #40 and post-repair `main` Gate #373 is green.
- GZ-010 prepares a POC Program only; POC-001～010 remain independent future execution tasks.
- Canonical POC IDs, task IDs, Requirement/Module mappings, Wave, Risk and Evidence paths come from `specs/coordination/program-plan.yaml` and may not be silently reinterpreted.
- No POC command, measurement, target result, PASS/FAIL decision or reviewer conclusion is known at Reservation time.
- Secrets, credentials and unapproved sensitive sample data must never be embedded in repository POC plans or Evidence.
- OPS-002 #41 is a separate Harness debt and does not modify GZ-010 scope.
