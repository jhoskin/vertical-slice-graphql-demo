"""
Main application entry point.

This sets up FastAPI with Strawberry GraphQL and initializes the database.
Also mounts the Restate workflow endpoint for durable execution.
"""
import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from app.infrastructure.api.schema import schema
from app.infrastructure.database.session import init_db
from app.usecases.workflows.onboard_trial_async.webhook import router as webhook_router

# Import Restate endpoint
from app.usecases.workflows.onboard_trial_async.restate_workflow import (
    onboard_trial_workflow,
)
from app.usecases.commands.trial_management.update_trial_metadata_via_vo.virtual_object import trial_virtual_object
from restate.endpoint import Endpoint

logger = logging.getLogger(__name__)


async def register_with_restate():
    """
    Auto-register this service with Restate on startup.

    This eliminates the need for manual CLI registration.
    Only attempts registration if RESTATE_ADMIN_URL is set.
    """
    import asyncio

    restate_url = os.getenv("RESTATE_ADMIN_URL", "http://localhost:9070")
    service_url = os.getenv("SERVICE_URL", "http://host.docker.internal:8000/restate")

    # Check if Restate is running
    try:
        async with httpx.AsyncClient() as client:
            health_response = await client.get(f"{restate_url}/health", timeout=2.0)
            if health_response.status_code != 200:
                logger.warning("Restate not available, skipping auto-registration")
                return
    except Exception as e:
        logger.info(f"Restate not available ({e}), skipping auto-registration")
        return

    # Wait a moment for server to be fully ready
    await asyncio.sleep(1)

    # Register deployment with retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{restate_url}/deployments",
                    json={"uri": service_url, "force": True},
                    timeout=10.0
                )

                if response.status_code in (200, 201):
                    logger.info(f"✓ Registered with Restate at {restate_url}")
                    # Log registered services
                    data = response.json()
                    if "services" in data:
                        for service in data["services"]:
                            logger.info(f"  - {service.get('name', 'Unknown')}")
                    return
                else:
                    logger.warning(f"Failed to register with Restate: {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
        except Exception as e:
            if attempt < max_retries - 1:
                logger.info(f"Registration attempt {attempt + 1} failed, retrying...")
                await asyncio.sleep(2)
            else:
                logger.warning(f"Could not register with Restate after {max_retries} attempts: {e}")


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """
    Lifespan context manager for application startup/shutdown.

    Initializes database and registers with Restate on startup.
    """
    # Startup: Initialize database
    init_db()
    print("✓ Database initialized")

    # Auto-register with Restate if available
    await register_with_restate()

    yield

    # Shutdown: cleanup if needed
    print("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Clinical Metadata Demo API",
    description="Vertical slice architecture demo with GraphQL",
    version="1.0.0",
    lifespan=lifespan,
)

# Create GraphQL router
graphql_app = GraphQLRouter(schema)

# Mount GraphQL endpoint
app.include_router(graphql_app, prefix="/graphql")

# Mount webhook endpoint for Restate workflow callbacks
app.include_router(webhook_router)

# Create and mount Restate endpoint
restate_endpoint = Endpoint()
restate_endpoint.bind(onboard_trial_workflow)
restate_endpoint.bind(trial_virtual_object)
app.mount("/restate", restate_endpoint.app())


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "Clinical Metadata Demo API",
        "graphql": "/graphql",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
