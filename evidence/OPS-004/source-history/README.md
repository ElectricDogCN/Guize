# OPS-004 Durable review source snapshots

The original local test SHAs and the later public archive SHAs are distinct. Raw logs retain the original Source Commit; the archives provide exactly the same complete Git trees for reproduction. They do not claim the original local commits are remote ancestors. The mapping and actual native fetch/tree/parent/full-diff checks are in `review-source-map.json`.

Both archive commits are included in this Review PR's immutable Git parent history: the evidence archive publication keeps the existing reviewed head as its first parent and `5dce717e6224e1cf955926721807cbda4db9034b` as an additional parent. The second archive is a child of the first, which is a child of the actual implementation merge. The archive branch remains an auxiliary ref; reproduction does not depend solely on retaining that mutable branch. Actual ancestry/object/tree checks on the published head are required before integration.

| Original local tested source | Exact tested tree | Durable equivalent commit |
| --- | --- | --- |
| b1f729aa360954ba6036c188c4c0f5d67122305a | 9e9876db50cf5ae1707ca834b3fed0c66157f4d3 | 5cb09fb1824dfc50a854456f24948b53b1696598 |
| 3517a9d633a534f4502938aedec9360887079903 | e896283d321aa469fc70836aa2e1a70eeac760dc | 5dce717e6224e1cf955926721807cbda4db9034b |

Fetch from a normal repository clone and reproduce the corrected metadata candidate in a separate worktree:

```bash
git fetch origin refs/heads/chore/OPS-004-lifecycle-repair-review:refs/remotes/origin/chore/OPS-004-lifecycle-repair-review
git merge-base --is-ancestor 5cb09fb1824dfc50a854456f24948b53b1696598 origin/chore/OPS-004-lifecycle-repair-review
git merge-base --is-ancestor 5dce717e6224e1cf955926721807cbda4db9034b origin/chore/OPS-004-lifecycle-repair-review
git cat-file -e 5dce717e6224e1cf955926721807cbda4db9034b^{commit}
git cat-file -e e896283d321aa469fc70836aa2e1a70eeac760dc^{tree}
git worktree add --detach ../ops004-review-reproduction 5dce717e6224e1cf955926721807cbda4db9034b
cd ../ops004-review-reproduction
git switch -c chore/OPS-004-lifecycle-repair-review
python scripts/check-task-file.py --task OPS-004
python scripts/check-program-plan-history.py --base-ref 726870c8ae161eab19f94a9b96980a7d9197b633 --head-ref HEAD --task OPS-004 --branch-name chore/OPS-004-lifecycle-repair-review
python scripts/run-program-lifecycle-gate.py --base-ref 726870c8ae161eab19f94a9b96980a7d9197b633 --head-ref HEAD --task OPS-004 --branch-name chore/OPS-004-lifecycle-repair-review
python scripts/run-agent-coordination-gate.py --base-ref 726870c8ae161eab19f94a9b96980a7d9197b633 --head-ref HEAD --task OPS-004 --branch-name chore/OPS-004-lifecycle-repair-review
python scripts/run-task-scope-gate.py --task OPS-004 --base 726870c8ae161eab19f94a9b96980a7d9197b633
```

Use an isolated clone if that branch already exists in another worktree. The other original check commands are preserved in `../test-results/review-3517a9d/`; substitute only the durable equivalent as the checkout, retain the actual base and branch parameters. The first b1 snapshot contains the subsequently corrected Task narrative and remains historical. Coordination must still reject capacity 2 > 1; lease expiry or later environment changes are not silently waived. Creating the archive is not an additional test run or an overall Gate PASS.

After this correction, validate the actual published PR HEAD and retain that reachable SHA for the next handoff. Completion identity remains PR-73 / 726870c8ae161eab19f94a9b96980a7d9197b633.
