"""Tools for searching and filtering variables (indicators)."""

from pathways_mcp.api import format_response, get_client

#TODO: Maybe this function  should be in metrics.py? 
async def search_variables(
    segmentation_code: str,
    search: str | None = None,
    theme_code: str | None = None,
    domain_code: str | None = None,
    data_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    """Search and filter variables (indicators) for a segmentation.

    Variables are quantitative indicators measured in a segmentation study.
    They can be health outcomes (e.g., "No current modern FP use") or
    vulnerability factors (e.g., "Education level").

    Args:
        segmentation_code: Segmentation code (e.g., "SEN_2019DHS8_v1").
        search: Optional text search on variable name (case-insensitive), 
        If no search term is provided, all active variables will be returned that match the other filters.
        theme_code: Optional theme code to filter by health theme
            (e.g., "sexual_and_reproductive_health"). Use
            list_themes_and_domains for available codes.
        domain_code: Optional domain code to filter by vulnerability domain
            (e.g., "household_economics_and_living_conditions").
        data_type: Optional data type filter: "binary", "categorical",
            "integer", or "continuous".
        limit: Max results to return (default 50, max 100).
        offset: Number of results to skip for pagination.
    """
    client = get_client()
    limit = min(limit, 100)
    page = (offset // limit) + 1

    filters: dict = {
        "segmentation": {"code": {"$eq": segmentation_code}},
        "active": {"$eq": "true"},
    }

    if search:
        filters["name_en"] = {"$containsi": search}
    if theme_code:
        filters["themes"] = {"code": {"$eq": theme_code}}
    if domain_code:
        filters["domain"] = {"code": {"$eq": domain_code}}
    if data_type:
        filters["data_type"] = {"$eq": data_type}

    result = await client.fetch_collection(
        "variables",
        filters=filters,
        populate=["themes", "domain", "variable_type"],
        page=page,
        page_size=limit,
        sort="order:asc",
    )

    pagination = result.get("meta", {}).get("pagination", {})
    variables = []
    for v in result.get("data", []):
        themes = [
            {"code": t.get("code"), "name": t.get("name_en")}
            for t in (v.get("themes") or [])
        ]
        domain = v.get("domain")
        var_type = v.get("variable_type")

        variables.append({
            "code": v.get("code"),
            "name": v.get("name_en"),
            "description": v.get("description_en"),
            "data_type": v.get("data_type"),
            "variable_type": var_type.get("name_en") if var_type else None,
            "themes": themes if themes else None,
            "domain": domain.get("name_en") if domain else None,
            "domain_code": domain.get("code") if domain else None,
        })

    output = {
        "variables": variables,
        "pagination": {
            "total": pagination.get("total", 0),
            "page": pagination.get("page", 1),
            "page_size": pagination.get("pageSize", limit),
            "page_count": pagination.get("pageCount", 1),
        },
    }

    return format_response(output)
