---
name: springboot-api-scaffold
description: Use when creating or extending the Spring Boot + PostgreSQL CRUD API that the MCP servers target. Triggers on requests like "scaffold the Spring Boot API", "add an entity", "add a CRUD endpoint", "set up Flyway", or work inside springboot-api/.
---

# springboot-api-scaffold

**Trigger:** any request to create, scaffold, or extend the Spring Boot CRUD API defined in [PRD.md](../../../PRD.md) §6.1. Also applies when touching files under `springboot-api/`.

This skill is the playbook for **M1** in the PRD. The goal is a small, realistic CRUD API that the API Explorer MCP can introspect and the Analytics MCP can query.

## Stack (fixed)

- Spring Boot 3.x (Java 21)
- Spring Web, Spring Data JPA, Spring Boot Actuator
- PostgreSQL JDBC driver
- Flyway (schema + seed data)
- springdoc-openapi-starter-webmvc-ui (OpenAPI JSON + Swagger UI)
- Maven (keep the tooling choice consistent — do not mix with Gradle)

## Project layout

```
springboot-api/
├── pom.xml
├── src/main/java/com/example/api/
│   ├── ApiApplication.java
│   ├── employee/
│   │   ├── Employee.java          # @Entity
│   │   ├── EmployeeRepository.java # extends JpaRepository
│   │   ├── EmployeeService.java
│   │   └── EmployeeController.java # @RestController
│   └── order/ ...                  # same pattern
├── src/main/resources/
│   ├── application.yml
│   └── db/migration/
│       ├── V1__init.sql            # schema
│       └── V2__seed.sql            # seed data for Analytics MCP
└── docker-compose.yml              # Postgres + the API
```

## Configuration (`application.yml`)

```yaml
spring:
  datasource:
    url: jdbc:postgresql://${DB_HOST:localhost}:${DB_PORT:5432}/${DB_NAME:appdb}
    username: ${DB_USER:app}
    password: ${DB_PASSWORD:app}
  jpa:
    hibernate.ddl-auto: validate   # Flyway owns the schema; JPA only validates
    properties.hibernate.jdbc.time_zone: UTC
  flyway:
    enabled: true
    locations: classpath:db/migration

springdoc:
  api-docs.path: /v3/api-docs
  swagger-ui.path: /swagger-ui.html

management:
  endpoints.web.exposure.include: health,info
```

`/v3/api-docs` and `/actuator/health` are **required** — the API Explorer MCP reads the first, and operators use the second.

## Entity/Repository/Service/Controller pattern

Use this exact layering. One worked example — `Employee`:

```java
// Employee.java
@Entity
@Table(name = "employees")
public class Employee {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;
    private String email;
    @Column(name = "joined_at") private Instant joinedAt;
    // getters/setters
}
```

```java
// EmployeeController.java — tag + operation summaries feed the MCP
@Tag(name = "Employees")
@RestController
@RequestMapping("/employees")
public class EmployeeController {
    @Operation(summary = "List employees, optionally filtered by join date")
    @GetMapping
    public List<Employee> list(@RequestParam(required = false) Instant joinedAfter) { ... }

    @Operation(summary = "Create a new employee")
    @PostMapping
    public Employee create(@RequestBody @Valid EmployeeCreate req) { ... }
    // getById, update, delete …
}
```

**Annotate every controller with `@Tag` and every method with `@Operation(summary = ...)`** — these land in the OpenAPI spec and become the primary hints the MCP uses for intent matching. Low-quality tags/summaries = low-quality MCP UX.

## Flyway migrations

- `V1__init.sql` — tables + a **PII-masked view** per entity (e.g. `v_employees_safe` excludes `email`). The Analytics MCP allowlist will point at views, not raw tables.
- `V2__seed.sql` — enough rows for realistic demos (50+ employees across a 90-day join window, 200+ orders across statuses).

## Read-only role (create here, consumed by Analytics MCP)

Add to `V1__init.sql` (or a later migration) — documented in [readonly-sql-mcp](../readonly-sql-mcp/SKILL.md):

```sql
CREATE ROLE mcp_readonly LOGIN PASSWORD 'change-me'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
GRANT CONNECT ON DATABASE appdb TO mcp_readonly;
GRANT USAGE ON SCHEMA public TO mcp_readonly;
GRANT SELECT ON v_employees_safe, v_orders_safe TO mcp_readonly;
-- Do NOT grant SELECT on raw tables.
```

## `docker-compose.yml`

Must include Postgres with a health check, a named volume, and the API depending on DB health. Bind Postgres to `127.0.0.1:5432` only — do not expose to 0.0.0.0.

## Verification checklist

1. `./mvnw spring-boot:run` starts clean.
2. `curl http://localhost:8080/actuator/health` → `{"status":"UP"}`.
3. `curl http://localhost:8080/v3/api-docs | jq '.paths | keys'` shows all CRUD paths.
4. Swagger UI at `http://localhost:8080/swagger-ui.html` renders with tags + summaries.
5. `psql -U mcp_readonly -d appdb -c "SELECT COUNT(*) FROM v_employees_safe;"` succeeds.
6. `psql -U mcp_readonly -d appdb -c "INSERT INTO employees ..."` **fails** with a permission error (proves the read-only role works).

Do not move on to M2 until all six pass.

## Anti-patterns to avoid

- Don't use `ddl-auto: update` — Flyway owns the schema.
- Don't skip `@Operation` summaries — the MCP depends on them.
- Don't grant the app's main DB user to the MCP server — always use `mcp_readonly`.
- Don't expose raw PII tables to `mcp_readonly`; always go via views.
