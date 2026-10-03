#!/usr/bin/env python3
"""Queue handling: inbox (packets from Two's VM) and outbox (results back).

Packet format (from the VM pipeline): JSON with packet_id, platform,
listing_url, listing_title, proposal_text (may be empty -> draft locally),
price_hint.

Result format written to outbox/<packet_id>.result.json:
  {packet_id, status: filed|blocked|skipped|error, detail, filed_at}
"""
import json
import os
import glob
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INBOX = os.path.join(BASE, "inbox")
OUTBOX = os.path.join(BASE, "outbox")
DONE = os.path.join(BASE, "done")


def ensure_dirs():
    for d in (INBOX, OUTBOX, DONE):
        os.makedirs(d, exist_ok=True)


def read_packets():
    """Return list of (path, packet_dict) for new packets in inbox."""
    ensure_dirs()
    out = []
    for path in sorted(glob.glob(os.path.join(INBOX, "*.packet.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                out.append((path, json.load(f)))
        except Exception:
            continue
    return out


def write_result(packet_id, status, detail=""):
    """Write a result file to the outbox for the VM side to collect."""
    ensure_dirs()
    result = {
        "packet_id": packet_id,
        "status": status,
        "detail": detail,
    }
    import datetime
    result["filed_at"] = datetime.datetime.now().isoformat()
    with open(os.path.join(OUTBOX, packet_id + ".result.json"),
              "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    return result


def archive_packet(path):
    """Move a processed packet to done/."""
    ensure_dirs()
    shutil.move(path, os.path.join(DONE, os.path.basename(path)))
