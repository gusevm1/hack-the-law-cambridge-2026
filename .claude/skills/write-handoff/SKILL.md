---
name: write-handoff
description: >-
  Use when the current session's work will be continued by a fresh session:
  pausing mid-feature, ending a work block with follow-on work, switching GCP
  accounts mid-task, or whenever the user says "write a handoff", "hand this
  off", or "prep this for the next session". Distills the session into a brief
  at .claude/handoffs/<slug>.md carrying exactly what the next session needs —
  live-bearing decisions, constraints, unfinished steps — and deliberately drops
  resolved dead ends. Do NOT use for work that finished cleanly (update STATE.md
  instead) or for mid-session note-taking.
---

# write-handoff — distill a session brief for the next session

A handoff is a **filter, not a transcript**. The next session pays context cost
for every line; the value you add is deciding what it does NOT need to read.
Write for a competent engineer with zero memory of this conversation.

## The distillation rule (the whole point)

Sort every fact into three buckets:

1. **Carry** — still load-bearing: decisions made (with the one-line why),
   constraints discovered, unfinished steps, sharp edges hit, operator
   preferences voiced.
2. **Park** — durable but not needed to continue: record it in its proper home
   *now* (`STATE.md`, project memory) and at most point to it from the brief.
   Never inline it.
3. **Drop** — consumed by the session itself: abandoned dead ends, intermediate
   states later steps superseded, anything re-derivable in one file-read or one
   command. Deleting these is the job, not a risk. If a dead end must be
   remembered so it isn't retried, carry the *conclusion* in one line.

When unsure: "if the next session never saw this, would it do something wrong or
redo paid work?" No → drop.

## Structure (adapt, omit empty sections)

Write `.claude/handoffs/<slug>.md` (slug matching the feature branch when one exists):

```markdown
# Handoff — <task name>

**Mode line.** One sentence: is the next session executing, designing, or
investigating? If operator decisions must be elicited before building, say so
HERE, bold, first.

## State (quantified)
What is done and VERIFIED (PR #s / live-URL checks), what is in flight (branch),
what is not started. Never report unverified work as done.

## Carry-over notes
Decisions + one-line rationale, constraints/invariants not to break, gotchas hit
(with pointers if parked in STATE.md / memory).

## Open questions / operator decisions pending
Each with enough context to decide. Mark which BLOCK the work.

## First moves
2-4 concrete steps. Name exact files to read (skim vs read fully) — the brief
routes attention, it doesn't duplicate content.

## Teardown note
"Delete this handoff (move to archive/) when consumed."
```

## Protocol

1. **Pair it with STATE.md.** A handoff never substitutes for hot state — update
   `STATE.md` (in-flight item pointing at the brief) in the same change.
2. **Land it on the right branch.** A brief for in-flight feature work lives on
   the feature branch; a cross-cutting brief lands on `main` via a normal docs PR.
3. **Consume = archive.** The session that finishes a brief moves it to
   `.claude/handoffs/archive/` in its wrap-up commit.
4. **Size guard.** A brief over ~100 lines is hoarding — push more into Park and
   Drop. The brief holds *momentum*, not history.
