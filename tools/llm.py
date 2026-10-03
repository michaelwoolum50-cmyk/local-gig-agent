#!/usr/bin/env python3
"""Local LLM client for the gig agent. Talks to llama-server on localhost:8081.
OpenAI-compatible chat completions. No tokens, no outside calls — all local.
"""
import json
import urllib.request
import urllib.error

ENDPOINT = "http://127.0.0.1:8081/v1/chat/completions"
TIMEOUT = 180


def chat(messages, max_tokens=1200, temperature=0.7):
    """Send chat messages, return the assistant's text. Raises on failure."""
    payload = json.dumps({
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=payload,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError("LLM unreachable at %s: %s" % (ENDPOINT, e))
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("LLM returned no choices: %s" % str(data)[:200])
    return choices[0]["message"]["content"]


def draft_proposal(listing_title, listing_url, listing_detail, price_hint, profile, disclosure):
    """Draft a tailored gig proposal. Returns the proposal text."""
    prompt = (
        "You are the owner's automated bidding assistant, writing a gig proposal.\n"
        "RULES: Identify as his automated bidding assistant. State the work is AI-delivered "
        "under his personal review. Never claim to be human. Never invent credentials, "
        "employers, degrees, past clients, or portfolio. Be specific to the listing.\n\n"
        "LISTING: %s\nURL: %s\nDETAIL: %s\nPRICE: %s\n\n"
        "APPLICANT: %s, %s, %s\n\n"
        "Write the proposal now. End with: %s"
        % (listing_title, listing_url, listing_detail[:1500], price_hint,
           profile["name"], profile["email"], profile["phone"], disclosure)
    )
    return chat([{"role": "user", "content": prompt}], max_tokens=1200)


def screen_listing(listing_title, listing_detail, hard_pass_keywords):
    """Ask the LLM whether this listing violates the never-pay rule or looks like a scam.
    Returns (ok: bool, reason: str)."""
    prompt = (
        "You screen gig listings for scams. NEVER-PAY RULE: if the listing requires ANY "
        "payment, deposit, minimum balance, or fee from the applicant to bid or apply, "
        "it is an automatic REJECT.\n\n"
        "LISTING: %s\nDETAIL: %s\n\n"
        "Reply with exactly one line: either 'OK' or 'REJECT: <short reason>'."
        % (listing_title, listing_detail[:1200])
    )
    out = chat([{"role": "user", "content": prompt}], max_tokens=100).strip()
    if out.upper().startswith("OK"):
        return True, ""
    return False, out


if __name__ == "__main__":
    print(chat([{"role": "user", "content": "Reply with exactly: READY"}],
               max_tokens=10))
