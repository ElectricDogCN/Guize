# GZ-004 Reservation Rollback

Before merge, close the reservation PR and retain the branch. After merge, create a dedicated Revert PR that restores GZ-004 Program status to `planned`, removes only the GZ-004 Active Work Lease, and removes the GZ-004 Task/Evidence reservation artifacts. Never push or rewrite `main` directly.
