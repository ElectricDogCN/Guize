# OPS-019 implementation

Accepted reservation main 7d82fb61f434f57bb97cb9d80f4613cee3be2721. Five declared code paths; original intent and all old artifacts remain. Activation metadata precedes code. New source gates and full source/main CI remain UNEXECUTED. No POC migration, largeLFS upload or experiment approved.

## Implementation and first local run

Source bb27de37 added the five registered paths, immutable small retired-commit graph and a 4096-byte LFS probe. Private native Git LFS 3.8.1 installed without global configuration. Preparation v1 rejected an unhydrated pointer; v2 hydrated correctly but receipt referenced absent local main. Both failures are preserved externally. Specialized v3 actually compiled successfully, then pytest returned 1: 2 passed, 10 fixture errors because cloning the prepared graph already creates its default fixture branch. The fixture now reuses only an existing branch at the exact expected commit; no reset, force, amendment or assertion relaxation. No migration or POC experiment occurred.

Independent early review identified three boundaries now implemented and covered by real Git cases: actual main Review before normal Completion; immutable intent/graph/approval even without branch edits; source transactions must descend from the fixed actual authority Completion, never an unadmitted Completion source. Future migration remains forbidden while OPS-019 is active.

The aa71de1a specialized v4 run proved the LFS check, unfinished-authority rejection and full positive source/P/H CLI/ordinary merge case before being superseded by the forward full-history correction. It was explicitly interrupted and is not a complete passing run; raw output, JUnit and actual exit codes are retained externally. The final positive test keeps both real checker CLIs plus exact ordinary-merge permission and replaces one redundant direct full replay with an exact two-path Git delta assertion. All original 842 assertions remain unchanged. The final source must pass all 20 new cases and the normal official CI without timeout changes.
