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
- `saga_onboard_trial(id, trial_id NULL, state, error NULL, created_at, updated_at)`

## Use Cases

### Commands
1) **create_trial**
- In: `{ name, phase }`
- Behavior: insert `trials(status='draft')`; write audit.
- Out: `{ id, name, phase, status }`

2) **register_site_to_trial** (multi-table transaction)
- In: `{ trial_id, site_name, country }`
- Behavior: upsert `sites`; insert `trial_sites(status='pending')`; single transaction; write one audit record.
- Out: `{ trial_id, site_id, link_status }`

3) **update_trial_metadata**
- In: `{ trial_id, name?, phase? }`
- Behavior: update `trials`; compute diff; audit.
- Out: updated trial.

### Queries
4) **get_trial**
- In: `{ id }`
- Out: trial core fields, sites, latest protocol (read-optimized SQL).

5) **list_trials**
- In: `{ phase?, status?, search?, limit=20, offset=0 }`
- Out: `{ items: [TrialSummary], total }`

6) **get_audit_log**
- In: `{ entity, entity_id, limit=50 }`
- Out: `[AuditEntry]`

### Workflow (Saga)
7) **onboard_trial**
- In: `{ name, phase, initial_protocol_version, sites: [{name, country}] }`
- Steps: create trial → add protocol version → register sites sequentially.
- State: `STARTED → SITES_ADDED → COMPLETED | ERROR` (stored in `saga_onboard_trial`).
- Writes audits at each step. No event sourcing. Simple in-process orchestration.

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
│   │   │   └── update_trial_metadata/
│   │   │       ├── handler.py
│   │   │       ├── types.py
│   │   │       ├── resolver.py
│   │   │       ├── test_handler.py
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
│       └── onboard_trial/
├── e2e_tests/             # End-to-end integration tests (NOT unit tests)
│   ├── conftest.py
│   ├── test_trial_lifecycle.py
│   ├── test_site_registration.py
│   └── test_onboarding_saga.py
└── main.py
```

**Key Principles:**
- **Unit tests co-located**: Each module's tests live alongside it (e.g., `test_handler.py` next to `handler.py`)
- **Shared code in sensible parents**: `trial_management/_validation.py` demonstrates "things that change together, live together"
- **Infrastructure separation**: Database and API concerns isolated from business logic
- **E2E tests clearly separated**: Integration tests in dedicated `e2e_tests/` folder

## GraphQL Design
- **One resolver per use case.** Commands as mutations. Queries as queries.
- Inputs: Strawberry `@input` mapped from each slice's DTO.
- Outputs: explicit per-slice types. Avoid leaking raw entities.
- Naming:
  - Mutations: `createTrial`, `registerSiteToTrial`, `updateTrialMetadata`, `startOnboarding`
  - Queries: `trialById`, `listTrials`, `auditLog`, `onboardingStatus`
- Composition example:
```python
# app/infrastructure/api/schema.py
import strawberry
from app.usecases.commands.trial_management.create_trial.resolver import create_trial
from app.usecases.commands.register_site_to_trial.resolver import register_site_to_trial
from app.usecases.commands.trial_management.update_trial_metadata.resolver import update_trial_metadata
from app.usecases.queries.get_trial.resolver import trial_by_id
from app.usecases.queries.list_trials.resolver import list_trials
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
    trial_by_id = trial_by_id
    list_trials = list_trials
    audit_log = audit_log
    onboarding_status = onboarding_status

schema = strawberry.Schema(query=Query, mutation=Mutation)
```

## Cross-Cutting
- **Audit**: `app/core/audit.py` provides `@audited(action, entity, id_fn)` to write to `audit_logs` on successful command; failures recorded with error info.
- **DB**: `app/infrastructure/database/session.py` exposes `SessionLocal()` context helper. Each handler opens and commits its own transaction.

## Tests
- **Unit tests**: Co-located with each slice (e.g., `test_handler.py`, `test_resolver.py`). Use in-memory SQLite. Verify success, rollback, and audit row creation.
- **End-to-end tests**: Located in `app/e2e_tests/`. ASGI client against the Strawberry app.
  - Create → Get → Update roundtrip
  - Register site transaction
  - Onboard saga happy path and failure path
  - Audit trail verification

## Seed Data
- 3 trials across phases.
- 2 sites linked to a trial.
- 1 protocol version per trial.
- Several audit rows.

Run: `uv run python -m app.infrastructure.database.seed`

## UV + Runbook
```bash
uv init clinical-demo
uv add "strawberry-graphql>=0.211" "uvicorn>=0.30" "SQLAlchemy>=2.0" "pydantic>=2.8" "python-dotenv>=1.0" "alembic>=1.13" "pytest>=8.0"

# optional migrations
uv run alembic upgrade head

# seed
uv run python -m app.infrastructure.database.seed

# serve
uv run uvicorn app.main:app --reload

# test
pytest  # Runs all co-located unit tests and e2e tests
```

## Acceptance Criteria
- Folders grouped by **use cases** under `commands/`, `queries/`, `workflows/`.
- One resolver per use case. No entity-centric resolvers.
- `register_site_to_trial` performs an atomic multi-table transaction.
- All commands write audit logs.
- Workflow `onboard_trial` updates saga table and exposes status.
- Unit and integration tests pass.
- Shared code minimal and aligned with lightweight vertical-slice guidance.
