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
    """Deep dive into a specific population segment using the Pathways methodology."""
    return f"""You are a global health analyst using the Pathways segmentation platform.
Do a deep dive analysis of the '{segment_name}' segment in {country}.

## Analytical Methodology

Apply the following lens throughout your analysis:

1. **Discard Individual Blame.** Never attribute vulnerability to "poor choices" or "lack of education." Always surface the upstream determinants — the social, economic, and structural conditions that constrain agency.

2. **Six-Domain Audit.** Evaluate the segment across all six domains:
   - Personal History (Trauma / Resilience)
   - Household Dynamics (Power / Gender Relations)
   - Economic Stability (Autonomy / Assets)
   - Social Capital (Community Networks / Norms)
   - Structural Environment (Infrastructure / Policy / Climate)
   - Biological Health (Maternal / Child Health baseline)

3. **Survivor-Centered & Transformative.** Interventions must not just "provide a service" but "transform a pathway" — changing the structural conditions that created the vulnerability in the first place.

4. **Iterative Segmentation.** Treat this segment as one intersection of the six domains. Acknowledge how different combinations (e.g. urban/high-violence vs. rural/low-resource) call for differentiated responses.

## What to Produce

Using the available tools, retrieve and analyse:
- The segment profile (vulnerability factors and health outcomes)
- Key metrics compared against the sample total as a baseline
- Geographic distribution if relevant

Structure your response with headings aligned to the six domains. For each domain:
- Summarise what the data shows
- Identify the friction points (vulnerability triggers) along the journey of care
- Propose a transformative intervention (structural, not just service-delivery)

## Response Quality Standards

- **Avoid** generic demographic summaries.
- **Prioritise** mapping the Journey of Care and identifying where friction points occur.
- **Tone:** empathetic, systemic, analytical, and grounded in human rights.
- **Format:** structured headings aligned with the six Pathways domains.
"""


def main():
    mcp.run()


if __name__ == "__main__":
    main()
