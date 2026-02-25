"""Strapi API client for Pathways CMS."""

import json
import os
from typing import Any

import httpx

# Maximum number of characters allowed in a tool response.
# 100,000 characters ≈ 25,000 tokens, should be well within the LLM context window.
RESPONSE_CHAR_LIMIT = 150_000


def format_response(data: Any, limit: int = RESPONSE_CHAR_LIMIT) -> str:
    """Serialize data to JSON, always returning a valid JSON string.

    Strategy:
    1. Try pretty-printed (indent=2) — readable and under limit → return it.
    2. Try compact (no indent) — saves ~30-40% chars → return if under limit.
    3. If still over limit, return a valid JSON error object rather than a
       truncated string, which would produce malformed JSON.
    """
    pretty = json.dumps(data, indent=2)
    if len(pretty) <= limit:
        return pretty

    compact = json.dumps(data)
    if len(compact) <= limit:
        return compact

    return json.dumps({
        "error": "response_too_large",
        "message": (
            f"The response ({len(compact):,} chars) exceeds the {limit:,} char limit. "
            "Use filters, pagination, or a more specific query to reduce the result size."
        ),
    })


class StrapiClient:
    """Async HTTP client for the Pathways Strapi CMS API."""

    def __init__(self) -> None:
        token = os.environ.get("PATHWAYS_API_TOKEN")
        if not token:
            raise RuntimeError(
                "PATHWAYS_API_TOKEN environment variable is required. "
                "Get a read-only API token from the Pathways Strapi admin."
            )
        base_url = os.environ.get("PATHWAYS_API_URL")
        if not base_url:
            raise RuntimeError(
                "PATHWAYS_API_URL environment variable is required. "
                "Set it to the base URL of the Pathways Strapi API."
            )
        self._base_url = base_url.rstrip("/") + "/api"
        self._headers = {"Authorization": f"Bearer {token}"}

    def _build_params(
        self,
        *,
        filters: dict[str, Any] | None = None,
        populate: list[str] | str | None = None,
        fields: list[str] | None = None,
        page: int = 1,
        page_size: int = 25,
        sort: str | None = None,
    ) -> dict[str, str]:
        """Build Strapi v5 query-string parameters.

        Filters use bracket syntax: filters[field][$op]=value
        Populate uses indexed syntax: populate[0]=rel1&populate[1]=rel2
        Fields use indexed syntax: fields[0]=code&fields[1]=name_en
        """
        params: dict[str, str] = {
            "pagination[page]": str(page),
            "pagination[pageSize]": str(page_size),
            "status": "published",
        }

        if filters:
            self._flatten_filters(filters, "filters", params)

        if populate:
            if isinstance(populate, str):
                params["populate"] = populate
            else:
                for i, rel in enumerate(populate):
                    params[f"populate[{i}]"] = rel

        if fields:
            for i, field in enumerate(fields):
                params[f"fields[{i}]"] = field

        if sort:
            params["sort"] = sort

        return params

    def _flatten_filters(
        self, obj: dict[str, Any], prefix: str, out: dict[str, str]
    ) -> None:
        """Recursively flatten nested filter dicts into bracket notation."""
        for key, value in obj.items():
            full_key = f"{prefix}[{key}]"
            if isinstance(value, dict):
                self._flatten_filters(value, full_key, out)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    out[f"{full_key}[{i}]"] = str(item)
            else:
                out[full_key] = str(value)

    async def fetch_collection(
        self,
        endpoint: str,
        *,
        filters: dict[str, Any] | None = None,
        populate: list[str] | str | None = None,
        fields: list[str] | None = None,
        page: int = 1,
        page_size: int = 25,
        sort: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a single page from a Strapi collection endpoint.

        Returns the full Strapi response with 'data' and 'meta' keys.
        """
        params = self._build_params(
            filters=filters,
            populate=populate,
            fields=fields,
            page=page,
            page_size=page_size,
            sort=sort,
        )
        url = f"{self._base_url}/{endpoint.lstrip('/')}"

        async with httpx.AsyncClient(headers=self._headers, timeout=30.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 403:
                raise RuntimeError(
                    f"Access denied to {endpoint}. Check your PATHWAYS_API_TOKEN."
                )
            if resp.status_code == 404:
                raise RuntimeError(f"Endpoint '{endpoint}' not found on the Strapi API.")
            resp.raise_for_status()
            return resp.json()

    async def fetch_all(
        self,
        endpoint: str,
        *,
        filters: dict[str, Any] | None = None,
        populate: list[str] | str | None = None,
        fields: list[str] | None = None,
        page_size: int = 100,
        max_records: int = 5000,
        sort: str | None = None,
    ) -> list[dict[str, Any]]:
        """Auto-paginate to fetch all records from a collection.

        Stops at max_records to prevent runaway fetches.
        """
        all_data: list[dict[str, Any]] = []
        page = 1

        while True:
            result = await self.fetch_collection(
                endpoint,
                filters=filters,
                populate=populate,
                fields=fields,
                page=page,
                page_size=page_size,
                sort=sort,
            )
            data = result.get("data", [])
            all_data.extend(data)

            pagination = result.get("meta", {}).get("pagination", {})
            total = pagination.get("total", 0)
            page_count = pagination.get("pageCount", 1)

            if page >= page_count or len(all_data) >= min(total, max_records):
                break
            page += 1

        return all_data[:max_records]


# Module-level singleton for lazy initialization
_client: StrapiClient | None = None


def get_client() -> StrapiClient:
    """Get or create the module-level StrapiClient singleton."""
    global _client
    if _client is None:
        _client = StrapiClient()
    return _client
