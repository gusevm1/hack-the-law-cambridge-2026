# CourtListener MCP — setup

A CourtListener MCP server is configured at repo root (`.mcp.json`) so sessions can
query the Free Law Project v4 API programmatically. Official FLP server, run via
`uvx` (no global install).

## One-time setup (in the shell that launches `claude`)

The server reads the token from **`COURTLISTENER_API_TOKEN`**, but our local token
lives in `app/.env.local` as **`COURTLISTENER_TOKEN`** (name mismatch — the `.mcp.json`
`env` block remaps it). Export it before launching Claude Code:

```sh
export COURTLISTENER_TOKEN=$(grep '^COURTLISTENER_TOKEN=' app/.env.local | cut -d= -f2-)
```

`.mcp.json` is loaded at **session start**, so an already-running session must be
restarted to pick it up.

## Verify

```sh
claude mcp list        # expect:  courtlistener: ... - ✓ Connected
```
Inside a session, `/mcp` lists its tools. First connect is slow (`uvx` downloads
fastmcp/tiktoken/eyecite once) and may trip a connect timeout — re-run after the
cache warms.

## Tools
`search`, `get_endpoint_item`, `get_more_results`, `get_counts`, `call_endpoint`
(any v4 endpoint), `get_endpoint_schema`, `get_choices`, `extract_citations`
(server-side, no limit), `analyze_citations` (~250/req → `job_id`),
`resume_citation_analysis`, plus alert/docket-subscription tools.

## Gotchas
- **Full opinion text:** the MCP hits the same v4 API, so it does **not** fix the
  empty `plain_text` on recent F.4th opinions (see `retrieval-ingestion-contract.md`
  §2a). Workarounds via `call_endpoint`: (a) read the opinion's `html` /
  `html_with_citations` / `html_lawbox` / `xml_harvard` — one is often populated when
  `plain_text` is empty; (b) go through RECAP — `/dockets/` + `/recap-documents/` for
  the filed **PDF**, which often exists when parsed text doesn't. (Retrieval lane.)
- Rate limits: `search` ≤100/call; `analyze_citations` ~250 citations/req.
- Pinned `==1.0.0` for reproducibility; bump deliberately.
