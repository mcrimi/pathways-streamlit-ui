"""Tools for exploring population segments within segmentations."""

from typing import Any

from pathways_mcp.api import format_response, get_client


def _blocks_to_text(blocks: list[dict] | None) -> str | None:
    """Convert Strapi rich text blocks to plain text / markdown."""
    if not blocks:
        return None
    if not isinstance(blocks, list):
        return str(blocks)
    parts = []
    for block in blocks:
        if block.get("type") == "paragraph":
            text = "".join(c.get("text", "") for c in block.get("children", []))
            if text:
                parts.append(text)
        elif block.get("type") == "heading":
            text = "".join(c.get("text", "") for c in block.get("children", []))
            level = block.get("level", 2)
            if text:
                parts.append(f"{'#' * level} {text}")
        elif block.get("type") == "list":
            for item in block.get("children", []):
                for child in item.get("children", []):
                    if child.get("type") == "paragraph":
                        text = "".join(
                            c.get("text", "") for c in child.get("children", [])
                        )
                        if text:
                            parts.append(f"- {text}")
    return "\n\n".join(parts) if parts else None


def _extract_text_field(val: Any) -> str | None:
    """Extract a field that may be plain text or Strapi blocks."""
    if val is None:
        return None
    if isinstance(val, list):
        return _blocks_to_text(val)
    return str(val) if val else None


async def list_segments(
    segmentation_code: str,
    vulnerability_level: str | None = None,
    stratum: str | None = None,
) -> str:
    """List population segments for a segmentation, with optional filters.

    Each segment represents a distinct group of women identified through
    cluster analysis, with a vulnerability level (least/less/more/most)
    and stratum (urban/rural).

    Args:
        segmentation_code: Segmentation code (e.g., "SEN_2019DHS8_v1").
        vulnerability_level: Filter by vulnerability level:
            "least", "less", "more", or "most".
        stratum: Filter by stratum: "urban" or "rural".
    """
    client = get_client()
    filters: dict = {
        "segmentation": {"code": {"$eq": segmentation_code}},
        "active": {"$eq": "true"},
    }
    if vulnerability_level:
        filters["vulnerability_level"] = {"$eq": vulnerability_level}
    if stratum:
        filters["stratum"] = {"$eq": stratum}

    result = await client.fetch_collection(
        "segments",
        filters=filters,
        page_size=100,
        sort="code:asc",
    )

    segments = []
    for s in result.get("data", []):
        segments.append({
            "code": s.get("code"),
            "label": s.get("label"),
            "stratum": s.get("stratum"),
            "vulnerability_level": s.get("vulnerability_level"),
            "prevalence": s.get("prevalence"),
            "sample_size": s.get("sample_size"),
            "active": s.get("active"),
        })

    return format_response(segments)


async def get_segment_profile(
    segmentation_code: str,
    segment_code: str,
) -> str:
    """Get a comprehensive profile for a specific population segment.

    This is the "who are these women?" view — returns the segment's
    vulnerability level, prevalence, and key metrics organized into:
    - **health_outcomes**: metrics linked to Themes (measurable health results
      such as maternal health, nutrition, sexual and reproductive health).
    - **vulnerability_factors**: metrics linked to Domains (structural and social
      determinants such as household economics, social support).

    To compare a segment against the sample total, call get_segment_metrics
    without a segment_code to retrieve the weighted sample-aggregate baseline.

    Use this to understand the characteristics, health outcomes, and vulnerability
    profile of a specific segment.

    Args:
        segmentation_code: Segmentation code (e.g., "SEN_2019DHS8_v1").
        segment_code: Segment code (e.g., "R4" for Rural-4).
    """
    client = get_client()

    # Fetch the segment
    seg_result = await client.fetch_collection(
        "segments",
        filters={
            "segmentation": {"code": {"$eq": segmentation_code}},
            "code": {"$eq": segment_code},
            "active": {"$eq": "true"},
        },
    )
    seg_data = seg_result.get("data", [])
    if not seg_data:
        return format_response({
            "error": f"Segment '{segment_code}' not found in segmentation '{segmentation_code}'."
        })

    segment = seg_data[0]

    # Fetch metrics for this segment with variable info
    metrics_data = await client.fetch_all(
        "metrics",
        filters={
            "segment": {"code": {"$eq": segment_code}},
            "variable": {"segmentation": {"code": {"$eq": segmentation_code}}},
        },
        populate=["variable", "categorical_level"],
        page_size=100,
        max_records=2000,
    )

    # Fetch variables with theme/domain info for grouping
    variables_data = await client.fetch_all(
        "variables",
        filters={"segmentation": {"code": {"$eq": segmentation_code}}},
        populate=["themes", "domain", "variable_type"],
        page_size=100,
        max_records=2000,
    )

    # Build variable lookup: code -> {themes, domain, variable_type}
    var_lookup: dict = {}
    for v in variables_data:
        themes = [t.get("code") for t in (v.get("themes") or [])]
        domain = (v.get("domain") or {}).get("code")
        var_type = (v.get("variable_type") or {}).get("code")
        var_lookup[v.get("code")] = {
            "themes": themes,
            "domain": domain,
            "variable_type": var_type,
            "name": v.get("name_en"),
            "data_type": v.get("data_type"),
        }

    # Organize metrics by variable_type, then domain/theme
    outcomes: dict[str, list] = {}
    vulnerabilities: dict[str, list] = {}

    for m in metrics_data:
        var = m.get("variable") or {}
        var_code = var.get("code")
        var_info = var_lookup.get(var_code, {})
        cat_level = m.get("categorical_level")

        metric_entry = {
            "variable_code": var_code,
            "variable_name": var.get("name_en"),
            "data_type": var.get("data_type"),
        }

        # Add the appropriate value
        if var.get("data_type") in ("categorical", "binary"):
            metric_entry["percentage"] = m.get("percentage")
            metric_entry["percentage_se"] = m.get("percentage_se")
            if cat_level:
                metric_entry["categorical_level"] = cat_level.get("name_en")
        else:
            metric_entry["avg"] = m.get("avg")
            metric_entry["median"] = m.get("median")
            metric_entry["min"] = m.get("min")
            metric_entry["max"] = m.get("max")

        group_key = var_info.get("domain") or (
            var_info.get("themes", [None])[0] if var_info.get("themes") else "other"
        ) or "other"

        if var_info.get("variable_type") == "outcome":
            outcomes.setdefault(group_key, []).append(metric_entry)
        else:
            vulnerabilities.setdefault(group_key, []).append(metric_entry)

    # Build qualitative narrative fields from the segment record
    narratives: dict[str, Any] = {}
    qualitative_fields = {
        "summary": ["summary_en", "summary"],
        "health_outcomes_narrative": [
            "health_outcomes_narrative_en",
            "health_outcomes_narrative",
            "health_narrative_en",
        ],
        "vulnerability_narrative": [
            "vulnerability_narrative_en",
            "vulnerability_narrative",
            "vulnerability_factors_narrative_en",
        ],
        "key_characteristics": [
            "key_characteristics_en",
            "key_characteristics",
            "characteristics_en",
        ],
        "recommendations": [
            "recommendations_en",
            "recommendations",
            "programmatic_recommendations_en",
        ],
    }
    for narrative_key, candidate_fields in qualitative_fields.items():
        for field_name in candidate_fields:
            raw = segment.get(field_name)
            if raw is not None:
                text = _extract_text_field(raw)
                if text:
                    narratives[narrative_key] = text
                    break

    output = {
        "segment": {
            "code": segment.get("code"),
            "label": segment.get("label"),
            "stratum": segment.get("stratum"),
            "vulnerability_level": segment.get("vulnerability_level"),
            "prevalence": segment.get("prevalence"),
            "sample_size": segment.get("sample_size"),
            **({k: v for k, v in narratives.items()} if narratives else {}),
        },
        "health_outcomes": outcomes,
        "vulnerability_factors": vulnerabilities,
    }

    return format_response(output)
