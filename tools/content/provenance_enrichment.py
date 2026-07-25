"""Refresh canonical provenance for legacy news events before a pitch is approved.

The news funnel historically retained URLs and a feed title but not always an
article publication date.  A briefing must not invent that date.  This module
retrieves the source page and accepts only explicit metadata (JSON-LD,
OpenGraph, or a canonical link); failures leave the event unverified.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import hmac
import ipaddress
import json
import os
import re
import socket
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from uuid import uuid4

import requests

from core.logger import get_logger
from schemas.youtube_pitch_schemas import YouTubeContentPitchItem

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 3600.0
_FAILURE_CACHE_TTL_SECONDS = 60.0
_CACHE: Dict[str, Tuple["ProvenanceRefresh", float]] = {}
_USER_AGENT = "invest-agents/1.0 (+provenance verification)"
_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "tsrc"}
_MAX_RECOVERY_CANDIDATES = 24
_RECOVERY_WORKERS = 6


@dataclass(frozen=True)
class ProvenanceRefresh:
    canonical_url: Optional[str] = None
    canonical_publisher: Optional[str] = None
    published_at: Optional[str] = None
    title: Optional[str] = None
    fetch_error: Optional[str] = None

    @property
    def is_complete(self) -> bool:
        return bool(self.canonical_url and self.canonical_publisher and self.published_at)


@dataclass(frozen=True)
class EligibilityTokenClaims:
    job_id: str
    thread_id: str
    pitch_id: str
    approval_revision: int
    issue_codes: tuple[str, ...]
    jti: str
    issued_at: int
    expires_at: int


def normalize_provenance_url(url: str) -> str:
    """Remove known tracking parameters without changing an article's identity."""
    raw = str(url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    if not parts.scheme or not parts.netloc:
        return raw
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold().lstrip(".") not in _TRACKING_QUERY_KEYS and not key.casefold().startswith("utm_")
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), ""))


def _normalise_iso_datetime(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    raw = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        # Metadata occasionally uses only a date.  It is still an explicit
        # article date, so preserve it rather than fabricating a time of day.
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return raw
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return parsed.isoformat()


def _meta_content(html: str, *names: str) -> Optional[str]:
    for name in names:
        escaped = re.escape(name)
        patterns = (
            rf'<meta[^>]+(?:property|name)=["\']{escaped}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{escaped}["\']',
        )
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return None


def _time_datetime(html: str) -> Optional[str]:
    """Read an explicit HTML ``<time datetime>`` when a publisher omits OG dates."""
    match = re.search(r'<time[^>]+datetime=["\']([^"\']+)["\']', html, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _json_ld_objects(html: str) -> Iterable[Dict[str, Any]]:
    for block in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        try:
            payload = json.loads(block.strip())
        except (TypeError, ValueError):
            continue
        values = payload.get("@graph", []) if isinstance(payload, dict) and isinstance(payload.get("@graph"), list) else payload
        if isinstance(values, dict):
            values = [values]
        if isinstance(values, list):
            for value in values:
                if isinstance(value, dict):
                    yield value


def _publisher_name(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        return str(value.get("name") or "").strip() or None
    if isinstance(value, str):
        return value.strip() or None
    return None


def _parse_page_provenance(html: str, response_url: str) -> ProvenanceRefresh:
    canonical_url = _meta_content(html, "og:url")
    canonical_match = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE
    )
    if canonical_match:
        canonical_url = canonical_match.group(1).strip()
    canonical_url = urljoin(response_url, canonical_url) if canonical_url else response_url

    publisher = _meta_content(html, "og:site_name", "publisher", "article:publisher")
    published_at = _normalise_iso_datetime(
        _meta_content(
            html,
            "article:published_time",
            "date",
            "datePublished",
            "parsely-pub-date",
            "publication_date",
            "publish-date",
        )
        or _time_datetime(html)
    )
    title = _meta_content(html, "og:title", "twitter:title")
    for obj in _json_ld_objects(html):
        obj_type = obj.get("@type")
        obj_types = {obj_type} if isinstance(obj_type, str) else set(obj_type or [])
        if obj_types and not obj_types.intersection({"NewsArticle", "Article", "ReportageNewsArticle", "WebPage"}):
            continue
        publisher = publisher or _publisher_name(obj.get("publisher")) or _publisher_name(obj.get("author"))
        published_at = published_at or _normalise_iso_datetime(obj.get("datePublished") or obj.get("dateCreated"))
        title = title or str(obj.get("headline") or obj.get("name") or "").strip() or None
        canonical_url = obj.get("url") or canonical_url
        if canonical_url:
            canonical_url = urljoin(response_url, str(canonical_url))

    # A host is a usable publisher identity only when the publisher metadata is
    # absent.  It is explicit enough for a *partial* source but never turns a
    # date-less event into verified provenance.
    publisher = publisher or urlsplit(canonical_url).netloc.replace("www.", "") or None
    
    if canonical_url and "youtube.com" in canonical_url.casefold():
        channel_id_match = re.search(r'<meta[^>]+itemprop=["\']channelId["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if channel_id_match:
            publisher = f"youtube_channel_{channel_id_match.group(1).strip()}"
        else:
            channel_link_match = re.search(r'<link[^>]+itemprop=["\']url["\'][^>]+href=["\']http[s]?://www\.youtube\.com/channel/([^"\']+)["\']', html, re.IGNORECASE)
            if channel_link_match:
                publisher = f"youtube_channel_{channel_link_match.group(1).strip()}"
            else:
                publisher = "youtube.com" # Plain publisher if fail
                
    return ProvenanceRefresh(normalize_provenance_url(canonical_url), publisher, published_at, title)


def _is_public_web_url(url: str) -> bool:
    """Reject anything that is not a plain http(s) URL resolving to a routable public IP.

    Shared by the requests-based fetch and the Playwright fallback so neither
    path can be used to reach loopback/private/link-local/metadata endpoints.
    """
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        addrinfo = socket.getaddrinfo(parsed.hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except OSError:
        return False
    for res in addrinfo:
        ip = ipaddress.ip_address(res[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False
    return True


def _safe_fetch(url: str, timeout_seconds: float) -> Tuple[str, str]:
    current_url = url
    for _ in range(5):
        if not _is_public_web_url(current_url):
            raise requests.RequestException("URL is missing, has an invalid scheme, or resolves to a restricted IP")

        resp = requests.get(current_url, headers={"User-Agent": _USER_AGENT}, timeout=timeout_seconds, allow_redirects=False, stream=True)
        if 300 <= resp.status_code < 400:
            location = resp.headers.get("Location")
            if not location:
                raise requests.RequestException("Redirect missing Location header")
            current_url = urljoin(current_url, location)
            continue
        
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if not content_type.startswith("text/"):
            raise requests.RequestException(f"Unsupported content type: {content_type}")
            
        content_bytes = resp.raw.read(5 * 1024 * 1024) # 5MB max
        return content_bytes.decode(resp.encoding or "utf-8", errors="replace"), current_url
        
    raise requests.RequestException("Too many redirects")


def refresh_url_provenance(
    url: str,
    *,
    timeout_seconds: float = 5.0,
    force_refresh: bool = False,
) -> ProvenanceRefresh:
    """Fetch and parse explicit provenance metadata with bounded retries/cache."""
    clean_url = normalize_provenance_url(url)
    if not clean_url.startswith(("http://", "https://")):
        return ProvenanceRefresh(fetch_error="source URL is missing or invalid")
    now = time.monotonic()
    cached = _CACHE.get(clean_url)
    if cached and not force_refresh and now < cached[1]:
        return cached[0]
    result = None
    try:
        text, final_url = _safe_fetch(clean_url, timeout_seconds)
        result = _parse_page_provenance(text, final_url)
        if not result.is_complete:
            raise ValueError("Incomplete metadata via standard fetch")
    except (requests.RequestException, ValueError) as exc:
        logger.info("Tier 1 provenance refresh failed/incomplete for %s: %s, falling back to Playwright", clean_url, exc)
        try:
            if not _is_public_web_url(clean_url):
                raise requests.RequestException("URL is missing, has an invalid scheme, or resolves to a restricted IP")

            import os
            from playwright.sync_api import sync_playwright
            from playwright_stealth.stealth import Stealth

            def _guard_route(route):
                # Applies to the main navigation *and* every redirect/sub-resource
                # it triggers, so a page cannot pivot the browser onto an
                # internal host after the initial URL passed the check above.
                if _is_public_web_url(route.request.url):
                    route.continue_()
                else:
                    route.abort()

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true")
                page = browser.new_page()
                Stealth().apply_stealth_sync(page)
                page.route("**/*", _guard_route)
                page.goto(clean_url, wait_until="domcontentloaded", timeout=15000)
                time.sleep(3)
                pw_text = page.content()
                pw_url = page.url
                browser.close()
            pw_result = _parse_page_provenance(pw_text, pw_url)
            if result is None or pw_result.is_complete or (not result.published_at and pw_result.published_at):
                result = pw_result
        except Exception as pw_exc:
            logger.info("Playwright provenance fallback failed for %s: %s", clean_url, pw_exc)
            if result is None:
                result = ProvenanceRefresh(fetch_error=f"Playwright fallback failed: {pw_exc} (Original: {exc})")
    ttl = _CACHE_TTL_SECONDS if result.is_complete else _FAILURE_CACHE_TTL_SECONDS
    _CACHE[clean_url] = (result, now + ttl)
    return result


def _event_url(event: Dict[str, Any]) -> str:
    links = event.get("links")
    if isinstance(links, list) and links:
        return str(links[0] or "")
    return str(event.get("canonical_url") or event.get("link") or "")


def _classify_provenance_issue(result: ProvenanceRefresh) -> str:
    if result.is_complete:
        return "verified"
    error = str(result.fetch_error or "").casefold()
    if not error:
        return "metadata_missing"
    if "403" in error or "401" in error or "forbidden" in error or "paywall" in error:
        return "access_restricted"
    if "429" in error or "rate" in error or "timeout" in error or "timed out" in error or "connection" in error:
        return "temporary_fetch_failure"
    if "invalid" in error or "missing" in error:
        return "invalid_url"
    return "temporary_fetch_failure"


def refresh_event_provenance(event: Dict[str, Any], *, force_refresh: bool = False) -> Dict[str, Any]:
    """Return a copied event upgraded only with page-supplied provenance."""
    refreshed = dict(event)
    url = str(refreshed.get("canonical_url") or _event_url(refreshed) or "")
    # New records carry canonical_* fields; already-verified records from the
    # prior ingestion contract carry publisher/published_at instead.  Both are
    # legitimate and must not trigger an unnecessary network request.
    has_complete = bool(
        url
        and (refreshed.get("canonical_publisher") or refreshed.get("publisher"))
        and (refreshed.get("canonical_published_at") or refreshed.get("published_at"))
        and str(refreshed.get("verification_status") or "").lower() == "verified"
    )
    if has_complete:
        refreshed.setdefault("provenance_status", "verified")
        refreshed.setdefault("provenance_recovery_method", "stored_metadata")
        return refreshed

    # A dated publisher record received directly from an RSS/source connector
    # is explicit provenance.  Preserve it rather than discarding it merely
    # because a legacy event pre-dates the verification-status field.
    if url and (refreshed.get("canonical_publisher") or refreshed.get("publisher")) and (
        refreshed.get("canonical_published_at") or refreshed.get("published_at")
    ):
        refreshed.setdefault("canonical_url", normalize_provenance_url(url))
        refreshed.setdefault("canonical_publisher", refreshed.get("publisher"))
        refreshed.setdefault("canonical_published_at", refreshed.get("published_at"))
        refreshed["verification_status"] = "verified"
        refreshed["provenance_status"] = "verified"
        refreshed["provenance_recovery_method"] = "source_feed_metadata"
        return refreshed

    result = refresh_url_provenance(url, force_refresh=force_refresh)
    if result.canonical_url:
        refreshed["canonical_url"] = result.canonical_url
    if result.canonical_publisher:
        refreshed["canonical_publisher"] = result.canonical_publisher
        refreshed.setdefault("publisher", result.canonical_publisher)
    if result.published_at:
        refreshed["canonical_published_at"] = result.published_at
        refreshed.setdefault("published_at", result.published_at)
    if result.title and not refreshed.get("original_title"):
        refreshed["original_title"] = result.title

    if result.is_complete:
        refreshed["verification_status"] = "verified"
        refreshed["provenance_status"] = "verified"
        refreshed["provenance_recovery_method"] = "page_metadata"
        refreshed.pop("provenance_refresh_error", None)
    else:
        current = str(refreshed.get("verification_status") or "unverified").lower()
        refreshed["verification_status"] = "partial" if (result.canonical_url or result.canonical_publisher) else current
        if result.fetch_error:
            refreshed["provenance_refresh_error"] = result.fetch_error
        refreshed["provenance_status"] = _classify_provenance_issue(result)
    refreshed["provenance_checked_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return refreshed


def refresh_selected_event_provenance(
    events: List[Dict[str, Any]],
    *,
    force_refresh: bool = False,
    max_workers: int = _RECOVERY_WORKERS,
) -> List[Dict[str, Any]]:
    """Refresh independent source pages concurrently while preserving input order."""
    if not events:
        return []
    workers = max(1, min(max_workers, len(events)))
    results: List[Optional[Dict[str, Any]]] = [None] * len(events)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="provenance") as pool:
        futures = {
            pool.submit(refresh_event_provenance, event, force_refresh=force_refresh): index
            for index, event in enumerate(events)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                results[index] = future.result()
            except Exception as exc:  # defensive; individual failures never abort the batch
                fallback = dict(events[index])
                fallback["provenance_status"] = "temporary_fetch_failure"
                fallback["provenance_refresh_error"] = str(exc)
                results[index] = fallback
    return [result if result is not None else dict(events[index]) for index, result in enumerate(results)]


def _is_verified_event(event: Dict[str, Any]) -> bool:
    return bool(
        (event.get("canonical_url") or _event_url(event))
        and (event.get("canonical_publisher") or event.get("publisher"))
        and (event.get("canonical_published_at") or event.get("published_at"))
        and str(event.get("verification_status") or "").casefold() == "verified"
    )


def _candidate_priority(event: Dict[str, Any], index: int) -> tuple[float, int]:
    """Prioritise impactful, partially-described stories for bounded recovery."""
    score = float(event.get("macro_impact_score") or 0) + float(event.get("asset_impact_score") or 0)
    if event.get("published_at") or event.get("canonical_published_at"):
        score += 2.0
    if event.get("publisher") or event.get("canonical_publisher"):
        score += 2.0
    if _event_url(event):
        score += 1.0
    return (-score, index)


def build_provenance_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    verified_publishers: set[str] = set()
    for event in events:
        status = str(event.get("provenance_status") or event.get("verification_status") or "unverified")
        counts[status] = counts.get(status, 0) + 1
        if _is_verified_event(event):
            publisher = str(event.get("canonical_publisher") or event.get("publisher") or "").strip().casefold()
            url = str(event.get("canonical_url") or _event_url(event) or "")
            host = urlsplit(url).netloc.replace("www.", "").casefold()
            
            # Base publisher independence primarily on the registrable domain to prevent spoofing
            if "youtube.com" in host or "youtu.be" in host:
                independence_key = publisher or host
            else:
                independence_key = host
                
            if independence_key:
                verified_publishers.add(independence_key)
    return {
        "total_candidates": len(events),
        "verified_candidates": sum(1 for event in events if _is_verified_event(event)),
        "independent_publishers": len(verified_publishers),
        "status_counts": counts,
    }


def prepare_verified_candidate_pool(
    candidates: List[Dict[str, Any]],
    *,
    force_refresh: bool = False,
    max_refresh_candidates: int = _MAX_RECOVERY_CANDIDATES,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Recover a bounded candidate set, then return only sources safe for a pitch.

    The raw news pool can be large.  Recovering every URL would be slow and
    rate-limit publishers, so only the highest-priority incomplete records are
    refreshed.  Existing verified records are always retained.
    """
    copied = [dict(candidate) for candidate in candidates if isinstance(candidate, dict)]
    incomplete_indexes = [index for index, candidate in enumerate(copied) if not _is_verified_event(candidate)]
    incomplete_indexes.sort(key=lambda index: _candidate_priority(copied[index], index))
    selected_indexes = incomplete_indexes[:max_refresh_candidates]
    selected = [copied[index] for index in selected_indexes]
    refreshed_selected = refresh_selected_event_provenance(selected, force_refresh=force_refresh)
    for index, refreshed in zip(selected_indexes, refreshed_selected):
        copied[index] = refreshed

    verified = [candidate for candidate in copied if _is_verified_event(candidate)]
    summary = build_provenance_summary(copied)
    summary["refreshed_candidates"] = len(selected_indexes)
    return copied, verified, summary


ALLOWLISTED_UNVERIFIED_DRAFT_CODES = {
    "MISSING_PUBLISHER",
    "MISSING_PUBLICATION_DATE",
    "TEMPORARY_METADATA_FAILURE",
    "METADATA_MISSING",
    "SINGLE_INDEPENDENT_SOURCE",
}


def evaluate_unverified_draft_eligibility(issue_codes: List[str]) -> bool:
    """Check if the given provenance issue codes are eligible for an Unverified Draft bypass."""
    if not issue_codes:
        return False
    for code in issue_codes:
        if code not in ALLOWLISTED_UNVERIFIED_DRAFT_CODES:
            return False
    return True


def _eligibility_signing_key() -> bytes:
    """Return the dedicated signing secret without ever logging it."""
    secret_str = os.environ.get("UNVERIFIED_DRAFT_SIGNING_KEY", "")
    if not secret_str:
        raise RuntimeError("UNVERIFIED_DRAFT_SIGNING_KEY not set in environment (fail-closed)")
    if len(secret_str.encode("utf-8")) < 32:
        raise RuntimeError("UNVERIFIED_DRAFT_SIGNING_KEY must be at least 32 bytes")
    return secret_str.encode("utf-8")


def generate_eligibility_token(job_id: str, thread_id: str, pitch_id: str, revision: int, issue_codes: List[str]) -> str:
    """Create a short-lived, single-use candidate token for one approval revision."""
    secret = _eligibility_signing_key()
    now = int(time.time())
    payload_dict = {
        "v": 1,
        "job_id": job_id,
        "thread_id": thread_id,
        "pitch_id": pitch_id,
        "approval_revision": revision,
        "issue_codes": sorted(issue_codes),
        "jti": uuid4().hex,
        "iat": now,
        "exp": now + 86400,
    }
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload_dict, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).decode("ascii")
    signature = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_eligibility_token(
    token: str,
    *,
    expected_job_id: str,
    expected_thread_id: str,
    expected_pitch_id: str,
    expected_revision: int,
    expected_issue_codes: Optional[List[str]] = None,
) -> Optional[EligibilityTokenClaims]:
    """Verify every authorization claim before a Draft is allowed to resume.

    Returning parsed claims keeps callers from decoding an unverified token just
    to derive its token identifier for replay protection.
    """
    try:
        secret = _eligibility_signing_key()
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        expected_sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None

        payload_dict = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8"))
        if payload_dict.get("v") != 1:
            return None
        if payload_dict.get("job_id") != expected_job_id:
            return None
        if payload_dict.get("thread_id") != expected_thread_id:
            return None
        if payload_dict.get("pitch_id") != expected_pitch_id:
            return None
        if payload_dict.get("approval_revision") != expected_revision:
            return None
        if not isinstance(payload_dict.get("jti"), str) or not payload_dict["jti"]:
            return None
        if not isinstance(payload_dict.get("iat"), int) or not isinstance(payload_dict.get("exp"), int):
            return None
        if payload_dict["exp"] <= int(time.time()):
            return None
        issue_codes = payload_dict.get("issue_codes")
        if not isinstance(issue_codes, list) or not all(isinstance(code, str) for code in issue_codes):
            return None
        if expected_issue_codes is not None and sorted(issue_codes) != sorted(expected_issue_codes):
            return None
        return EligibilityTokenClaims(
            job_id=payload_dict["job_id"],
            thread_id=payload_dict["thread_id"],
            pitch_id=payload_dict["pitch_id"],
            approval_revision=payload_dict["approval_revision"],
            issue_codes=tuple(issue_codes),
            jti=payload_dict["jti"],
            issued_at=payload_dict["iat"],
            expires_at=payload_dict["exp"],
        )
    except Exception:
        return None

def assess_pitch_source_readiness(
    pitch: YouTubeContentPitchItem,
    candidates: List[Dict[str, Any]],
    *,
    refresh: bool = True,
    force_refresh: bool = False,
) -> tuple[str, List[str], List[str], List[Dict[str, Any]]]:
    """Return approval readiness without lowering the later quality gate.

    ``needs_refresh`` is reserved for a recoverable network failure; ``blocked``
    means the page was inspected but lacks mandatory canonical metadata.
    """
    selected_ids = set(pitch.source_event_ids)
    selected = [event for event in candidates if event.get("event_id") in selected_ids]
    if not selected:
        return "blocked", ["ไม่พบข่าวต้นทางของ Pitch นี้ใน candidate pool"], ["SOURCE_NOT_FOUND"], []
    checked = (
        refresh_selected_event_provenance(selected, force_refresh=force_refresh)
        if refresh else [dict(event) for event in selected]
    )
    issues: List[str] = []
    issue_codes: List[str] = []
    recoverable = False
    independence_groups: set[str] = set()
    for event in checked:
        title = str(event.get("canonical_title") or event.get("title") or event.get("event_id") or "source")
        if not event.get("canonical_url") and not _event_url(event):
            issues.append(f"{title}: ไม่มี URL ต้นทาง")
            issue_codes.append("MISSING_SOURCE_URL")
        if not (event.get("canonical_publisher") or event.get("publisher")):
            issues.append(f"{title}: ไม่พบสำนักข่าวจากหน้าแหล่งข้อมูล")
            issue_codes.append("MISSING_PUBLISHER")
        if not (event.get("canonical_published_at") or event.get("published_at")):
            issues.append(f"{title}: ไม่พบวันเผยแพร่จากหน้าแหล่งข้อมูล")
            issue_codes.append("MISSING_PUBLICATION_DATE")
        if str(event.get("verification_status") or "unverified").lower() != "verified":
            if event.get("provenance_refresh_error"):
                recoverable = True
                status = str(event.get("provenance_status") or "temporary_fetch_failure")
                issues.append(f"{title}: ตรวจ metadata ไม่สำเร็จ ({status})")
                issue_codes.append("TEMPORARY_METADATA_FAILURE")
            else:
                status = str(event.get("provenance_status") or "metadata_missing")
                issues.append(f"{title}: provenance ยังไม่ครบ ({status})")
                issue_codes.append("METADATA_MISSING")
                
        if str(event.get("provenance_status") or "").lower() == "mock_source" or "mock" in str(event.get("canonical_url") or "").lower():
            issues.append(f"{title}: Mock Source Detected")
            issue_codes.append("MOCK_SOURCE")
        publisher = str(event.get("canonical_publisher") or event.get("publisher") or "").strip().casefold()
        url = str(event.get("canonical_url") or _event_url(event) or "")
        host = urlsplit(url).netloc.replace("www.", "").casefold()
        if publisher or host:
            independence_groups.add(publisher or host)
    if len(independence_groups) < 2:
        issues.append("ต้องมีอย่างน้อย 2 กลุ่มแหล่งข่าวอิสระเพื่อผ่าน Research Quality Gate")
        issue_codes.append("SINGLE_INDEPENDENT_SOURCE")
    issues = list(dict.fromkeys(issues))
    issue_codes = list(dict.fromkeys(issue_codes))
    if not issues:
        return "ready", [], [], checked
    return ("needs_refresh" if recoverable else "blocked"), issues, issue_codes, checked
