# GZ-003 Security Evidence

GZ-003 changes repository governance utilities only.

Security-relevant checks required before merge:

- no Secret or credential is introduced;
- file paths are normalized and remain inside the repository;
- collaboration validation fails closed for missing Git history, schema, descriptor, handoff or diff;
- prompt rendering reads only declared text context and does not fetch external content;
- workflows use read-only repository permissions;
- no workflow pushes, merges, deploys or accesses production systems;
- Owner/Reviewer separation is enforced.

Final status must be taken from the latest Secret Scan, governance tests, Collaboration Checker and PR review.
