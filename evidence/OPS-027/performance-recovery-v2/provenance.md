# OPS-027 freeze verification evidence

Both executions used validated main `ba5f5a086cecc2a595b16f4e34da0cd85d60e237` and the same frozen event. The execution ending `2026-11-19T08:49:29.122887+00:00` passed all five commands. Its temporary workspace was unavailable after it exited, so its JUnit file could not be archived.

`programIntegrity.txt`, `lifecycle.txt`, `coordination.txt`, and `verify.txt` retain the original output from that execution. The unchanged full governance command ran again and passed at `2026-11-19T09:36:03.438242+00:00`. `governance.txt` and `governance.xml` come from that second execution. `proof.json` binds these five logs and the retained JUnit.
