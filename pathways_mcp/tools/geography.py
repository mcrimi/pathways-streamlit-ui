"""Tools for geographic distribution of segments across regions."""

from pathways_mcp.api import format_response, get_client


async def get_geographic_distribution(
    segmentation_code: str,
    segment_code: str | None = None,
    region_code: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    """Get the geographic distribution of population segments across regions.

    Each record shows what percentage of a region's population belongs to
    a given segment. Use this to answer questions like:
    - "Which regions have the highest concentration of the most vulnerable segment?"
    - "How are the segments distributed across Dakar?"
    - "Where is segment R2 most prevalent?"

    Supply only segmentation_code to get the full distribution matrix.
    Filter by segment_code to rank regions for a specific segment.
    Filter by region_code to see the segment breakdown within one region.
    Both filters can be combined.

    Results are sorted by percentage descending (highest concentration first).

    Args:
        segmentation_code: Segmentation code (e.g., "SEN_2019DHS8_v1").
        segment_code: Optional segment code to filter by (e.g., "R4").
            Use list_segments to find available codes.
        region_code: Optional region code to filter by (e.g., "dakar").
            Use list_regions to find available codes.
        limit: Max records to return per page (default 50, max 100).
        offset: Number of records to skip for pagination (default 0).
    """
    client = get_client()
    limit = min(limit, 100)
    page = (offset // limit) + 1

    filters: dict = {
        "segment": {
            "segmentation": {"code": {"$eq": segmentation_code}},
            "active": {"$eq": "true"},
        },
    }

    if segment_code:
        filters["segment"]["code"] = {"$eq": segment_code}

    if region_code:
        filters["region"] = {"code": {"$eq": region_code}}

    result = await client.fetch_collection(
        "geographic-distributions",
        filters=filters,
        populate=["segment", "region"],
        page=page,
        page_size=limit,
        sort="percentage:desc",
    )

    pagination_meta = result.get("meta", {}).get("pagination", {})
    total = pagination_meta.get("total", 0)

    distributions = []
    for item in result.get("data", []):
        seg = item.get("segment") or {}
        region = item.get("region") or {}

        distributions.append({
            "segment_code": seg.get("code"),
            "segment_label": seg.get("label"),
            "vulnerability_level": seg.get("vulnerability_level"),
            "stratum": seg.get("stratum"),
            "region_code": region.get("code"),
            "region_name": region.get("name_en"),
            "percentage": item.get("percentage"),
        })

    output = {
        "distributions": distributions,
        "pagination": {
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": (offset + limit) < total,
        },
    }

    return format_response(output)
