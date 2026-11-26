# Database and SQL documentation

## Scope and ownership

List actual databases/stores, configuration sources, data ownership, and authoritative schema/migration paths. If none exist, explain alternatives and implementation evidence.

## Tables and relationships

| Table / source | Primary / unique keys | Fields / defaults | Indexes / relations |
|---|---|---|---|
| <table> | <keys> | <types/nullability> | <indexes> |

## Query and write paths

Map key SQL/queries to source and APIs/background jobs. Explain transaction boundaries, locks, consistency, idempotency, cleanup, and performance constraints. Parameterize all queries; never include credentials.

## Migrations and recovery

Forward/backward compatibility, release order, data backfills, rollback, and validation commands. Record version/source checked and update triggers.
