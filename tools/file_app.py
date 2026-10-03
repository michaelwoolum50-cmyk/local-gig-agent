#!/usr/bin/env python3
"""File gig applications via Playwright on Ninja.

Persistent Chromium profile at C:\\apps\\gig-agent\\browser-profile so logins
survive restarts. Headless by default; headed for debugging.

Rails enforced here (not just in the prompt):
- NEVER pay: before submitting anything, scan the page text for payment
  demands (deposit, minimum balance, unlock bidding, pay to apply). If found,
  abort and return blocked.
- Truthful profile only: fill from config profile, never invent.
- WeWorkRemotely: account creation is pre-approved. If not logged in,
  register with the profile email (password comes from the Two-side handoff
  file C:\\apps\\gig-agent\\wwr_password.txt — written once by Two, read once,
  then deleted).

Each function returns (ok: bool, detail: str).
"""
import os
import re
import json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_DIR = os.path.join(BASE, "browser-profile")
WWR_PASSWORD_FILE = os.path.join(BASE, "wwr_password.txt")

PAYMENT_PATTERNS = [
    r"minimum balance", r"unlock bidding", r"deposit \$",
    r"pay to (apply|bid)", r"registration fee", r"maintain a minimum",
]

CONFIG = {}
try:
    with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
        CONFIG = json.load(f)
except Exception:
    pass
PROFILE = CONFIG.get("profile", {})


def _page_has_payment_demand(page):
    try:
        text = page.content()
    except Exception:
        return False
    low = text.lower()
    return any(re.search(p, low) for p in PAYMENT_PATTERNS)


def _launch():
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    os.makedirs(PROFILE_DIR, exist_ok=True)
    browser = pw.chromium.launch_persistent_context(
        PROFILE_DIR, headless=True,
        args=["--disable-blink-features=AutomationControlled"])
    return pw, browser


def file_weworkremotely(listing_url, cover_text):
    """File a WeWorkRemotely application. Handles account creation if needed."""
    from playwright.sync_api import TimeoutError as PWTimeout
    pw, ctx = _launch()
    page = ctx.new_page()
    try:
        page.goto(listing_url, timeout=30000)
        page.wait_for_timeout(3000)
        if _page_has_payment_demand(page):
            return False, "blocked: payment demand on page (never-pay rule)"
        # Find the apply link/button
        apply = None
        for sel in ["a:has-text('Apply Now')", "a:has-text('Apply')",
                    "button:has-text('Apply Now')", "button:has-text('Apply')"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    apply = el
                    break
            except Exception:
                continue
        if not apply:
            return False, "blocked: no apply button found"
        href = apply.get_attribute("href") or ""
        if "register" in href or "account" in href:
            ok, detail = _wwr_ensure_account(ctx)
            if not ok:
                return False, "blocked: account creation needed: " + detail
            page.goto(listing_url, timeout=30000)
            page.wait_for_timeout(3000)
            for sel in ["a:has-text('Apply Now')", "a:has-text('Apply')"]:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        apply = el
                        break
                except Exception:
                    continue
        try:
            apply.click(timeout=10000)
        except PWTimeout:
            return False, "blocked: apply click timed out"
        page.wait_for_timeout(4000)
        if _page_has_payment_demand(page):
            return False, "blocked: payment demand after apply click"
        # Fill the application form
        filled = _fill_generic_form(page, cover_text)
        # Look for a submit button and click it
        submitted = _click_submit(page)
        page.wait_for_timeout(5000)
        body = page.content().lower()
        if any(w in body for w in ["thank you", "application received",
                                   "successfully submitted", "we'll be in touch",
                                   "application sent"]):
            return True, "filed: confirmation text found"
        return (submitted,
                "submitted click=%s, confirmation unconfirmed — verify" % submitted)
    except Exception as e:
        return False, "error: %s" % str(e)[:200]
    finally:
        try:
            ctx.close()
        except Exception:
            pass
        pw.stop()


def _wwr_ensure_account(ctx):
    """Create the WWR job-seeker account if not logged in. Returns (ok, detail)."""
    if os.path.exists(WWR_PASSWORD_FILE):
        with open(WWR_PASSWORD_FILE, encoding="utf-8") as f:
            password = f.read().strip()
    else:
        return False, "no password handoff file (Two must provide once)"
    page = ctx.new_page()
    try:
        page.goto("https://weworkremotely.com/job-seekers/account/register",
                  timeout=30000)
        page.wait_for_timeout(3000)
        # Already logged in?
        if "logout" in page.content().lower() or "sign out" in page.content().lower():
            return True, "already logged in"
        email = PROFILE.get("email", "")
        for sel in ["input[type='email']", "input[name='email']",
                    "input[placeholder*='mail' i]"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.fill(email)
                    break
            except Exception:
                continue
        for sel in ["input[type='password']"]:
            try:
                els = page.query_selector_all(sel)
                for el in els:
                    if el.is_visible():
                        el.fill(password)
            except Exception:
                continue
        for sel in ["input[type='checkbox']"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and not el.is_checked():
                    el.check()
            except Exception:
                continue
        for sel in ["button[type='submit']", "input[type='submit']",
                    "button:has-text('Register')", "button:has-text('Sign up')",
                    "button:has-text('Create')"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click(timeout=8000)
                    break
            except Exception:
                continue
        page.wait_for_timeout(5000)
        # Delete the password file after use (one-shot)
        try:
            os.remove(WWR_PASSWORD_FILE)
        except Exception:
            pass
        body = page.content().lower()
        if "logout" in body or "sign out" in body or "welcome" in body:
            return True, "account created and logged in"
        return False, "registration submit unclear — check manually"
    except Exception as e:
        return False, "error: %s" % str(e)[:200]
    finally:
        try:
            page.close()
        except Exception:
            pass


def _fill_generic_form(page, cover_text):
    """Fill common application fields from the truthful profile. Returns count."""
    n = 0
    prof = PROFILE
    field_map = [
        (["input[name*='name' i]", "input[placeholder*='name' i]",
          "input[id*='name' i]"], prof.get("name", "")),
        (["input[type='email']", "input[name*='email' i]"], prof.get("email", "")),
        (["input[name*='phone' i]", "input[type='tel']",
          "input[placeholder*='phone' i]"], prof.get("phone", "")),
    ]
    for sels, val in field_map:
        if not val:
            continue
        for sel in sels:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    cur = el.input_value() or ""
                    if not cur.strip():
                        el.fill(val)
                        n += 1
                    break
            except Exception:
                continue
    # Cover letter / message textareas
    for sel in ["textarea[name*='cover' i]", "textarea[name*='message' i]",
                "textarea[name*='letter' i]", "textarea"]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                cur = el.input_value() or ""
                if not cur.strip() and cover_text:
                    el.fill(cover_text)
                    n += 1
                break
        except Exception:
            continue
    return n


def _click_submit(page):
    """Click the most likely submit button. Returns True if clicked."""
    for sel in ["button[type='submit']", "input[type='submit']",
                "button:has-text('Submit Application')",
                "button:has-text('Submit')", "button:has-text('Send Application')",
                "button:has-text('Apply')"]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible() and el.is_enabled():
                el.click(timeout=8000)
                return True
        except Exception:
            continue
    return False


def file_remoteok(listing_url, cover_text):
    """File a RemoteOK application (usually an external apply link)."""
    pw, ctx = _launch()
    page = ctx.new_page()
    try:
        page.goto(listing_url, timeout=30000)
        page.wait_for_timeout(3000)
        if _page_has_payment_demand(page):
            return False, "blocked: payment demand on page (never-pay rule)"
        body = page.content().lower()
        if "expired" in body or "no longer available" in body or "not found" in body:
            return False, "blocked: listing expired or removed"
        return _generic_apply(page, cover_text)
    except Exception as e:
        return False, "error: %s" % str(e)[:200]
    finally:
        try:
            ctx.close()
        except Exception:
            pass
        pw.stop()


def _generic_apply(page, cover_text):
    from playwright.sync_api import TimeoutError as PWTimeout
    for sel in ["a:has-text('Apply')", "button:has-text('Apply')"]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=10000)
                break
        except Exception:
            continue
    page.wait_for_timeout(4000)
    if _page_has_payment_demand(page):
        return False, "blocked: payment demand after apply"
    _fill_generic_form(page, cover_text)
    submitted = _click_submit(page)
    page.wait_for_timeout(5000)
    body = page.content().lower()
    if any(w in body for w in ["thank you", "application received",
                               "successfully submitted", "we'll be in touch"]):
        return True, "filed: confirmation text found"
    return submitted, "submitted click=%s, unconfirmed" % submitted


def file_freelancer(listing_url, cover_text, price_hint):
    """Freelancer: HARD-PASS any listing requiring payment. Otherwise blocked
    (bidding API needs session funds; never deposit)."""
    return False, "skipped: freelancer requires manual review (never-pay rail)"
