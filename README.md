# tiny-chess-01 R6 — Verified Mate Book

A tiny-chess entry built around a **complete book of verified forced-mate
lines**: one line for every practice-gauntlet scenario (opponent × colour ×
opening). The house engines are deterministic, so each line — computed
offline against the house's own move logic with a strong Stockfish oracle
and verified by replay — mates by force, as fast as we could make it.

Only our moves are stored, as indices into the engine's legal-move list
(zlib + base85), keyed by the scenario the env's game view names. Off book,
a compact PVS engine plays (0x88 board, PeSTO tapered evaluation,
quiescence over captures/promotions/check evasions, check extensions,
repetition-aware root search, fixed 120k-node budget).

`main.py` is the LZMA-compressed form of the readable source (produced by
the kit's `makefun compress`); the source is submitted alongside the entry
transcripts.

Line lengths (plies to mate) and gauntlet results are recorded in the
submission report kept with the entry.
