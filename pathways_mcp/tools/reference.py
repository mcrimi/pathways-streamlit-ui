"""Tools for reference data: themes, domains, and regions."""

from pathways_mcp.api import format_response, get_client


async def list_themes_and_domains() -> str:
    """List all health themes (Health Outcomes) and vulnerability domains (Vulnerability Factors).

    - **Themes** relate to **Health Outcomes**: measurable health results such as
      Maternal Health, Nutrition, or Sexual and Reproductive Health.
    - **Domains** describe sets of **Vulnerability Factors**: structural and social
      determinants that explain why a segment is vulnerable, such as Household
      Economics or Social Support.

    Use theme codes to filter health outcome metrics and domain codes to filter
    vulnerability factor metrics in get_segment_metrics.
    """
    client = get_client()

    themes_result = await client.fetch_collection(
        "themes", page_size=100, sort="order:asc"
    )
    domains_result = await client.fetch_collection(
        "domains", page_size=100, sort="order:asc"
    )

    themes = []
    for t in themes_result.get("data", []):
        entry: dict = {"code": t.get("code"), "name": t.get("name_en"), "order": t.get("order")}
        if t.get("description_en"):
            entry["description"] = t.get("description_en")
        themes.append(entry)

    domains = []
    for d in domains_result.get("data", []):
        entry = {"code": d.get("code"), "name": d.get("name_en"), "order": d.get("order")}
        if d.get("description_en"):
            entry["description"] = d.get("description_en")
        domains.append(entry)

    output = {
        "themes": {
            "description": "Health Outcomes — measurable health results. Use theme codes to filter health outcome metrics.",
            "items": themes,
        },
        "domains": {
            "description": "Vulnerability Factors — structural and social determinants of vulnerability. Use domain codes to filter vulnerability factor metrics.",
            "items": domains,
        },
    }
    return format_response(output)


async def list_regions(segmentation_code: str) -> str:
    """List sub-national regions for a segmentation's country.

    Regions are administrative areas within a country. The geometry
    (GeoJSON) is excluded to keep the response small.

    Args:
        segmentation_code: Segmentation code (e.g., "SEN_2019DHS8_v1").
            The regions returned are for the country associated with
            this segmentation.
    """
    client = get_client()

    # First, get the geography code for this segmentation
    seg_result = await client.fetch_collection(
        "segmentations",
        filters={"code": {"$eq": segmentation_code}},
        populate="geography",
    )
    seg_data = seg_result.get("data", [])
    if not seg_data:
        return format_response({"error": f"Segmentation '{segmentation_code}' not found."})

    geo = seg_data[0].get("geography") or {}
    geo_code = geo.get("code")
    if not geo_code:
        return format_response({"error": "Segmentation has no associated geography."})

    # Fetch active regions for this geography, excluding geometry
    regions_data = await client.fetch_all(
        "regions",
        filters={
            "geography": {"code": {"$eq": geo_code}},
            "active": {"$eq": "true"},
        },
        fields=["code", "name_en", "name_fr", "active"],
        page_size=100,
    )

    regions = [
        {
            "code": r.get("code"),
            "name": r.get("name_en"),
            "active": r.get("active"),
        }
        for r in regions_data
    ]

    output = {
        "segmentation": segmentation_code,
        "country": geo.get("name_en"),
        "country_code": geo_code,
        "regions": regions,
    }

    return format_response(output)
