#!/usr/bin/env python3
"""Gig agent — autonomous gig-work loop on Ninja.

The loop:
  1. Read new packets from inbox/ (pushed by Two's VM pipeline).
  2. For each packet: screen with the LLM (never-pay rail + scam check).
  3. Draft the proposal with the local LLM (or use packet's proposal_text).
  4. File via Playwright (file_app tools per platform).
  5. Write result to outbox/ and archive the packet.

Runs forever under a Windows scheduled task. Logs to agent.log.
"""
import json
import os
import sys
import time
import traceback
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "tools"))

from llm import draft_proposal, screen_listing
from queue import read_packets, write_result, archive_packet
import file_app

CONFIG_PATH = os.path.join(BASE, "config.json")
LOG_PATH = os.path.join(BASE, "agent.log")


def log(msg):
    line = "%s %s" % (datetime.datetime.now().isoformat(), msg)
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def process_packet(cfg, path, pkt):
    pid = pkt.get("packet_id", os.path.basename(path))
    platform = (pkt.get("platform") or "").lower()
    url = pkt.get("listing_url", "")
    title = pkt.get("listing_title", "")
    detail = pkt.get("listing_detail", "") or title
    log("packet %s [%s] %s" % (pid, platform, title[:60]))

    rails = cfg["rails"]
    profile = cfg["profile"]

    # Rail 1: LLM scam / never-pay screen
    try:
        ok, reason = screen_listing(title, detail,
                                    rails.get("hard_pass_keywords", []))
    except Exception as e:
        write_result(pid, "error", "screen failed: %s" % str(e)[:150])
        archive_packet(path)
        return
    if not ok:
        log("  REJECT %s" % reason)
        write_result(pid, "skipped", "llm screen: " + reason)
        archive_packet(path)
        return

    # Proposal text: use packet's, or draft locally
    proposal = pkt.get("proposal_text") or ""
    if not proposal.strip():
        try:
            proposal = draft_proposal(title, url, detail,
                                      pkt.get("price_hint", ""),
                                      profile, rails["honesty_disclosure"])
            log("  drafted %d chars" % len(proposal))
        except Exception as e:
            write_result(pid, "error", "draft failed: %s" % str(e)[:150])
            archive_packet(path)
            return

    # File per platform
    try:
        if "weworkremotely" in platform or "weworkremotely" in url:
            ok, detail = file_app.file_weworkremotely(url, proposal)
        elif "remoteok" in platform or "remoteok" in url:
            ok, detail = file_app.file_remoteok(url, proposal)
        elif "freelancer" in platform or "freelancer" in url:
            ok, detail = file_app.file_freelancer(url, proposal,
                                                  pkt.get("price_hint", ""))
        else:
            ok, detail = False, "skipped: unknown platform %s" % platform
    except Exception as e:
        ok, detail = False, "error: %s" % str(e)[:200]
        log("  EXC %s" % traceback.format_exc(limit=3))

    status = "filed" if ok and detail.startswith("filed") else (
        "blocked" if "blocked" in detail else ("error" if "error" in detail else "skipped"))
    log("  %s: %s" % (status.upper(), detail[:120]))
    write_result(pid, status, detail)
    archive_packet(path)


def run_once(cfg):
    packets = read_packets()
    if not packets:
        return 0
    max_n = cfg["rails"].get("max_applications_per_run", 10)
    n = 0
    for path, pkt in packets[:max_n]:
        try:
            process_packet(cfg, path, pkt)
        except Exception:
            log("FATAL packet %s\n%s" % (path, traceback.format_exc(limit=5)))
        n += 1
    return n


def main():
    cfg = load_config()
    log("gig-agent v%s starting (loop %ss)" %
        (cfg.get("version"), cfg["rails"].get("loop_interval_sec", 300)))
    interval = cfg["rails"].get("loop_interval_sec", 300)
    while True:
        try:
            n = run_once(cfg)
            if n:
                log("run done: %d packets" % n)
        except Exception:
            log("FATAL loop\n%s" % traceback.format_exc(limit=5))
        time.sleep(interval)


if __name__ == "__main__":
    main()
