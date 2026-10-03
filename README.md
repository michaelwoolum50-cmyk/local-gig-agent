# Local Gig Agent

**A fully local AI gig-filing assistant. No cloud. No API costs. No data ever leaves your machine.**

Built for a friend who needed help finding freelance work but couldn't afford to feed his data (and his wallet) into cloud AI subscriptions. Every part of this system runs on his own computer.

## How it works

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│ Gig packets │────▶│  Qwen 2.5 Coder  │────▶│  Playwright  │
│ (JSON)      │     │  7B — LOCAL LLM  │     │  browser     │
└─────────────┘     │  screens + drafts│     │  files forms │
                    └──────────────────┘     └──────────────┘
        Runs on llama-server, localhost:8081. Zero cloud calls.
```

1. **Packets arrive** — gig listings as structured JSON (title, description, URL, pay).
2. **The local model screens** — Qwen 2.5 Coder 7B reads each listing and rejects scams, pay-to-apply traps, and bad fits. Nothing fake ever goes out.
3. **The local model drafts** — a truthful, tailored proposal for every listing that passes screening.
4. **Playwright files** — the agent opens the real listing in a browser and submits the application, saving a receipt for every filing.

## The brain: 100% open-source

- **Model:** `qwen2.5-coder-7b-instruct-q4_k_m.gguf` (Qwen 2.5 Coder, Apache 2.0)
- **Runtime:** `llama-server` from llama.cpp (MIT)
- **Hardware:** a plain CPU box with 32GB RAM. No GPU. ~5GB model file.
- **Cost to run:** $0. Forever.

## Built-in rails (the important part)

An autonomous agent that files job applications under someone's name needs guardrails, so they're in the code, not in a promise:

- `never_pay_to_apply` — any listing that wants a deposit, minimum balance, or fee to bid is auto-rejected
- `truthful_profile_only` — the model drafts only from the real profile in `config.json`; it cannot invent credentials
- `hard_pass_keywords` — scam patterns kill a listing before the model even sees it
- Every filing writes a receipt to `outbox/` — a full audit trail

## Project layout

```
agent.py        # the main loop: inbox → screen → draft → file → outbox
ninja_llm.py    # local LLM client (screen / draft_proposal)
tools/
  llm.py        # LLM wrapper
  queue.py      # packet queue
  file_app.py   # Playwright filing
config.json     # profile + rails (template — fill in your own)
```

## Quick start

```bash
# 1. Start the local model
llama-server -m qwen2.5-coder-7b-instruct-q4_k_m.gguf --port 8081

# 2. Fill in config.json with your real profile

# 3. Drop a gig packet into inbox/ and run
python agent.py
```

## Why this exists

Cloud AI charges you per token to do work you could do on hardware you already own. A 7B open-source model on a five-year-old desktop screens gigs and writes proposals just fine. The person this was built for keeps his data, his money, and his autonomy.

*Built with open-source AI, for the Hacktoberfest Weekend Challenge — "build for a friend."*
