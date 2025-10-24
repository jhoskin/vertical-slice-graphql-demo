# PRD: Clinical Metadata Demo API (Lightweight + Vertical Slice + CQS)

## Goal
Demonstrate vertical slice architecture in Python with **Command–Query Separation (CQS)**. Show backend organized by **use cases** (not entities), using:
- SQLite + SQLAlchemy ORM
- Strawberry GraphQL (one resolver per use case)
- UV for package management
- Audit logging
- Lightweight principles from Toeggel’s “Lightweight with vertical slices”
- Unit and integration tests

## Principles
- Shape slices around **actual user-facing use cases**, not entities or layers.
- **One slice = one purpose**. High cohesion inside the slice, low coupling between slices.
- Keep shared code **minimal** (DB session, audit helper).
- CQS: **Commands mutate**, **Queries read**. No CQRS/event sourcing.
- Prefer simple, explicit code over abstraction. Accept small duplication.


## Data Model (SQLite, ORM)
- `trials(id, name, phase, status, created_at)`
- `sites(id, name, country)`
- `trial_sites(trial_id, site_id, status, UNIQUE(trial_id, site_id))`
- `protocol_versions(id, trial_id, version, notes, created_at)`
- `audit_logs(id, user, action, entity, entity_id, payload_json, created_at)`

## Use Cases

### Commands
1) **create_trial**
- In: `{ name, phase }`
- Behavior: insert `trials(status='draft')`; write audit.
- Out: `{ id, name, phase, status }`
- **Demonstrates**: CQS command pattern with automatic audit logging via decorator. Shows how commands encapsulate mutations with side effects (audit trail).

2) **register_site_to_trial** (multi-table transaction)
- In: `{ trial_id, site_name, country }`
- Behavior: upsert `sites`; insert `trial_sites(status='pending')`; single transaction; write one audit record.
- Out: `{ trial_id, site_id, link_status }`
- **Demonstrates**: Multi-table atomic transactions with upsert semantics. Shows how a single command can coordinate operations across multiple entities while maintaining ACID properties.

3) **update_trial_metadata**
- In: `{ trial_id, name?, phase? }`
- Behavior: update `trials`; compute diff; audit.
- Out: updated trial.
- **Demonstrates**: Partial updates with validation and change tracking. Phase transitions validated against business rules, changes logged to audit trail.

### Queries
4) **get_trial**
- In: `{ id }`
- Out: trial core fields, sites, latest protocol (read-optimized SQL).
- **Demonstrates**: Read-optimized query with eager loading. Uses SQLAlchemy relationships to efficiently fetch related data in single query, avoiding N+1 problems.

5) **list_trials**
- In: `{ phase?, status?, search?, limit=20, offset=0 }`
- Out: `{ items: [TrialSummary], total }`
- **Demonstrates**: Filtering, pagination, and search patterns. Shows how to build composable query filters while maintaining clean separation between GraphQL and database layers.

6) **get_audit_log**
- In: `{ entity, entity_id, limit=50 }`
- Out: `[AuditEntry]`
- **Demonstrates**: Audit trail querying for compliance. Retrieves chronological history of changes to any entity, supporting regulatory requirements for clinical trials.

### Workflows
Two workflow patterns demonstrating different orchestration approaches:

7) **onboard_trial_sync** (Synchronous Saga)
- In: `{ name, phase, initial_protocol_version, sites: [{name, country}] }`
- Pattern: Fast-running, in-memory saga with compensation pattern
- Behavior: Blocks GraphQL request until complete. On failure, compensates (rolls back) all previous steps.
- Steps: create trial → add protocol → register sites sequentially
- No state persistence - pure in-memory compensation stack
- Returns: `{ success, trial_id, message, steps_completed }`
- **Demonstrates**: Traditional saga pattern with compensation. Shows how to coordinate multi-step business processes with rollback capability when steps fail. Good for fast, synchronous operations.

8) **start_onboard_trial_async** (Async Restate Workflow)
- In: `{ name, phase, initial_protocol_version, sites: [{name, country}] }`
- Pattern: Durable async workflow with GraphQL subscriptions for progress
- Behavior: Returns immediately with workflow ID. Execution happens durably via Restate.
- Progress: Subscribe via `workflowProgress(workflow_id)` for real-time updates
- Steps: create trial → add protocol → register sites (with synthetic delays for observation)
- Durable execution: Workflow state journaled by Restate, survives restarts
- Returns immediately: `{ workflow_id, message }`
- **Demonstrates**: Durable async execution with Restate Workflows. Workflow survives application restarts - if the process crashes mid-execution, Restate automatically resumes from last completed step. Progress updates via GraphQL subscriptions provide real-time visibility.

### Concurrency Control
9) **update_trial_metadata_via_vo** (Virtual Object for Concurrency)
- In: `{ trial_id, name?, phase? }`
- Behavior: Routes update through Restate Virtual Object for automatic serialization; validates and persists to database.
- Out: updated trial (same as #3)
- **Demonstrates**: Restate Virtual Objects for concurrency protection. All concurrent updates to the same trial_id are automatically serialized by Restate, eliminating need for database-level locking (`SELECT FOR UPDATE`) or optimistic locking. Hybrid pattern: Virtual Object coordinates access, database persists state. Compare with #3 to see traditional vs Virtual Object approach.

## Folder Structure
```
app/
├── infrastructure/
│   ├── database/          # Database models, session, seed scripts
│   │   ├── models.py
│   │   ├── session.py
│   │   ├── seed.py
│   │   └── test_models.py
│   └── api/               # GraphQL schema composition
│       └── schema.py
├── core/                  # Cross-cutting utilities
│   ├── audit.py
│   └── test_audit.py
├── domain/                # Restate Virtual Objects and Services
│   ├── trial_virtual_object.py   # Virtual Object for trial concurrency
│   └── test_trial_virtual_object.py
├── usecases/
│   ├── commands/
│   │   ├── trial_management/     # Grouped commands with shared validation
│   │   │   ├── _validation.py   # Shared phase validation logic
│   │   │   ├── test_validation.py
│   │   │   ├── create_trial/
│   │   │   │   ├── handler.py
│   │   │   │   ├── types.py
│   │   │   │   ├── resolver.py
│   │   │   │   ├── test_handler.py
│   │   │   │   └── test_resolver.py
│   │   │   ├── update_trial_metadata/
│   │   │   │   ├── handler.py
│   │   │   │   ├── types.py
│   │   │   │   ├── resolver.py
│   │   │   │   ├── test_handler.py
│   │   │   │   └── test_resolver.py
│   │   │   └── update_trial_metadata_via_vo/   # Virtual Object variant
│   │   │       ├── handler.py
│   │   │       ├── types.py
│   │   │       ├── resolver.py
│   │   │       └── test_resolver.py
│   │   └── register_site_to_trial/
│   │       ├── handler.py
│   │       ├── types.py
│   │       ├── resolver.py
│   │       ├── test_handler.py
│   │       └── test_resolver.py
│   ├── queries/
│   │   ├── get_trial/
│   │   ├── list_trials/
│   │   └── get_audit_log/
│   └── workflows/
│       ├── onboard_trial_sync/      # Synchronous saga workflow
│       │   ├── handler.py           # Saga orchestration with compensation
│       │   ├── types.py
│       │   ├── resolver.py
│       │   ├── test_handler.py
│       │   └── test_resolver.py
│       └── onboard_trial_async/     # Async Restate workflow
│           ├── restate_workflow.py  # Restate workflow definition
│           ├── types.py
│           ├── resolver.py          # Mutation + subscription
│           ├── webhook.py           # Webhook for progress callbacks
│           ├── pubsub.py            # In-memory pub/sub for subscriptions
│           ├── test_resolver.py
│           ├── test_pubsub.py
│           └── test_webhook.py
├── e2e_tests/             # End-to-end integration tests (NOT unit tests)
│   ├── conftest.py
│   ├── test_trial_lifecycle.py
│   ├── test_site_registration.py
│   ├── test_sync_saga_workflow.py
│   ├── test_async_workflow_integration.py
│   ├── test_async_workflow_e2e.py  # Requires Restate running
│   ├── test_trial_virtual_object_e2e.py  # Virtual Object concurrency tests
│   └── test_audit_trail.py
└── main.py                # Main app with GraphQL + Restate endpoint
```

**Key Principles:**
- **Unit tests co-located**: Each module's tests live alongside it (e.g., `test_handler.py` next to `handler.py`)
- **Shared code in sensible parents**: `trial_management/_validation.py` demonstrates "things that change together, live together"
- **Infrastructure separation**: Database and API concerns isolated from business logic
- **E2E tests clearly separated**: Integration tests in dedicated `e2e_tests/` folder

## GraphQL Schema Design (Apollo Best Practices)

This schema follows [Apollo's naming conventions](https://www.apollographql.com/docs/graphos/schema-design/guides/naming-conventions):

### Casing Standards
- **Field names**: `camelCase` (queries, mutations, arguments)
- **Types**: `PascalCase` (objects, inputs, enums, interfaces)
- **Enum values**: `SCREAMING_SNAKE_CASE`

### Query Naming
- ❌ Avoid verb prefixes: `getProducts`, `listTrials`
- ✅ Use noun-based names: `products`, `trials`
- Examples: `trial(id: Int!)`, `trials(input: TrialsInput!)`

### Mutation Naming
- ✅ Begin with action verbs: `createTrial`, `updateTrialMetadata`
- Follow pattern: `{verb}{Noun}`

### Type Naming
- **Input types**: Use `Input` suffix (e.g., `CreateTrialInput`)
- **Response types**: Use `Response` suffix (e.g., `CreateTrialResponse`)
- **Domain types**: Use descriptive names without suffixes (e.g., `TrialDetail`, `SiteInfo`)

### Our Schema Conventions
- One resolver per use case (high cohesion)
- Explicit input/response types per operation (no entity leakage)
- Consistent verb usage: `create`, `update`, `register`, `start`

## GraphQL Design
- **One resolver per use case.** Commands as mutations. Queries as queries.
- Inputs: Strawberry `@input` mapped from each slice's DTO.
- Outputs: explicit per-slice types. Avoid leaking raw entities.
- Naming:
  - Mutations: `createTrial`, `registerSiteToTrial`, `updateTrialMetadata`, `startOnboarding`
  - Queries: `trial`, `trials`, `auditLog`, `onboardingStatus`
- Composition example:
```python
# app/infrastructure/api/schema.py
import strawberry
from app.usecases.commands.trial_management.create_trial.resolver import create_trial
from app.usecases.commands.register_site_to_trial.resolver import register_site_to_trial
from app.usecases.commands.trial_management.update_trial_metadata.resolver import update_trial_metadata
from app.usecases.queries.get_trial.resolver import trial
from app.usecases.queries.list_trials.resolver import trials
from app.usecases.queries.get_audit_log.resolver import audit_log
from app.usecases.workflows.onboard_trial.resolver import start_onboarding, onboarding_status

@strawberry.type
class Mutation:
    create_trial = create_trial
    register_site_to_trial = register_site_to_trial
    update_trial_metadata = update_trial_metadata
    start_onboarding = start_onboarding

@strawberry.type
class Query:
    trial = trial
    trials = trials
    audit_log = audit_log
    onboarding_status = onboarding_status

schema = strawberry.Schema(query=Query, mutation=Mutation)
```

## Example GraphQL Queries

### Query a single trial
```graphql
query GetTrial($id: Int!) {
  trial(id: $id) {
    id
    name
    phase
    status
    sites {
      name
      country
      linkStatus
    }
    latestProtocol {
      version
      notes
    }
  }
}
```

### List trials with filters
```graphql
query ListTrials($input: ListTrialsInput!) {
  trials(input: $input) {
    total
    items {
      id
      name
      phase
      status
      siteCount
      createdAt
    }
  }
}
```

Variables:
```json
{
  "input": {
    "phase": "Phase II",
    "limit": 10,
    "offset": 0
  }
}
```

### Create a trial
```graphql
mutation CreateTrial($input: CreateTrialInput!) {
  createTrial(input: $input) {
    id
    name
    phase
    status
    createdAt
  }
}
```

Variables:
```json
{
  "input": {
    "name": "New Trial",
    "phase": "Phase I"
  }
}
```

### Register a site to a trial
```graphql
mutation RegisterSite($input: RegisterSiteToTrialInput!) {
  registerSiteToTrial(input: $input) {
    siteId
    siteName
    country
    trialId
    linkStatus
  }
}
```

### Synchronous Saga Workflow
```graphql
mutation OnboardTrialSync($input: OnboardTrialSyncInput!) {
  onboardTrialSync(input: $input) {
    success
    trialId
    message
    stepsCompleted
  }
}
```

Variables:
```json
{
  "input": {
    "name": "New Trial",
    "phase": "Phase I",
    "initialProtocolVersion": "v1.0",
    "sites": [
      { "name": "Site A", "country": "USA" },
      { "name": "Site B", "country": "UK" }
    ]
  }
}
```

### Async Restate Workflow
```graphql
# Start workflow (returns immediately)
mutation StartAsync($input: OnboardTrialAsyncInput!) {
  startOnboardTrialAsync(input: $input) {
    workflowId
    message
  }
}

# Subscribe to progress updates
subscription WorkflowProgress($workflowId: String!) {
  workflowProgress(workflowId: $workflowId) {
    workflowId
    status
    message
    trialId
  }
}
```

### Update Trial via Virtual Object (Concurrency Protection)
```graphql
mutation UpdateTrialViaVO($input: UpdateTrialMetadataInput!) {
  updateTrialMetadataViaVo(input: $input) {
    id
    name
    phase
    status
    changes
    createdAt
  }
}
```

Variables:
```json
{
  "input": {
    "trialId": 1,
    "name": "Updated Trial Name",
    "phase": "Phase II"
  }
}
```

**Note**: This mutation uses Restate Virtual Objects for automatic concurrency protection. Multiple simultaneous updates to the same trial are serialized by Restate, preventing race conditions without database locks. Compare with regular `updateTrialMetadata` mutation to see the difference.

## Cross-Cutting
- **Audit**: `app/core/audit.py` provides `@audited(action, entity, id_fn)` to write to `audit_logs` on successful command; failures recorded with error info.
- **DB**: `app/infrastructure/database/session.py` exposes `SessionLocal()` context helper. Each handler opens and commits its own transaction.

## Tests

### Unit Tests
- **Location**: Co-located with each slice (e.g., `test_handler.py`, `test_resolver.py`)
- **Scope**: Test individual components in isolation
- **Database**: In-memory SQLite
- **Coverage**: Success paths, error handling, rollback, audit logging

### Integration Tests
- **Location**: `app/e2e_tests/test_async_workflow_integration.py`
- **Scope**: Test component interactions with mocked external dependencies
- **Examples**: Webhook → pub/sub → subscription flow (with mocked Restate)

### End-to-End Tests
- **Location**: `app/e2e_tests/`
- **Scope**: Full system tests through GraphQL API
- **Files**:
  - `test_trial_lifecycle.py` - Create → Get → Update roundtrip
  - `test_site_registration.py` - Site registration transactions
  - `test_sync_saga_workflow.py` - Synchronous saga with compensation
  - `test_audit_trail.py` - Audit trail verification
  - `test_async_workflow_e2e.py` - **Requires Restate running** (marked with `@pytest.mark.restate_e2e`)

### Running Tests

```bash
# Run all tests except Restate E2E (default)
pytest

# Or explicitly exclude Restate E2E tests
pytest -m "not restate_e2e"

# Run only Restate E2E tests (requires docker-compose up)
pytest -m restate_e2e

# Run with verbose output
pytest -v

# Run specific test file
pytest app/e2e_tests/test_sync_saga_workflow.py
```

**Note on Restate E2E Tests:**
- Require Restate runtime running via `docker-compose up`
- Test actual workflow execution through Restate
- Verify webhook callbacks and database state
- Automatically skipped if Restate is not running

### Restate Auto-Registration

The application automatically registers its services with Restate on startup. This eliminates the need for manual CLI registration.

**How it works:**
1. On startup, the app checks if Restate is available at `RESTATE_ADMIN_URL` (default: `http://localhost:9070`)
2. If Restate is running, it automatically registers the deployment at `SERVICE_URL` (default: `http://host.docker.internal:8000/restate`)
3. Registration uses HTTP/1.1 and retries up to 3 times with backoff
4. If Restate is not available, the app continues without error (graceful degradation)

**Configuration (optional):**
```bash
# Override Restate admin URL
export RESTATE_ADMIN_URL=http://localhost:9070

# Override service URL (useful in production)
export SERVICE_URL=http://myapp.example.com:8000/restate
```

**Manual registration (if needed):**
```bash
# Using Restate CLI (if auto-registration fails)
restate deployments register http://host.docker.internal:8000/restate --use-http1.1 --yes
```

The auto-registration feature ensures developers don't need to remember CLI commands - just start the API and Restate, and they'll connect automatically.

## Seed Data
- 3 trials across phases.
- 2 sites linked to a trial.
- 1 protocol version per trial.
- Several audit rows.

Run: `uv run python -m app.infrastructure.database.seed`

## Docker + Restate Setup

The async workflow requires Restate runtime for durable execution.

### Architecture
- **Single App Service**: Runs locally, hosts both GraphQL API and Restate workflow endpoint
- **Restate Container**: Official Restate Docker image for durable execution engine
- **SQLite Database**: Local file, managed by the app

### Quick Start

```bash
# Terminal 1: Start Restate container
docker-compose up

# Terminal 2: Start app (serves GraphQL + Restate workflows)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 3: Register workflow with Restate (one-time setup)
docker exec vertical-slice-graphql-demo-restate-1 \
  restate deployments register --yes --use-http1.1 \
  http://host.docker.internal:8000/restate
```

**Services:**
- Restate server: `http://localhost:8080` (workflow invocation)
- Restate admin: `http://localhost:9070` (management UI)
- GraphQL API: `http://localhost:8000/graphql`
- Restate endpoint: `http://localhost:8000/restate` (workflow service)

**Note**: The app serves both the GraphQL API and Restate workflow endpoints on the same port. Restate connects to the `/restate` path to discover and invoke workflows.

## UV + Runbook
```bash
# Install dependencies
uv sync

# Seed database
uv run python -m app.infrastructure.database.seed

# Run all tests (excluding Restate E2E)
pytest

# Run Restate E2E tests (requires docker-compose up)
pytest -m restate_e2e

# Serve locally (sync saga works, async workflow won't)
uv run uvicorn app.main:app --reload

# Serve with Restate for full async workflow support
# Terminal 1:
docker-compose up

# Terminal 2:
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 3 (one-time):
docker exec vertical-slice-graphql-demo-restate-1 \
  restate deployments register --yes --use-http1.1 \
  http://host.docker.internal:8000/restate
```

**Dependencies:**
- strawberry-graphql (GraphQL server)
- uvicorn (ASGI server)
- SQLAlchemy (ORM)
- pydantic (validation)
- restate-sdk (durable workflows)
- httpx (HTTP client for Restate)
- pytest (testing)
```

## Acceptance Criteria
- Folders grouped by **use cases** under `commands/`, `queries/`, `workflows/`.
- One resolver per use case. No entity-centric resolvers.
- `register_site_to_trial` performs an atomic multi-table transaction.
- All commands write audit logs.
- **Two workflow patterns**:
  - Synchronous saga with in-memory compensation
  - Async Restate workflow with durable execution and GraphQL subscriptions
- **Concurrency protection** via Restate Virtual Objects (trial updates).
- Unit tests pass.
- Shared code minimal and aligned with lightweight vertical-slice guidance.
