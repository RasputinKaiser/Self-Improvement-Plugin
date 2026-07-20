from __future__ import annotations
from collections import Counter
from typing import Any

from memory_fabric_search_filters import trust_status
from memory_fabric_task_cue_ledger import cue_ledger


CLAIM_BOUNDARY = "Task profiles are deterministic routing hints; they do not prove task completion."

PROFILES = [
    {
        "id": "object_identification_pricing",
        "keywords": {
            "identify",
            "identification",
            "item",
            "object",
            "ebay",
            "price",
            "pricing",
            "logo",
            "logos",
            "code",
            "codes",
            "marking",
            "glass",
            "wood",
            "trim",
            "style",
            "material",
            "vintage",
        },
        "next_checks": [
            "capture_general_visual_description",
            "extract_text_logos_codes_markings",
            "record_material_style_trim_details",
            "combine_visual_and_text_signals",
            "compare_candidate_matches_visually",
            "price_only_after_likely_same_item",
        ],
        "proof_boundary": (
            "Visual or web-search context is not identity or pricing proof until "
            "matched to current source evidence."
        ),
        "cue_groups": [
            {
                "id": "general_visual_description",
                "label": "General visual description",
                "keywords": {"visual", "description", "shape", "color", "size", "object", "item"},
                "next_check": "capture_general_visual_description",
            },
            {
                "id": "text_logos_codes_markings",
                "label": "Text, logos, codes, or markings",
                "keywords": {"text", "logo", "logos", "code", "codes", "marking", "markings", "label"},
                "next_check": "extract_text_logos_codes_markings",
            },
            {
                "id": "material_style_trim",
                "label": "Material, style, trim, or construction details",
                "keywords": {"material", "materials", "glass", "wood", "trim", "style", "metal", "ceramic"},
                "next_check": "record_material_style_trim_details",
            },
            {
                "id": "candidate_match",
                "label": "Candidate match source",
                "keywords": {"candidate", "match", "matches", "ebay", "listing", "seller", "source"},
                "next_check": "find_candidate_match_before_pricing",
            },
            {
                "id": "visual_comparison",
                "label": "Visual comparison against likely same item",
                "keywords": {"compare", "comparison", "same", "identical", "likely"},
                "next_check": "compare_candidate_matches_visually",
            },
        ],
    },
    {
        "id": "plugin_release",
        "keywords": {
            "plugin",
            "release",
            "cache",
            "live",
            "mcp",
            "doctor",
            "eval",
            "schema",
            "receipt",
        },
        "next_checks": [
            "validate_source_behavior",
            "sync_cache_and_record_receipt",
            "check_current_live_tool_schema",
            "compare_source_vs_live_behavior",
            "write_release_report_with_attention_codes",
        ],
        "proof_boundary": "Source, cache, stdio, and current-live receipts are separate proof layers.",
    },
    {
        "id": "code_debugging",
        "keywords": {
            "bug",
            "debug",
            "failure",
            "trace",
            "test",
            "repro",
            "fix",
        },
        "next_checks": [
            "capture_repro_command",
            "isolate_smallest_failing_case",
            "inspect_recent_related_changes",
            "patch_minimal_cause",
            "rerun_targeted_then_broader_tests",
        ],
        "proof_boundary": "Passing a narrow repro is not broad product proof.",
    },
]

GENERIC_PROFILE = {
    "id": "general_memory_handoff",
    "keywords": set(),
    "next_checks": [
        "review_selected_work",
        "verify_source_backed_knowledge",
        "apply_relevant_learning",
        "record_new_verified_outcome",
    ],
    "proof_boundary": "A memory brief is context; verify claims before relying on them.",
}


def task_profile(query_terms: list[str], records: list[dict[str, Any]]) -> dict[str, Any]:
    profile = best_profile(query_terms)
    trusts = Counter(trust_status(record)["status"] for record in records)
    tiers = Counter(str(record.get("tier", "unknown")) for record in records)
    return {
        "id": profile["id"],
        "matched_keywords": matched_keywords(profile, query_terms),
        "next_checks": profile["next_checks"],
        "cue_ledger": cue_ledger(profile, query_terms, records),
        "selected_record_count": len(records),
        "selected_tier_counts": dict(sorted(tiers.items())),
        "selected_trust_counts": dict(sorted(trusts.items())),
        "proof_boundary": profile["proof_boundary"],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def best_profile(query_terms: list[str]) -> dict[str, Any]:
    scored = [(len(set(query_terms) & profile["keywords"]), profile) for profile in PROFILES]
    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    if scored and scored[0][0] > 0:
        return scored[0][1]
    return GENERIC_PROFILE


def matched_keywords(profile: dict[str, Any], query_terms: list[str]) -> list[str]:
    return sorted(set(query_terms) & profile["keywords"])
