"""Tools for querying quantitative metrics (the core data points)."""

from pathways_mcp.api import format_response, get_client


async def get_segment_metrics(
    segmentation_code: str,
    segment_code: str | None = None,
    theme_code: str | None = None,
    domain_code: str | None = None,
    variable_codes: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    """Get quantitative metrics (indicators, prevalence) for a segment or the sample total.

    **Sample-total metrics**: metrics with no segment represent the weighted
    aggregate across all sample respondents (not a census). Omit segment_code
    to retrieve them. Use these as a baseline to compare individual segments.

    **Segment-level metrics**: pass a segment_code to retrieve metrics for a
    specific population group.

    Metrics fall into two categories:
    - **Health Outcomes**: linked to Themes (e.g., maternal_health, nutrition).
      Filter with theme_code.
    - **Vulnerability Factors**: linked to Domains (e.g., household_economics,
      social_support). Filter with domain_code.

    Use list_themes_and_domains to discover available theme and domain codes.

    Args:
        segmentation_code: Segmentation code (e.g., "SEN_2019DHS8_v1").
        segment_code: Segment code (e.g., "R4"). Omit to get sample-total
            metrics (weighted aggregate across all sample respondents).
        theme_code: Optional theme code to filter Health Outcome metrics
            (e.g., "sexual_and_reproductive_health", "nutrition",
            "maternal_health").
        domain_code: Optional domain code to filter Vulnerability Factor metrics
            (e.g., "household_economics", "social_support").
        variable_codes: Optional list of specific variable codes to filter by.
        limit: Maximum number of metrics to return (default 50, max 100).
        offset: Number of metrics to skip for pagination (default 0).
    """
    client = get_client()
    limit = min(limit, 100)
    page = (offset // limit) + 1

    filters: dict = {
        "variable": {"segmentation": {"code": {"$eq": segmentation_code}}},
    }

    if segment_code:
        filters["segment"] = {"code": {"$eq": segment_code}}
    else:
        filters["segment"] = {"$null": "true"}

    if theme_code:
        filters["variable"]["themes"] = {"code": {"$eq": theme_code}}

    if domain_code:
        filters["variable"]["domain"] = {"code": {"$eq": domain_code}}

    if variable_codes:
        filters["variable"]["code"] = {"$in": variable_codes}

    result = await client.fetch_collection(
        "metrics",
        filters=filters,
        populate=["variable", "categorical_level"],
        page=page,
        page_size=limit,
    )

    pagination = result.get("meta", {}).get("pagination", {})
    metrics = []
    for m in result.get("data", []):
        var = m.get("variable") or {}
        cat_level = m.get("categorical_level")

        entry: dict = {
            "variable_code": var.get("code"),
            "variable_name": var.get("name_en"),
            "data_type": var.get("data_type"),
        }

        if var.get("data_type") in ("categorical", "binary"):
            entry["percentage"] = m.get("percentage")
            entry["percentage_se"] = m.get("percentage_se")
            if cat_level:
                entry["categorical_level"] = cat_level.get("name_en")
        else:
            entry["avg"] = m.get("avg")
            entry["avg_se"] = m.get("avg_se")
            entry["median"] = m.get("median")
            entry["min"] = m.get("min")
            entry["max"] = m.get("max")

        metrics.append(entry)

    output = {
        "level": "sample_total" if not segment_code else "segment",
        "segment_code": segment_code,
        "metrics": metrics,
        "pagination": {
            "total": pagination.get("total", 0),
            "page": pagination.get("page", 1),
            "page_size": pagination.get("pageSize", limit),
            "page_count": pagination.get("pageCount", 1),
        },
    }

    return format_response(output)


