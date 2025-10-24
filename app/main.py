"""
Main application entry point.

This sets up FastAPI with Strawberry GraphQL and initializes the database.
Also mounts the Restate workflow endpoint for durable execution.
"""
from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for application startup/shutdown.

    Initializes database on startup.
    """
    # Startup: Initialize database
    init_db()
    print("✓ Database initialized")

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
