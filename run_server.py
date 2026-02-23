"""Entry point for the Pathways MCP server subprocess.

This script is invoked by the Streamlit app as a child process over stdio.
It adds the streamlit-ui directory to sys.path so the pathways_mcp package
can be imported without installation.
"""

import sys
from pathlib import Path

# Make sure pathways_mcp is importable from this directory
sys.path.insert(0, str(Path(__file__).parent))

from pathways_mcp.server import main  # noqa: E402

main()
