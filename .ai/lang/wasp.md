# Wasp Framework Guide

Consolidated reference for Wasp projects: structure, patterns, security, testing, and CLI workflow.

## Project Structure

Wasp projects have a fixed layout:
- `main.wasp` -- declarative app config (single source of truth)
- `schema.prisma` -- database models (Prisma)
- `src/` -- all application code (client + server together)
- `.wasp/` -- generated code (NEVER edit)
- `.env.server` -- server secrets (NEVER commit)
- `.env.client` -- client env vars (REACT_APP_ prefix)

## .wasp File Conventions

- One `app` declaration per project
- Declaration syntax: `<type> <Name> { key: value }`
- All imports use `@src/` prefix: `import { fn } from "@src/path"`
- Use PascalCase for declaration names: `route DashboardRoute`, `page DashboardPage`
- Group related declarations together (route + page, query + action for same entity)

## TypeScript Conventions

- Always type operations using Wasp-generated types:
  ```typescript
  import { type GetTasks } from 'wasp/server/operations'
  export const getTasks: GetTasks<void, Task[]> = async (args, context) => { ... }
  ```
- Import entities from `wasp/entities`, not from Prisma directly
- Import client operations from `wasp/client/operations`
- Import server utilities from `wasp/server`
- Use `HttpError` for operation errors: `throw new HttpError(401, 'Not authorized')`
- Organize `src/` by feature, not by type

## Operations (Queries and Actions)

- Queries are for reading data, Actions are for writing data
- Always check `context.user` in authenticated operations
- Always declare `entities` in .wasp for operations that access the database
- Use Prisma client via `context.entities.ModelName`, not raw `prisma`
- Never import server code in client files (causes "process is not defined")
- Exception: `import { prisma } from 'wasp/server'` is allowed for complex queries not tied to a single operation

## Auth Pattern

Declare auth in the `app` block, implement hooks in `src/auth/`:

```wasp
app MyApp {
  auth: {
    userEntity: User,
    methods: {
      email: {},
      google: {},
      gitHub: {},
    },
    onAuthFailedRedirectTo: "/login",
    onAuthSucceededRedirectTo: "/",
  }
}
```

Use pre-built components: `LoginForm`, `SignupForm`, `useAuth()`, `logout()`

Auth hooks for custom logic: `onBeforeSignup`, `onAfterSignup`, `onBeforeLogin`, `onAfterLogin`

## CRUD Pattern

For simple entity CRUD, use automatic CRUD instead of manual queries/actions:

```wasp
crud Tasks {
  entity: Task,
  operations: {
    getAll: { isPublic: true },
    create: {},
    update: {},
    delete: {},
  }
}
```

Override specific operations when you need custom logic:
```wasp
crud Tasks {
  entity: Task,
  operations: {
    create: { overrideFn: import { createTask } from "@src/tasks" },
  }
}
```

Client usage: `Tasks.getAll.useQuery()`, `Tasks.create.useAction()`

## Optimistic Updates

```typescript
const createTaskOptimistic = useAction(createTask, {
  optimisticUpdates: [{
    getQuerySpecifier: () => [getTasks],
    updateQuery: (payload, oldData) => [...oldData, { ...payload, id: -1 }]
  }]
})
```

## Background Jobs

- Use PgBoss executor (requires PostgreSQL + Docker)
- Schedule with cron or submit programmatically
- Jobs run inside the server process
- Access entities via `context.entities`

## API Routes

For endpoints that don't fit query/action model (webhooks, streaming, file upload):

```wasp
api stripeWebhook {
  fn: import { stripeWebhook } from "@src/apis",
  httpRoute: (POST, "/stripe-webhook"),
  auth: false,
  middlewareConfigFn: import { stripeMiddleware } from "@src/apis"
}
```

## WebSockets

Declare in app block, use `useSocket()` and `useSocketListener()` on client.
Auto-authenticated -- `socket.data.user` available on server.

## Environment Variables

- Server secrets in `.env.server` (DATABASE_URL, JWT_SECRET, API keys)
- Client vars in `.env.client` with `REACT_APP_` prefix
- Validate with Zod schema via `app.server.envValidationSchema`
- Access via `import { env } from 'wasp/server'` or `'wasp/client'`
- Required server vars: DATABASE_URL, WASP_WEB_CLIENT_URL, WASP_SERVER_URL, JWT_SECRET

## Security

### Authentication
- Always set `authRequired: true` on pages that need auth
- Always check `context.user` in queries/actions before accessing data
- Never trust client-sent user IDs -- use `context.user.id` from the session
- Set `auth: false` explicitly on public API routes (webhooks)

### Operations Security
- CRUD operations pass all client data through -- always override with custom functions for validation
- Never expose internal IDs or sensitive fields in query responses
- Filter entity fields in queries -- don't return `select: *`
- Use `HttpError` for controlled error responses (don't leak stack traces)

### Database
- PostgreSQL required in production (SQLite is dev-only)
- Use Prisma migrations via `wasp db migrate-dev`
- Never run `prisma` CLI directly -- always use `wasp db` commands

### Common Vulnerabilities
- Importing server code in client exposes secrets
- CRUD without overrides allows unauthorized data access
- Missing `context.user` checks = privilege escalation
- Exposing API keys in `.env.client` = leaked secrets

## Testing

- Client-side testing only (server-side not yet supported by Wasp)
- Uses Vitest + @testing-library/react + msw (pre-configured)
- NEVER run `wasp test` and `wasp start` simultaneously (both write to .wasp/out)

```typescript
import { renderInContext, mockServer } from 'wasp/client/test'

renderInContext(<MyComponent />)

const { mockQuery, mockApi } = mockServer()
mockQuery(getTasks, [{ id: 1, description: 'Test' }])
```

- Use `renderInContext` instead of bare `render` (Wasp components need providers)
- 80% minimum coverage for business logic
- Focus on operations and user flows over UI layout

## CLI Workflow

- `wasp start` -- development (hot reload on both client and server)
- `wasp start db` -- spin up a managed dev PostgreSQL via Docker
- `wasp db migrate-dev` -- after changing `schema.prisma`
- `wasp db studio` -- visually inspect the database
- `wasp clean` -- when things get weird (deletes .wasp/ and node_modules)
- `wasp build` -- production artifacts

## Common Gotchas

- Changing `schema.prisma` requires `wasp db migrate-dev`
- Adding a new dependency requires restarting `wasp start`
- PgBoss jobs need Docker running
- Auth provider env vars must be set before `wasp start`
- Routes are lazy-loaded by default (v0.22+) -- use `lazy: false` if needed

## Pre-Commit Checks

- [ ] `.env.server` is in `.gitignore`
- [ ] No server imports in client code
- [ ] All operations check `context.user` where needed
- [ ] `wasp build` succeeds (catches .wasp syntax errors)
- [ ] CRUD operations have overrides for validation/authorization
