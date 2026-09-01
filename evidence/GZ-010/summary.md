# GZ-010 Reservation v2 Summary

Task: GZ-010
Status: RESERVED candidate
Base: `main@d23543f97facff00d02f79aab1693a37788765c9`
Reservation branch: `chore/GZ-010-reservation-v2`
Implementation branch: `chore/GZ-010-poc-program-baseline`

## Purpose

This commit reserves GZ-010 only. It registers Program status, one Active Work lease, Task Spec, roles, exclusive output paths and task-bound Evidence. It does not implement `POC-PROTOCOL-V1` and does not execute POC-01～10.

## Prior attempt

PR #42 was the first Reservation attempt. Its Gate #374 failed because a governance test fixture deleted a legitimate copied Active Work lease. PR #42 was closed without merge. OPS-003 #43 was repaired by PR #44 and post-merge main Gate #380 succeeded. This v2 Reservation is rebuilt from that new green main and does not inherit #42 as a PASS result.

## Current claim boundary

Only Reservation metadata is claimed. No POC command, measurement, result, decision or reviewer outcome exists yet. The v2 exact-head PR Gate and post-merge main Gate remain required before implementation may begin.
