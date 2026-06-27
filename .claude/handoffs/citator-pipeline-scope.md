# Citator pipeline — scope & contracts (gun law, anchored on Bruen)

The aligned spec for the proposition-level citator. Each pipeline stage ships as
its own feature in a fresh session (FE + BE contract scoped here). This doc is the
shared source of truth those sessions start from. Grounded numbers below are real,
pulled from the CourtListener API on 2026-06-27.

## 1. Vision & value proposition

A **proposition-level** citator for gun law. Not "is Bruen good? 🟢/🔴" — that
question is malformed, because a case is a *bundle of propositions* and treatment
attaches to each one separately. The deliverable a litigator actually wants:

> **The composed operative rule, per proposition, with stability + provenance.**
> For Bruen: *"Good law as modified by Rahimi (2024) — the public-carry holding
> (P1) is intact; the text-history-tradition methodology (P2/P2a) and sensitive
> places (P3) are now iffy to cite without the Rahimi gloss."*

That "still good but iffy on these propositions" signal **is** the product.

## 2. Locked decisions

- **Scope:** built generally, proven on **Bruen**, then expanded to the gun-case
  cluster (Heller / McDonald / Caetano / Rahimi + circuit battlegrounds).
- **Starting data is clean** (see §3) — the retrieval engine reliably delivers the
  correct inbound edges (incl. Rahimi). Downstream stages assume this.
- **Never drop, tier by depth.** The filter decides *how much analysis* an edge
  gets (`deep | shallow | mention`), never *whether it's visible*. A lawyer can
  discard fast; hiding is worse than mentioning. Surface everything, rank it.
- **Operative-rule format:** "Bruen as modified by Rahimi."
- **Ship per-feature, one at a time, in fresh sessions.** Contract-first: the
  frontend mock leads, the backend implements *to* it.
- **Proposition spine is lawyer-confirmed** (§4).

## 3. Retrieval contract (the "clean starting data")

Forward-looking: given a target, find later opinions that cite/treat it.

> **Retrieval = full-text search for ALL of the target's parallel citations,
> unioned with the structured `cites:` graph, deduped by cluster.**
> Bruen's parallel cites: `597 U.S. 1` · `142 S. Ct. 2111` · `213 L. Ed. 2d 387`.

**Why full-text is mandatory, not optional** — verified on Bruen:

| Path | Catches the binding Rahimi→Bruen edge? |
|---|---|
| `cites:(6352829)` search operator | ❌ |
| Rahimi's own `opinions_cited` list (85 entries) | ❌ |
| `/opinions-cited/` raw M2M table | ❌ |
| Full-text `q="597 U.S. 1"` (Rahimi's text cites Bruen) | ✅ |

CL's citation extractor (eyecite) missed Rahimi→Bruen — almost certainly because
Bruen's official `597 U. S. ___` pagination wasn't final when Rahimi was ingested
(June 2024). **Quantified:** structured graph returns **7** SCOTUS citers of Bruen;
full-text returns **15**, adding Rahimi (2024) and Hemani (2026) — the two missing
binding gun-merits cases. Per-case the graph is unreliable; full-text guarantees
recall. No hand-injection needed: anything citing the target by reporter is
catchable. (Residual gap: a binding case discussing the target *only by name* — a
named-entity pass mops that up later.)

Every edge carries provenance: `source: "graph" | "fulltext"`, the matched
citation string, and the citing opinion URL.

## 4. Proposition spine (lawyer-confirmed)

Track each proposition + the verbatim opinion-text phrases a classifier should
detect. Bruen citers grounded by phrase: §922(g) **289**, methodology **168**,
sensitive places **99**, common-use/AWB **91** (of **847** total).

| ID | Proposition | Status | Signal phrases |
|---|---|---|---|
| P1 | Public-carry right; "proper cause" struck | settled holding | `proper cause`, `special need`, `may-issue`, `shall-issue`, `second-class right` |
| P2 | Text-history-tradition; means-end scrutiny rejected | settled method | `text, history, and tradition`, `means-end`, `two-step`, `interest balancing`, `one step too many` |
| P2a | Analogue **not** twin; "how & why" / relevantly similar | clarified by Rahimi (hot) | `historical twin`, `dead ringer`, `relevantly similar`, `how and why`, `comparable burden`, `regulatory straightjacket` |
| P3 | "Sensitive places" (left undefined — dicta) | contested/expanding | `sensitive place(s)`, `island of Manhattan`, `polling places`, `private property` default |
| P4 | Arms scope: common use / dangerous & unusual | circuit split (AWB/LCM) | `in common use`, `dangerous and unusual`, `assault weapon`, `large-capacity magazine`, `Caetano` |
| P5 | "The people" / disqualification (felon, DV, §922(g)) | hottest split | `the people`, `law-abiding`, `responsible`, `922(g)(1)`, `categorical`, `as-applied`, `non-dangerous` |
| P6 | Historical era 1791 vs 1868 (reserved) | open/background | `1791`, `1868`, `Reconstruction`, `level of generality`, `too late` |
| P7 | Shall-issue licensing presumptively lawful (fn.9 + concurrence) | dicta, reaffirmed | `shall-issue`, `footnote 9`, `good moral character`, `43 States`, `exorbitant fees` |
| P8 | Heller "presumptively lawful" carve-outs survive | reaffirmed dicta | `presumptively lawful`, `longstanding prohibitions`, `felons and the mentally ill`, `commercial sale` |

**Rahimi (602 U.S. 680, 2024) treatment, by proposition:** reaffirms P2; **clarifies/
narrows the rigid reading of P2a** ("misunderstood the methodology", "trapped in
amber", "not a dead ringer / historical twin"); adds the **dangerousness principle**
("credible threat to physical safety" → may be disarmed); **limits P5's
"responsible"** framing (rejects it as a vague standard); reaffirms P8. **Does not
overrule Bruen.**

**Attribution trap:** "trapped in amber" is *Rahimi's* phrase, not Bruen's. A citer
quoting it is echoing Rahimi — attribute the treatment to Rahimi (self-vs-reported),
do not score it as the citer's own overruling.

## 5. Bruen golden example (the worked end-state)

```
Target: NYSRPA v. Bruen, 597 U.S. 1 (2022)  ·  CL cluster 6480696
Operative rule: "Good law as modified by United States v. Rahimi (2024)."

  P1 public-carry right ............ 🟢 GREEN  reaffirmed; no binding negative
  P2 text-history-tradition ........ 🟢 GREEN  reaffirmed (Rahimi follows it)
  P2a analogue-not-twin ............ 🟡 AMBER  limited/clarified by Rahimi (binding)
  P3 sensitive places .............. 🟡 AMBER  contested; Wolford (2026) partial
  P4 common use / AWB .............. ⚪ watch  circuit split, SCOTUS grant likely
  P5 the people / §922(g) .......... ⚪ watch  entrenched felon split; Rahimi gloss

Key edges:
  Rahimi (SCOTUS 2024)  → limited · scope P2a · attribution self · binding · conf .9
  Antonyuk (CA2 2024)   → followed · scope P1/P3 · binding-in-circuit
  "...overruled by Bruen" (DCD)  → mention · reversed-direction (Bruen is the actor)
  "overruled by operation of law" → mention · procedural noise
```

A draft TS fixture of this exists at `frontend/lib/fixtures/bruen.ts` (predates the
§2/§4 refinements — adopt & update it in the feature work, don't treat as final).

## 6. Pipeline & per-feature roadmap

Each row = one fresh session = one PR, with a scoped FE screen + BE contract.
`[code]` deterministic · `[LLM]` constrained model · `[API]` primary source.

| # | Feature | Stage type | One-line job |
|---|---|---|---|
| 0 | **Input framework** | spec | *this doc* — grounded inputs + propositions ✅ |
| 1 | **Filter** | `[code]` | tier the long list (deep/shallow/mention); never drop |
| 2 | **Classify** | `[LLM]+[API]` | per-edge: treatment + scope→proposition + attribution + verbatim quote |
| 3 | **Relate / Chain** | `[code]+[LLM-verify]` | bucket edges by proposition; foundation/refinement chain |
| 4 | **Aggregate** | `[code]` | per-proposition signed risk; compose the operative rule |
| 5 | **Synthesize** | `[LLM]` | grounded, source-linked rationale |

The stepper frontend grows one screen per feature (Resolve → Citations/Filter →
Treatment → Relation → Verdict).

## 7. Feature 1 — Filter (next session)

**Job:** from ~847 edges, decide *depth of analysis* per edge so the expensive LLM
runs only where it pays. Cheap, deterministic, auditable. **Never drops** — even
noise is surfaced as `mention`.

- **Input contract** `Edge[]`:
  `{ citing_case{name,court,date}, citation, passage, source, proposition_phrase_hits[] }`
- **Output contract** `TieredEdge[]`:
  `Edge & { tier: "deep"|"shallow"|"mention", reasons[], signals{ binding, treatment_kw, propositions_engaged[], recency } }`
- **Logic:** score = binding-court × treatment-keyword × proposition-phrase ×
  recency. `deep` = binding court + strong treatment/proposition hit (and apex
  binding treatments like Rahimi are force-`deep`). `mention` = reversed-direction
  ("overruled by <target>"), procedural ("by operation of law"), bare cite —
  surfaced, low-ranked, not analyzed deeply.
- **FE screen:** "long list → shortlist" — 847 collapsing to N, each with
  why-tiered, grouped by proposition. The funnel made visible.

## 8. Cross-cutting principles

- **LLM proposes & reads · code decides & computes · API grounds every claim.**
  The risk score is never the model's. Every LLM output is schema-constrained +
  verbatim-quote-verified, or checked by a second pass.
- **Provenance non-negotiable:** every signal links a quote + source URL.
- **Abstain when uncertain** (low confidence / conflicting strong signals →
  "needs review"). A confident wrong answer is the malpractice boundary.

## 9. Parked / verify-before-lawyer-facing

- **AWB/LCM cert cluster** (Duncan, Gator's, NAGR v. Lamont, Viramontes, Grant) —
  NOT granted/denied as of 2026-06-27; re-pull the latest order list before any
  output asserts a grant. Most volatile fact in the space.
- **Pin cites** for F.4th circuit cases and the 2024–26 SCOTUS slip opinions need a
  reporter/Westlaw confirm before lawyer-facing output (slip PDFs 403'd fetchers).
- Name-collision traps to encode later (e.g. §922(g)(1) "Jackson" 8th Cir vs §922(n)
  "Jackson" 4th Cir; *Connelly* is §922(g)(3) not §922(n); vacated ≠ good law).
