---
name: backend-elixir
description: Elixir/Erlang patterns: OTP, GenServer, Supervisor trees, ETS/DETS/Mnesia, Phoenix, LiveView, Ecto, Broadway, Oban, testing, deployment, and BEAM VM optimization
license: MIT
compatibility: opencode
metadata:
  audience: backend-developers
  domain: backend
  paradigm: actor-model
  capabilities:
    - otp-genserver
    - supervisor-trees
    - ets-mnesia
    - phoenix-liveview
    - ecto-queries
    - concurrency-pipelines
    - error-recovery
    - property-testing
    - release-deployment
  integrates_with:
    - paradigm-functional
    - paradigm-actor
    - database-postgres
    - database-event-sourcing
    - infra-observability
---

## Backend Elixir/Erlang Skill

### OTP Core (The BEAM Trifecta)

#### GenServer

```elixir
defmodule MyServer do
  use GenServer

  # Client API (runs in caller process)
  def start_link(initial) do
    GenServer.start_link(__MODULE__, initial, name: __MODULE__)
  end

  def get_state do
    GenServer.call(__MODULE__, :get)
  end

  def increment(amount) do
    GenServer.cast(__MODULE__, {:inc, amount})
  end

  # Server callbacks (runs in server process)
  @impl true
  def init(initial) do
    {:ok, initial}
  end

  @impl true
  def handle_call(:get, _from, state) do
    {:reply, state, state}
  end

  @impl true
  def handle_cast({:inc, amount}, state) do
    {:noreply, state + amount}
  end

  @impl true
  def handle_info(:cleanup, state) do
    {:noreply, state, :hibernate}
  end
end
```

**Return tuples**: `{:reply, reply, state}` | `{:noreply, state}` | `{:stop, reason, state}` | `{:reply, reply, state, timeout_or_opts}`

**Timeouts**: `{:noreply, state, 30_000}` — calls handle_info(:timeout, state) after 30s of inactivity. Use `:hibernate` to hibernate idle processes (GCs heap, saves memory).

**Name registration**: `name: {:via, Registry, {MyRegistry, "key"}}` for dynamic lookup; `name: {:global, name}` for cluster-global; `name: __MODULE__` for singleton.

**Debugging**: `:sys.get_state(pid)` to peek state; `:sys.trace(pid, true)` for message tracing; `:sys.get_status(pid)` for full status.

**GenServer vs Agent**: Agent is GenServer with get/update API. Use Agent only for simple state access; GenServer for any logic beyond get/put.

#### Supervisor

```elixir
children = [
  # Permanent: always restarted (default)
  {MyServer, []},

  # Temporary: never restarted
  %{id: Worker, start: {Task, :start_link, [fn -> work() end]}, restart: :temporary},

  # Transient: restarted only on abnormal exit
  %{id: Cleanup, start: {Cleanup, :start_link, []}, restart: :transient}
]

Supervisor.start_link(children, strategy: :one_for_one,
                        max_restarts: 5, max_seconds: 60)
```

**Strategies**:
- `:one_for_one` — only failed child restarted (isolated workers)
- `:one_for_all` — all children restarted if any fails (tightly coupled)
- `:rest_for_one` — failed child + children started after it (dependency order)

**Restart intensity**: `{max_restarts, max_seconds}` — if exceeded, supervisor terminates all children and itself. Default: `{3, 5}`.

**DynamicSupervisor**: For children created at runtime. `DynamicSupervisor.start_child(sup, {Worker, arg})`. Children are always `:temporary`. Use for connection pools, session processes, or user-bound resources.

**Supervision tree design**: Root → Application-level supervisors → Business-domain supervisors → Workers. Each leaf should have a clear failure domain.

#### Application

```elixir
defmodule MyApp.Application do
  use Application

  @impl true
  def start(_type, _args) do
    children = [
      {Phoenix.PubSub, name: MyApp.PubSub},
      MyApp.Repo,
      {DNSCluster, query: Application.compile_env(:my_app, :dns_cluster_query) || :ignore},
      MyAppWeb.Endpoint
    ]

    opts = [strategy: :one_for_one, name: MyApp.Supervisor]
    Supervisor.start_link(children, opts)
  end

  @impl true
  def stop(_state), do: :ok
end
```

**Environment config**: Prefer `Application.compile_env/3` over `Application.get_env/2` in module bodies — it's evaluated at compile time and more explicit. Use `config/runtime.exs` for runtime configuration (deployment secrets, environment-specific values).

#### Process Monitoring & Linking

```elixir
# Linking — if one dies, the other dies
spawn_link(fn -> raise "boom" end)

# Monitoring — receive DOWN message instead of dying
ref = Process.monitor(pid)
receive do
  {:DOWN, ^ref, :process, _pid, reason} -> handle_down(reason)
end

# Trapping exits — catch linked process deaths
Process.flag(:trap_exit, true)
spawn_link(fn -> exit(:normal) end)
receive do
  {:EXIT, _pid, reason} -> handle_exit(reason)
end
```

**When to use which**:
- `spawn_link` — for supervision tree children; failure should cascade
- `Process.monitor` — for observing without coupling lifecycles
- `trap_exit` — in supervisors and processes that manage cleanup on failure

#### Task & Task.Supervisor

```elixir
# Fire-and-forget
Task.start(fn -> do_work() end)

# Await result
task = Task.async(fn -> expensive_calc() end)
result = Task.await(task, 5000)

# Parallel streaming with backpressure control
Task.async_stream(urls, &fetch/1,
  max_concurrency: 10,
  timeout: 30_000,
  on_timeout: :kill_task
)
|> Stream.each(fn {:ok, resp} -> process(resp) end)
|> Stream.run()

# Supervised tasks
Task.Supervisor.start_child(MyTaskSupervisor, fn -> risky_work() end)
```

**Task.yield_many**: Wait on multiple tasks with timeout. Returns `{id, {:ok, result}}` or `{id, {:exit, reason}}` or `{id, nil}` for still-running tasks.

#### Registry

```elixir
# Start registry (in supervision tree)
{Registry, keys: :unique, name: MyRegistry}

# Register via GenServer
GenServer.start_link(MyHandler, data, name: {:via, Registry, {MyRegistry, "key1"}})

# Lookup and call
case Registry.lookup(MyRegistry, "key1") do
  [{pid, _}] -> GenServer.call(pid, :action)
  [] -> {:error, :not_found}
end
```

**Key types**: `:unique` (one process per key) or `:duplicate` (many processes per key). Use `:via` tuples with `Registry` for dynamic process discovery without atoms.

---

### Data Storage

#### ETS (Erlang Term Storage)

```elixir
# Create table
table = :ets.new(:my_table, [:set, :public, :named_table,
  read_concurrency: true, write_concurrency: true])

# CRUD operations
:ets.insert(:my_table, {:key, value, timestamp})
:ets.lookup(:my_table, :key)        # returns [tuple] or []
:ets.update_counter(:my_table, :counter, {2, 1})  # atomic increment
:ets.select(:my_table, [{{:"$1", :"$2", :_}, [{:>, :"$2", 100}], [:"$1"]}])
:ets.match_delete(:my_table, {:_, :_, 0})  # bulk delete with pattern

# Ordered set — for range queries
table = :ets.new(:by_date, [:ordered_set])
:ets.insert(:by_date, [{ts1, data1}, {ts2, data2}])
:ets.select(:by_date, [
  {{:"$1", :"$2"}, [{:>=, :"$1", min_ts}, {:"=<", :"$1", max_ts}], [{{:"$1", :"$2"}}]}
])
```

**Table types**: `:set` (default, key unique), `:ordered_set` (key unique, ordered), `:bag` (duplicate keys allowed), `:duplicate_bag` (duplicate key-value pairs allowed).

**Access control**: `:public` (any process read/write), `:protected` (any process read, only owner write), `:private` (only owner).

**Concurrency**: Set `read_concurrency: true` for read-heavy workloads (uses fine-grained reader locks). Set `write_concurrency: true` for write-heavy (uses per-bucket locks).

**Gotchas**: Owner process death destroys the table. `:ets.lookup_element/3` for O(1) single-field access without copying the whole tuple.

#### DETS (Disk ETS)

```elixir
{:ok, dets} = :dets.open_file(:my_dets, [type: :set, file: 'path/to/file'])
:det.insert(dets, {:key, "data"})
:dets.close(dets)
```

**Limitations**: Much slower than ETS; supports only `:set` and `:bag`; file size limit of 2GB. Use for small, persistent lookups or as Mnesia's disk backend.

#### Mnesia

```elixir
# Schema setup (run once per node)
:mnesia.create_schema([node()])

# Start Mnesia
:mnesia.start()

# Create table
:mnesia.create_table(:users, [
  attributes: [:id, :name, :email],
  disc_copies: [node()],
  type: :ordered_set
])

# Transactional write
:mnesia.transaction(fn ->
  :mnesia.write({:users, user_id, name, email})
end)

# Dirty read (no transaction, faster, eventually consistent)
:mnesia.dirty_read({:users, user_id})

# Dirty write — bulk inserts
:mnesia.dirty_write({:users, id, name, email})
```

**Storage backends**: `:ram_copies` (in-memory ETS), `:disc_copies` (ETS + DETS), `:disc_only_copies` (DETS only, slower). Use `:disc_copies` for persistence with good read performance.

**Transactions**: Guarantee ACID across table operations within a single node. Use `:mnesia.sync_dirty` context for replicated writes.

**Gotchas**: Schema migration is painful; prefer Ecto + PostgreSQL for new projects. Mnesia excels for in-memory clustered state that needs persistence.

#### Persistent Term

```elixir
# Set (once per key, cannot be updated frequently)
:persistent_term.put(:app_config, %{limit: 100, timeout: 5000})

# Get (zero-copy reads — returns reference to term in memory)
:persistent_term.get(:app_config, default)
```

**Performance**: Reads bypass process heap — they access the shared persistent_term area directly. Nearly as fast as reading a module attribute. 10-100x faster than ETS reads.

**Gotchas**: Not for frequently updated data — each update incurs a global GC. Keys can only be put once unless `:persistent_term.erase/1` is called first. Use for configuration, routing tables, or static reference data.

#### Caching: Cachex / Nebulex

```elixir
# Cachex — simple, fast, feature-rich
Cachex.put!(:my_cache, "key", "value", ttl: :timer.minutes(5))
Cachex.get(:my_cache, "key")

# Nebulex — multi-level caching with adapters
defmodule MyCache do
  use Nebulex.Cache, otp_app: :my_app, adapter: Nebulex.Adapters.Local
end
MyCache.put("key", "value", ttl: 60_000)
MyCache.get("key")
```

**When to use**: Cachex for single-node caching with TTL. Nebulex for multi-level caching (local + Redis) with adapter swap capability. For distributed caches: Nebulex with Redis adapter or Mnesia.

---

### Phoenix Framework

#### LiveView Lifecycle

```elixir
defmodule MyAppWeb.UserLive do
  use MyAppWeb, :live_view

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, users: [], loading: true)}
  end

  @impl true
  def handle_params(params, _uri, socket) do
    page = String.to_integer(params["page"] || "1")
    {:noreply, assign(socket, page: page) |> start_async_load(page)}
  end

  @impl true
  def handle_event("search", %{"query" => q}, socket) do
    results = Accounts.search_users(q)
    {:noreply, assign(socket, users: results, loading: false)}
  end

  @impl true
  def handle_info({:users_loaded, users}, socket) do
    {:noreply, assign(socket, users: users, loading: false)}
  end
end
```

**Lifecycle order**: `mount/3` → `handle_params/3` → render → `handle_event/3` → `handle_info/2` → render.

**Temporary assigns**: `assign(socket, results: results, temporary: true)` — value is nil-ified after render, freeing memory. Essential for large datasets that need not persist between renders.

**Streams**: `stream(socket, :posts, posts, reset: true)` — for efficiently inserting, updating, and removing items from large lists without full re-render. Use `<ul id="posts" phx-update="stream">` in templates.

**LiveComponent**: For stateful, reusable UI components with their own `mount/1`, `update/2`, `handle_event/3`. Components have their own lifecycle and can receive messages independently of their parent LiveView.

#### PubSub

```elixir
# Broadcast from anywhere
Phoenix.PubSub.broadcast(MyApp.PubSub, "room:lobby", {:new_message, msg})

# Subscribe in LiveView
if connected?(socket) do
  Phoenix.PubSub.subscribe(MyApp.PubSub, "room:#{room_id}")
end

# Handle broadcast in LiveView
def handle_info({:new_message, msg}, socket) do
  {:noreply, stream_insert(socket, :messages, msg)}
end
```

**Presence**: Track connected users with `Phoenix.Presence`. Uses CRDT internally for conflict-free tracking. Provides `Presence.list("room:lobby")` to enumerate present users.

#### Channels

```elixir
defmodule MyAppWeb.UserSocket do
  use Phoenix.Socket
  channel "room:*", MyAppWeb.RoomChannel

  def connect(params, socket, _connect_info) do
    case Accounts.verify_token(params["token"]) do
      {:ok, user} -> {:ok, assign(socket, :user, user)}
      :error -> :error
    end
  end
end

defmodule MyAppWeb.RoomChannel do
  use Phoenix.Channel

  def join("room:" <> room_id, _payload, socket) do
    {:ok, assign(socket, :room_id, room_id)}
  end

  def handle_in("message", %{"body" => body}, socket) do
    broadcast!(socket, "message", %{user: socket.assigns.user, body: body})
    {:noreply, socket}
  end
end
```

**Socket authentication**: Authenticate in `connect/3` via token, session, or header. Return `{:ok, socket}` or `:error`. The `_connect_info` contains request metadata (X-Headers, peer data, URI).

#### Contexts

```elixir
defmodule MyApp.Accounts do
  alias MyApp.Accounts.User
  alias MyApp.Repo

  def create_user(attrs) do
    %User{}
    |> User.changeset(attrs)
    |> Repo.insert()
  end

  def get_user!(id), do: Repo.get!(User, id)
end
```

**Purpose**: Module-based API boundaries that encapsulate business logic. Contexts prevent controllers/LiveViews from directly calling Repo functions. Each context groups related schemas and operations.

**Design rules**: One context per business domain (Accounts, Orders, Billing). Expose only `get_*`, `create_*`, `update_*`, `delete_*`, `list_*` functions and specific queries. Never expose Ecto schemas or Repo calls directly.

#### LiveView Testing

```elixir
defmodule MyAppWeb.UserLiveTest do
  use MyAppWeb.ConnCase
  import Phoenix.LiveViewTest

  test "renders user list", %{conn: conn} do
    {:ok, view, html} = live(conn, "/users")

    assert html =~ "Users"
    assert render(view) =~ "alice@example.com"

    view
    |> element("button", "Add User")
    |> render_click()

    assert_patch(view, "/users/new")
  end
end
```

**Test helpers**: `live/2` mounts the LiveView, `render/1` returns HTML, `render_click/1` triggers click event, `render_submit/1` submits a form, `assert_patch/2` checks URL, `assert_redirect/2` checks redirect.

#### LiveView Forms with Ecto Changesets

```elixir
# In LiveView
def handle_event("validate", %{"user" => params}, socket) do
  changeset =
    socket.assigns.user
    |> User.changeset(params)
    |> Map.put(:action, :validate)

  {:noreply, assign(socket, changeset: changeset)}
end

# In template
<.form for={@changeset} phx-change="validate" phx-submit="save">
  <.input field={@changeset[:email]} label="Email" />
  <.error :for={msg <- @changeset.errors}><%= msg %></.error>
  <.button phx-disable-with="Saving...">Save</.button>
</.form>
```

**phx-change vs phx-submit**: `phx-change` fires on every input change (for real-time validation), `phx-submit` fires on form submission. Combine both: validate on keyup, persist on submit.

#### Phoenix.Component & HEEx

```elixir
defmodule MyAppWeb.CoreComponents do
  use Phoenix.Component

  slot :inner_block, required: true
  slot :actions

  def card(assigns) do
    ~H"""
    <div class="card">
      <div class="card-body"><%= render_slot(@inner_block) %></div>
      <div :if={@actions != []} class="card-actions">
        <%= render_slot(@actions) %>
      </div>
    </div>
    """
  end

  def button(assigns) do
    ~H"""
    <button {@rest} class={["btn", @variant && "btn-#{@variant}"]}>
      <%= render_slot(@inner_block) %>
    </button>
    """
  end
end
```

**Function components**: Stateless, pure rendering functions. Prefer over LiveComponent when no local state is needed. Slots enable composable component APIs.

---

### Ecto

#### Schemas & Changesets

```elixir
defmodule MyApp.Accounts.User do
  use Ecto.Schema
  import Ecto.Changeset

  schema "users" do
    field :email, :string
    field :name, :string
    field :role, Ecto.Enum, values: [:admin, :user, :viewer]
    field :deleted_at, :utc_datetime
    has_many :orders, MyApp.Orders.Order
    timestamps()
  end

  def changeset(user, attrs) do
    user
    |> cast(attrs, [:email, :name, :role])
    |> validate_required([:email, :name])
    |> validate_format(:email, ~r/@/)
    |> unique_constraint(:email)
    |> validate_inclusion(:role, [:admin, :user, :viewer])
    |> prepare_changes(fn changeset ->
      # runs just before insert/update, after all validations
      changeset
    end)
  end

  # Separate changeset for admin updates
  def admin_changeset(user, attrs) do
    user |> cast(attrs, [:role])
  end
end
```

**Virtual fields**: Fields not persisted to DB — `field :password, :string, virtual: true`. Useful for form inputs that don't map 1:1 to columns.

**Embedded schemas**: `embedded_schema do ... end` for non-persistent structs with validation. Use for JSON API request/response validation or nested form data.

#### Query Composition

```elixir
# Pipe-based query building
def list_active_users do
  User
  |> where([u], u.deleted_at |> is_nil())
  |> order_by([u], desc: u.inserted_at)
  |> Repo.all()
end

# Dynamic query
def search(filters) do
  User
  |> where(^filter_deleted())
  |> maybe_filter_by_email(filters[:email])
  |> Repo.all()
end

defp filter_deleted, do: dynamic([u], is_nil(u.deleted_at))

defp maybe_filter_by_email(query, nil), do: query
defp maybe_filter_by_email(query, email) do
  query |> where([u], ilike(u.email, ^"%#{email}%"))
end

# Subquery
active_order_ids =
  Order
  |> where([o], o.status == :active)
  |> select([o], o.id)

users_with_active_orders =
  User
  |> join(:inner, [u], o in subquery(active_order_ids), on: u.id == o.user_id)
  |> Repo.all()

# Preloading
Repo.all(User) |> Repo.preload(:orders)
Repo.all(from u in User, preload: [:orders])
Repo.all(from u in User, left_join: o in assoc(u, :orders), preload: [orders: o])
```

#### Multi for Transactions

```elixir
alias Ecto.Multi

Multi.new()
|> Multi.insert(:user, User.changeset(%User{}, user_params))
|> Multi.insert(:profile, fn %{user: user} ->
  Profile.changeset(%Profile{}, %{user_id: user.id})
end)
|> Multi.run(:audit, fn repo, %{user: user} ->
  repo.insert(%AuditLog{action: "user_created", user_id: user.id})
end)
|> Repo.transaction()
|> case do
  {:ok, %{user: user, profile: profile}} -> {:ok, user}
  {:error, :user, changeset, _changes_so_far} -> {:error, changeset}
end
```

**Multi advantages**: Atomic (all or nothing), passes results between steps, tracks errors per operation name. Always use Multi when inserting across multiple schemas in a single transaction.

#### Repo

```elixir
defmodule MyApp.Repo do
  use Ecto.Repo, otp_app: :my_app, adapter: Ecto.Adapters.Postgres
end

# Common operations
Repo.get(User, id)                          # fetch by primary key
Repo.get_by(User, email: email)             # fetch by attributes
Repo.insert(changeset)                      # insert from changeset
Repo.update(changeset)                      # update from changeset
Repo.delete(struct)                         # delete struct
Repo.delete_all(from u in User, where: u.deleted_at < ^cutoff)
Repo.one(query)                             # expect exactly one result
Repo.all(query)                             # fetch all
Repo.transaction(fn -> ... end)             # wrap in transaction
Repo.exists?(from u in User, where: u.id == ^id)  # existence check
```

#### Migrations

```elixir
defmodule MyApp.Repo.Migrations.CreateUsers do
  use Ecto.Migration

  def change do
    create table(:users, primary_key: false) do
      add :id, :binary_id, primary_key: true
      add :email, :string, null: false
      add :role, :string, default: "user"
      add :metadata, :jsonb
      timestamps()
    end

    create unique_index(:users, [:email])
    create index(:users, [:role])
  end
end
```

**Rules**: Always run `mix ecto.gen.migration`; never edit applied migrations; rollback must be explicitly defined via separate `up/0` and `down/0` functions if `change/0` isn't reversible.

---

### Concurrency Patterns

#### Task: Async/Await/Stream

```elixir
# Sequential async — wait for result
task = Task.async(fn -> fetch_user(id) end)
user = Task.await(task, 5000)

# Parallel streaming with control
[url1, url2, url3]
|> Task.async_stream(&HTTPoison.get/1,
     max_concurrency: 5,
     ordered: false,
     timeout: 30_000,
     on_timeout: :kill_task
   )
|> Stream.filter(&match?({:ok, _}, &1))
|> Stream.run()

# yield_many with partial results
tasks = for id <- user_ids do
  Task.async(fn -> {id, fetch_user(id)} end)
end

results = Task.yield_many(tasks, timeout: 5000)
Enum.map(results, fn
  {_task, {:ok, {id, user}}} -> %{id: id, user: user}
  {_task, {:exit, reason}} -> %{error: reason}
  {task, nil} ->
    Task.shutdown(task, :brutal_kill)
    %{error: :timeout}
end)
```

#### Flow / GenStage

```elixir
# GenStage: producer → producer_consumer → consumer pipeline
defmodule Producer do
  use GenStage
  def init(initial), do: {:producer, initial}

  def handle_demand(demand, state) when demand > 0 do
    events = Enum.take(state, demand)
    {:noreply, events, state -- events}
  end
end

# Flow: high-level parallel processing
[1, 2, 3, 4, 5, 6]
|> Flow.from_enumerable()
|> Flow.partition()
|> Flow.map(&expensive_transform/1)
|> Flow.reduce(fn -> %{} end, &Map.put(&1, &2.id, &2))
|> Enum.to_list()
```

**When to use Flow/GenStage**: CPU-bound pipelines that benefit from parallelism; when you need back-pressure (producer won't flood consumer); data transformation pipelines with multiple stages.

#### Broadway

```elixir
defmodule MyApp.Pipeline do
  use Broadway

  def start_link(_opts) do
    Broadway.start_link(__MODULE__,
      name: MyPipeline,
      producer: [
        module: {BroadwaySQS.Producer, queue_url: "https://..."},
        concurrency: 1
      ],
      processors: [
        default: [concurrency: 10]
      ],
      batchers: [
        database: [concurrency: 2, batch_size: 100, batch_timeout: 2000]
      ]
    )
  end

  @impl true
  def handle_message(_processor, message, _context) do
    data = Jason.decode!(message.data)
    Broadway.Message.update_data(message, fn _ -> data end)
  end

  @impl true
  def handle_batch(:database, messages, _batch_info, _context) do
    rows = Enum.map(messages, & &1.data)
    Repo.insert_all(Item, rows)
    messages
  end
end
```

**Broadway architecture**: Producer (ingests from source) → Processors (transform in parallel) → Batchers (group into batches) → handle_batch (persist in batch). Built-in back-pressure at every stage.

**Acknowledgers**: Broadway auto-acks messages after successful `handle_batch`. Use `Broadway.Message.configure_ack/2` for custom ack behavior (e.g., SQS visibility timeout extension).

#### Oban (Background Jobs)

```elixir
defmodule MyApp.Workers.ProcessOrder do
  use Oban.Worker, queue: :orders, max_attempts: 5

  @impl true
  def perform(%Oban.Job{args: %{"order_id" => order_id}}) do
    order = Repo.get!(Order, order_id)
    Orders.fulfill(order)
    :ok
  end
end

# Enqueue
%{order_id: order.id}
|> MyApp.Workers.ProcessOrder.new(schedule_in: 5)
|> Oban.insert()

# Unique jobs (deduplication)
%{user_id: user.id}
|> MyApp.Workers.SendWelcome.new(unique: [period: :infinity, fields: [:worker, :args]])
|> Oban.insert()
```

**Oban features**: Cron jobs, scheduled jobs, retries with backoff, unique jobs, telemetry integration, dashboard UI, pruning of completed jobs. Use for any work that shouldn't block a request.

#### Rate Limiting

```elixir
# Hammer — pluggable rate limiter with ETS backend
defmodule MyApp.RateLimit do
  use Hammer, backend: :ets

  def check_rate(key, limit, scale_ms \\ 60_000) do
    Hammer.check_rate("rate:#{key}", scale_ms, limit)
  end
end

# Use in plug
def call(conn, _opts) do
  key = conn.remote_ip |> :inet.ntoa() |> to_string()

  case RateLimit.check_rate(key, 100, 60_000) do
    {:allow, _count} -> conn
    {:deny, _limit} ->
      conn
      |> put_resp_content_type("application/json")
      |> send_resp(429, ~s({"error": "rate_limited"}))
      |> halt()
  end
end
```

**Alternatives**: `ExRated` (simple count-based), `Membrane` (token bucket via GenServer), `:ets.update_counter/4` for raw counter-based rate limiting with atomic increments.

---

### Error Handling

#### Let It Crash Philosophy

The BEAM isolates failures. A process failure never corrupts another process's state. When something unexpected happens, let the process crash — the supervisor restarts it to a known-good state. This is simpler and more robust than defensive try/catch everywhere.

**Rules**: Catch only expected errors (network timeouts, validation failures, file not found). Crash on programmer errors (type mismatches, nil access, logic bugs).

#### with/1 for Happy-Path Chaining

```elixir
def create_order(user_id, items) do
  with {:ok, user} <- Accounts.get_user(user_id),
       {:ok, validated_items} <- Orders.validate_items(items),
       {:ok, total} <- Orders.calculate_total(validated_items),
       {:ok, order} <- Orders.insert(user, validated_items, total),
       :ok <- Notifications.order_confirmed(user, order) do
    {:ok, order}
  else
    {:error, :not_found} -> {:error, "User not found"}
    {:error, %Ecto.Changeset{} = changeset} -> {:error, changeset}
    {:error, reason} -> {:error, reason}
  end
end
```

**with/1 rules**: Each clause must return `{:ok, val}` or `{:error, reason}`. The `else` block handles non-matching tuples. Use `=` for side-effect-free assignments; avoid side effects in `with` (use `|>` pipeline instead).

#### Error Tuples

```elixir
# Idiomatic Erlang/Elixir pattern
def divide(a, b) do
  if b == 0, do: {:error, :division_by_zero}, else: {:ok, a / b}
end

# Pattern match on result
case divide(10, x) do
  {:ok, result} -> IO.puts("Result: #{result}")
  {:error, reason} -> Logger.error("Division failed: #{reason}")
end
```

#### Rescue Patterns

```elixir
# Rescue only when calling external/untrusted code
try do
  unpredictable_external_call()
rescue
  e in RuntimeError -> {:error, e.message}
  e in ErlangError -> {:error, e.original}
end

# Rescue with after (cleanup)
try do
  File.write!(path, data)
after
  File.rm(tmp_path)  # always runs
end
```

**When to rescue**: External API calls, file I/O, JSON parsing, database deadlocks. Never rescue for control flow.

#### Logger

```elixir
require Logger

# Levels: :emergency > :alert > :critical > :error > :warning > :notice > :info > :debug
Logger.info("User #{user_id} logged in")
Logger.error("Payment failed: #{inspect(reason)}")
Logger.debug(fn -> "Expensive debug: #{expensive_calc()}" end)  # lazy evaluation

# Metadata
Logger.metadata(user_id: user_id, request_id: request_id)
Logger.info("Request processed")
```

**Best practices**: Use lazy evaluation for expensive debug messages (`fn ->` form). Attach metadata in controllers/LiveViews for request tracing. Never log secrets (passwords, tokens) — use `:redact` in Logger configuration.

---

### Testing

#### ExUnit Best Practices

```elixir
defmodule MyApp.AccountsTest do
  use MyApp.DataCase

  setup do
    user = insert!(:user)
    %{user: user}
  end

  describe "create_user/1" do
    test "with valid attrs creates user", %{user: _admin} do
      attrs = %{email: "new@test.com", name: "New"}
      assert {:ok, %User{} = user} = Accounts.create_user(attrs)
      assert user.email == "new@test.com"
    end

    test "with invalid email returns error" do
      assert {:error, %Ecto.Changeset{}} = Accounts.create_user(%{email: "bad"})
    end
  end
end
```

**Conventions**: `describe/2` groups tests by function; `test/2` has descriptive name; `setup/1` returns context map; `assert` for all expectations. One `assert` per test for clear failure messages.

#### Test Factories (ExMachina)

```elixir
defmodule MyApp.Factory do
  use ExMachina.Ecto, repo: MyApp.Repo

  def user_factory do
    %MyApp.Accounts.User{
      name: sequence(:name, &"User #{&1}"),
      email: sequence(:email, &"user#{&1}@test.com"),
      role: :user
    }
  end

  def admin_factory do
    %MyApp.Accounts.User{
      name: "Admin",
      email: "admin@test.com",
      role: :admin
    }
  end
end

# In tests
user = insert!(:user)
admin = insert!(:admin)
```

**ExMachina patterns**: `build(:user)` for struct only, `insert(:user)` for persisted, `params_for(:user)` for attributes map. Use `sequence/2` for unique values.

#### Property-Based Testing (StreamData)

```elixir
property "encoding/decoding is identity" do
  check all data <- StreamData.binary() do
    assert decode(encode(data)) == data
  end
end

property "sorting preserves length" do
  check all list <- list_of(integer()) do
    assert length(Enum.sort(list)) == length(list)
  end
end
```

**When to use**: Pure functions with well-defined invariants; serialization/deserialization; encoders/decoders; any "round-trip" property.

#### Mocks & Stubs (Mox)

```elixir
# Define behaviour
defmodule MyApp.HTTPClient do
  @callback get(String.t()) :: {:ok, map()} | {:error, term()}
end

# In application config
config :my_app, :http_client, HTTPoison

# In test, use Mox
import Mox

setup :verify_on_exit!
setup :set_mox_from_context

test "fetches data" do
  expect(MyApp.MockHTTPClient, :get, fn _url ->
    {:ok, %{body: "response"}}
  end)

  assert {:ok, result} = MyApp.Service.fetch_data()
end
```

**Mox rules**: Always define a behaviour first. Use `Mox.defmock/2` based on the behaviour. Call `verify_on_exit!` to ensure all expected calls were made.

#### Phoenix.ConnTest & LiveViewTest

```elixir
# ConnTest
test "GET /api/users returns users", %{conn: conn} do
  conn = get(conn, "/api/users")
  assert json_response(conn, 200)["data"]
end

# LiveViewTest
test "toggles visibility", %{conn: conn} do
  {:ok, view, _html} = live(conn, "/dashboard")

  view |> element("#toggle-btn") |> render_click()
  assert render(view) =~ "Visible content"

  view |> element("#toggle-btn") |> render_click()
  refute render(view) =~ "Visible content"
end
```

---

### Performance

#### BEAM VM Tuning

```elixir
# erlang flags to tune (in vm.args or mix release config)

# Process limits
+P 2_000_000        # max processes (default 262144)

# Async thread pool (for file I/O, DNS)
+A 64               # default 10

# Schedulers
+S 8                # default = CPU cores
+SDPcpu 8           # dirty CPU schedulers (default = CPUs)

# Memory
-env ERL_MAX_ETS_TABLES 5000   # default 2053
```

**Key tunables**: Increase `+P` for apps with many concurrent connections (Phoenix Channels). Increase `+A` for file-heavy apps. Set dirty schedulers for CPU-bound NIFs.

#### IODATA / Iolist Patterns

```elixir
# Bad — string concatenation creates intermediate binaries
IO.puts("<html>" <> body <> "</html>")

# Good — iolist, no allocation
IO.puts(["<html>", body, "</html>"])
IO.puts([?<, "div", ?>, content, ?<, "/div", ?>])

# iolist in Ecto/JSON encoding — Phoenix does this automatically
iodata = ["{\"users\":", json_array, "}"]
{:ok, json} = Jason.encode_to_iodata(data)  # uses iodata internally
```

**Why**: Iolists are deeply nested lists of strings/charlists that the BEAM can output without concatenation. Phoenix, Plug, and Ecto use this internally. Never concatenate strings for output.

#### Binary Optimization

```elixir
# Binary pattern matching is O(1)
<<len::32, body::binary-size(len), rest::binary>> = data

# Append with <<>> — efficient for building binaries
bin = <<>>
bin = <<bin::binary, "chunk1">>
bin = <<bin::binary, "chunk2">>

# Use iodata for building large binaries
[header, <<len::32>>, body, footer] |> IO.iodata_to_binary()
```

#### ETS vs Process Dictionary

```elixir
# ETS: shared across processes, persistent until table owner dies
:ets.insert(:cache, {:key, value})

# Process dictionary: single process, zero overhead
Process.put(:key, value)
Process.get(:key)

# Persistent Term: global, read-only after set, zero-copy reads
:persistent_term.put(:routes, routes)
:persistent_term.get(:routes)
```

**Decision matrix**: Process dict for process-local state (avoid; use GenServer state instead). ETS for shared, mutable data. Persistent term for read-heavy, rarely-changed global data.

#### Telemetry

```elixir
# Emit custom metrics
:telemetry.execute([:my_app, :orders, :created], %{count: 1}, %{user_id: user.id})

# Attach handler
:telemetry.attach("order-logger", [:my_app, :orders, :created], fn
  _event, %{count: count}, %{user_id: user_id}, _config ->
    Logger.info("Order created by user #{user_id}")
end, nil)

# Built-in telemetry events
# [:phoenix, :endpoint, :start]  [:phoenix, :endpoint, :stop]
# [:phoenix, :router_dispatch, :start]  [:phoenix, :router_dispatch, :stop]
# [:ecto, :repo, :query]  [:oban, :job, :start]  [:oban, :job, :stop]
```

**Instrumentation**: Use `telemetry_metrics` + `telemetry_poller` for Prometheus metrics. Phoenix LiveDashboard shows real-time telemetry data for development/debugging.

---

### Security

#### Plug Security Headers

```elixir
# In endpoint.ex
plug Plug.RequestId
plug Plug.Telemetry, event_prefix: [:phoenix, :endpoint]
plug Plug.MethodOverride
plug Plug.Head
plug Plug.Session, @session_options
plug MyAppWeb.Router
```

**Hardening**:
```elixir
# Add to endpoint.ex or router pipeline
plug :secure_headers

def secure_headers(conn, _opts) do
  conn
  |> put_resp_header("x-content-type-options", "nosniff")
  |> put_resp_header("x-frame-options", "DENY")
  |> put_resp_header("x-xss-protection", "0")
  |> put_resp_header("referrer-policy", "strict-origin-when-cross-origin")
  |> put_resp_header("permissions-policy", "camera=(), microphone=()")
  |> put_resp_header("content-security-policy",
       "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'")
end
```

#### CSRF Protection

Phoenix includes CSRF protection by default via `Plug.CSRF`. Every non-GET request requires a CSRF token. In LiveView, CSRF is handled automatically. For JavaScript clients, include `x-csrf-token` header from meta tag: `<meta name="csrf-token" content="<%= Plug.CSRF.get_csrf_token() %>" />`.

#### SQL Injection via Ecto

```elixir
# SAFE — Ecto parameterizes all queries
Repo.all(from u in User, where: u.email == ^user_input)

# DANGER — raw SQL with interpolation
Ecto.Adapters.SQL.query!(Repo, "SELECT * FROM users WHERE email = '#{user_input}'", [])

# SAFE — raw SQL with parameters
Ecto.Adapters.SQL.query!(Repo, "SELECT * FROM users WHERE email = $1", [user_input])
```

**Ecto is safe by default**: `^` operator parameterizes values. `Ecto.Query` never interpolates strings into SQL. Only `Ecto.Adapters.SQL.query!/4` with string interpolation is dangerous.

#### LiveView-Specific Security

```elixir
# Validate all messages from client
def handle_event("delete", %{"id" => id}, socket) do
  item = Repo.get!(Item, id)

  if item.user_id == socket.assigns.current_user.id do
    Repo.delete!(item)
    {:noreply, socket}
  else
    {:noreply, put_flash(socket, :error, "Not authorized")}
  end
end

# Never trust assigns from client
# socket.assigns can only be set on the server — client cannot modify them
```

**LiveView security model**: All state lives on the server. The client sends only events (name + params). Assigns are server-only. Diff tracking sends minimal DOM changes. Socket authentication via token in `connect/3`.

---

### Deployment

#### Releases with mix release

```bash
# Build release
MIX_ENV=prod mix release

# Run
_build/prod/rel/my_app/bin/my_app start
_build/prod/rel/my_app/bin/my_app remote   # attach remote console

# Config in config/runtime.exs (evaluated at boot, not compile)
config :my_app, MyApp.Repo,
  url: System.get_env("DATABASE_URL"),
  pool_size: String.to_integer(System.get_env("POOL_SIZE") || "10")
```

**Release structure**: `mix release` bundles ERTS, all dependencies, and application code into a self-contained tarball. `config/runtime.exs` is evaluated at boot time, supporting environment variable-based configuration.

#### Dockerization

```dockerfile
FROM hexpm/elixir:1.17.3-erlang-27.1-alpine-3.20.3 AS builder

WORKDIR /app
COPY mix.exs mix.lock ./
RUN mix deps.get --only prod

COPY . .
RUN mix compile
RUN mix release

FROM alpine:3.20.3
RUN apk add --no-cache openssl ncurses-libs libstdc++

COPY --from=builder /app/_build/prod/rel/my_app /app
ENV HOME=/app

CMD ["/app/bin/my_app", "start"]
```

**Multi-stage build**: Compile in full Elixir image, copy release to minimal Alpine runtime. Include only necessary runtime libraries (openssl for crypto, ncurses for remote console).

#### Clustering with libcluster

```elixir
# config/prod.exs
config :libcluster,
  topologies: [
    k8s: [
      strategy: Cluster.Strategy.Kubernetes,
      config: [
        kubernetes_selector: "app=my_app",
        kubernetes_node_basename: "my_app"
      ]
    ]
  ]

# For non-K8s, use DNS or EPMD strategies
config :libcluster,
  topologies: [
    dns: [
      strategy: Cluster.Strategy.DNSPoll,
      config: [service_name: "my_app", polling_interval: 5000]
    ]
  ]
```

**Clustering uses**: PubSub across nodes, global process registry, distributed task execution, session sharing. Required for multi-node Phoenix deployments.

#### Hot Code Upgrades

```elixir
# Basic release upgrade
# Old version running → build new release → deploy upgrade tarball

# Build upgrade release
MIX_ENV=prod mix release --upgrade

# Deploy upgrade
_build/prod/rel/my_app/bin/my_app upgrade 0.2.0

# In app, handle code change callback
defmodule MyApp do
  use Application

  def code_change(old_vsn, state, extra) do
    # Migrate state from old version to new version
    {:ok, state |> Map.put(:version, old_vsn)}
  end
end
```

**Requirements**: OTP application must specify modules with `@behaviour :gen_server` or implement `code_change/3`. Careful with state format changes between versions. For most apps, rolling restart via Kubernetes/Docker is simpler and safer than hot code upgrade.

---

### Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| **Global atoms** | `String.to_atom(user_input)` creates unlimited atoms, exhausting atom table | Use `String.to_existing_atom/1` or store as string |
| **Blocking the caller** | `GenServer.call(pid, :slow_work)` — blocks caller while server does 30s work | Use `GenServer.cast/2` for async work, or `handle_continue/2` for post-init work |
| **Nested with/1 without else** | `with {:ok, a} <- step1(), {:ok, b} <- step2() do ... end` — if step1 fails, returns `{:error, reason}` but you don't know which step | Always add `else` blocks, or ensure callers handle all error shapes |
| **Exposing Ecto schemas** | Controllers call `Repo.all(User)` directly — no business logic boundary | Route all DB access through Context modules |
| **Premature ETS** | Using ETS for data that fits in GenServer state (a few KB) | GenServer state is simpler, ETS only when state is large (MB+) or needs concurrent reads |
| **DynamicSupervisor for fixed children** | `DynamicSupervisor.start_child` used in Application.start for known children | Use regular Supervisor with static children list |
| **Ignoring handle_info** | Not implementing `handle_info/2` or using `{:noreply, state}` stub — messages silently disappear | Always handle or log unexpected messages; crash on truly unexpected ones |
| **Timeouts as control flow** | Using GenServer timeouts for periodic work | Use `Process.send_after/3` with explicit messages, or Oban cron jobs |
| **Logger in hot paths** | `Logger.info("..." <> expensive_format())` on every request | Use `Logger.info(fn -> "..." end)` for lazy evaluation; set appropriate log level |
| **Unsupervised tasks** | `Task.start(fn -> forever_loop() end)` — no supervision, no cleanup | Use `Task.Supervisor.start_child/2` or `{Task, fn -> ...}` in supervision tree |

---

### Troubleshooting

#### Process Bottleneck Detection

```bash
# Find processes with large message queues
:recon.proc_count(:message_queue_len, 5)

# Find processes using most memory
:recon.proc_count(:memory, 5)

# In production console
iex> :observer.start()  # GUI only if accessible

# Runtime process info
iex> Process.info(pid, [:message_queue_len, :memory, :reductions])
```

#### Common Runtime Issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| `{:timeout, {GenServer, :call, ...}}` | GenServer process is stuck or message queue is full | Check `handle_call` for blocking ops; increase timeout; convert to `handle_cast` + reply via `Process.send` |
| High memory, frequent GC | Large GenServer state or unreleased refs | Split state across processes; use ETS for large data; check for leaked monitors |
| `:ets.insert` errors | Table is full or wrong type | Check table type (`:set` rejects duplicate keys); increase table size |
| `Process exited: :normal` (unexpected) | Linked process exited with `:normal` (default exit reason) | Processes that should crash on failure must call `exit(:shutdown)` or use `spawn_monitor` |
| Slow Ecto queries | Missing indexes or N+1 queries | Use `EXPLAIN ANALYZE`; add indexes; use `Repo.preload` instead of per-item queries |
| LiveView disconnects | Network issue or client timeout | Check JS console for errors; verify WebSocket connection; increase `connect_info` timeout |
| Release fails to start | Missing runtime config or env vars | Check `config/runtime.exs`; run release in foreground (`bin/my_app foreground`) to see errors |
| Atom table exhaustion | `String.to_atom/1` on user input | Use `String.to_existing_atom/1`; never create atoms from external data |

---

### Implementation Checklist

**Design Phase**:
- [ ] Supervision tree designed with clear failure domains
- [ ] GenServer for stateful processes; Agent only for simple access
- [ ] Registry for dynamic process discovery
- [ ] ETS for large shared state (>MB); Process dict avoided
- [ ] Persistent term for read-heavy static data
- [ ] Contexts for business logic boundaries (no direct Repo calls from controllers)

**Development Phase**:
- [ ] `handle_call` for sync, `handle_cast` for async, `handle_info` for messages
- [ ] Timeouts on all `GenServer.call` (default 5000ms or explicit)
- [ ] `with/1` for happy-path chaining; else block always present
- [ ] Error tuples `{:ok, val}` / `{:error, reason}` throughout
- [ ] Structured logging via `Logger` with metadata
- [ ] Telemetry events on all critical execution paths
- [ ] IODATA/iolist patterns for string building (no concatenation)

**Testing Phase**:
- [ ] ExUnit with `describe` blocks and descriptive test names
- [ ] ExMachina factories for test data
- [ ] Property-based testing via StreamData
- [ ] Mox for behaviour-based mocking
- [ ] Phoenix.ConnTest and Phoenix.LiveViewTest for integration
- [ ] Tests isolated (no shared state between tests)

**Security Phase**:
- [ ] CSRF protection enabled (default in Phoenix)
- [ ] Ecto parameterizes all queries (safe by default)
- [ ] Raw SQL only via `Ecto.Adapters.SQL.query!` with `$1` placeholders
- [ ] Security headers: CSP, X-Frame-Options, X-Content-Type-Options
- [ ] LiveView: all `handle_event` validates user authorization
- [ ] Secrets via `System.get_env` or Vault (never hardcoded)

**Deployment Phase**:
- [ ] `mix release` for production builds
- [ ] `config/runtime.exs` for environment-specific config
- [ ] Docker multi-stage build (compile in Elixir image, run in Alpine)
- [ ] Clustering via libcluster for multi-node deployments
- [ ] BEAM VM tuned: `+P` for max processes, `+A` for async threads
- [ ] Observer/`recon` available for production debugging
- [ ] Database: Ecto with PgBouncer in transaction mode
