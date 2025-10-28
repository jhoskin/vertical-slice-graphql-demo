"""
Lightweight GraphQL client utility.

This module provides a simple GraphQL client built on httpx with intelligent
error classification for retry logic. The client is stateless and can be used
standalone or wrapped with retry mechanisms (e.g., Restate's ctx.run()).
"""
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


def get_api_url() -> str:
    """
    Get the API URL from environment configuration.

    This centralizes API URL configuration so it doesn't need to be
    passed around or logged in application/workflow code.

    Returns:
        The configured API URL
    """
    return os.getenv("API_URL", "http://localhost:8000")


class GraphQLError(Exception):
    """Base exception for GraphQL client errors."""
    pass


class GraphQLTerminalError(GraphQLError):
    """
    Terminal error that should not be retried.

    Raised for client errors (4xx except 408, 429) where retry won't help.
    Examples: 400 (bad request), 401 (unauthorized), 403 (forbidden),
    404 (not found), 422 (validation error).
    """
    pass


class GraphQLTransientError(GraphQLError):
    """
    Transient error that can be retried.

    Raised for network errors, server errors (5xx), timeouts (408),
    and rate limits (429) where retry may succeed.
    """
    pass


async def execute_graphql_mutation(
    mutation: str,
    variables: Dict[str, Any],
    api_url: str,
    timeout: float = 30.0,
    log_prefix: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a GraphQL mutation via HTTP POST.

    This is a stateless function that performs a GraphQL mutation and classifies
    errors as terminal (shouldn't retry) or transient (can retry). Callers can
    wrap this with their own retry logic (e.g., Restate's ctx.run()).

    Args:
        mutation: GraphQL mutation string
        variables: Variables for the mutation
        api_url: Base API URL (e.g., "http://localhost:8000")
        timeout: Request timeout in seconds (default: 30.0)
        log_prefix: Optional prefix for log messages (e.g., "[WORKFLOW 123]")

    Returns:
        The parsed JSON response from the GraphQL API

    Raises:
        GraphQLTerminalError: For client errors that should not be retried
            (400, 401, 403, 404, 422, GraphQL validation errors)
        GraphQLTransientError: For transient errors that may succeed on retry
            (network errors, 5xx, 408, 429)

    Example:
        # Standalone usage
        result = await execute_graphql_mutation(
            "mutation CreateTrial($input: CreateTrialInput!) { createTrial(input: $input) { id } }",
            {"input": {"name": "My Trial", "phase": "Phase I"}},
            "http://localhost:8000"
        )
        trial_id = result["data"]["createTrial"]["id"]

        # With Restate retry logic
        result = await ctx.run(
            "create_trial",
            lambda: execute_graphql_mutation(mutation, variables, api_url, log_prefix=f"[WORKFLOW {ctx.key()}]")
        )
    """
    prefix = log_prefix or "[GraphQL]"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            url = f"{api_url}/graphql"
            payload = {
                "query": mutation,
                "variables": variables,
            }

            logger.info(f"{prefix} GraphQL request to {url}")
            response = await client.post(url, json=payload)

            # Check for HTTP errors
            if response.status_code >= 400:
                error_msg = f"HTTP {response.status_code}: {response.text}"

                # Terminal errors (don't retry)
                if response.status_code in (400, 401, 403, 404, 422):
                    logger.error(f"{prefix} Terminal error: {error_msg}")
                    raise GraphQLTerminalError(error_msg)

                # Transient errors (can retry)
                # 408 = Request Timeout, 429 = Too Many Requests, 5xx = Server errors
                if response.status_code in (408, 429) or response.status_code >= 500:
                    logger.warning(f"{prefix} Transient error: {error_msg}")
                    raise GraphQLTransientError(error_msg)

                # Other 4xx errors - treat as terminal
                logger.error(f"{prefix} Terminal error: {error_msg}")
                raise GraphQLTerminalError(error_msg)

            # Parse response
            data = response.json()

            # Check for GraphQL errors in response
            if "errors" in data:
                error_msg = f"GraphQL errors: {data['errors']}"
                logger.error(f"{prefix} {error_msg}")
                # Treat GraphQL errors as terminal (validation/logic errors)
                raise GraphQLTerminalError(error_msg)

            logger.info(f"{prefix} GraphQL request successful")
            return data

    except httpx.RequestError as e:
        # Network errors are transient
        error_msg = f"Network error: {str(e)}"
        logger.warning(f"{prefix} {error_msg}")
        raise GraphQLTransientError(error_msg) from e
    except (GraphQLTerminalError, GraphQLTransientError):
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        # Unknown errors - treat as terminal to avoid infinite retries
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"{prefix} {error_msg}")
        raise GraphQLTerminalError(error_msg) from e
