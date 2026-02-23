"""Tools for qualitative content: case studies."""

import json

from pathways_mcp.api import RESPONSE_CHAR_LIMIT, get_client


def _blocks_to_text(blocks: list[dict] | None) -> str | None:
    """Convert Strapi rich text blocks to plain text."""
    if not blocks:
        return None
    parts = []
    for block in blocks:
        if block.get("type") == "paragraph":
            children = block.get("children", [])
            text = "".join(c.get("text", "") for c in children)
            parts.append(text)
        elif block.get("type") == "heading":
            children = block.get("children", [])
            text = "".join(c.get("text", "") for c in children)
            level = block.get("level", 2)
            parts.append(f"{'#' * level} {text}")
        elif block.get("type") == "list":
            for item in block.get("children", []):
                children = item.get("children", [])
                for child in children:
                    if child.get("type") == "paragraph":
                        text = "".join(
                            c.get("text", "") for c in child.get("children", [])
                        )
                        parts.append(f"- {text}")
    return "\n\n".join(parts) if parts else None


async def get_case_studies(slug: str | None = None) -> str:
    """Get qualitative case study content from Pathways.

    Case studies provide real-world examples and narratives about how
    Pathways segmentation data has been applied. If no slug is given,
    lists all available case studies.

    Args:
        slug: Optional case study slug. If omitted, returns a list of
            all available case studies with titles and slugs.
    """
    client = get_client()

    if slug:
        result = await client.fetch_collection(
            "case-studies",
            filters={"slug": {"$eq": slug}},
        )
        data = result.get("data", [])
        if not data:
            return json.dumps({"error": f"Case study '{slug}' not found."})

        cs = data[0]
        output = {
            "title": cs.get("title"),
            "slug": cs.get("slug"),
            "authors": cs.get("authors"),
            "publication_date": cs.get("publication_date"),
            "headline": cs.get("headline"),
            "content": _blocks_to_text(cs.get("content")),
            "location": cs.get("location"),
        }
    else:
        result = await client.fetch_collection("case-studies", page_size=100)
        case_studies = []
        for cs in result.get("data", []):
            case_studies.append({
                "title": cs.get("title"),
                "slug": cs.get("slug"),
                "authors": cs.get("authors"),
                "publication_date": cs.get("publication_date"),
                "headline": cs.get("headline"),
            })
        output = {"case_studies": case_studies}

    return json.dumps(output, indent=2)[:RESPONSE_CHAR_LIMIT]
