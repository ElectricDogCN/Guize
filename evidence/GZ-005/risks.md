# GZ-005 risks

The normal YAML anchor resides on GZ-005: changing its status without preserving
other tasks' resolved statuses would claim unrelated work. Compare fully parsed plans.
The implementation branch claim differs from the pure reservation PR branch; reserved
coordination explicitly permits this same-Task reservation route.
Metadata validation does not prove API correctness. Schema parsing, meaningful negative
tests, permission review and compatibility checks remain implementation acceptance work.
