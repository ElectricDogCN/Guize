# OPS-013 actual parent-source test results

Parent480dc0b607453ba26ec3d9d650c79c1b85f1c06e: Task15 all exit0; full native713/1152.72s, zero failures/errors/skips; JUnit713cases. CI829713/1088.06s and CI830713/1399.25s terminal success with skip audit success. See ../reservation-480dc0b-source-attestation.json, ../reservation-480dc0b-native-retry-accepted/ and the two separate CI archives.

Original3d78e5c Task failure and480 first full-run689passed/1failed/23errors are retained. The latter required isolated Git object-store dissociation, not source/test changes. Actual before/after refs and full fsck are archived with the first failure.

The two unresolved threads prevented480 merge despite successful tests. This own-metadata successor records those real results and fixes text diff attributes. Its exact new source checks, CI and independent merge decision remain PENDING; no copied result is relabeled with the successor hash. Actual main and implementation have not been accepted.
