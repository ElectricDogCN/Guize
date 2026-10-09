# OPS-004 failed Completion source reconstruction

Original actual published source: c5bf21c9be5ed69fcda283bc64b3e2d4b4755bf4
Original tree: 7b86f49ac661286611042ae76627296ec6af1794
Original parent: 62d4ef826e0be1acb2839c3f04fe62d1894f9585
Original PR #75 is closed, unmerged; the source branch is retained.

The scope archive will also include this exact failed source as an additional Git parent; its first parent remains the actual tested scope source 7f77774ea2bce6948b4de7214f49e8bbc0fc0c09. This preserves the original Git object and raw source, not a rewritten equivalent alias. No completed metadata from the failed tree is adopted by the final scope tree. Verify actual parents/ancestors after publication.

```bash
git fetch origin chore/OPS-004-history-scope-registration
git cat-file -e c5bf21c9be5ed69fcda283bc64b3e2d4b4755bf4^{commit}
git rev-parse c5bf21c9be5ed69fcda283bc64b3e2d4b4755bf4^{tree}
git merge-base --is-ancestor c5bf21c9be5ed69fcda283bc64b3e2d4b4755bf4 origin/chore/OPS-004-history-scope-registration
git checkout --detach c5bf21c9be5ed69fcda283bc64b3e2d4b4755bf4
git diff 62d4ef826e0be1acb2839c3f04fe62d1894f9585 HEAD -- specs/coordination/program-plan.yaml specs/coordination/active-work.yaml specs/tasks/OPS-004.md
```

Its original local formal failure commands remain in test-results/completion-first-c5bf/. Actual Gate598 had349 passes/2 failures. Failure is retained and has not been rerun as success or relabeled.
