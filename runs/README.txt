runs/ is the measurement record.

One directory per session: runs/<date>-<version>/. Every number quoted in
HANDOFF.md, in a report, or in a chat has to be reproducible from a script in
here. Scripts that produce numbers live here alongside their output; scripts that
are part of the workflow live in tools/.

APPEND ONLY. Never delete anything under runs/, including directories that look
stale. This directory is in .gitignore, so a deletion is permanent and
unrecoverable. Most of it was destroyed once, on 5 September 2026, during a
tidy-up. The scripts were restored from copies held outside the repository; two
FINDINGS.md write-ups had to be rewritten from memory.

If something in here looks like clutter, say so and let the human decide.

--------------------------------------------------------------------------
COMMIT REFERENCE MAP -- 2026-09-18

main was rewritten to drop AI co-author metadata from its commits. File
content is byte-identical; only author and message trailers changed. Three
commit ids cited in entries below therefore moved:

    5780243  ->  c3736fd   Add TASKS.md: parallel-safe work for a new collaborator
    5963d9c  ->  5197c06   Add Doubled and Isolated pawn evaluation terms
    e078c41  ->  0f575b8   Add Rook open file and 7th rank evaluation term

Entries are not edited -- this directory is append-only. Read the old id in
any entry above as the new one here. Ids reachable from the danny-test branch
(d27c6f7, 5fb2495, 7b41bcc, 9d21403) were not rewritten and still resolve.
