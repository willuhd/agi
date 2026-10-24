"""Course-selection evaluator. Rule source: Courses.gpa presets + rules
(selection/exclusion logic — the file's valid use; its "weight" fields
are GPA credits, never time, and are not used for scheduling here).

Validates a student's planned selection for one preset (e.g. shsid2026grade11):
  - per-module limit / minSelection
  - exclusionIds (same course in two modules)
  - dynamicLimits (e.g. 2-in-M1 locks M3/M4 to 0)
  - conditionalRequirements (econ_ap_rule, ap_es_rule)
  - requirements (tag triggers)

Selection format: {module_name: [subject_ref, ...]} where subject_ref is
the subject 'id' when present else its 'name'. Module order = JSON order;
rule moduleIndex values refer to that order.

Known source quirks (flagged, not silently fixed):
  - 'g11_m4_maybe_same_micro/macro' in exclusionIds match no subject: dangling.
  - PDF-only rules absent from JSON: AP-Econ/Draw/3D-in-M4 => no AP in M3;
    AS-in-M1 => no School Biology. Encode via extra_rules when confirmed.
"""
from __future__ import annotations

import os
import re
import json

GPA_FILE = os.environ.get(
    "GPA_FILE", "/Volumes/thinkplus/Code/CourseResources/Courses.gpa")


def load_gpa(path: str = GPA_FILE) -> dict:
    with open(path) as f:
        t = f.read()
    t = re.sub(r"//.*", "", t)
    t = re.sub(r",(\s*[}\]])", r"\1", t)
    return json.loads(t)


def get_preset(gpa: dict, preset_id: str) -> dict:
    for p in gpa["presets"]:
        if p["id"] == preset_id:
            return p
    raise KeyError(f"preset {preset_id!r} not found")


def resolve_subjects(module: dict, templates: dict) -> dict:
    """key -> {name, tags, weight}. key = id if present else name."""
    out = {}
    for s in module.get("subjects", []):
        key = s.get("id", s["name"])
        levels = s.get("levels")
        if levels is None and "template" in s:
            t = templates.get(s["template"], {})
            levels = t.get("levels", [])
            weight = s.get("weight", t.get("weight"))
        else:
            weight = s.get("weight")
        tags = {t for lv in (levels or []) for t in lv.get("tags", [])}
        out[key] = {"name": s["name"], "tags": tags, "weight": weight,
                    "levels": [lv["name"] for lv in (levels or [])]}
    return out


def _mod_index(preset: dict, name: str) -> int:
    for i, m in enumerate(preset["modules"]):
        if m.get("name", f"core_{i}") == name:
            return i
    raise KeyError(f"module {name!r} not found")


def evaluate(preset: dict, templates: dict, selection: dict,
             extra_rules: dict | None = None) -> list[str]:
    """Return list of violation messages; empty means the selection is legal."""
    errors: list[str] = []
    resolved = [resolve_subjects(m, templates) for m in preset["modules"]]
    by_name = {m.get("name", f"core_{i}"): i
               for i, m in enumerate(preset["modules"])}
    chosen: dict[int, list[str]] = {}
    for mod_name, refs in selection.items():
        i = by_name[mod_name]
        known = resolved[i]
        for r in refs:
            if r not in known:
                errors.append(f"{mod_name}: unknown subject {r!r}")
        chosen[i] = [r for r in refs if r in known]

    rules = dict(preset.get("rules", {}))
    if extra_rules:
        rules.update(extra_rules)
    # None = unlimited (core modules carry limit: 0 meaning no cap).
    # A rule-supplied newLimit of 0 means FORBID — distinct from None.
    limits = {i: (m.get("limit") or None) for i, m in enumerate(preset["modules"])}

    for t in rules.get("dynamicLimits", []):
        trig = t["triggerModuleIndex"]
        n = len(chosen.get(trig, []))
        cond = t["triggerCondition"].strip()
        hit = (n >= int(cond[2:]) if cond.startswith(">=")
               else n == int(cond[2:]) if cond.startswith("==") else False)
        if hit:
            for tgt in t["targetModuleIndices"]:
                limits[tgt] = t["newLimit"]

    for i, m in enumerate(preset["modules"]):
        name = m.get("name", f"core_{i}")
        n = len(chosen.get(i, []))
        lim, minimum = limits[i], m.get("minSelection", 0)
        if lim is not None and n > lim:
            errors.append(f"{name}: selects {n}, limit is {lim}")
        if n < minimum:
            errors.append(f"{name}: selects {n}, minimum is {minimum}")

    for group in rules.get("exclusionIds", []):
        picked = {g for g in group for mi, refs in chosen.items()
                  if g in refs}
        if len(picked) > 1:
            errors.append(f"mutually exclusive subjects co-selected: {group}")

    for cr in rules.get("conditionalRequirements", []):
        trig = cr["trigger"]
        trig_ids = set(trig.get("selectedSubjectIds", []))
        selected_ids = {r for refs in chosen.values() for r in refs}
        if trig_ids and not (trig_ids & selected_ids):
            continue
        ok = True
        for mc in trig.get("moduleConditions", []):
            refs = chosen.get(mc["moduleIndex"], [])
            ap_n = sum(1 for r in refs
                       if "AP" in resolved[mc["moduleIndex"]][r]["tags"]
                       or "ASA2" in resolved[mc["moduleIndex"]][r]["tags"])
            if len(refs) < mc.get("minSelected", 0):
                ok = False
            if mc.get("requireTag") in ("AP", "ASA2"):
                if ap_n != mc.get("exactCount", ap_n):
                    ok = False
        if not ok:
            continue
        for em in cr.get("enforceModuleLimits", []):
            limits[em["moduleIndex"]] = em["newLimit"]
        if "requiresAnyOfSubjectIds" in cr:
            want = set(cr["requiresAnyOfSubjectIds"])
            if not (want & selected_ids):
                errors.append(f"{cr['id']}: {cr.get('errorMessage', '')}")
        # re-check limits tightened by this rule
        for em in cr.get("enforceModuleLimits", []):
            i = em["moduleIndex"]
            n = len(chosen.get(i, []))
            if em["newLimit"] is not None and n > em["newLimit"]:
                errors.append(
                    f"{cr['id']}: module {i} selects {n}, "
                    f"rule caps at {em['newLimit']}")

    for rq in rules.get("requirements", []):
        tagged = any(
            rq["triggerTag"] in resolved[mi][r]["tags"]
            for mi, refs in chosen.items() for r in refs)
        if tagged:
            want = set(rq.get("requiredAnyTag", []))
            has = any(
                want & resolved[mi][r]["tags"]
                for mi, refs in chosen.items() for r in refs)
            if not has:
                errors.append(f"requirement: {rq.get('errorMessage', '')}")
    return errors


def audit_rules(preset: dict, templates: dict) -> list[str]:
    """Report dangling rule references (source quirks, not selection errors)."""
    notes: list[str] = []
    resolved = [resolve_subjects(m, templates) for m in preset["modules"]]
    all_ids = {r for mod in resolved for r in mod}
    for group in preset.get("rules", {}).get("exclusionIds", []):
        for g in group:
            if g not in all_ids:
                notes.append(f"dangling exclusionId: {g!r}")
    return notes
