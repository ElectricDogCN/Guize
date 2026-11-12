# OPS-024 implementation validation

Normal implementation starts from accepted reservation main
`439c2c33685dfae9d3893d852bf4044bcfc7e193`, after the separate Own activation
commit `9f4964e877b4e12232c2d418c452998cc7dffd30`.

The workflow changes two existing commands: install fixed pytest-xdist 3.8.0
and append explicit `-n 2 --dist loadfile --max-worker-restart=0` to the original
complete pytest invocation. Original test selection, JUnit location, Skip audit,
steps, runner, action pins and 30-minute limit remain. No environment-level
PYTEST_ADDOPTS is introduced.

Four new regression cases actually passed under Python 3.11.17 / pytest 8.4.2 /
xdist 3.8.0: the command contract and three actual subprocess outcomes (success,
assertion failure, worker crash). The success and assertion cases verify all
four bounded child cases, two worker processes, file grouping and auditable
JUnit. A nested pytest verifies serial configuration. Assertion and crash cases
return failure; crashes are not silently restarted. JUnit skip audit passes.
The working regression run completed with exit 0, four passed, zero skips.

This targeted result is not full-suite or official CI acceptance. The fixed
source still requires original fourteen checks, all original 1,039 cases plus
the four new cases, actual two-worker full execution, complete official source
and actual-main CI, independent Code Review, and normal Review/Completion.
Original cancelled runs remain cancelled. No POC result or old performance
qualification is transferred by this change.
