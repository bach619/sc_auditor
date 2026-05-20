---
name: backend-python
description: Python (Advanced): FastAPI, async/await patterns, SQLAlchemy 2.0, Pydantic v2, type hints, testing with pytest, architecture, security, performance, and production deployment
license: MIT
compatibility: opencode
metadata:
  audience: backend-developers
  domain: backend
  paradigm: async
  capabilities:
    - async-python
    - fastapi
    - sqlalchemy-orm
    - pydantic-validation
    - type-safety
    - api-design
    - testing
    - architecture
    - performance-tuning
    - security
    - production-deployment
  integrates_with:
    - backend-go
    - backend-elixir
    - database-postgres
    - database-event-sourcing
    - security-audit
    - security-crypto
    - infra-observability
    - paradigm-functional
---

## Backend Python Skill

### Async Python Mastery

#### asyncio Event Loop Lifecycle
Python's asyncio provides the foundation for all async I/O. Understanding the event loop is essential.

```
┌──────────────────────────────────────────────────┐
│                EVENT LOOP LIFECYCLE               │
│                                                    │
│  asyncio.run(coro)                                 │
│       │                                            │
│       ▼                                            │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐     │
│  │ Create  │───▶│ Schedule │───▶│  Execute  │     │
│  │  Loop   │    │ Coroutine│    │  Tasks    │     │
│  └─────────┘    └──────────┘    └─────┬────┘     │
│                                       │           │
│                          ┌────────────▼──────┐    │
│                          │  Await I/O / Sleep │    │
│                          │  (loop yields)     │◀───┤
│                          └────────┬──────────┘    │
│                                   │               │
│                          ┌────────▼──────┐        │
│                          │  I/O Complete  │        │
│                          │  Resume Task   │        │
│                          └────────┬──────┘        │
│                                   │               │
│                          ┌────────▼──────┐        │
│                          │  All Tasks     │        │
│                          │  Done? ──YES──▶ Cancel│
│                          └───────────────┘        │
└──────────────────────────────────────────────────┘
```

- **`asyncio.run()`**: Create event loop, run coroutine, close loop. Call ONCE at entry point.
- **`asyncio.get_event_loop()`**: Get current loop (only inside async context; deprecated outside).
- **Custom loops**: Rarely needed. Use `asyncio.Runner` (3.11+) for multiple `run()` calls.

#### Task Management
```python
import asyncio

# create_task: schedule coroutine, returns Task immediately (fire-and-forget)
async def main():
    task = asyncio.create_task(fetch_data("url1"))
    # main continues executing while fetch_data runs concurrently
    result = await task  # wait for completion when needed

# gather: run multiple coroutines concurrently, return results in order
results = await asyncio.gather(
    fetch_data("url1"),
    fetch_data("url2"),
    fetch_data("url3"),
    return_exceptions=True  # don't cancel siblings if one fails
)

# as_completed: process results as they finish (order not guaranteed)
async for task in asyncio.as_completed(coros):
    result = await task
    process(result)

# wait: with timeout and FIRST_COMPLETED / FIRST_EXCEPTION options
done, pending = await asyncio.wait(coros, timeout=10.0)
for task in pending:
    task.cancel()  # clean up unfinished tasks

# TaskGroup (Python 3.11+): structured concurrency, auto-cancels siblings on error
async with asyncio.TaskGroup() as tg:
    tg.create_task(fetch("url1"))
    tg.create_task(fetch("url2"))
    # if any task raises, all others are cancelled automatically
```

#### Coroutine Patterns

**Producer-Consumer:**
```python
import asyncio

async def producer(queue: asyncio.Queue[str]):
    for item in generate_items():
        await queue.put(item)
    await queue.put(None)  # sentinel to signal completion

async def consumer(queue: asyncio.Queue[str]):
    while True:
        item = await queue.get()
        if item is None:
            break
        await process(item)

async def main():
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
    # producer and consumer run concurrently, backpressure via maxsize
    await asyncio.gather(producer(queue), consumer(queue))
```

**Fan-Out / Fan-In:**
```python
async def fan_out_fan_in(items: list[str]) -> list[Result]:
    # Fan-out: create a task per item
    tasks = [asyncio.create_task(process_item(item)) for item in items]
    # Fan-in: collect all results
    return await asyncio.gather(*tasks, return_exceptions=True)
```

**Semaphore (rate limiting):**
```python
sem = asyncio.Semaphore(10)  # max 10 concurrent operations

async def rate_limited_fetch(url: str) -> Response:
    async with sem:
        return await client.get(url)
```

#### Async Context Managers and Generators
```python
# Async context manager
class Database:
    async def __aenter__(self):
        self.pool = await asyncpg.create_pool(dsn)
        return self.pool

    async def __aexit__(self, exc_type, exc, tb):
        await self.pool.close()

async def main():
    async with Database() as pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM users")

# Async generator (yield with async for)
async def paginated_fetch(client: httpx.AsyncClient, url: str) -> AsyncGenerator[dict, None]:
    page = 1
    while True:
        resp = await client.get(f"{url}?page={page}")
        items = resp.json()
        if not items:
            return
        for item in items:
            yield item
        page += 1
```

#### FastAPI Deep Dive

**Dependency Injection with Depends():**
```python
from fastapi import FastAPI, Depends
from typing import Annotated

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session  # yields to route, then cleans up after response

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    payload = decode_jwt(token)
    user = await db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=401)
    return user

# Type-alias for cleaner signatures (Python 3.9+)
CurrentUser = Annotated[User, Depends(get_current_user)]
DBSession = Annotated[AsyncSession, Depends(get_db)]

@app.get("/me")
async def read_me(user: CurrentUser, db: DBSession):
    return user
```

**Middleware:**
```python
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import time

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://example.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware
class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Process-Time"] = str(time.perf_counter() - start)
        return response

app.add_middleware(TimingMiddleware)
```

**Exception Handlers:**
```python
from fastapi import Request
from fastapi.responses import JSONResponse

class DomainError(Exception):
    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code

@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(
        status_code=400,
        content={"error": exc.code, "message": exc.message}
    )

# Override default validation error format
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})
```

**Lifespan Events (startup / shutdown):**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.db_pool = await asyncpg.create_pool(dsn)
    yield
    # Shutdown
    await app.state.db_pool.close()

app = FastAPI(lifespan=lifespan)

# Access in routes: request.app.state.db_pool
```

**BackgroundTasks:**
```python
from fastapi import BackgroundTasks

def send_confirmation_email(email: str, token: str):
    """Synchronous or async — runs after response is sent."""
    smtp.send(to=email, body=f"Confirm: {token}")

@app.post("/register")
async def register(email: str, background_tasks: BackgroundTasks):
    user = await create_user(email)
    background_tasks.add_task(send_confirmation_email, email, user.confirmation_token)
    return {"status": "ok"}  # response sent immediately, email sent after
```

#### HTTP Clients (httpx)

```python
import httpx

# Connection pooling: reuse clients, never create per-request
async def get_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        base_url="https://api.example.com",
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    ) as client:
        yield client

# Retry with tenacity
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
async def fetch_with_retry(client: httpx.AsyncClient, url: str):
    resp = await client.get(url)
    resp.raise_for_status()
    return resp

# Circuit breaker (via semaphore pattern)
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 30):
        self.failure_count = 0
        self.last_failure = 0.0
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout

    async def call(self, coro):
        if self.failure_count >= self.threshold:
            if time.monotonic() - self.last_failure < self.reset_timeout:
                raise CircuitBreakerOpenError()
            self.failure_count = 0  # reset after timeout
        try:
            result = await coro
            self.failure_count = 0
            return result
        except Exception:
            self.failure_count += 1
            self.last_failure = time.monotonic()
            raise
```

#### Avoiding Blocking Calls

```python
# CPU-bound work: offload to thread pool
import concurrent.futures

pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
result = await loop.run_in_executor(pool, cpu_intensive_function, arg1, arg2)

# For sync ORM calls in async context:
# fastapi.concurrency.run_in_threadpool
from fastapi.concurrency import run_in_threadpool
user = await run_in_threadpool(db.query(User).get, user_id)

# NEVER: time.sleep(n) — use await asyncio.sleep(n)
# NEVER: file I/O without aiofiles
import aiofiles
async with aiofiles.open("file.txt") as f:
    content = await f.read()
```

#### Trio / AnyIO (Structured Concurrency)

**Trio** enforces structured concurrency: every task belongs to a nursery; child tasks must complete before the nursery block exits. **AnyIO** provides a unified API that works with both asyncio and trio backends.

```python
# AnyIO — works with asyncio or trio backend
import anyio

async def anyio_example():
    async with anyio.create_task_group() as tg:
        tg.start_soon(fetch, "url1")
        tg.start_soon(fetch, "url2")
    # All tasks guaranteed complete here

# trio — pure structured concurrency
import trio

async def trio_example():
    async with trio.open_nursery() as nursery:
        nursery.start_soon(fetch, "url1")
        nursery.start_soon(fetch, "url2")
```

Prefer **anyio** when writing libraries that may run under different event loop backends. Use **trio** when you want the strongest correctness guarantees and are willing to commit to the trio ecosystem.

---

### Type System (MANDATORY)

#### Core Type Hints
```python
from typing import Protocol, TypedDict, Literal, Final, TypeGuard, Generic, TypeVar
from collections.abc import Callable, Awaitable, Sequence, Mapping
from typing_extensions import ParamSpec, Concatenate

# Protocol: structural subtyping (duck typing with type safety)
class SupportsClose(Protocol):
    def close(self) -> None: ...

def cleanup(resource: SupportsClose) -> None:
    resource.close()

class Database:
    def close(self) -> None:
        self.pool.dispose()

cleanup(Database())  # valid — Database satisfies SupportsClose Protocol

# TypedDict: structured dictionaries with known keys
class UserDict(TypedDict):
    id: int
    name: str
    email: str

# Literal: restrict to specific string/int values
Status = Literal["active", "inactive", "pending"]
def filter_users(status: Status) -> list[User]: ...

# Final: prevent reassignment / override
API_VERSION: Final = "v1"
class Base:
    @final
    def method(self) -> None: ...

# TypeGuard: user-defined type narrowing
def is_user(obj: object) -> TypeGuard[User]:
    return isinstance(obj, User)

# Overload for multiple signatures
@overload
def get_user(identifier: int) -> User: ...
@overload
def get_user(identifier: str) -> User | None: ...
def get_user(identifier: int | str) -> User | None:
    ...
```

#### Generics
```python
T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")

# Generic class
class Repository(Generic[T]):
    def __init__(self, model: type[T]) -> None:
        self.model = model
    async def get(self, db: AsyncSession, id_: int) -> T | None:
        return await db.get(self.model, id_)

# ParamSpec: preserve function signature
def with_logging(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        logger.info("Calling %s", func.__name__)
        return await func(*args, **kwargs)
    return wrapper

# Concatenate: prepend parameters
def inject_db(func: Callable[Concatenate[AsyncSession, P], Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        async with AsyncSessionLocal() as db:
            return await func(db, *args, **kwargs)
    return wrapper
```

#### mypy / pyright Configuration
```ini
# pyproject.toml
[tool.mypy]
strict = true
disallow_any_generics = true
disallow_untyped_defs = true
warn_return_any = true
warn_unused_ignores = true
plugins = ["pydantic.mypy"]

[tool.pyright]
typeCheckingMode = "strict"
reportUnknownMemberType = true
reportUnknownArgumentType = true
```

#### Pydantic v2 + Typing Integration
```python
from pydantic import BaseModel, Field, field_validator, model_validator

class UserCreate(BaseModel):
    model_config = {"str_strip_whitespace": True, "validate_assignment": True}
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@]+@[^@]+\.[^@]+$")
    age: int = Field(ge=0, le=150)
    tags: list[str] = Field(default_factory=list)

# Type from model (preferred pattern for contracts)
CreateUserPayload = UserCreate

# Discriminated unions
class CatPayload(BaseModel):
    type: Literal["cat"]
    meow_volume: int

class DogPayload(BaseModel):
    type: Literal["dog"]
    bark_pitch: str

AnimalPayload = Annotated[CatPayload | DogPayload, Field(discriminator="type")]
```

---

### ORM: SQLAlchemy 2.0

#### Declarative Models with Mapped[]
```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, DateTime, func
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Relationship
    posts: Mapped[list["Post"]] = relationship(back_populates="author", lazy="raise")

class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    author: Mapped[User] = relationship(back_populates="posts")
```

#### AsyncSession Patterns
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@host/db",
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,  # verify connections are alive
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Context manager (recommended)
async with AsyncSessionLocal() as session:
    async with session.begin():  # auto-commit / rollback
        user = User(email="a@b.com")
        session.add(user)

# Dependency injection (FastAPI)
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

#### Query Patterns: select() (2.0 Style)
```python
from sqlalchemy import select, func, and_, or_, text, desc, asc
from sqlalchemy.orm import selectinload, joinedload, contains_eager

# Simple select
stmt = select(User).where(User.email == "a@b.com")
result = await session.execute(stmt)
user = result.scalar_one_or_none()

# Multi-column select with join
stmt = (
    select(User.name, Post.title)
    .join(Post, User.id == Post.author_id)
    .where(User.is_active == True)
    .order_by(desc(Post.created_at))
    .limit(50)
)
rows = (await session.execute(stmt)).all()

# Aggregation and grouping
stmt = (
    select(User.id, func.count(Post.id).label("post_count"))
    .outerjoin(Post)
    .group_by(User.id)
    .having(func.count(Post.id) > 0)
)

# CTE (Common Table Expressions)
cte = select(Post.author_id, func.count().label("cnt")).group_by(Post.author_id).cte()
stmt = select(User).join(cte, User.id == cte.c.author_id).where(cte.c.cnt >= 5)

# Raw SQL with text()
stmt = text("SELECT * FROM users WHERE created_at >= :since")
result = await session.execute(stmt, {"since": datetime(2026, 1, 1)})
```

#### Relationship Loading Strategies

| Loader | When | Memory |
|--------|------|--------|
| `selectinload()` | Default. Separate SELECT IN query for each relationship. Avoids N+1. | Low per-query |
| `joinedload()` | When you need parent+child in one query. Can cause cartesian explosion. | High |
| `subqueryload()` | Legacy. Similar to selectinload but via subquery. | Medium |
| `lazyload()` / `raise` | Disallow implicit loading. Use `raise` in async to catch N+1 errors. | N/A |
| `contains_eager()` | When you already joined the table manually. | N/A |

```python
# Eager load relationships
stmt = (
    select(User)
    .options(selectinload(User.posts))  # eager loads posts in second query
    .where(User.id == user_id)
)
user = (await session.execute(stmt)).scalar_one()

# Multi-level eager loading
stmt = select(User).options(
    selectinload(User.posts).selectinload(Post.comments)
)
```

#### Alembic Migrations
```bash
alembic init -t async migrations
alembic revision --autogenerate -m "add users table"
alembic upgrade head
alembic downgrade -1  # rollback one revision
```

```python
# migrations/env.py — async engine setup
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine(config.get_main_option("sqlalchemy.url"))

async def run_async_migrations():
    async with engine.connect() as conn:
        await conn.run_sync(do_run_migrations)
```

#### Connection Pooling Explained
- **pool_size**: Max persistent connections. For CPU-bound, set near worker count.
- **max_overflow**: Additional connections beyond pool_size. Burst handling.
- **pool_recycle**: Max age in seconds before connection is refreshed. Prevents stale DB connections.
- **pool_pre_ping**: Issue SELECT 1 before using a connection. Adds latency, catches severed connections.
- **NullPool**: Disable pooling. Use for serverless (Lambda) where each invocation is independent.
- **QueuePool**: Default. Thread-safe queue of connections.

---

### Data Validation: Pydantic v2

#### Model Configuration
```python
class UserSchema(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,       # auto-strip string fields
        validate_assignment=True,         # validate on attribute assignment
        extra="forbid",                   # reject unknown fields
        frozen=False,                     # True = immutable
        use_enum_values=True,             # serialize enums as values
        from_attributes=True,             # ORM mode: populate from .attribute
        populate_by_name=True,            # allow alias AND field name
        json_schema_extra={"example": {"email": "user@example.com"}},
    )
    email: str
    name: str = Field(min_length=1, max_length=100)
```

#### Field Validators (before, after, wrap)
```python
class SignupSchema(BaseModel):
    email: str
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password", mode="after")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("email", mode="wrap")
    @classmethod
    def validate_email(cls, v: str, handler):
        # handler() calls the default pydantic validation
        return handler(v)
```

#### Model Validators
```python
class TransferSchema(BaseModel):
    from_account: str
    to_account: str
    amount: float

    @model_validator(mode="after")
    def check_accounts_different(self):
        if self.from_account == self.to_account:
            raise ValueError("Cannot transfer to the same account")
        return self

    @model_validator(mode="before")
    @classmethod
    def parse_raw(cls, data: Any) -> Any:
        if isinstance(data, str):
            return json.loads(data)
        return data
```

#### Computed Fields
```python
class OrderSchema(BaseModel):
    items: list[OrderItemSchema]
    tax_rate: float = 0.10

    @computed_field
    @property
    def subtotal(self) -> float:
        return sum(item.price * item.quantity for item in self.items)

    @computed_field
    @property
    def total(self) -> float:
        return self.subtotal * (1 + self.tax_rate)
```

#### Custom Types
```python
from pydantic import BeforeValidator, AfterValidator, PlainValidator
from typing import Annotated

# Reusable validated types
def validate_non_empty(v: str) -> str:
    if not v.strip():
        raise ValueError("must not be empty")
    return v

NonEmptyStr = Annotated[str, AfterValidator(validate_non_empty)]

class CreateUserSchema(BaseModel):
    name: NonEmptyStr  # reusable validated type
```

---

### API Design

#### RESTful Patterns with FastAPI
```python
from fastapi import FastAPI, APIRouter, Query, Path, status

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=list[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    order: Literal["asc", "desc"] = Query("desc"),
    search: str | None = Query(None, description="Filter by name or email"),
    is_active: bool | None = Query(None),
) -> list[User]:
    """List users with pagination, sorting, and filtering."""
    ...

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int = Path(..., ge=1)) -> User:
    user = await find_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: DBSession) -> User:
    user = User(**payload.model_dump())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, payload: UserUpdate, db: DBSession) -> User:
    user = await db.get(User, user_id)
    for key, val in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, val)
    await db.commit()
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: DBSession) -> None:
    user = await db.get(User, user_id)
    await db.delete(user)
    await db.commit()
```

#### Pagination Patterns
```python
# Offset pagination (simple, common)
@app.get("/items")
async def list_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[Item]:
    total = await count_items()
    items = await fetch_items(offset=offset, limit=limit)
    return PaginatedResponse(total=total, offset=offset, limit=limit, items=items)

# Cursor pagination (stable for real-time / infinite scroll)
@app.get("/items/cursor")
async def list_items_cursor(
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> CursorResponse[Item]:
    items = await fetch_items_after(cursor, limit=limit)
    next_cursor = items[-1].cursor if len(items) == limit else None
    return CursorResponse(items=items, next_cursor=next_cursor)
```

#### File Upload / Download
```python
from fastapi import UploadFile, File

@app.post("/upload")
async def upload_file(file: UploadFile = File(..., max_size=10 * 1024 * 1024)):
    # file.file is a SpooledTemporaryFile (in-memory for small, disk for large)
    content = await file.read()
    # Or stream in chunks:
    # async for chunk in file.file:
    #     process(chunk)
    path = f"/uploads/{uuid4()}_{file.filename}"
    async with aiofiles.open(path, "wb") as f:
        await f.write(content)
    return {"filename": file.filename, "path": path}

@app.get("/download/{file_id}")
async def download_file(file_id: str):
    path = get_file_path(file_id)
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)
```

#### Server-Sent Events (SSE) and WebSocket
```python
from fastapi.responses import StreamingResponse
import asyncio

@app.get("/events")
async def sse_endpoint():
    async def event_stream():
        while True:
            data = await get_latest_events()
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            response = await process_message(data)
            await websocket.send_json(response)
    except WebSocketDisconnect:
        await cleanup_client(client_id)
```

#### API Versioning
```python
# Strategy 1: URL prefix (explicit, easy to route)
v1 = APIRouter(prefix="/api/v1")
v2 = APIRouter(prefix="/api/v2")
app.include_router(v1)
app.include_router(v2)

# Strategy 2: Accept header (content negotiation)
from fastapi import Header

@app.get("/users")
async def get_users(accept_version: str = Header(default="1.0")):
    if accept_version == "2.0":
        return await get_users_v2()
    return await get_users_v1()

# Strategy 3: Subdomain / Gateway routing (production):
# api-v1.example.com -> v1 service
# api-v2.example.com -> v2 service
```

---

### Testing Deep Dive

#### pytest Fixtures
```python
# conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from myapp.main import app

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="function")  # function (default), class, module, package, session
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.fixture
async def test_db(async_client):
    """Yield a test database with seeded data, then rollback."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(params=["active", "inactive", "pending"])
async def user_by_status(request, test_db):
    """Parametrized fixture: runs test once per status."""
    return await create_user(status=request.param)
```

#### FastAPI TestClient Patterns
```python
# tests/test_users.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_user(async_client: AsyncClient):
    payload = {"email": "test@example.com", "name": "Test User"}
    resp = await async_client.post("/users/", json=payload)
    assert resp.status_code == 201
    assert resp.json()["email"] == "test@example.com"

@pytest.mark.asyncio
async def test_validation_error(async_client: AsyncClient):
    resp = await async_client.post("/users/", json={"email": "invalid"})
    assert resp.status_code == 422
    assert "detail" in resp.json()

@pytest.mark.asyncio
async def test_not_found(async_client: AsyncClient):
    resp = await async_client.get("/users/99999")
    assert resp.status_code == 404
```

#### Mocking
```python
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

# pytest-mock plugin (recommended)
@pytest.mark.asyncio
async def test_with_mock(mocker, async_client):
    mock_send = mocker.patch("app.services.email.send_email", return_value={"id": "msg_123"})
    resp = await async_client.post("/register", json={"email": "a@b.com"})
    mock_send.assert_awaited_once_with("a@b.com")

# unittest.mock (stdlib)
@pytest.mark.asyncio
async def test_external_service():
    with patch("app.clients.payment.PaymentClient.charge", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "ch_123"}
        result = await process_payment(100)
        assert result["id"] == "ch_123"
```

#### Database Testing Strategies
```python
# Strategy 1: Test database with transaction rollback (fastest)
@pytest.fixture
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            yield session
            await session.rollback()  # discard changes
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

# Strategy 2: In-memory SQLite (fast, but not postgres-compatible)
# Only use for simple unit tests, not integration tests
sqlite_engine = create_async_engine("sqlite+aiosqlite://", echo=False)

# Strategy 3: Testcontainers (closest to production)
# pip install testcontainers[postgres]
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as container:
        yield container.get_connection_url()
```

#### Coverage
```bash
pytest --cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=90
```

---

### Architecture

#### Clean Architecture / Hexagonal

```
┌─────────────────────────────────────────────────────┐
│                  Domain Layer (inner)                 │
│  ┌───────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Entities  │  │ Value Objects│  │ Domain Errors │  │
│  └───────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐                                    │
│  │   Use Cases  │  (orchestrate entities, pure)      │
│  └──────┬───────┘                                    │
├─────────┼───────────────────────────────────────────┤
│         │          Application Layer                  │
│  ┌──────▼───────┐  ┌──────────────┐                 │
│  │  Ports (ABC) │  │    DTOs      │                 │
│  └──────┬───────┘  └──────────────┘                 │
├─────────┼───────────────────────────────────────────┤
│         │          Infrastructure Layer              │
│  ┌──────▼───────┐  ┌──────────────┐  ┌───────────┐  │
│  │  SQLAlchemy  │  │ Redis Cache   │  │  S3 File   │  │
│  │  Adapter     │  │  Adapter      │  │  Adapter   │  │
│  └──────────────┘  └──────────────┘  └───────────┘  │
├─────────────────────────────────────────────────────┤
│                  Presentation Layer                   │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │  FastAPI      │  │   Celery     │  │   CLI     │  │
│  │  Routers      │  │   Tasks      │  │  Commands │  │
│  └──────────────┘  └──────────────┘  └───────────┘  │
└─────────────────────────────────────────────────────┘
```

Key rule: **Dependencies point inward**. Domain has zero imports from infrastructure.

```python
# Domain layer — pure, no framework imports
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(frozen=True)
class UserRegistered:
    user_id: str
    email: str

class UserRepository(ABC):
    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...
    @abstractmethod
    async def add(self, user: User) -> None: ...

class RegisterUserUseCase:
    def __init__(self, repo: UserRepository, event_bus: EventBus) -> None:
        self.repo = repo
        self.event_bus = event_bus

    async def execute(self, email: str, password: str) -> User:
        if await self.repo.get_by_email(email):
            raise EmailAlreadyExistsError(email)
        user = User.create(email=email, password=password)
        await self.repo.add(user)
        await self.event_bus.publish(UserRegistered(user.id, email))
        return user

# Infrastructure — implements ports
class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def add(self, user: User) -> None:
        self.session.add(UserModel.from_domain(user))
```

#### Dependency Injection Frameworks
```python
# FastAPI Depends() — built-in, ideal for web layer
app.dependency_overrides[UserRepository] = lambda: SqlAlchemyUserRepository(session)

# dependency-injector — for complex apps
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    db = providers.Singleton(create_async_engine, config.db.url)
    session = providers.Factory(AsyncSessionLocal, bind=db)
    user_repo = providers.Factory(SqlAlchemyUserRepository, session=session)
    register_use_case = providers.Factory(RegisterUserUseCase, repo=user_repo)

# Wire it up
container = Container()
container.config.from_pydantic(settings)
RegisterUserUseCase = container.register_use_case
```

#### Event-Driven Patterns
```python
# Simple in-process event bus
from collections import defaultdict
from typing import Any

class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: Any) -> None:
        for handler in self._handlers[type(event)]:
            await handler(event)

# Usage
bus = EventBus()
bus.subscribe(UserRegistered, send_welcome_email)
bus.subscribe(UserRegistered, create_default_profile)
```

---

### Performance

#### Profiling
```bash
# py-spy: sampling profiler, no instrumentation needed
py-spy top --pid <PID>
py-spy record -o profile.svg --pid <PID>
py-spy dump --pid <PID>

# cProfile: built-in function-level profiler
python -m cProfile -s cumulative -o output.prof app.py
# Visualize with snakeviz
pip install snakeviz && snakeviz output.prof
```

#### GIL Considerations
- The GIL ensures only one thread executes Python bytecode at a time.
- **CPU-bound code**: Use `multiprocessing` or `concurrent.futures.ProcessPoolExecutor`.
- **I/O-bound code**: Async is the right model; GIL is released during I/O (network, files via aiofiles, etc.).
- **C extensions**: NumPy, asyncpg, orjson release the GIL during computation.
- **Free-threaded Python (3.13+)**: Experimental no-GIL build. Not production-ready yet.

#### Gunicorn + Uvicorn Worker Tuning
```bash
# Gunicorn manages worker processes; Uvicorn handles the async event loop per worker
gunicorn app.main:app \
    --workers 4 \             # = (2 * CPU_cores) + 1  for I/O-bound
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 30 \
    --keepalive 5 \
    --max-requests 10000 \    # recycle workers periodically
    --max-requests-jitter 1000 \
    --log-level info
```

#### Caching Strategies
```python
# In-memory cache (simple, per-process, lost on restart)
from functools import lru_cache
from cachetools import TTLCache

cache = TTLCache(maxsize=1000, ttl=300)  # 5-minute TTL

async def get_user_cached(user_id: int) -> User | None:
    if user_id in cache:
        return cache[user_id]
    user = await db.get(User, user_id)
    cache[user_id] = user
    return user

# Redis cache (shared across workers / services)
import redis.asyncio as redis
redis_client = redis.Redis.from_url("redis://localhost:6379", decode_responses=True)

async def get_user_cached(user_id: int) -> dict | None:
    key = f"user:{user_id}"
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)
    user = await fetch_user_from_db(user_id)
    await redis_client.setex(key, 300, json.dumps(user))
    return user
```

#### Connection Pooling (Database)
- PostgreSQL: `pool_size = (max_connections / number_of_service_instances) * 0.8`
- Always use PgBouncer between your app and PostgreSQL (transaction mode for web workloads).
- httpx: Default limits=Limits(max_connections=100). Increase for high-throughput services.
- Redis: Max connections in pool = worker count * 2.

---

### Security

#### OWASP Top 10 for Python Backends
1. **Injection**: Always parameterize queries. Never concatenate user input into SQL.
2. **Broken Authentication**: Use battle-tested libraries (python-jose for JWT, httpx-oauth for OAuth2).
3. **Sensitive Data Exposure**: Never log passwords, tokens, or PII. Use pydantic-settings SecretStr.
4. **Access Control**: Every endpoint must verify auth. Use Depends() to enforce.
5. **Security Misconfiguration**: Disable debug mode in production. Pin dependency versions.

#### Input Validation
```python
from pydantic import BaseModel, Field, ConfigDict

class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_max_length=255, extra="forbid")

    email: str = Field(pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=150)
```

#### JWT / OAuth2 Patterns
```python
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
SECRET_KEY = os.environ["JWT_SECRET"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(minutes=15)

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.get(User, int(user_id))
    if not user:
        raise credentials_exception
    return user
```

#### CORS Configuration
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Total-Count", "X-Next-Cursor"],
    max_age=600,
)
```

#### Rate Limiting
```python
# Using slowapi (FOSS, compatible with FastAPI)
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/users", dependencies=[Depends(limiter.limit("100/minute"))])
async def get_users(): ...

# For sensitive endpoints
auth_limiter = Limiter(key_func=get_remote_address)

@app.post("/auth/login")
@auth_limiter.limit("5/minute")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]): ...
```

#### Secure Configuration with pydantic-settings
```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str  # not secret, just configuration
    JWT_SECRET: SecretStr  # SecretStr masks value in logs and repr
    OPENAI_API_KEY: SecretStr
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]
    LOG_LEVEL: str = "INFO"
```

---

### Production Deployment

#### Dockerfile (Multi-stage)
```dockerfile
FROM python:3.12-slim AS build
WORKDIR /app
RUN pip install --no-cache-dir poetry
COPY pyproject.toml poetry.lock ./
RUN poetry export -f requirements.txt --output requirements.txt --without dev
RUN pip wheel --no-cache-dir -r requirements.txt -w /wheels

FROM python:3.12-slim
WORKDIR /app
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY src/ ./src/
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["gunicorn", "src.main:app", "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", "--bind", "0.0.0.0:8000"]
```

#### Structured Logging
```python
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer() if DEBUG else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

log = structlog.get_logger()
log.info("request_processed", user_id=user.id, duration_ms=42.5, status=200)
```

#### Health Checks
```python
@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "ok"}

@app.get("/health/ready", include_in_schema=False)
async def readiness_check(db: DBSession):
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ready"}
```

#### Config Management Hierarchy
```
1. pydantic-settings for typed config (loads from env, .env, vault)
2. NEVER hardcode secrets
3. Use SecretStr for sensitive values
4. Validate at startup (app startup event validates all config)
5. Feature flags via environment variables or dedicated service
```

---

### Implementation Checklist

**Design Phase**:
- [ ] Async/await used for all I/O (no blocking calls on event loop)
- [ ] Type hints on all function signatures (mypy strict mode)
- [ ] Pydantic v2 models for all request/response validation
- [ ] SQLAlchemy 2.0 declarative models with `Mapped[]`
- [ ] Alembic migrations created for all schema changes

**Development Phase**:
- [ ] All FastAPI endpoints have `response_model` set
- [ ] Dependency injection via `Depends()` for DB sessions, auth
- [ ] HTTP calls use `httpx.AsyncClient` (reused, not per-request)
- [ ] Structured logging via `structlog` with JSON renderer
- [ ] `SecretStr` for all sensitive configuration values

**Testing Phase**:
- [ ] pytest with async fixtures (`anyio_backend = "asyncio"`)
- [ ] Database testing via transaction rollback (fast) or testcontainers (accurate)
- [ ] Coverage ≥ 80% line, ≥ 75% branch
- [ ] Property-based tests for invariant-heavy logic (Hypothesis)
- [ ] Integration tests for all critical API flows

**Security Phase**:
- [ ] Input validation via Pydantic on ALL endpoints
- [ ] Parameterized queries (no string concatenation in SQL)
- [ ] Rate limiting on auth endpoints (5/minute)
- [ ] CORS restricted to explicit origins (no `*`)
- [ ] JWT with RS256 or EdDSA (asymmetric, not HS256)
- [ ] Passwords hashed with Argon2id

**Deployment Phase**:
- [ ] Multi-stage Dockerfile with non-root user
- [ ] Gunicorn + Uvicorn workers tuned (`workers = 2*CPU + 1`)
- [ ] Health check and readiness check endpoints
- [ ] Connection pool sizing (PgBouncer in front of Postgres)
- [ ] Graceful shutdown via lifespan events
- [ ] Logs output as JSON to stdout/stderr

---

### Anti-Patterns

| Anti-Pattern | Why Bad | Fix |
|---|---|---|
| **Mixing sync and async** | Calling `requests.get()` in async handler blocks the entire event loop | Use `httpx.AsyncClient` or `run_in_executor` |
| **Raw SQL string concatenation** | SQL injection vulnerability | Always use parameterized `text("...", params)` or ORM |
| **Using `Any` type** | Kills type safety, hides bugs | Use `object`, generics, or `Protocol` |
| **Creating httpx client per request** | Exhausts connections, no keep-alive | Singleton `AsyncClient` reused across requests |
| **`.all()` on large tables** | Loads entire table into memory | Use `.yield_per()` for streaming, or pagination |
| **Catching `Exception` broadly** | Swallows critical errors like `KeyboardInterrupt` | Catch specific exceptions, let unexpected ones propagate |
| **Secrets in source code** | Credentials leaked to version control | Use `pydantic-settings` + env vars + `SecretStr` |
| **No timeout on HTTP calls** | Hangs forever if downstream is unresponsive | Set `httpx.Timeout()` on every client |
| **N+1 queries** | Each related object triggers a separate query | Use `selectinload()` or `joinedload()` |
| **`session.commit()` in DI `yield`** | Commits after response sent; lost errors | Commit explicitly in route handler before return |
| **`asyncio.run()` inside async function** | `RuntimeError: cannot be called from a running event loop` | Call `asyncio.run()` only once at entry point |
| **Logging passwords / tokens** | Secrets end up in log aggregation, PII breach | Use `SecretStr`, redact sensitive fields in logging |

---

### Troubleshooting

#### Common Errors and Solutions

| Error | Likely Cause | Solution |
|---|---|---|
| `RuntimeError: Event loop is closed` | Calling `asyncio.run()` inside an already-running loop, or FastAPI test with wrong fixture | Ensure single `asyncio.run()` at entry. In tests, use `@pytest.mark.asyncio` or session-scoped event loop |
| `sqlalchemy.exc.MissingGreenlet` | Accessing lazy-loaded relationship in async context | Use `lazy="raise"` on relationships, eager-load with `selectinload()` |
| `PoolTimeout: QueuePool limit of size X overflow Y reached` | Connection pool exhausted | Increase `pool_size` / `max_overflow`, or check for leaked connections (missing `.close()`) |
| `PydanticSerializationError` | Returning ORM model directly from route without `from_attributes=True` | Set `ConfigDict(from_attributes=True)` on response model |
| `AssertionError: enforce_route_response_model` | Route returns a non-dict object but response_model is set | Ensure return value matches response_model structure |
| `403 Forbidden` on POST/PUT | CORS preflight not configured | Add `OPTIONS` to CORS `allow_methods`, or use `CORSMiddleware` with `allow_methods=["*"]` for development |
| `SSL: CERTIFICATE_VERIFY_FAILED` with httpx | Self-signed cert or proxy intercepting TLS | Set `verify=False` only for dev; in prod, provide CA bundle path |

#### Debugging Checklist
1. **Check event loop**: Are you mixing sync and async? Use `asyncio.iscoroutinefunction()` to verify.
2. **Check DB connections**: Run `SELECT count(*) FROM pg_stat_activity` to see open connections.
3. **Check N+1**: Enable `echo=True` on engine temporarily to see all emitted SQL.
4. **Check Pydantic**: Use `.model_dump()` and `.model_validate()` explicitly for debugging.
5. **Check types**: Run `mypy --strict src/` and fix all errors before deploying.
6. **Check prod config**: `debug=False`, `SecretStr` used, no `*` in CORS origins, rate limiting on auth endpoints.
