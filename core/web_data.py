from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

from core.config import (
    ANTHROPIC_API_KEY,
    ENABLE_OFFICIAL_WEB_DATA,
    ENABLE_WEB_SEARCH,
    MODEL,
    TAVILY_API_KEY,
    WEB_TIMEOUT_SECONDS,
    should_use_llm,
)
from core.local_analysis import extract_situation, utc_now

try:
    import anthropic
except ImportError:
    anthropic = None


STATE_NAMES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "IA": "Iowa",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "MA": "Massachusetts",
    "MD": "Maryland",
    "ME": "Maine",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MO": "Missouri",
    "MS": "Mississippi",
    "MT": "Montana",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "NE": "Nebraska",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NV": "Nevada",
    "NY": "New York",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VA": "Virginia",
    "VT": "Vermont",
    "WA": "Washington",
    "WI": "Wisconsin",
    "WV": "West Virginia",
    "WY": "Wyoming",
}


def collect_web_data(situation_report: str) -> dict[str, Any]:
    situation = extract_situation(situation_report)
    state = _extract_state(situation_report)
    findings = []
    errors = []

    if ENABLE_OFFICIAL_WEB_DATA:
        for collector in (_nws_alerts, _usgs_earthquakes, _fema_declarations):
            try:
                result = collector(situation, state)
                findings.extend(result.get("findings", []))
                errors.extend(result.get("errors", []))
            except Exception as exc:
                errors.append(f"{collector.__name__} failed: {exc}")

    if ENABLE_WEB_SEARCH:
        search = _search_web(situation_report, situation)
        findings.extend(search.get("findings", []))
        errors.extend(search.get("errors", []))

    summary = _summarize_findings(situation_report, findings) if findings else ""

    return {
        "enabled_sources": {
            "official": ENABLE_OFFICIAL_WEB_DATA,
            "web_search": ENABLE_WEB_SEARCH,
            "llm_summary": bool(findings and should_use_llm() and anthropic and ANTHROPIC_API_KEY),
        },
        "state": state,
        "location": situation["location"],
        "findings": findings,
        "summary": summary,
        "errors": errors,
        "collected_at": utc_now(),
    }


def web_context_block(web_data: dict[str, Any]) -> str:
    if not web_data.get("findings") and not web_data.get("errors"):
        return ""
    return "\n\nWEB DATA CONTEXT\n" + json.dumps(web_data, indent=2)


def _request_json(url: str, *, headers: dict[str, str] | None = None, method: str = "GET", body: bytes | None = None) -> dict[str, Any]:
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "User-Agent": "disaster-response-mas/1.0 contact@example.com",
            "Accept": "application/json",
            **(headers or {}),
        },
    )
    with urlopen(request, timeout=WEB_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _finding(
    *,
    source: str,
    category: str,
    finding: str,
    url: str,
    confidence: str = "verified",
    timestamp: str | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "category": category,
        "finding": finding,
        "url": url,
        "timestamp": timestamp or utc_now(),
        "confidence": confidence,
        "raw": raw or {},
    }


def _extract_state(text: str) -> str | None:
    for code, name in STATE_NAMES.items():
        if re.search(rf"\b{code}\b", text):
            return code
        if name.lower() in text.lower():
            return code
    return None


def _nws_alerts(situation: dict[str, Any], state: str | None) -> dict[str, Any]:
    if not state:
        return {"findings": [], "errors": ["NWS skipped: no US state detected."]}
    url = f"https://api.weather.gov/alerts/active?area={quote(state)}"
    try:
        payload = _request_json(url)
    except (HTTPError, URLError, TimeoutError) as exc:
        return {"findings": [], "errors": [f"NWS alerts unavailable: {exc}"]}

    findings = []
    for feature in payload.get("features", [])[:5]:
        props = feature.get("properties", {})
        event = props.get("event", "Weather alert")
        area = props.get("areaDesc", state)
        severity = props.get("severity", "Unknown")
        certainty = props.get("certainty", "Unknown")
        findings.append(
            _finding(
                source="National Weather Service",
                category="weather",
                finding=f"{event} for {area}. Severity: {severity}; certainty: {certainty}.",
                url=props.get("@id") or url,
                timestamp=props.get("sent"),
                raw={"event": event, "area": area, "severity": severity, "certainty": certainty},
            )
        )
    return {"findings": findings, "errors": []}


def _usgs_earthquakes(situation: dict[str, Any], state: str | None) -> dict[str, Any]:
    if "earthquake" not in situation.get("hazards", []):
        return {"findings": [], "errors": []}
    start = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    params = urlencode({"format": "geojson", "starttime": start, "minmagnitude": 4.0, "orderby": "time"})
    url = f"https://earthquake.usgs.gov/fdsnws/event/1/query?{params}"
    try:
        payload = _request_json(url)
    except (HTTPError, URLError, TimeoutError) as exc:
        return {"findings": [], "errors": [f"USGS earthquakes unavailable: {exc}"]}

    location_hint = situation.get("location", "").lower()
    features = payload.get("features", [])
    if location_hint:
        matching = [f for f in features if location_hint.split(",")[0] in (f.get("properties", {}).get("place", "").lower())]
        features = matching or features

    findings = []
    for feature in features[:5]:
        props = feature.get("properties", {})
        mag = props.get("mag")
        place = props.get("place", "unknown location")
        detail = props.get("detail") or url
        findings.append(
            _finding(
                source="USGS Earthquake Hazards Program",
                category="earthquake",
                finding=f"Magnitude {mag} earthquake reported at {place}.",
                url=detail,
                timestamp=datetime.fromtimestamp((props.get("time") or 0) / 1000, timezone.utc).isoformat()
                if props.get("time")
                else utc_now(),
                raw={"magnitude": mag, "place": place},
            )
        )
    return {"findings": findings, "errors": []}


def _fema_declarations(situation: dict[str, Any], state: str | None) -> dict[str, Any]:
    if not state:
        return {"findings": [], "errors": ["FEMA skipped: no US state detected."]}
    query = urlencode(
        {
            "$select": "disasterNumber,state,declarationTitle,incidentType,declarationDate,designatedArea",
            "$filter": f"state eq '{state}'",
            "$orderby": "declarationDate desc",
            "$top": "5",
        },
        safe="' ,",
    )
    url = f"https://www.fema.gov/openfema-data-hub/data-sets/disaster-declarations-summaries/v2?{query}"
    alt_url = f"https://www.fema.gov/openfema-data-page/disaster-declarations-summaries"
    try:
        payload = _request_json(url)
    except (HTTPError, URLError, TimeoutError) as exc:
        return {"findings": [], "errors": [f"FEMA declarations unavailable: {exc}"]}

    rows = payload.get("DisasterDeclarationsSummaries", []) or payload.get("data", [])
    findings = [
        _finding(
            source="FEMA OpenFEMA",
            category="declaration",
            finding=f"{row.get('incidentType', 'Incident')} declaration: {row.get('declarationTitle', 'untitled')} in {row.get('designatedArea', state)}.",
            url=alt_url,
            timestamp=row.get("declarationDate"),
            raw=row,
        )
        for row in rows[:5]
    ]
    return {"findings": findings, "errors": []}


def _search_web(situation_report: str, situation: dict[str, Any]) -> dict[str, Any]:
    if TAVILY_API_KEY:
        return _tavily_search(situation_report, situation)
    if should_use_llm() and anthropic and ANTHROPIC_API_KEY:
        return _anthropic_web_search(situation_report, situation)
    return {"findings": [], "errors": ["Web search skipped: set TAVILY_API_KEY or ANTHROPIC_API_KEY with ENABLE_WEB_SEARCH=true."]}


def _tavily_search(situation_report: str, situation: dict[str, Any]) -> dict[str, Any]:
    query = f"{situation['location']} {' '.join(situation['hazards'])} emergency official update"
    body = json.dumps({"api_key": TAVILY_API_KEY, "query": query, "max_results": 5, "search_depth": "basic"}).encode("utf-8")
    try:
        payload = _request_json("https://api.tavily.com/search", method="POST", body=body)
    except (HTTPError, URLError, TimeoutError) as exc:
        return {"findings": [], "errors": [f"Tavily search unavailable: {exc}"]}

    findings = [
        _finding(
            source="Tavily Search",
            category="web_search",
            finding=result.get("content") or result.get("title") or "Search result",
            url=result.get("url", ""),
            confidence="unverified",
            raw={"title": result.get("title"), "score": result.get("score")},
        )
        for result in payload.get("results", [])[:5]
    ]
    return {"findings": findings, "errors": []}


def _anthropic_web_search(situation_report: str, situation: dict[str, Any]) -> dict[str, Any]:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = f"""
Find current official or high-confidence web updates for this incident.
Prefer government, emergency management, weather, geological, transportation, hospital, and utility sources.
Return JSON only with:
{{"findings":[{{"source":"...","category":"official|news|weather|transportation|utility|medical","finding":"...","url":"...","timestamp":"...","confidence":"verified|unverified"}}]}}

Situation:
{situation_report}
"""
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=900,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        return {"findings": [], "errors": [f"Anthropic web search unavailable: {exc}"]}

    text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
    try:
        payload = json.loads(text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
    except json.JSONDecodeError as exc:
        return {"findings": [], "errors": [f"Anthropic web search parse failed: {exc}"]}

    findings = [
        _finding(
            source=item.get("source", "Anthropic Web Search"),
            category=item.get("category", "web_search"),
            finding=item.get("finding", ""),
            url=item.get("url", ""),
            timestamp=item.get("timestamp") or utc_now(),
            confidence=item.get("confidence", "unverified"),
            raw=item,
        )
        for item in payload.get("findings", [])[:5]
        if item.get("finding")
    ]
    return {"findings": findings, "errors": []}


def _summarize_findings(situation_report: str, findings: list[dict[str, Any]]) -> str:
    if not should_use_llm() or not anthropic or not ANTHROPIC_API_KEY:
        return _local_summary(findings)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = f"""
Summarize these web findings for a disaster response commander.
Keep it under 120 words. Distinguish verified official data from unverified search results.

Situation:
{situation_report}

Findings:
{json.dumps(findings, indent=2)}
"""
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=220,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if getattr(block, "type", "") == "text").strip()
    except Exception:
        return _local_summary(findings)


def _local_summary(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return ""
    verified = [item for item in findings if item.get("confidence") == "verified"]
    unverified = [item for item in findings if item.get("confidence") != "verified"]
    examples = findings[:3]
    lead = f"{len(findings)} web findings collected"
    if verified:
        lead += f", including {len(verified)} verified official finding(s)"
    if unverified:
        lead += f" and {len(unverified)} unverified search finding(s)"
    return lead + ": " + " ".join(item["finding"] for item in examples)
