---
name: business-logic
description: God-tier business logic design: domain modeling, DDD (entities, value objects, aggregates, repositories), business rules engine, state machines, workflow orchestration, policy patterns, specification pattern, event-driven business logic, validation chains, and anti-corruption layers
license: MIT
compatibility: opencode
metadata:
  audience: backend-developers
  domain: backend
  paradigm: object-oriented
  capabilities:
    - domain-driven-design
    - business-rules-engine
    - state-machine-design
    - workflow-orchestration
    - policy-pattern
    - specification-pattern
    - event-driven-logic
    - validation-chains
    - anti-corruption-layer
    - domain-event-modeling
    - aggregate-design
    - repository-pattern
    - factory-pattern
    - service-layer-design
  prerequisites: none
  integrates_with:
    - backend-go
    - backend-python
    - backend-nodejs
    - backend-elixir
    - database-postgres
    - database-event-sourcing
---

## Business Logic Design — God-Tier

### Core Philosophy

> **Business logic is the soul of the application. Everything else — UI, database, infrastructure — is just plumbing.**
> Good business logic is: explicit (not hidden in controllers), testable (pure functions where possible), and expressive (reads like business requirements).

```
┌─────────────────────────────────────────────────────────────┐
│              BUSINESS LOGIC ARCHITECTURE                     │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              DOMAIN LAYER (Pure Business)             │   │
│  │  Entities │ Value Objects │ Aggregates │ Domain Events│   │
│  │  Business Rules │ Specifications │ State Machines     │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ▲                                   │
│                          │ depends on                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              APPLICATION LAYER (Orchestration)        │   │
│  │  Use Cases │ Command Handlers │ Query Handlers        │   │
│  │  Workflow Orchestrators │ Saga Coordinators           │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ▲                                   │
│                          │ depends on                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              INFRASTRUCTURE LAYER (Technical)         │   │
│  │  Repositories │ API Endpoints │ External Services     │   │
│  │  Database │ Message Queue │ Cache                     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Dependency Rule: Inner layers know NOTHING about outer     │
│  layers. Outer layers depend on inner layers.               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Domain-Driven Design (DDD)

### 1.1 Building Blocks

```
┌─────────────────────────────────────────────────────────┐
│              DDD BUILDING BLOCKS                         │
│                                                         │
│  ENTITY                                                 │
│  • Has identity (ID)                                    │
│  • Mutable state                                        │
│  • Business invariants enforced                         │
│  • Example: User, Order, Product                        │
│                                                         │
│  VALUE OBJECT                                           │
│  • No identity — defined by attributes                  │
│  • Immutable                                            │
│  • Self-validating                                      │
│  • Example: Money, Address, Email, DateRange            │
│                                                         │
│  AGGREGATE                                              │
│  • Cluster of entities + value objects                  │
│  • One aggregate root (entry point)                     │
│  • Invariants enforced within boundary                  │
│  • Transaction boundary                                 │
│  • Example: Order (root) + OrderItems (children)        │
│                                                         │
│  DOMAIN EVENT                                           │
│  • Something that happened in the domain                │
│  • Immutable, past tense                                │
│  • Example: OrderPlaced, PaymentReceived, UserRegistered│
│                                                         │
│  REPOSITORY                                             │
│  • Collection-like interface for aggregates             │
│  • Abstracts persistence                                │
│  • Returns aggregates, not raw data                     │
│  • Example: OrderRepository.GetById(id)                 │
│                                                         │
│  DOMAIN SERVICE                                         │
│  • Business logic that doesn't fit in one entity        │
│  • Stateless, operates on multiple aggregates           │
│  • Example: TransferService.Transfer(from, to, amount)  │
│                                                         │
│  FACTORY                                                │
│  • Creates complex aggregates                           │
│  • Ensures invariants at creation                       │
│  • Example: OrderFactory.CreateFromCart(cart)           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Aggregate Design Rules

| Rule | Why | Example |
|------|-----|---------|
| **Small aggregates** | Less contention, easier concurrency | Order ≠ Order + Inventory + Shipping |
| **Reference by ID** | Don't embed other aggregates | Order.CustomerId, not Order.Customer |
| **One writer** | Avoid conflicts | Only Order aggregate modifies OrderItems |
| **Eventual consistency** | Cross-aggregate updates async | Order placed → Inventory updated later |
| **Invariants within boundary** | Root enforces all rules | Order.Total = sum(OrderItems) always |

### 1.3 Value Object Patterns

```typescript
// Immutable Value Object
class Money {
  constructor(
    readonly amount: number,
    readonly currency: string
  ) {
    if (amount < 0) throw new Error("Amount cannot be negative");
    if (!["USD", "EUR", "IDR"].includes(currency)) {
      throw new Error("Unsupported currency");
    }
  }

  add(other: Money): Money {
    if (this.currency !== other.currency) {
      throw new Error("Cannot add different currencies");
    }
    return new Money(this.amount + other.amount, this.currency);
  }

  multiply(factor: number): Money {
    return new Money(this.amount * factor, this.currency);
  }

  equals(other: Money): boolean {
    return this.amount === other.amount && this.currency === other.currency;
  }
}

// Usage
const price = new Money(100000, "IDR");
const tax = price.multiply(0.11);
const total = price.add(tax);
```

---

## 2. Business Rules Engine

### 2.1 Rule Pattern

```typescript
interface Rule<T> {
  isSatisfiedBy(candidate: T): boolean;
  errorMessage(): string;
}

// Composite rules
class AndRule<T> implements Rule<T> {
  constructor(private rules: Rule<T>[]) {}

  isSatisfiedBy(candidate: T): boolean {
    return this.rules.every(r => r.isSatisfiedBy(candidate));
  }

  errorMessage(): string {
    return this.rules
      .filter(r => !r.isSatisfiedBy(/* candidate */))
      .map(r => r.errorMessage())
      .join("; ");
  }
}

class OrRule<T> implements Rule<T> {
  constructor(private rules: Rule<T>[]) {}

  isSatisfiedBy(candidate: T): boolean {
    return this.rules.some(r => r.isSatisfiedBy(candidate));
  }

  errorMessage(): string {
    return "None of the conditions were met";
  }
}

// Concrete rules
class MinimumAgeRule implements Rule<User> {
  constructor(private minAge: number) {}

  isSatisfiedBy(user: User): boolean {
    return user.age >= this.minAge;
  }

  errorMessage(): string {
    return `User must be at least ${this.minAge} years old`;
  }
}

class SufficientBalanceRule implements Rule<Order> {
  constructor(private wallet: Wallet) {}

  isSatisfiedBy(order: Order): boolean {
    return this.wallet.balance.greaterThanOrEqual(order.total);
  }

  errorMessage(): string {
    return "Insufficient balance";
  }
}

// Usage
const rules = new AndRule<User>([
  new MinimumAgeRule(18),
  new EmailVerifiedRule(),
  new NotSuspendedRule()
]);

if (!rules.isSatisfiedBy(user)) {
  throw new BusinessRuleViolation(rules.errorMessage());
}
```

### 2.2 Decision Table Pattern

For complex business rules with many conditions:

```
┌─────────────────────────────────────────────────────────┐
│              DECISION TABLE: Loan Approval               │
│                                                         │
│  Conditions          Rule 1  Rule 2  Rule 3  Rule 4     │
│  ───────────────────────────────────────────────────── │
│  Credit Score > 700   Y       Y       N       N        │
│  Income > 50M         Y       N       Y       N        │
│  Employment > 2yr     Y       Y       Y       N        │
│  Existing Debt < 30%  Y       N       N       N        │
│  ───────────────────────────────────────────────────── │
│  Decision          APPROVE  REVIEW  REVIEW  REJECT     │
│                                                         │
│  Implementation:                                        │
│  const rules = [                                        │
│    { conditions: [c1, c2, c3, c4], action: "APPROVE" },│
│    { conditions: [c1, c2, c3, !c4], action: "REVIEW" },│
│    { conditions: [!c1, c2, c3, any], action: "REVIEW" },│
│    { conditions: [any, any, any, any], action: "REJECT" }│
│  ];                                                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 3. State Machine Design

### 3.1 State Machine Pattern

```typescript
type OrderStatus = "DRAFT" | "SUBMITTED" | "PAID" | "SHIPPED" | "DELIVERED" | "CANCELLED" | "REFUNDED";

interface Transition {
  from: OrderStatus;
  to: OrderStatus;
  event: string;
  guard?: (order: Order) => boolean;
  action?: (order: Order) => void;
}

const transitions: Transition[] = [
  { from: "DRAFT", to: "SUBMITTED", event: "SUBMIT", guard: (o) => o.items.length > 0 },
  { from: "SUBMITTED", to: "PAID", event: "PAY", guard: (o) => o.paymentValid },
  { from: "PAID", to: "SHIPPED", event: "SHIP" },
  { from: "SHIPPED", to: "DELIVERED", event: "DELIVER" },
  { from: "SUBMITTED", to: "CANCELLED", event: "CANCEL", guard: (o) => !o.paid },
  { from: "PAID", to: "REFUNDED", event: "REFUND" },
  { from: "SHIPPED", to: "REFUNDED", event: "REFUND" },
];

class OrderStateMachine {
  private current: OrderStatus;

  constructor(initial: OrderStatus = "DRAFT") {
    this.current = initial;
  }

  canTransition(event: string): boolean {
    return transitions.some(
      t => t.from === this.current && t.event === event && (!t.guard || t.guard(/* order */))
    );
  }

  transition(event: string, order: Order): OrderStatus {
    const t = transitions.find(
      t => t.from === this.current && t.event === event
    );
    if (!t) throw new InvalidTransitionError(`Cannot ${event} from ${this.current}`);
    if (t.guard && !t.guard(order)) throw new GuardFailedError(`Guard failed for ${event}`);

    if (t.action) t.action(order);
    this.current = t.to;
    return this.current;
  }
}
```

### 3.2 State Machine Visualization

```
┌─────────────────────────────────────────────────────────┐
│              ORDER STATE MACHINE                         │
│                                                         │
│  ┌───────┐  SUBMIT   ┌───────────┐  PAY   ┌──────┐     │
│  │ DRAFT │──────────▶│ SUBMITTED │───────▶│ PAID │     │
│  └───────┘          └─────┬─────┘        └──┬───┘     │
│                           │                 │          │
│                      CANCEL│            SHIP │          │
│                           ▼                 ▼          │
│                     ┌───────────┐      ┌─────────┐     │
│                     │ CANCELLED │      │ SHIPPED │     │
│                     └───────────┘      └────┬────┘     │
│                                             │          │
│                                        DELIVER│        │
│                                             ▼          │
│                                       ┌───────────┐    │
│                                       │ DELIVERED │    │
│                                       └───────────┘    │
│                                                         │
│  PAID/SHIPPED ──REFUND──▶ REFUNDED                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Workflow Orchestration

### 4.1 Saga Pattern (Distributed Transactions)

```
┌─────────────────────────────────────────────────────────┐
│              SAGA: Order Fulfillment                     │
│                                                         │
│  Step 1: Create Order                                   │
│    → Compensating: Cancel Order                         │
│                                                         │
│  Step 2: Reserve Inventory                              │
│    → Compensating: Release Inventory                    │
│                                                         │
│  Step 3: Process Payment                                │
│    → Compensating: Refund Payment                       │
│                                                         │
│  Step 4: Create Shipment                                │
│    → Compensating: Cancel Shipment                      │
│                                                         │
│  Step 5: Update Order Status to SHIPPED                 │
│    → Compensating: Revert Order Status                  │
│                                                         │
│  If Step 3 fails:                                       │
│    → Execute compensating: Release Inventory            │
│    → Execute compensating: Cancel Order                 │
│    → Saga complete (failed)                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Workflow Engine Pattern

```typescript
interface Step<T> {
  name: string;
  execute: (ctx: T) => Promise<void>;
  compensate?: (ctx: T) => Promise<void>;
  retry?: number;
}

class WorkflowEngine<T> {
  private steps: Step<T>[] = [];

  addStep(step: Step<T>): this {
    this.steps.push(step);
    return this;
  }

  async execute(ctx: T): Promise<void> {
    const completed: Step<T>[] = [];

    for (const step of this.steps) {
      try {
        await this.executeWithRetry(step, ctx);
        completed.push(step);
      } catch (error) {
        // Compensate in reverse order
        for (const c of completed.reverse()) {
          if (c.compensate) {
            await c.compensate(ctx);
          }
        }
        throw error;
      }
    }
  }

  private async executeWithRetry(step: Step<T>, ctx: T, maxRetries = 3): Promise<void> {
    let lastError: Error;
    for (let i = 0; i <= maxRetries; i++) {
      try {
        await step.execute(ctx);
        return;
      } catch (e) {
        lastError = e as Error;
        if (i < maxRetries) await this.delay(1000 * Math.pow(2, i));
      }
    }
    throw lastError!;
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

---

## 5. Specification Pattern

Composable business predicates:

```typescript
interface Specification<T> {
  isSatisfiedBy(candidate: T): boolean;
  and(other: Specification<T>): Specification<T>;
  or(other: Specification<T>): Specification<T>;
  not(): Specification<T>;
}

class CompositeSpecification<T> implements Specification<T> {
  isSatisfiedBy(candidate: T): boolean {
    throw new Error("Abstract method");
  }

  and(other: Specification<T>): Specification<T> {
    return new AndSpecification(this, other);
  }

  or(other: Specification<T>): Specification<T> {
    return new OrSpecification(this, other);
  }

  not(): Specification<T> {
    return new NotSpecification(this);
  }
}

// Concrete specifications
class PremiumCustomerSpec extends CompositeSpecification<Customer> {
  isSatisfiedBy(c: Customer): boolean {
    return c.totalPurchases > 10000000 && c.yearsAsCustomer >= 2;
  }
}

class ActiveOrderSpec extends CompositeSpecification<Order> {
  isSatisfiedBy(o: Order): boolean {
    return ["SUBMITTED", "PAID", "SHIPPED"].includes(o.status);
  }
}

// Composable usage
const eligibleForDiscount = new PremiumCustomerSpec()
  .and(new ActiveOrderSpec());

if (eligibleForDiscount.isSatisfiedBy(customer)) {
  applyDiscount(order, 0.15);
}
```

---

## 6. Validation Chains

```typescript
class ValidationChain<T> {
  private rules: Array<(value: T) => string | null> = [];

  addRule(rule: (value: T) => string | null): this {
    this.rules.push(rule);
    return this;
  }

  validate(value: T): string[] {
    return this.rules
      .map(rule => rule(value))
      .filter((msg): msg is string => msg !== null);
  }

  isValid(value: T): boolean {
    return this.validate(value).length === 0;
  }
}

// Usage
const orderValidator = new ValidationChain<Order>()
  .addRule(o => o.items.length === 0 ? "Order must have at least one item" : null)
  .addRule(o => o.total.amount <= 0 ? "Total must be positive" : null)
  .addRule(o => !o.shippingAddress ? "Shipping address is required" : null)
  .addRule(o => o.items.some(i => i.quantity <= 0) ? "All quantities must be positive" : null);

const errors = orderValidator.validate(order);
if (errors.length > 0) {
  throw new ValidationError(errors);
}
```

---

## 7. Anti-Corruption Layer (ACL)

When integrating with external systems or legacy code:

```
┌─────────────────────────────────────────────────────────┐
│              ANTI-CORRUPTION LAYER                       │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │   YOUR       │    │     ACL      │    │ EXTERNAL  │ │
│  │   DOMAIN     │◄──►│  (Adapter +  │◄──►│  SYSTEM   │ │
│  │   (Clean)    │    │  Translator) │    │ (Legacy/  │ │
│  │              │    │              │    │  3rd Party)│ │
│  └──────────────┘    └──────────────┘    └───────────┘ │
│                                                         │
│  ACL Responsibilities:                                  │
│  1. Translate external models → domain models           │
│  2. Translate domain models → external models           │
│  3. Handle external system quirks                       │
│  4. Protect domain from external changes                │
│  5. Provide stable interface despite external changes   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 8. Event-Driven Business Logic

```typescript
// Domain Events
interface DomainEvent {
  type: string;
  aggregateId: string;
  timestamp: Date;
  data: Record<string, unknown>;
}

// Event Handler
interface EventHandler<T extends DomainEvent> {
  handles: string;
  handle: (event: T) => Promise<void>;
}

// Event Sourcing Lite
class AggregateRoot {
  private uncommittedEvents: DomainEvent[] = [];

  protected raiseEvent(event: DomainEvent): void {
    this.applyEvent(event);
    this.uncommittedEvents.push(event);
  }

  protected applyEvent(event: DomainEvent): void {
    // Apply event to state
  }

  getUncommittedEvents(): DomainEvent[] {
    return [...this.uncommittedEvents];
  }

  markEventsAsCommitted(): void {
    this.uncommittedEvents = [];
  }
}

// Usage
class Order extends AggregateRoot {
  placeOrder(items: OrderItem[], customer: Customer): void {
    if (items.length === 0) throw new Error("Order must have items");

    this.raiseEvent({
      type: "OrderPlaced",
      aggregateId: this.id,
      timestamp: new Date(),
      data: { items, customerId: customer.id }
    });
  }

  protected applyEvent(event: DomainEvent): void {
    switch (event.type) {
      case "OrderPlaced":
        this.status = "SUBMITTED";
        this.items = event.data.items as OrderItem[];
        break;
    }
  }
}
```

---

## 9. Business Logic Anti-Patterns

| Anti-Pattern | Symptom | Fix |
|--------------|---------|-----|
| **Anemic Domain Model** | Entities are just getters/setters | Move logic into entities |
| **Transaction Script** | All logic in service layer | Use rich domain model |
| **God Service** | One service does everything | Split by aggregate/bounded context |
| **Logic in Controller** | Business rules in HTTP handlers | Move to domain/application layer |
| **Logic in Repository** | Queries contain business rules | Repositories return data, domain applies rules |
| **Primitive Obsession** | Using strings/numbers for domain concepts | Create value objects (Money, Email, etc.) |
| **Feature Envy** | Method uses another class's data more than its own | Move method to the class it envies |
| **Shotgun Surgery** | One change requires edits in many places | Consolidate logic in one place |

---

## 10. Business Logic Design Checklist

- [ ] **Domain model identified**: Entities, value objects, aggregates defined
- [ ] **Invariants enforced**: Business rules cannot be violated
- [ ] **No anemic models**: Entities contain behavior, not just data
- [ ] **Value objects immutable**: No setters, created via constructor
- [ ] **Aggregate boundaries clear**: Transaction boundaries defined
- [ ] **Repositories return aggregates**: Not raw data or DTOs
- [ ] **Domain events raised**: Significant state changes emit events
- [ ] **Anti-corruption layer**: External systems isolated from domain
- [ ] **State machine explicit**: Valid transitions defined and enforced
- [ ] **Validation at boundary**: Input validated before entering domain
- [ ] **Pure functions where possible**: Business rules as pure functions
- [ ] **Testable in isolation**: Domain logic testable without infrastructure
