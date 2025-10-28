# GraphQL Demo Projects

This repository contains multiple demo projects showcasing different GraphQL patterns and architectures.

## Projects

### [Vertical Slice GraphQL Demo](vertical-slice-graphql-demo/)

A comprehensive example demonstrating Vertical Slice Architecture with GraphQL, Strawberry, and Restate.

**Key Features:**
- Vertical slice architecture for maintainability
- GraphQL API with Strawberry
- Restate for durable execution and Virtual Objects
- Synchronous sagas with compensation
- Asynchronous workflows with GraphQL subscriptions
- Real-time progress updates via pub/sub
- Comprehensive test suite (97 unit/integration tests, 23 E2E tests)

**Tech Stack:** Python, FastAPI, SQLAlchemy, Strawberry GraphQL, Restate, SQLite

See the [project README](vertical-slice-graphql-demo/README.md) for full documentation.

---

## Repository Structure

```
.
├── vertical-slice-graphql-demo/   # Vertical Slice Architecture + GraphQL
│   ├── app/                       # Application code
│   ├── pyproject.toml            # Project dependencies
│   └── README.md                 # Project documentation
│
└── (future demo projects)
```

## Getting Started

Each project is self-contained with its own virtual environment and dependencies. Navigate to a project directory and follow its README for setup instructions.

## License

MIT
