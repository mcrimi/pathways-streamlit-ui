"""Tools for exploring Pathways segmentations (country studies)."""

from pathways_mcp.api import format_response, get_client


async def list_segmentations() -> str:
    """List all available Pathways segmentations (country-level studies).

    Each segmentation represents a population segmentation study for a specific
    country, based on survey data (e.g., DHS). Use this to discover which
    countries and studies are available. Only returns active, published
    segmentations.
    """
    client = get_client()
    filters: dict = {"active": {"$eq": "true"}}

    result = await client.fetch_collection(
        "segmentations",
        filters=filters,
        populate="geography",
        page_size=100,
    )

    segmentations = []
    for item in result.get("data", []):
        geo = item.get("geography") or {}
        segmentations.append({
            "code": item.get("code"),
            "description": item.get("description_en"),
            "country": geo.get("name_en"),
            "country_code": geo.get("country_code"),
            "source": item.get("source_en"),
            "population_size": item.get("population_size"),
            "sample_size": item.get("sample_size"),
            "active": item.get("active"),
        })

    return format_response(segmentations)


async def get_segmentation(code: str) -> str:
    """Get full details of a segmentation including all its segments.

    Returns segmentation metadata (country, source, methodology) plus
    a list of all population segments with their vulnerability levels
    and prevalence.

    Args:
        code: Segmentation code (e.g., "SEN_2019DHS8_v1"). Use
              list_segmentations to find available codes.
    """
    client = get_client()

    # Fetch the segmentation
    seg_result = await client.fetch_collection(
        "segmentations",
        filters={"code": {"$eq": code}},
        populate="geography",
    )
    seg_data = seg_result.get("data", [])
    if not seg_data:
        return format_response({"error": f"Segmentation '{code}' not found."})

    seg = seg_data[0]
    geo = seg.get("geography") or {}

    # Fetch its segments (active only)
    segments_result = await client.fetch_collection(
        "segments",
        filters={
            "segmentation": {"code": {"$eq": code}},
            "active": {"$eq": "true"},
        },
        page_size=100,
        sort="code:asc",
    )

    segments = []
    for s in segments_result.get("data", []):
        segments.append({
            "code": s.get("code"),
            "label": s.get("label"),
            "stratum": s.get("stratum"),
            "vulnerability_level": s.get("vulnerability_level"),
            "prevalence": s.get("prevalence"),
            "sample_size": s.get("sample_size"),
            "active": s.get("active"),
        })

    output = {
        "code": seg.get("code"),
        "description": seg.get("description_en"),
        "country": geo.get("name_en"),
        "country_code": geo.get("country_code"),
        "source": seg.get("source_en"),
        "methodology": seg.get("methodology_en"),
        "population_size": seg.get("population_size"),
        "sample_size": seg.get("sample_size"),
        "geographic_coverage": seg.get("geographic_coverage_en"),
        "representativeness": seg.get("representativeness_en"),
        "active": seg.get("active"),
        "segments": segments,
    }

    return format_response(output)
