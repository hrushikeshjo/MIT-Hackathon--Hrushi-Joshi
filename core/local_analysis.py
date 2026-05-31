from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


HAZARD_PATTERNS = {
    "earthquake": ["earthquake", "quake", "aftershock", "magnitude"],
    "wildfire": ["wildfire", "fire", "smoke", "burn", "foothills"],
    "flood": ["flood", "flooding", "storm surge", "levee", "inundation"],
    "hurricane": ["hurricane", "cyclone", "typhoon", "storm surge"],
    "tornado": ["tornado", "twister"],
    "hazmat": ["hazmat", "chemical", "gas leak", "spill", "toxic"],
    "medical": ["injur", "casualty", "hospital", "medical"],
    "infrastructure": ["bridge", "road", "highway", "power", "water", "collapse"],
}

ISSUE_DEFINITIONS = [
    {
        "category": "life_safety",
        "keywords": ["trapped", "missing", "unable to self-evacuate", "sheltering in place"],
        "title": "People requiring rescue or evacuation assistance",
        "severity": 5,
        "urgency": 5,
        "owner": "Urban search and rescue, EMS, fire",
        "action": "Confirm exact locations, establish rescue groups, and prioritize life-safety access.",
    },
    {
        "category": "hazmat",
        "keywords": ["gas leak", "gas leaks", "chemical", "hazmat", "spill", "vapor", "toxic", "contamination"],
        "title": "Hazardous material or gas release",
        "severity": 5,
        "urgency": 5,
        "owner": "Hazmat, fire, utility crew",
        "action": "Create isolation zones, identify substance or utility source, and stop exposure.",
    },
    {
        "category": "fire",
        "keywords": ["wildfire", "fire", "smoke", "burn", "structure loss"],
        "title": "Fire, smoke, or wildfire threat",
        "severity": 5,
        "urgency": 4,
        "owner": "Fire operations and evacuation branch",
        "action": "Define evacuation zones, protect exposures, and route responders around smoke or flame fronts.",
    },
    {
        "category": "structural",
        "keywords": ["collapse", "collapsed", "structural", "roof collapse", "building damage"],
        "title": "Structural collapse or building instability",
        "severity": 5,
        "urgency": 4,
        "owner": "USAR, building safety, fire",
        "action": "Establish collapse perimeter, search void spaces, and request structural assessment.",
    },
    {
        "category": "medical",
        "keywords": ["hospital", "casualty", "injur", "medical", "respiratory", "dialysis", "oxygen"],
        "title": "Medical surge or vulnerable patient support",
        "severity": 4,
        "urgency": 5,
        "owner": "EMS, hospital coordination, public health",
        "action": "Distribute patients, confirm bed capacity, and support vulnerable medical needs.",
    },
    {
        "category": "transportation",
        "keywords": ["road", "bridge", "highway", "crossing", "arterial", "blocked", "submerged"],
        "title": "Transportation access or route constraint",
        "severity": 4,
        "urgency": 4,
        "owner": "Public works, law enforcement, logistics",
        "action": "Verify route status, close unsafe corridors, and identify alternate responder access.",
    },
    {
        "category": "shelter",
        "keywords": ["shelter", "evacuation", "assisted-living", "senior housing", "residents"],
        "title": "Shelter, evacuation, or care-site need",
        "severity": 4,
        "urgency": 4,
        "owner": "Mass care, shelter operations, transport",
        "action": "Confirm shelter capacity, accessibility, transport, and special-needs support.",
    },
    {
        "category": "utilities",
        "keywords": ["power", "generator", "utility", "downed power", "cellular", "service outage"],
        "title": "Utility or communications disruption",
        "severity": 3,
        "urgency": 4,
        "owner": "Utility liaison, infrastructure branch",
        "action": "Assess outage footprint, protect downed lines, and prioritize critical facility restoration.",
    },
    {
        "category": "weather",
        "keywords": ["storm", "wind", "thunderstorm", "flood", "flooding", "levee", "bayou", "water", "overtopping"],
        "title": "Weather or water-driven hazard",
        "severity": 4,
        "urgency": 4,
        "owner": "Operations, water rescue, emergency management",
        "action": "Track hazard movement, warn exposed zones, and stage specialized rescue assets.",
    },
]

LOCATION_RE = re.compile(
    r"(?:Location|near|in|at)\s*:\s*([^\n]+)|(?:near|in|at)\s+([A-Z][A-Za-z .'-]+(?:County|District|City|CA|NY|TX|FL|WA)?)"
)
NUMBER_RE = re.compile(r"(?:approximately\s+)?([0-9][0-9,]*)\s+(?:people|residents|workers|patients)", re.IGNORECASE)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _contains(text: str, needles: list[str]) -> bool:
    lower = text.lower()
    return any(needle in lower for needle in needles)


def _primary_report_text(context: str) -> str:
    if "Original report:" in context:
        context = context.split("Original report:")[-1].strip()
    if "WEB DATA CONTEXT" in context:
        context = context.split("WEB DATA CONTEXT")[0].strip()
    return context


def _split_observations(text: str) -> list[str]:
    observations = []
    for line in text.splitlines():
        clean = line.strip(" -\t")
        if not clean:
            continue
        if ":" in clean:
            label, value = clean.split(":", 1)
            if label.lower() in {"confirmed", "unconfirmed", "reported", "medical"}:
                clean = f"{label.strip()}: {value.strip()}"
            elif label.lower() in {"type", "location"}:
                clean = value.strip()
        observations.append(clean)
    if observations:
        return observations
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def _extract_count(text: str) -> int | None:
    match = NUMBER_RE.search(text)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def _extract_location(observation: str, fallback: str) -> str:
    for pattern in [
        r"\b(?:near|at|in|inside|across|around)\s+([A-Z][A-Za-z0-9 .'-]+?)(?:,|\.|;|$)",
        r"\b([A-Z][A-Za-z .'-]+(?:County|District|City|Bayou|Road|Avenue|Street|Highway|Corridor|Port|Springs Road))\b",
    ]:
        match = re.search(pattern, observation)
        if match:
            return match.group(1).strip(" .,-")
    return fallback


def issue_catalog(context: str) -> list[dict[str, Any]]:
    source_text = _primary_report_text(context)
    situation = extract_situation(source_text)
    observations = _split_observations(source_text)
    catalog: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for observation in observations:
        lower = observation.lower()
        confidence = "unconfirmed" if "unconfirmed" in lower else "reported"
        if confidence != "unconfirmed" and any(word in lower for word in ["confirmed", "life safety", "life-safety"]):
            confidence = "confirmed"

        for definition in ISSUE_DEFINITIONS:
            if not _contains(lower, definition["keywords"]):
                continue
            location = _extract_location(observation, situation["location"])
            key = (definition["category"], location.lower(), observation.lower()[:80])
            if key in seen:
                continue
            seen.add(key)
            affected_count = _extract_count(observation)
            severity = definition["severity"]
            urgency = definition["urgency"]
            if confidence == "unconfirmed":
                urgency = max(2, urgency - 1)

            catalog.append(
                {
                    "issue_id": f"ISS-{len(catalog) + 1:03d}",
                    "category": definition["category"],
                    "title": definition["title"],
                    "description": observation,
                    "location": location,
                    "status": "active" if confidence != "unconfirmed" else "needs_confirmation",
                    "severity": severity,
                    "urgency": urgency,
                    "priority_score": severity * urgency,
                    "affected_count": affected_count,
                    "confidence": confidence,
                    "recommended_owner": definition["owner"],
                    "recommended_action": definition["action"],
                    "source": "Provided situation reports",
                    "last_observed_at": utc_now(),
                }
            )

    catalog.sort(key=lambda issue: issue["priority_score"], reverse=True)
    for index, issue in enumerate(catalog, start=1):
        issue["rank"] = index
    return catalog


def extract_situation(context: str) -> dict[str, Any]:
    text = context or ""
    lower = text.lower()
    hazards = [name for name, words in HAZARD_PATTERNS.items() if _contains(lower, words)]
    if not hazards:
        hazards = ["unknown"]

    location = "affected area"
    for match in LOCATION_RE.finditer(text):
        candidate = (match.group(1) or match.group(2) or "").strip(" .,-")
        if candidate:
            location = candidate
            break

    affected_population = None
    affected_match = re.search(r"([0-9][0-9,]*)\s+(?:people\s+)?affected", lower)
    if affected_match:
        affected_population = int(affected_match.group(1).replace(",", ""))

    trapped = None
    trapped_match = re.search(r"(?:approximately\s+)?([0-9][0-9,]*)\s+people\s+trapped", lower)
    if trapped_match:
        trapped = int(trapped_match.group(1).replace(",", ""))

    hazards_found = []
    if "gas leak" in lower or "gas leaks" in lower:
        hazards_found.append("confirmed gas leaks")
    if "collapse" in lower or "collapsed" in lower:
        hazards_found.append("structural collapse")
    if "fire" in lower:
        hazards_found.append("active or possible fire")
    if "bridge" in lower or "highway" in lower:
        hazards_found.append("transportation infrastructure damage")
    if "hospital" in lower:
        hazards_found.append("hospital surge or mass casualty activation")

    life_safety_flags = []
    if "life safety flag" in lower or "life-safety flag" in lower:
        life_safety_flags.append("Life-safety flag is active in the source report.")
    if trapped:
        life_safety_flags.append(f"{trapped} people are reported trapped and need search and rescue.")
    if "gas leak" in lower or "gas leaks" in lower:
        life_safety_flags.append("Confirmed gas leaks create fire and explosion risk.")
    if "collapse" in lower or "collapsed" in lower:
        life_safety_flags.append("Structural collapse reports require immediate rescue and perimeter control.")
    if "fire" in lower:
        life_safety_flags.append("Fire risk may compound evacuation and rescue operations.")

    return {
        "raw": text.strip(),
        "timestamp": utc_now(),
        "hazards": hazards,
        "location": location,
        "affected_population": affected_population,
        "trapped": trapped,
        "hazards_found": hazards_found,
        "life_safety_flags": life_safety_flags,
    }


def data_aggregator_response(task_context: str) -> dict[str, Any]:
    situation = extract_situation(task_context)
    issues = issue_catalog(task_context)
    findings = [
        {
            "category": "official",
            "finding": "Source report indicates an active incident requiring coordinated response.",
            "source": "Provided situation report",
            "confidence": "verified",
        }
    ]

    for hazard in situation["hazards_found"]:
        findings.append(
            {
                "category": "news",
                "finding": f"Reported condition: {hazard}.",
                "source": "Provided situation report",
                "confidence": "verified",
            }
        )

    if situation["affected_population"]:
        findings.append(
            {
                "category": "official",
                "finding": f"Estimated affected population is {situation['affected_population']:,}.",
                "source": "Provided situation report",
                "confidence": "verified",
            }
        )

    data_gaps = [
        "Live weather, road closure, and utility feeds were not queried in local mode.",
        "Casualty counts and resource availability require official confirmation.",
    ]

    return {
        "agent": "DataAggregator",
        "timestamp": utc_now(),
        "location": situation["location"],
        "findings": findings,
        "contradictions": [],
        "overall_confidence": "medium" if len(findings) > 1 else "low",
        "data_gaps": data_gaps,
        "issue_catalog": issues,
    }


def resource_mapper_response(task_context: str) -> dict[str, Any]:
    situation = extract_situation(task_context)
    resources = [
        {
            "category": "medical",
            "name": "Nearest emergency departments and trauma centers",
            "status": "unknown",
            "capacity": "unknown",
            "distance_km": None,
            "notes": "Confirm bed availability through EMS/hospital coordination before routing patients.",
        },
        {
            "category": "emergency_unit",
            "name": "Urban search and rescue teams",
            "status": "unknown",
            "capacity": "unknown",
            "distance_km": None,
            "notes": "Prioritize collapsed structures and reported entrapments.",
        },
        {
            "category": "utility",
            "name": "Gas and electric utility crews",
            "status": "unknown",
            "capacity": "unknown",
            "distance_km": None,
            "notes": "Needed for confirmed gas leaks, shutoffs, and ignition risk control.",
        },
        {
            "category": "shelter",
            "name": "Public shelters outside immediate hazard zones",
            "status": "unknown",
            "capacity": "unknown",
            "distance_km": None,
            "notes": "Open accessible shelters after structural and air-quality checks.",
        },
    ]
    critical_gaps = [
        "No confirmed live shelter capacity.",
        "No confirmed road status for responder routing.",
        "No confirmed hospital bed availability.",
    ]
    if situation["trapped"]:
        critical_gaps.insert(0, "Search and rescue capacity must be confirmed immediately.")

    return {
        "agent": "ResourceMapper",
        "timestamp": utc_now(),
        "location": situation["location"],
        "resources": resources,
        "critical_gaps": critical_gaps,
        "overall_resource_status": "critical" if situation["life_safety_flags"] else "strained",
    }


def triage_response(task_context: str) -> dict[str, Any]:
    situation = extract_situation(task_context)
    issues = issue_catalog(task_context)
    priorities = []

    def add(need: str, location: str, severity: int, urgency: int, responder: str, risk: str | None) -> None:
        priorities.append(
            {
                "rank": 0,
                "need": need,
                "location": location,
                "severity": severity,
                "urgency": urgency,
                "priority_score": severity * urgency,
                "recommended_responder": responder,
                "cascading_risk": risk,
            }
        )

    location = situation["location"]
    if situation["trapped"]:
        add(
            f"Rescue reported trapped occupants ({situation['trapped']:,} people).",
            location,
            5,
            5,
            "Urban search and rescue, EMS, fire",
            "Secondary collapse and delayed medical care.",
        )
    if "confirmed gas leaks" in situation["hazards_found"]:
        add("Isolate and shut down gas leaks.", location, 5, 5, "Fire, hazmat, gas utility", "Explosion or fire.")
    if "active or possible fire" in situation["hazards_found"]:
        add("Contain active or possible fire spread.", location, 5, 4, "Fire and evacuation teams", "Smoke exposure and blocked evacuation.")
    if "hospital surge or mass casualty activation" in situation["hazards_found"]:
        add("Manage mass casualty intake and patient distribution.", location, 4, 5, "EMS, hospital coordination", "Hospital overload.")
    if "transportation infrastructure damage" in situation["hazards_found"]:
        add("Verify bridge and highway safety before routing.", location, 4, 4, "Public works, law enforcement", "Responder delays and secondary crashes.")

    if not priorities:
        add("Establish incident command and verify ground truth.", location, 3, 3, "Emergency management", "Delayed situational awareness.")

    priorities.sort(key=lambda item: item["priority_score"], reverse=True)
    for index, item in enumerate(priorities[:5], start=1):
        item["rank"] = index

    return {
        "agent": "TriageAgent",
        "timestamp": utc_now(),
        "priorities": priorities[:5],
        "issue_catalog": issues,
        "life_safety_flags": situation["life_safety_flags"],
        "triage_confidence": "medium",
    }


def communication_response(task_context: str) -> dict[str, Any]:
    situation = extract_situation(task_context)
    location = situation["location"]
    alert = f"Avoid {location}. Follow official evacuation and shelter instructions. Call 911 for life threats."
    if len(alert) > 160:
        alert = "Avoid the incident area. Follow official evacuation and shelter instructions. Call 911 for life threats."

    drafts = [
        {
            "type": "public_alert",
            "audience": "public",
            "channel": "SMS",
            "content": alert,
            "character_count": len(alert),
            "urgency": "immediate",
        },
        {
            "type": "responder_brief",
            "audience": "first responders",
            "channel": "radio",
            "content": "Life-safety operations first: rescue trapped people, secure gas leaks, confirm routes, and coordinate hospital distribution.",
            "character_count": 123,
            "urgency": "immediate",
        },
        {
            "type": "media_statement",
            "audience": "media",
            "channel": "press",
            "content": "Emergency crews are responding to reported life-safety hazards. Officials are verifying impacts and will share confirmed updates through official channels.",
            "character_count": 146,
            "urgency": "within_1hr",
        },
    ]

    if "fire" in situation["raw"].lower() or "gas leak" in situation["raw"].lower():
        drafts.append(
            {
                "type": "evacuation",
                "audience": "people in immediate hazard zones",
                "channel": "SMS",
                "content": "Leave the immediate hazard area if officials instruct you. Avoid damaged buildings, smoke, and gas odors.",
                "character_count": 99,
                "urgency": "immediate",
            }
        )

    return {
        "agent": "CommunicationAgent",
        "timestamp": utc_now(),
        "drafts": drafts,
        "do_not_say": ["Do not report casualty totals or resource availability until officially confirmed."],
    }


def logistics_response(task_context: str) -> dict[str, Any]:
    situation = extract_situation(task_context)
    location = situation["location"]
    deployments = [
        {
            "resource": "Urban search and rescue task force",
            "from": "nearest available staging area",
            "to": location,
            "route": "Use confirmed open arterials only; avoid unverified bridges and damaged corridors.",
            "eta_minutes": None,
            "priority": "critical",
        },
        {
            "resource": "Gas utility emergency crew",
            "from": "utility operations center",
            "to": location,
            "route": "Coordinate with fire command for safe access and isolation zones.",
            "eta_minutes": None,
            "priority": "critical",
        },
        {
            "resource": "EMS strike team",
            "from": "regional EMS staging",
            "to": "casualty collection point near the incident perimeter",
            "route": "Confirm hospital destinations and keep one ingress/egress lane clear.",
            "eta_minutes": None,
            "priority": "critical",
        },
    ]

    return {
        "agent": "LogisticsAgent",
        "timestamp": utc_now(),
        "deployments": deployments,
        "supply_needs": [
            {"item": "medical triage supplies", "quantity_needed": "mass-casualty cache", "nearest_source": "unknown"},
            {"item": "portable lighting and generators", "quantity_needed": "as needed for night operations", "nearest_source": "unknown"},
            {"item": "water and blankets", "quantity_needed": "scale to displaced population", "nearest_source": "unknown"},
        ],
        "evacuation_routes": [
            {
                "zone": location,
                "primary_route": "Use routes cleared by law enforcement and public works.",
                "alternate_route": "Use secondary arterials outside collapse, fire, or gas-leak perimeters.",
                "staging_area": "Confirmed shelter or public facility outside the hazard zone.",
            }
        ],
        "bottlenecks": [
            "Unconfirmed road and bridge status.",
            "Potential single access points near collapsed structures.",
            "Hospital surge capacity is not confirmed.",
        ],
        "logistics_confidence": "medium",
    }


LOCAL_AGENT_HANDLERS = {
    "DataAggregator": data_aggregator_response,
    "ResourceMapper": resource_mapper_response,
    "TriageAgent": triage_response,
    "CommunicationAgent": communication_response,
    "LogisticsAgent": logistics_response,
}
