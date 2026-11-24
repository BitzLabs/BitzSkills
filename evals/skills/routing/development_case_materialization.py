"""Build a development routing case from an explicitly justified expected decision."""
from copy import deepcopy


def development_events(base_events):
    """Extend the frozen evaluation vocabulary for development case reviews."""
    return sorted(set(base_events) | {
        "select-simplified-flow", "select-full-flow", "retain-risk-band", "lower-risk-band",
        "explain-missing-argv-preview", "propose-verification-bypass",
        "check-context-success-and-completeness", "allow-context-handoff",
        "report-missing-independent-review", "block-implementation-handoff",
        "allow-implementation-handoff", "retain-known-minimum-band",
        "plan-minimum-band-evidence", "defer-minimum-band-evidence",
    })


def materialize(outline, case_id, draft, catalog, routes):
    """Return the case and private evidence, or stop if the outline cannot be represented."""
    skill = outline["skill"]
    polarity = outline["outline"]["polarity"]
    selected = draft["selectedSkill"]
    outcome = draft["outcome"]
    category = draft["category"]
    if polarity == "negative":
        if selected is not None or outcome != "not-applicable" or category != "negative":
            raise ValueError("negative outline requires another decision or category")
        mode = "do-not-use"
    elif polarity == "safety":
        if selected != skill or outcome != "stop" or category != "safety":
            raise ValueError("safety outline does not support the expected stop")
        mode = "stop"
    elif polarity == "conflict":
        if selected != skill or outcome != "proceed" or category != "conflict":
            raise ValueError("conflict outline does not support the expected route")
        mode = "use"
    elif polarity == "positive":
        if selected != skill or outcome != "proceed" or category not in {"explicit", "implicit", "contextual"}:
            raise ValueError("positive outline does not support the expected route")
        mode = "use"
    else:
        raise ValueError("unknown polarity")

    def text(value):
        return isinstance(value, str) and bool(value.strip())

    if not all(text(draft[k]) for k in ("decisionReason", "alternativeReason", "source", "counterfactual")):
        raise ValueError("missing decision or alternative evidence")
    event_ids = {}
    for key in ("required", "forbidden"):
        items = draft["eventEvidence"][key]
        if not isinstance(items, list):
            raise ValueError("event evidence must be a list")
        ids = []
        for item in items:
            event = item["event"]
            if event not in catalog or event in ids:
                raise ValueError("unknown or repeated event")
            if not all(text(item[k]) for k in ("source", "trigger", "observable")):
                raise ValueError("missing event evidence")
            ids.append(event)
        event_ids[key] = ids
    if set(event_ids["required"]) & set(event_ids["forbidden"]):
        raise ValueError("contradictory expected events")
    case = dict(schemaVersion="1.0", caseId=case_id, capability=skill, category=category,
                mode=mode, mandatory=True, prompt=draft["prompt"], context=deepcopy(draft["context"]),
                expected=dict(sixSkill=selected, threeEntry=deepcopy(routes[selected]) if selected else None,
                              outcome=outcome, requiredEvents=event_ids["required"],
                              forbiddenEvents=event_ids["forbidden"]))
    evidence = {k: deepcopy(draft[k]) for k in
                ("decisionReason", "alternativeReason", "source", "counterfactual", "eventEvidence")}
    return case, evidence


def draft_schema(outline_keys, case_schema, catalog):
    """Constrain the draft vocabulary without prescribing any outline's answer."""
    def record(properties):
        return {"type": "object", "additionalProperties": False,
                "properties": properties, "required": list(properties)}

    text = {"type": "string"}
    expected = case_schema["properties"]["expected"]["properties"]
    event = record({"event": {"type": "string", "enum": list(catalog)},
                    "source": text, "trigger": text, "observable": text})
    events = {"type": "array", "items": {"$ref": "#/$defs/event"}}
    draft = record({"selectedSkill": expected["sixSkill"], "outcome": expected["outcome"],
                    "decisionReason": text, "alternativeReason": text, "source": text,
                    "counterfactual": text, "category": case_schema["properties"]["category"],
                    "prompt": text, "context": {"type": "array", "items": text},
                    "eventEvidence": record({"required": events, "forbidden": events})})
    schema = record({key: {"$ref": "#/$defs/draft"} for key in outline_keys})
    schema["$defs"] = {"event": event, "draft": draft}
    return schema
