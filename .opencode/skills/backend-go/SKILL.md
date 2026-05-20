---
name: backend-go
description: Go (Golang) patterns: concurrency (goroutines, channels, select), interfaces, error handling, net/http, chi, generics, testing, architecture patterns, performance optimization, security, and production deployment
license: MIT
compatibility: opencode
metadata:
  audience: backend-developers
  domain: backend
  paradigm: concurrent
  capabilities:
    - error-handling-patterns
    - interface-design
    - generics
    - goroutine-lifecycle
    - channel-patterns
    - http-server
    - middleware
    - database-sql
    - structured-logging
    - tracing-metrics
    - clean-architecture
    - ddd-patterns
    - dependency-injection
    - table-driven-tests
    - mocking
    - benchmarking
    - fuzz-testing
    - pprof-profiling
    - memory-optimization
    - security-hardening
  integrates_with:
    - database-postgres
    - database-event-sourcing
    - infra-observability
    - security-audit
    - workflow-general
---

## Backend Go Skill

### 1. Idiomatic Go Patterns

#### Error Handling (Errors Are Values)
- Always handle errors explicitly; wrap with `fmt.Errorf("context: %w", err)` to preserve chain
- `errors.Is(err, target)` for sentinel comparisons; `errors.As(err, &target)` for type assertions
- Never panic in library code; `panic` only for unrecoverable startup errors
- Use `defer` + named return for closing resources safely

```go
// Sentinel errors
var ErrNotFound = errors.New("not found")
var ErrConflict = errors.New("resource conflict")

// Custom error types for structured info
type ValidationError struct {
    Field   string
    Message string
}
func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation: %s %s", e.Field, e.Message)
}

// Defer + named return for safe close
func readFile(path string) (content string, err error) {
    f, err := os.Open(path)
    if err != nil {
        return "", fmt.Errorf("open %s: %w", path, err)
    }
    defer func() {
        if cerr := f.Close(); cerr != nil && err == nil {
            err = cerr
        }
    }()
    var buf strings.Builder
    if _, err := io.Copy(&buf, f); err != nil {
        return "", fmt.Errorf("read %s: %w", path, err)
    }
    return buf.String(), nil
}
```

#### Interface Design
- Define where consumed (caller side), not where produced; accept interfaces, return structs
- Keep interfaces small (1-3 methods); compose: `type ReadWriter interface { io.Reader; io.Writer }`
- Verify at compile time: `var _ io.Reader = (*MyType)(nil)`

```go
// Consumer-side interface — only declare methods you actually use
type UserStore interface {
    FindByID(ctx context.Context, id string) (*User, error)
}

func NewUserService(store UserStore) *UserService {
    return &UserService{store: store}
}
```

#### Generics Deep Dive
- Use for data structures and algorithms; don't over-use — concrete types are often clearer
- `cmp.Ordered` is built-in for ordered types; `golang.org/x/exp/constraints` for legacy
- Type inference works at most call sites; no runtime overhead (monomorphization-like compilation)

```go
// Valid: generic data structure
type Set[T comparable] map[T]struct{}
func (s Set[T]) Add(v T)        { s[v] = struct{}{} }
func (s Set[T]) Contains(v T) bool { _, ok := s[v]; return ok }

// Valid: functional helpers
func Map[T, U any](slice []T, fn func(T) U) []U {
    result := make([]U, len(slice))
    for i, v := range slice { result[i] = fn(v) }
    return result
}
```

#### Zero Value & Functional Options
- Design zero values to be useful: `sync.Mutex`, `sync.WaitGroup`, `bytes.Buffer`, `strings.Builder`
- Nil slices/maps should behave correctly in methods
- Functional options pattern for flexible constructors:

```go
type Option func(*Server)
func WithTimeout(d time.Duration) Option { return func(s *Server) { s.timeout = d } }
func NewServer(addr string, opts ...Option) *Server {
    s := &Server{addr: addr, timeout: 30 * time.Second, maxConn: 1000}
    for _, o := range opts { o(s) }
    return s
}
```

---

### 2. Concurrency

#### Goroutine Lifecycle Management
- Every goroutine must have a known exit path — never leak goroutines
- `sync.WaitGroup` for fire-and-forget; `errgroup.Group` for parallel work with error propagation
- `context.Context` for cancellation propagation and deadline control

```go
g, ctx := errgroup.WithContext(ctx)
for _, url := range urls {
    url := url
    g.Go(func() error { return fetch(ctx, url) })
}
if err := g.Wait(); err != nil {
    return fmt.Errorf("fetch batch: %w", err)
}
```

#### Channel Patterns
- **Unbuffered**: synchronization guarantee (sender blocks until receiver ready)
- **Buffered**: bounded capacity only; **close only from sender side**
- **nil channel blocks forever** — useful for disabling select cases

```go
// Fan-in: merge N channels into one
func fanIn[T any](ctx context.Context, chs ...<-chan T) <-chan T {
    out := make(chan T)
    var wg sync.WaitGroup
    for _, ch := range chs {
        wg.Add(1)
        go func(c <-chan T) { defer wg.Done()
            for v := range c {
                select { case out <- v: case <-ctx.Done(): return }
            }
        }(ch)
    }
    go func() { wg.Wait(); close(out) }()
    return out
}

// Fan-out: distribute to N workers with errgroup
func fanOut[T any](ctx context.Context, n int, in <-chan T, fn func(T) error) error {
    g, ctx := errgroup.WithContext(ctx)
    for i := 0; i < n; i++ {
        g.Go(func() error { for v := range in { if err := fn(v); err != nil { return err } }; return nil })
    }
    return g.Wait()
}
```

#### Select Patterns & sync Package
- **Timeout**: `case <-time.After(d)`, **Heartbeat**: `time.NewTicker` in select loop
- **Graceful shutdown**: `case <-ctx.Done():` in select with drain logic
- **Semaphore**: buffered channel of empty structs; `Acquire`/`Release`
- **Rate limiter**: `time.NewTicker(time.Second / time.Duration(rps))`
- `sync.RWMutex` when reads dominate; `sync.Once` for single execution; `sync.Pool` to amortize GC

```go
type Semaphore chan struct{}
func NewSemaphore(n int) Semaphore { return make(chan struct{}, n) }
func (s Semaphore) Acquire()       { s <- struct{}{} }
func (s Semaphore) Release()       { <-s }
```

#### Happens-Before Guarantees
- Chan send happens-before the corresponding receive
- Chan close happens-before receiving zero value
- `Mutex.Unlock()` happens-before subsequent `Lock()`
- `sync.Once` completion happens-before any return from `Do()`
- **Do NOT rely on goroutine scheduling order** — always use synchronization primitives

---

### 3. HTTP Server

#### net/http Best Practices + Graceful Shutdown
```go
srv := &http.Server{
    Addr: ":8080", Handler: router,
    ReadTimeout: 5 * time.Second, WriteTimeout: 10 * time.Second,
    IdleTimeout: 120 * time.Second, MaxHeaderBytes: 1 << 20,
}

ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
defer stop()
go func() { srv.ListenAndServe() }()
<-ctx.Done()
shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
srv.Shutdown(shutdownCtx)
```

#### chi Router + Middleware
```go
r := chi.NewRouter()
r.Use(middleware.RequestID, middleware.RealIP, middleware.Logger, middleware.Recoverer)
r.Use(middleware.Timeout(60 * time.Second))

r.Route("/api/v1", func(r chi.Router) {
    r.Use(authMiddleware)
    r.Get("/users/{id}", getUser)
    r.Post("/users", createUser)
})

// Route with extracted context param
r.Route("/orgs/{orgID}", func(r chi.Router) {
    r.Use(orgCtx)  // loads org into context via URL param
    r.Get("/", getOrg)
})
```

#### Middleware Patterns
```go
// Auth middleware
func authMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        token := r.Header.Get("Authorization")
        if token == "" { http.Error(w, "unauthorized", 401); return }
        claims, err := validateToken(token)
        if err != nil { http.Error(w, "invalid token", 401); return }
        ctx := context.WithValue(r.Context(), userKey, claims)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

// Recovery (panic → 500)
func recovery(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if rec := recover(); rec != nil {
                slog.Error("panic", "err", rec, "stack", debug.Stack())
                http.Error(w, "internal server error", 500)
            }
        }()
        next.ServeHTTP(w, r)
    })
}
// Chain: handler := logging(recovery(auth(r)))   or   r.Use(logging, recovery, auth)
```

#### Request Validation, File Upload, SSE
```go
// Validate request body with go-playground/validator
var req struct { Name string `validate:"required,min=2,max=100"` }
if err := json.NewDecoder(r.Body).Decode(&req); err != nil { ... }
if err := validate.Struct(req); err != nil { ... }

// File upload with size/content-type validation
r.Body = http.MaxBytesReader(w, r.Body, 32<<20)
r.ParseMultipartForm(10 << 20)
file, header, _ := r.FormFile("file")
defer file.Close()
buf := make([]byte, 512); file.Read(buf)
if !allowedTypes[http.DetectContentType(buf)] { /* reject */ }
file.Seek(0, io.SeekStart)
io.Copy(dst, file)

// Server-Sent Events
w.Header().Set("Content-Type", "text/event-stream")
w.Header().Set("Cache-Control", "no-cache")
w.Header().Set("Connection", "keep-alive")
flusher := w.(http.Flusher)
for { select { case <-r.Context().Done(): return; case msg := <-eventCh: fmt.Fprintf(w, "data: %s\n\n", msg); flusher.Flush() } }
```

---

### 4. Dependencies

#### Database: Connection Pool Tuning
```go
db.SetMaxOpenConns(25)                  // cores * 4 for postgres
db.SetMaxIdleConns(25)                  // match max open
db.SetConnMaxLifetime(5 * time.Minute)  // recycle before infra kills
db.SetConnMaxIdleTime(1 * time.Minute)  // release idle connections

// sqlx for struct scanning + In()
type User struct { ID string `db:"id"`; Name string `db:"name"` }
var users []User
db.SelectContext(ctx, &users, "SELECT id, name FROM users WHERE id IN (?)", ids)

// pgx for PostgreSQL-native features (COPY, LISTEN/NOTIFY)
conn, _ := pgxpool.New(ctx, os.Getenv("DATABASE_URL"))
rows, _ := conn.Query(ctx, "SELECT id, name FROM users WHERE active = $1", true)

// Migrations: golang-migrate or embed with //go:embed db/migrations/*.sql
```

#### Configuration & Observability
```go
// envconfig (12-factor)
type Config struct {
    Port        int           `envconfig:"PORT" default:"8080"`
    DatabaseURL string        `envconfig:"DATABASE_URL" required:"true"`
    Timeout     time.Duration `envconfig:"TIMEOUT" default:"30s"`
}
envconfig.Process("app", &cfg)

// slog structured logging (JSON to stdout)
logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
slog.SetDefault(logger)
logger.InfoContext(ctx, "user created", "user_id", user.ID, "duration", time.Since(start))

// OpenTelemetry tracing
ctx, span := tracer.Start(ctx, "getUser"); defer span.End()
span.SetAttributes(attribute.String("user.id", id))
r.Use(otelmiddleware.NewMiddleware("my-service"))  // auto-trace propagation

// Prometheus metrics
var requestDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{Name: "http_request_duration_seconds"}, []string{"method", "path", "status"})
timer := prometheus.NewTimer(requestDuration.WithLabelValues(...)); defer timer.ObserveDuration()
```

#### Caching: go-redis + In-Memory
```go
rdb := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
val, err := rdb.Get(ctx, key).Result()
if err == redis.Nil { return "", ErrCacheMiss }

// In-memory: sync.RWMutex + map with TTL eviction goroutine
type Cache[K comparable, V any] struct { mu sync.RWMutex; items map[K]item[V] }
```

---

### 5. Architecture Patterns

#### Clean Architecture in Go
```
handler/http → usecase → domain/entity
                  ↓
              repository (interface)
                  ↓
            postgres/memory (implementation)
```

```go
// Domain (no dependencies)
type User struct { ID, Name, Email string }

// Repository interface (defined in usecase/domain layer)
type UserRepository interface {
    FindByID(ctx context.Context, id string) (*User, error)
    Save(ctx context.Context, user *User) error
}

// Usecase (orchestrates)
type UserUsecase struct { repo UserRepository }
func (uc *UserUsecase) GetUser(ctx context.Context, id string) (*User, error) {
    return uc.repo.FindByID(ctx, id)
}

// Implementation (infrastructure)
type PostgresUserRepo struct { db *sql.DB }
func (r *PostgresUserRepo) FindByID(ctx context.Context, id string) (*User, error) { ... }
```

#### Dependency Injection
- **Manual DI**: preferred for small-medium projects — explicit, no magic
- **Wire** (compile-time): `//go:build wireinject` + `wire.Build(...)` — Google, no runtime overhead
- **fx** (runtime): `fx.Provide(...)` + `fx.Invoke(...)` — Uber, good for large apps with lifecycle
- Repository pattern: generic `Repository[T]` interface for common CRUD operations

---

### 6. Testing Deep Dive

#### Table-Driven Tests + Subtests
```go
func TestAdd(t *testing.T) {
    tests := []struct{ name string; a, b, want int }{
        {"positive", 1, 2, 3}, {"negative", -1, -2, -3},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            if got := Add(tt.a, tt.b); got != tt.want {
                t.Errorf("Add(%d, %d) = %d, want %d", tt.a, tt.b, got, tt.want)
            }
        })
    }
}
```

#### Mocking + Integration Tests
```go
// Mock with gomock: mockery --name EmailSender --output mocks
ctrl := gomock.NewController(t); defer ctrl.Finish()
mock := mocks.NewMockEmailSender(ctrl)
mock.EXPECT().Send(gomock.Any(), "user@test.com", gomock.Any(), gomock.Any()).Return(nil).Times(1)

// Integration tests with testcontainers-go
req := testcontainers.ContainerRequest{
    Image: "postgres:16-alpine", ExposedPorts: []string{"5432/tcp"},
    Env: map[string]string{"POSTGRES_DB": "testdb", "POSTGRES_USER": "test", "POSTGRES_PASSWORD": "test"},
    WaitingFor: wait.ForListeningPort("5432/tcp"),
}
container, _ := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{ContainerRequest: req, Started: true})
defer container.Terminate(ctx)
```

#### Benchmark + Fuzz + Golden Files
```go
func BenchmarkFormat(b *testing.B) {
    b.ReportAllocs(); b.ResetTimer()
    for i := 0; i < b.N; i++ { _ = fmt.Sprintf("User{ID=%s}", u.ID) }
}

func FuzzParseID(f *testing.F) {
    f.Add("usr_abc123"); f.Add("")
    f.Fuzz(func(t *testing.T, input string) {
        id, err := ParseID(input)
        if err == nil && !strings.HasPrefix(id, "usr_") { t.Errorf("bad prefix") }
    })
}

// Golden files: write output to testdata/*.golden, compare on subsequent runs
// go test -update to regenerate golden files
```

---

### 7. Performance

#### Memory Allocation & Escape Analysis
```go
// Pre-allocate slices with known capacity
ids := make([]string, 0, len(users))

// strings.Builder > + concatenation in loops
var sb strings.Builder
sb.Grow(estimatedSize)
for _, s := range strs { sb.WriteString(s) }

// sync.Pool for frequently allocated short-lived objects
var bufPool = sync.Pool{New: func() any { return new(bytes.Buffer) }}
buf := bufPool.Get().(*bytes.Buffer)
defer func() { buf.Reset(); bufPool.Put(buf) }()
```
```bash
go build -gcflags="-m" ./...  # escape analysis: see what escapes to heap
# Rules: don't return pointers to locals; value receivers stay on stack;
# prefer concrete types over interfaces in hot paths; []byte vs string
```

#### pprof Profiling
```go
import _ "net/http/pprof"  // http://localhost:6060/debug/pprof/
// go tool pprof -http=:8081 cpu.prof
// go tool pprof -http=:8081 --alloc_objects heap.prof
```

---

### 8. Security

#### Input Validation & SQL Injection Prevention
```go
// Validate input boundaries
func sanitize(input string) (string, error) {
    input = strings.TrimSpace(input)
    if len(input) == 0 || len(input) > 1024 { return "", fmt.Errorf("invalid length") }
    return html.EscapeString(input), nil
}

// Path traversal prevention
cleaned := filepath.Clean(userPath)
if strings.Contains(cleaned, "..") { return "", fmt.Errorf("path traversal") }

// ALWAYS use parameterized queries — NEVER concatenate SQL
db.QueryContext(ctx, "SELECT * FROM users WHERE id = $1", userInput)   // SAFE
// db.QueryContext(ctx, "SELECT * FROM users WHERE id = "+userInput)   // DANGEROUS
```

#### CSRF, Cookies, TLS
```go
// CSRF: use nosurf (gorilla/csrf is archived since late 2022)
import "github.com/justinas/nosurf"
// csrfHandler := nosurf.New(baseHandler)
// csrfHandler.SetFailureHandler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
//     http.Error(w, "CSRF token invalid", 400)
// }))
// IMPORTANT: CSRF key MUST come from environment, never hardcoded — os.Getenv("CSRF_KEY")

// Secure cookies
http.SetCookie(w, &http.Cookie{Name: "session", Value: token, HttpOnly: true, Secure: true, SameSite: http.SameSiteLaxMode, MaxAge: 86400})

// TLS 1.2+ with strong ciphers
tlsConfig := &tls.Config{MinVersion: tls.VersionTLS12,
    CurvePreferences: []tls.CurveID{tls.X25519, tls.CurveP256},
    CipherSuites: []uint16{tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384, tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384}}
```

---

### 9. Production Deployment

```dockerfile
# Multi-stage Dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o server ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /app/server /server
EXPOSE 8080
ENTRYPOINT ["/server"]
```
```bash
go build -ldflags="-s -w" -o app ./cmd/server   # strip debug info (-s: symbols, -w: DWARF)
CGO_ENABLED=0 go build -o app ./cmd/server       # static linking for scratch/distroless
```

**Health checks**: `/health` (liveness, 200 ok) + `/health/ready` (readiness, DB ping). **Feature flags**: `os.Getenv("FEATURE_X") == "true"` for simple; OpenFeature/LaunchDarkly for runtime toggles.

---

### 10. Anti-Patterns

| Anti-Pattern | Fix |
|---|---|
| `data, _ := os.ReadFile(...)` | Always handle or propagate errors |
| `go func() { for { doWork() } }()` | Goroutine must have ctx.Done() exit path |
| Closing channel from receiver | Only close from sender side; use context for done signal |
| Large interface at implementation (5+ methods) | Define small interfaces where consumed |
| `var result string; for ... { result += s }` | Use `strings.Builder` |
| `type Service struct { ctx context.Context }` | Context must be first param of each method, not stored in struct |
| `panic(err)` for normal error flow | Return error to caller |
| `time.Sleep` in tests | Use `require.Eventually` with polling |
| `db.QueryContext(ctx, "SELECT ... "+userInput)` | Always parameterize: `$1` placeholders |
| `http.ListenAndServe(":8080", nil)` | Set ReadTimeout, WriteTimeout, IdleTimeout |
| `sync.WaitGroup.Add(1)` inside goroutine | Add before launching goroutine |

---

### 11. Troubleshooting

```
"goroutine leak"           → Missing ctx.Done() case; check WaitGroup.Add/Done balance
"all goroutines are asleep" → Channel send/receive mismatch; mutex double-lock
"send on closed channel"   → Sender wrote after close; only close from sender side
"data race detected"       → Run: go test -race ./...; add Mutex/channel/atomics
"context deadline exceeded" → Parent timeout too short; verify propagation chain
"too many open files"      → Missing defer resp.Body.Close(); defer f.Close()
"connection pool exhausted" → Check MaxOpenConns; ensure defer rows.Close()
```

---

### Key Rules Summary
- Context always first parameter: `func(ctx context.Context, ...)`
- No `init()` unless absolutely necessary (driver registration)
- `go mod tidy` after every dependency change
- `gofmt`/`goimports` enforced; `golangci-lint` for comprehensive linting
- Package name = directory name; single word, lowercase, no underscores
- `defer` for cleanup (LIFO order); never start a goroutine without knowing how it stops
- `go test -race` and `go test -count=1` (disable cache) in CI
- Prefer `io.Reader`/`io.Writer` over concrete types; export only what's needed

---

### Implementation Checklist

**Design Phase**:
- [ ] Interfaces defined where consumed (caller side), kept small (1-3 methods)
- [ ] Error types defined (sentinel errors + custom types for structured info)
- [ ] Context always first parameter: `func(ctx context.Context, ...)`
- [ ] Zero-value useful types designed for struct defaults
- [ ] Functional options pattern for constructors with >3 parameters

**Development Phase**:
- [ ] Every goroutine has a known exit path (never leak)
- [ ] `errgroup.WithContext` for parallel work with error propagation
- [ ] Channel closed only from sender side
- [ ] `select` always has `ctx.Done()` case
- [ ] `gofmt`/`goimports` enforced; `golangci-lint` for comprehensive linting
- [ ] Structured logging via `log/slog` with JSON handler
- [ ] OpenTelemetry spans on all service boundaries

**Testing Phase**:
- [ ] Table-driven tests with `t.Run()` subtests
- [ ] Mocks generated via `gomock`/`mockery`
- [ ] Integration tests with `testcontainers-go`
- [ ] Benchmark tests for performance-critical paths
- [ ] Fuzz tests for parsing/validation functions
- [ ] `go test -race` in CI (race detector enabled)
- [ ] `go test -count=1` in CI (disable test cache)

**Security Phase**:
- [ ] All SQL parameterized (never string concatenation)
- [ ] Path traversal prevention via `filepath.Clean` + `..` check
- [ ] TLS 1.2 minimum with X25519, ECDHE cipher suites
- [ ] Secure cookies: HttpOnly, Secure, SameSite=Lax
- [ ] CSRF protection via `nosurf`
- [ ] Input validation: trim, length checks, sanitize for context

**Deployment Phase**:
- [ ] Multi-stage Dockerfile with `gcr.io/distroless` (or `chainguard`)
- [ ] `CGO_ENABLED=0` for static linking
- [ ] Build flags: `-ldflags="-s -w"` for stripped binary
- [ ] `ReadTimeout`, `WriteTimeout`, `IdleTimeout` set on `http.Server`
- [ ] Graceful shutdown via `signal.NotifyContext`
- [ ] Health (`/health`) + readiness (`/health/ready`) endpoints
- [ ] pprof endpoint for production profiling (`net/http/pprof`)
