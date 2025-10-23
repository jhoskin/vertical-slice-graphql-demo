"""
Restate service endpoint.

This serves the Restate workflow service via ASGI.
It should run on a separate port from the main FastAPI app.
"""
from restate import Endpoint

from app.usecases.workflows.onboard_trial_async.restate_workflow import (
    onboard_trial_workflow,
)

# Create Restate endpoint
endpoint = Endpoint()

# Bind workflow service
endpoint.bind(onboard_trial_workflow)

# Export the ASGI app
app = endpoint.app()

if __name__ == "__main__":
    import uvicorn

    # Run Restate service on port 9080
    # Restate runtime will connect to this endpoint
    uvicorn.run(app, host="0.0.0.0", port=9080)
