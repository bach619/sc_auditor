---
name: algorithm
description: God-tier algorithm design & analysis: complexity theory (Big-O, amortized, space), data structures (arrays, trees, graphs, heaps, tries, segment trees), algorithm paradigms (divide & conquer, DP, greedy, backtracking, branch & bound), graph algorithms, string algorithms, computational geometry, number theory, randomized algorithms, and competitive programming patterns
license: MIT
compatibility: opencode
metadata:
  audience: all-developers
  domain: computer-science
  paradigm: algorithmic
  capabilities:
    - complexity-analysis
    - data-structure-design
    - divide-and-conquer
    - dynamic-programming
    - greedy-algorithms
    - backtracking
    - graph-algorithms
    - string-algorithms
    - computational-geometry
    - number-theory
    - randomized-algorithms
    - competitive-programming
    - algorithm-optimization
    - space-time-tradeoffs
  prerequisites: none
  integrates_with:
    - math-ml
    - math-hpc
    - backend-go
    - backend-python
    - systems-embedded
---

## Algorithm Design & Analysis — God-Tier

### Core Philosophy

> **Algorithms are not about memorizing code. They are about recognizing patterns and applying the right abstraction.**
> Every problem can be reduced to a known algorithmic pattern. The skill is in the reduction.

```
┌─────────────────────────────────────────────────────────────┐
│              ALGORITHM SELECTION DECISION TREE               │
│                                                              │
│  What's the problem type?                                    │
│                                                              │
│  ┌─ Sorting/Searching ──▶ Binary Search, Quick/Merge Sort   │
│  │                                                             │
│  ├─ Optimization ────────▶ DP, Greedy, Branch & Bound       │
│  │                                                             │
│  ├─ Connectivity/Path ───▶ BFS, DFS, Dijkstra, Union-Find   │
│  │                                                             │
│  ├─ String Matching ─────▶ KMP, Rabin-Karp, Trie, Suffix    │
│  │                                                             │
│  ├─ Counting/Ranking ────▶ BIT, Segment Tree, Order Statistic│
│  │                                                             │
│  ├─ Geometry ────────────▶ Sweep Line, Convex Hull, Voronoi │
│  │                                                             │
│  └─ Number Theory ───────▶ GCD, Sieve, Modular Arithmetic   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Complexity Analysis

### 1.1 Big-O Notation — Complete Reference

```
┌─────────────────────────────────────────────────────────┐
│              COMPLEXITY HIERARCHY                         │
│                                                         │
│  O(1)          Constant          Hash lookup            │
│  O(log n)      Logarithmic       Binary search          │
│  O(√n)         Square root       Trial division         │
│  O(n)          Linear            Array scan             │
│  O(n log n)    Linearithmic      Merge sort             │
│  O(n²)         Quadratic         Bubble sort            │
│  O(n³)         Cubic             Matrix multiply        │
│  O(2ⁿ)         Exponential       Subset generation      │
│  O(n!)         Factorial         Permutation            │
│                                                         │
│  Acceptable for production: O(1), O(log n), O(n),      │
│  O(n log n)                                           │
│  Acceptable for n < 1000: O(n²)                        │
│  Acceptable for n < 20: O(2ⁿ), O(n!)                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Amortized Analysis

| Technique | When to Use | Example |
|-----------|-------------|---------|
| **Aggregate** | Total cost / n operations | Dynamic array append |
| **Accounting** | Pre-pay for expensive ops | Stack with multipop |
| **Potential** | Energy function on state | Fibonacci heap |

### 1.3 Space-Time Tradeoffs

```
┌─────────────────────────────────────────────────────────┐
│              SPACE-TIME TRADEOFF PATTERNS                │
│                                                         │
│  MORE SPACE → LESS TIME:                                │
│  • Memoization / Caching                                │
│  • Lookup tables                                      │
│  • Index structures (B-tree, Hash)                      │
│  • Precomputation                                       │
│                                                         │
│  LESS SPACE → MORE TIME:                                │
│  • In-place algorithms                                  │
│  • Streaming / One-pass                                 │
│  • Bit manipulation                                     │
│  • Generator / Lazy evaluation                          │
│                                                         │
│  BALANCED:                                              │
│  • Bloom filters (probabilistic, small space)           │
│  • LRU Cache (bounded space, fast access)               │
│  • Segment Tree (O(n) space, O(log n) query)           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Data Structures

### 2.1 Core Data Structures — When to Use

| Structure | Access | Search | Insert | Delete | Best For |
|-----------|--------|--------|--------|--------|----------|
| **Array** | O(1) | O(n) | O(n) | O(n) | Random access, cache-friendly |
| **Linked List** | O(n) | O(n) | O(1) | O(1) | Frequent insert/delete |
| **Stack** | O(1)* | O(n) | O(1) | O(1) | Undo, parsing, DFS |
| **Queue** | O(1)* | O(n) | O(1) | O(1) | BFS, scheduling |
| **Hash Table** | N/A | O(1)* | O(1)* | O(1)* | Lookup, dedup, counting |
| **BST** | O(log n)* | O(log n)* | O(log n)* | O(log n)* | Ordered data |
| **AVL/Red-Black** | O(log n) | O(log n) | O(log n) | O(log n) | Balanced ordered data |
| **Heap** | O(1)* | O(n) | O(log n) | O(log n)* | Priority queue, top-k |
| **Trie** | O(L) | O(L) | O(L) | O(L) | Prefix search, autocomplete |
| **Segment Tree** | N/A | O(log n) | O(log n) | O(log n) | Range queries |
| **BIT/Fenwick** | N/A | O(log n) | O(log n) | O(log n) | Prefix sums |
| **Union-Find** | N/A | O(α(n)) | N/A | O(α(n)) | Connectivity, clustering |
| **Bloom Filter** | N/A | O(k) | O(k) | N/A | Membership test (probabilistic) |

*amortized or average case

### 2.2 Advanced Data Structures

```
┌─────────────────────────────────────────────────────────┐
│              ADVANCED DATA STRUCTURES                    │
│                                                         │
│  Structure          Use Case              Complexity    │
│  ───────────────────────────────────────────────────── │
│  Suffix Array       String search         O(n log n)    │
│  Suffix Tree        Pattern matching      O(n) build    │
│  K-D Tree           Spatial search        O(log n)*     │
│  Skip List          Concurrent ordered    O(log n)      │
│  Treap              Randomized BST        O(log n)      │
│  Splay Tree         Self-adjusting        O(log n)*     │
│  B-Tree             Disk-based storage    O(log n)      │
│  Disjoint Set       Union-Find            O(α(n))       │
│  Sparse Table       RMQ (static)          O(1) query    │
│  Deque              Sliding window        O(1)          │
│  Monotonic Stack    Next greater element  O(n) total    │
│  Monotonic Queue    Sliding window max    O(n) total    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Algorithm Paradigms

### 3.1 Divide & Conquer

```
┌─────────────────────────────────────────────────────────┐
│              DIVIDE & CONQUER PATTERN                    │
│                                                         │
│  1. DIVIDE: Split problem into smaller sub-problems     │
│  2. CONQUER: Solve sub-problems recursively             │
│  3. COMBINE: Merge solutions into final answer          │
│                                                         │
│  Master Theorem: T(n) = aT(n/b) + f(n)                  │
│  Case 1: f(n) < n^(log_b a) → T(n) = Θ(n^(log_b a))    │
│  Case 2: f(n) = n^(log_b a) → T(n) = Θ(n^(log_b a) log n)│
│  Case 3: f(n) > n^(log_b a) → T(n) = Θ(f(n))           │
│                                                         │
│  Classic Examples:                                      │
│  • Merge Sort: T(n) = 2T(n/2) + O(n) → O(n log n)      │
│  • Binary Search: T(n) = T(n/2) + O(1) → O(log n)      │
│  • Strassen's Matrix: T(n) = 7T(n/2) + O(n²) → O(n^2.81)│
│  • FFT: T(n) = 2T(n/2) + O(n) → O(n log n)             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Dynamic Programming

**When to use:**
- Overlapping subproblems
- Optimal substructure
- Can be solved recursively with memoization

**DP Pattern Library:**

| Pattern | Problem Type | State Definition | Transition |
|---------|-------------|------------------|------------|
| **Linear DP** | Sequence, subsequence | `dp[i]` = best using first i | `dp[i] = max(dp[i-1], ...)` |
| **Interval DP** | Range optimization | `dp[i][j]` = best in range [i,j] | `dp[i][j] = min/max(dp[i][k] + dp[k+1][j])` |
| **Tree DP** | Tree optimization | `dp[u]` = best in subtree u | `dp[u] = combine(dp[v] for v in children)` |
| **Bitmask DP** | Subset, permutation | `dp[mask]` = best for subset mask | `dp[mask] = min(dp[mask^(1<<i)] + cost)` |
| **Digit DP** | Counting with digit constraints | `dp[pos][tight][state]` | Iterate digits 0-9 |
| **DP on Broken Profile** | Tiling, grid | `dp[row][profile]` | Transition between rows |
| **Knapsack** | Resource allocation | `dp[i][w]` = best value with weight w | `dp[i][w] = max(dp[i-1][w], dp[i-1][w-wt[i]] + val[i])` |
| **LCS/LIS** | String/sequence | `dp[i][j]` = LCS of first i,j | Match/mismatch cases |

**DP Optimization Techniques:**

| Technique | Reduces | When Applicable |
|-----------|---------|-----------------|
| **Space Optimization** | O(n²) → O(n) | Only need previous row |
| **Prefix Sums** | O(n) → O(1) query | Range sum queries |
| **Monotonic Queue** | O(n²) → O(n) | Sliding window DP |
| **Convex Hull Trick** | O(n²) → O(n log n) | Linear function optimization |
| **Divide & Conquer Optimization** | O(n²) → O(n log n) | Opt[k] is monotonic |
| **Knuth Optimization** | O(n³) → O(n²) | Opt[i][j-1] ≤ Opt[i][j] ≤ Opt[i+1][j] |

### 3.3 Greedy Algorithms

**When greedy works:**
- Greedy choice property: locally optimal → globally optimal
- Optimal substructure

**Classic Greedy Problems:**

| Problem | Greedy Strategy | Proof Technique |
|---------|-----------------|-----------------|
| Activity Selection | Earliest finish time | Exchange argument |
| Huffman Coding | Merge smallest frequencies | Induction |
| Kruskal's MST | Smallest edge first | Cut property |
| Dijkstra's | Smallest distance first | Induction |
| Fractional Knapsack | Highest value/weight ratio | Exchange argument |
| Interval Coloring | Earliest start, assign first available | Pigeonhole |

### 3.4 Backtracking

**Template:**
```
function backtrack(state):
    if is_solution(state):
        record(state)
        return

    for choice in candidates(state):
        if is_valid(choice, state):
            make_choice(choice, state)
            backtrack(state)
            undo_choice(choice, state)  // backtrack
```

**Pruning Techniques:**
- Constraint propagation
- Forward checking
- Branch and bound (use upper/lower bounds to prune)
- Symmetry breaking

---

## 4. Graph Algorithms

### 4.1 Graph Representation

| Representation | Space | Edge Lookup | Iterate Neighbors | Best For |
|---------------|-------|-------------|-------------------|----------|
| Adjacency Matrix | O(V²) | O(1) | O(V) | Dense graphs |
| Adjacency List | O(V+E) | O(degree) | O(degree) | Sparse graphs |
| Edge List | O(E) | O(E) | O(E) | Edge-centric ops |

### 4.2 Traversal

| Algorithm | Time | Space | Use Case |
|-----------|------|-------|----------|
| **BFS** | O(V+E) | O(V) | Shortest path (unweighted), level-order |
| **DFS** | O(V+E) | O(V) | Connectivity, topological sort, cycles |
| **Iterative DFS** | O(V+E) | O(V) | Avoid recursion depth limits |

### 4.3 Shortest Path

| Algorithm | Time | Space | Constraints |
|-----------|------|-------|-------------|
| **Dijkstra** | O((V+E) log V) | O(V) | Non-negative weights |
| **Bellman-Ford** | O(VE) | O(V) | Negative weights, detect negative cycles |
| **Floyd-Warshall** | O(V³) | O(V²) | All-pairs, negative weights |
| **SPFA** | O(kE) avg | O(V) | Negative weights (faster than BF avg) |
| **A*** | O(E) avg | O(V) | Heuristic-guided, optimal if admissible |
| **0-1 BFS** | O(V+E) | O(V) | Weights are 0 or 1 |

### 4.4 Minimum Spanning Tree

| Algorithm | Time | Best For |
|-----------|------|----------|
| **Kruskal's** | O(E log E) | Sparse graphs |
| **Prim's** | O((V+E) log V) | Dense graphs |
| **Boruvka's** | O(E log V) | Parallel MST |

### 4.5 Network Flow

| Algorithm | Time | Use Case |
|-----------|------|----------|
| **Ford-Fulkerson** | O(E * max_flow) | Simple, small capacities |
| **Edmonds-Karp** | O(VE²) | BFS-based, guaranteed termination |
| **Dinic's** | O(V²E) | General purpose, fast in practice |
| **Min-Cost Max-Flow** | O(V²E log V) | Flow with costs |

### 4.6 Graph Properties

| Property | Algorithm | Time |
|----------|-----------|------|
| **Cycle Detection** | DFS | O(V+E) |
| **Bipartite Check** | BFS/DFS 2-coloring | O(V+E) |
| **Topological Sort** | DFS / Kahn's | O(V+E) |
| **Strongly Connected** | Kosaraju's / Tarjan's | O(V+E) |
| **Articulation Points** | DFS with low-link | O(V+E) |
| **Bridge Detection** | DFS with low-link | O(V+E) |
| **Eulerian Path** | Degree check + Hierholzer's | O(V+E) |

---

## 5. String Algorithms

| Algorithm | Time | Space | Use Case |
|-----------|------|-------|----------|
| **KMP** | O(n+m) | O(m) | Pattern matching |
| **Rabin-Karp** | O(n+m) avg | O(1) | Multiple pattern matching |
| **Z-Algorithm** | O(n) | O(n) | Pattern matching, LCP |
| **Aho-Corasick** | O(n + m + z) | O(m * alphabet) | Multiple patterns |
| **Manacher's** | O(n) | O(n) | Longest palindromic substring |
| **Suffix Array** | O(n log n) | O(n) | Pattern matching, LCP |
| **Suffix Automaton** | O(n) | O(n) | All substrings, distinct count |

---

## 6. Number Theory

| Concept | Algorithm | Time | Use Case |
|---------|-----------|------|----------|
| **GCD** | Euclidean | O(log min(a,b)) | Simplification |
| **Extended GCD** | Extended Euclidean | O(log min(a,b)) | Modular inverse |
| **Modular Inverse** | Fermat's / Extended GCD | O(log MOD) | Division mod p |
| **Prime Sieve** | Sieve of Eratosthenes | O(n log log n) | Prime generation |
| **Modular Exponentiation** | Binary exponentiation | O(log n) | Power mod p |
| **Chinese Remainder** | CRT | O(log n) | System of congruences |
| **Euler's Totient** | Sieve-based | O(n log log n) | Counting coprimes |
| **Miller-Rabin** | Probabilistic | O(k log³ n) | Primality test |

---

## 7. Computational Geometry

| Problem | Algorithm | Time |
|---------|-----------|------|
| **Convex Hull** | Graham Scan / Monotone Chain | O(n log n) |
| **Line Intersection** | Cross product | O(1) |
| **Point in Polygon** | Ray casting | O(n) |
| **Closest Pair** | Divide & Conquer | O(n log n) |
| **Sweep Line** | Event processing | O(n log n) |
| **Voronoi Diagram** | Fortune's Algorithm | O(n log n) |

---

## 8. Randomized Algorithms

| Algorithm | Type | Expected Time | Use Case |
|-----------|------|---------------|----------|
| **QuickSelect** | Monte Carlo | O(n) | k-th element |
| **Randomized QuickSort** | Las Vegas | O(n log n) | Sorting |
| **Bloom Filter** | Monte Carlo | O(k) | Membership test |
| **MinHash** | Monte Carlo | O(n) | Jaccard similarity |
| **Reservoir Sampling** | Las Vegas | O(n) | Random sample from stream |

---

## 9. Competitive Programming Patterns

### 9.1 Common Problem Types

| Pattern | Recognition | Solution |
|---------|-------------|----------|
| **Two Pointers** | Sorted array, pair sum | Left/right pointers converge |
| **Sliding Window** | Subarray/substring constraint | Expand/shrink window |
| **Binary Search on Answer** | Monotonic property | BS on result space |
| **Meet in the Middle** | n ≤ 40, exponential | Split into two halves |
| **Mo's Algorithm** | Offline range queries | Sort queries by block |
| **Coordinate Compression** | Large range, few points | Map to 0..n-1 |
| **Difference Array** | Range updates, point query | Prefix sum of differences |

### 9.2 Debugging Checklist

- [ ] Off-by-one errors (0-indexed vs 1-indexed)
- [ ] Integer overflow (use 64-bit for sums)
- [ ] Edge cases: empty input, single element, all same
- [ ] Negative numbers handling
- [ ] Modulo arithmetic (apply at each step)
- [ ] Graph: disconnected components, self-loops, multi-edges
- [ ] Recursion: base case, stack overflow
- [ ] Sorting: stable vs unstable, custom comparator

---

## 10. Algorithm Design Checklist

Before implementing any algorithm:

- [ ] **Problem type identified**: Which paradigm applies?
- [ ] **Constraints analyzed**: n size, time limit, memory limit
- [ ] **Complexity target**: What Big-O is acceptable?
- [ ] **Edge cases listed**: Empty, single, max, min, negative
- [ ] **Data structure chosen**: Optimal for access pattern?
- [ ] **Space-time tradeoff considered**: Can we use more space for less time?
- [ ] **Overflow checked**: Will intermediate values exceed limits?
- [ ] **Modulo applied**: If required, at every arithmetic step?
- [ ] **Test cases prepared**: Small, medium, large, edge cases
