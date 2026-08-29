# GZ-014 Risks

- Changing future Task IDs after implementation starts could invalidate handoffs; therefore GZ-014 blocks downstream starts.
- Public contract ownership can be over-constrained if owner and consumer are not separated.
- Repository checks cannot enforce direct-push prevention while GitHub Ruleset remains disabled.
- A stale lease must be released or renewed by the Coordinator rather than silently ignored.
