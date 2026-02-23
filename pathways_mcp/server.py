"""Pathways MCP Server — exposes the Pathways health segmentation platform via MCP tools."""

from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from pathways_mcp.tools.segmentations import list_segmentations, get_segmentation
from pathways_mcp.tools.segments import list_segments, get_segment_profile
from pathways_mcp.tools.metrics import get_segment_metrics
from pathways_mcp.tools.variables import search_variables
from pathways_mcp.tools.reference import list_themes_and_domains, list_regions
from pathways_mcp.tools.geography import get_geographic_distribution

# Load .env from project root if present
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

mcp = FastMCP(
    "pathways",
    instructions=(
        "Pathways is a health segmentation platform providing woman-centered data "
        "and insights for global health. Use these tools to explore country-level "
        "segmentations, understand population segments and their vulnerability profiles, "
        "query health outcome metrics (linked to Themes), and vulnerability factor metrics "
        "(linked to Domains). Start with list_segmentations to discover available countries, "
        "then drill into segments and metrics."
    ),
)

# Register all tools
mcp.tool()(list_segmentations)
mcp.tool()(get_segmentation)
mcp.tool()(list_segments)
mcp.tool()(get_segment_profile)
mcp.tool()(get_segment_metrics)
mcp.tool()(search_variables)
mcp.tool()(list_themes_and_domains)
mcp.tool()(list_regions)
mcp.tool()(get_geographic_distribution)


@mcp.prompt()
def segment_deep_dive(segment_name: str, country: str) -> str:
    """Deep dive into a specific population segment."""
    return (
        f"Do a deep dive analysis of the '{segment_name}' segment in {country}. "
        f"Include their demographic profile, vulnerability factors (linked to Domains), "
        f"health outcomes (linked to Themes), and programmatic recommendations. "
        f"Compare their key metrics against the national average where possible."
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
