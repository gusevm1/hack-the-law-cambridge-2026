# Feature 5 (C) — Use-aware verdict (the payoff)

You're building the **crown-jewel** stage: risk **relative to the lawyer's intended
use**, not the case as a whole. "Bruen is fine for public-carry (P1) — but if you
lean on the rigid history-twin reading (P2a), Rahimi limited that: real risk." Fresh
session — read before coding.

## Read first (in order)
1. `.claude/CLAUDE.md` + `STATE.md`.
2. `.claude/handoffs/citator-pipeline-scope.md` — §1 vision, §4 spine, §5 golden end-state.
3. `.claude/handoffs/citator-pipeline-contracts.md` — **Contract B is your input,
   Contract C is your output.**
4. See `frontend/app/assistant/page.tsx` for the existing use-dropdown idiom.
5. Invoke `ship-feature` BEFORE coding. ponytail. Branch: `feat/citator-use-verdict`.

## What you're building
Backend `POST /cases/{id}/verdict {use, intent} → VerdictResponse` (Contract C) +
the stepper's **entry input** (use dropdown + free-form) and **Verdict** step.

The logic:
1. **Map use → propositions.** The dropdown is **substantive, proposition-aligned**
   (decision 1a): "public-carry right (P1)", "history-and-tradition test (P2/P2a)",
   "sensitive-places restriction (P3)", "assault-weapon/magazine ban (P4)",
   "felon/§922(g) disqualification (P5)", "licensing regime (P7)". The free-form
   `intent` refines; an LLM maps anything off-menu to proposition ids (schema-
   constrained to `PROP_IDS`). Each dropdown option SHOULD carry its default P-id(s)
   so the common path is deterministic and the LLM only handles free-form nuance.
2. **Intersect** the engaged propositions with the **compromised** ones (signal
   amber/red from Contract B). `real_risk = engaged ∩ compromised ≠ ∅`.
3. **Explain** for THIS use: which engaged propositions are compromised and how
   (pull B's `what_changed`), or why the use is safe despite erosion elsewhere.
4. **Compose final_labels** from B's signals: operative rule + per-proposition
   signal + split/cert/close-to-overruled flags relevant to the use.

## Build
- Consume Contract B (`PropositionsResponse`) — **mock it to contract** (Feature 4
  builds it in parallel); seed a Bruen mock matching §5 (P1 green, P2/P2a, P3 amber,
  P5 split).
- Keep the use→risk computation a **pure function** (`compose_verdict(props, mapping)
  -> VerdictResponse`), unit-testable. The use→proposition LLM map is the one impure
  part (mirror `llm/classify.py`: schema-constrained + fallback to the dropdown's
  default P-ids).
- New module `citator/verdict.py` (pure) + `llm/usemap.py` + route `routes/verdict.py`.
  Models per Contract C in `api.py`. Register in `main.py`.
- Frontend: add the use dropdown + free-form to the entry/Resolve screen (own file
  or minimal page edit); own step file `app/citator/analyze/steps/verdict.tsx` —
  lead with the **use-specific** real-risk banner (green/red FOR YOUR USE), the
  operative rule, then the per-proposition breakdown with "relevant to your use"
  highlighted.

## Acceptance
- `just lint && just test` green; pure-function unit test: use→P1 only, P1 green ⇒
  `real_risk=false` ("safe for your use though P2a eroded"); use→P2a, P2a amber ⇒
  `real_risk=true` with explanation; off-menu intent maps via the LLM (mocked).
- `pnpm build` clean; Verdict step renders the Bruen golden end-state per use.
- PR vs main, CI green, preview checked. Deploy with `PROJECT_ID=…`.

## Boundaries
- You consume per-proposition verdicts + the user's use; you emit the **use-aware
  final**. **No re-deriving proposition risk** (that's B) and no deep reading (A).
- Real risk is the **intersection**, computed in code — the model only maps use→
  propositions (schema-constrained, with a deterministic dropdown default).
- Contract-first: FE mirrors `VerdictResponse` exactly.
