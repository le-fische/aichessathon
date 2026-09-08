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
