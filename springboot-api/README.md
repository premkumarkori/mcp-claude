# springboot-api — M1

Sample Spring Boot CRUD API targeted by the MCP servers. Implements the [`springboot-api-scaffold`](../.claude/skills/springboot-api-scaffold/SKILL.md) playbook.

## Stack

- Spring Boot 3.3 · Java 21 · Maven
- Spring Web · Spring Data JPA · Spring Validation · Actuator
- PostgreSQL 16 · Flyway (schema + seed)
- springdoc-openapi (OpenAPI JSON + Swagger UI)

## What's here

```
springboot-api/
├── pom.xml
├── Dockerfile                        # multi-stage, builds fat jar
├── docker-compose.yml                # Postgres + API, loopback-only
├── .env.example
└── src/main/
    ├── java/com/example/api/
    │   ├── ApiApplication.java
    │   ├── employee/                 # Employee entity/repo/service/controller
    │   └── order/                    # Order entity/repo/service/controller
    └── resources/
        ├── application.yml
        └── db/migration/
            ├── V1__schema.sql        # tables + v_*_safe views
            ├── V2__readonly_role.sql # mcp_readonly role + GRANTs
            └── V3__seed.sql          # 60 employees, 240 orders
```

## Quick start (Docker)

```bash
cp .env.example .env                 # then edit MCP_READONLY_PASSWORD
docker compose up --build
```

- API:       http://localhost:8080
- OpenAPI:   http://localhost:8080/v3/api-docs
- Swagger:   http://localhost:8080/swagger-ui.html
- Health:    http://localhost:8080/actuator/health

## Quick start (local Maven, external Postgres)

```bash
docker compose up -d postgres
export $(grep -v '^#' .env | xargs)
mvn spring-boot:run
```

## Endpoints

| Method | Path | Summary |
|---|---|---|
| GET    | `/employees`        | List employees (filter: `joinedAfter`) |
| GET    | `/employees/{id}`   | Get one employee |
| POST   | `/employees`        | Create employee |
| PUT    | `/employees/{id}`   | Update employee |
| DELETE | `/employees/{id}`   | Delete employee |
| GET    | `/orders`           | List orders (filter: `status`) |
| GET    | `/orders/{id}`      | Get one order |
| POST   | `/orders`           | Create order |
| PUT    | `/orders/{id}`      | Update order |
| DELETE | `/orders/{id}`      | Delete order |

Every endpoint is annotated with `@Tag` + `@Operation(summary=…)` — the API Explorer MCP reads these for intent matching.

## Read-only role — verification

The V2 migration creates `mcp_readonly` with `SELECT` on the `v_*_safe` views only. From the [PRD §7](../PRD.md#7-guardrails-critical), a direct `INSERT` under this role **must fail** at the DB layer.

```bash
# SELECT succeeds
docker exec -it mcp_postgres psql -U mcp_readonly -d appdb \
  -c "SELECT COUNT(*) FROM v_employees_safe;"

# INSERT must fail (permission denied)
docker exec -it mcp_postgres psql -U mcp_readonly -d appdb \
  -c "INSERT INTO employees(name,email,joined_at) VALUES ('x','x@x',NOW());"
```

If the `INSERT` succeeds, the role setup is broken — stop and fix before moving to M3.

## M1 exit checklist

- [ ] `docker compose up --build` starts cleanly; both containers become healthy.
- [ ] `curl http://localhost:8080/actuator/health` → `{"status":"UP"}`.
- [ ] `curl -s http://localhost:8080/v3/api-docs | jq '.paths | keys'` lists all 10 endpoints.
- [ ] Swagger UI renders with the `Employees` and `Orders` tags.
- [ ] `SELECT` as `mcp_readonly` on `v_employees_safe` returns 60 rows.
- [ ] `INSERT` as `mcp_readonly` on `employees` returns `permission denied`.

Only then start M2 (API Explorer MCP).
