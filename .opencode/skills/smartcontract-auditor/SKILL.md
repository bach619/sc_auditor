---
name: smartcontract-auditor
description: God-tier smart contract security auditing: EVM/Solidity vulnerabilities (reentrancy, overflow, access control, oracle manipulation, flash loan attacks), audit methodology, attack vector analysis, gas optimization, formal verification, Slither/Mythril/Echidna usage, and professional audit report generation
license: MIT
compatibility: opencode
metadata:
  audience: security-auditors
  domain: blockchain-security
  paradigm: security-analysis
  capabilities:
    - vulnerability-detection
    - reentrancy-analysis
    - access-control-audit
    - oracle-manipulation-detection
    - flash-loan-attack-analysis
    - gas-optimization
    - formal-verification
    - static-analysis
    - fuzzing-testing
    - invariant-testing
    - audit-report-generation
    - evm-bytecode-analysis
    - upgradeable-contract-audit
    - defi-protocol-audit
    - nft-contract-audit
    - cross-chain-security
  prerequisites:
    - security-audit
  integrates_with:
    - security-audit
    - security-crypto
    - backend-go
    - backend-python
---

## Smart Contract Auditor — God-Tier

### Core Philosophy

> **In smart contracts, bugs are not inconveniences — they are bank robberies.**
> Once deployed, code is immutable. There is no "patch tomorrow." There is no "rollback."
> Every line of code is a potential million-dollar vulnerability.

```
┌─────────────────────────────────────────────────────────────┐
│              SMART CONTRACT AUDIT LIFECYCLE                  │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │  SCOPE   │──▶│  STATIC  │──▶│ DYNAMIC  │──▶│  MANUAL  │  │
│  │  & PLAN  │   │ ANALYSIS │   │ TESTING  │   │  REVIEW  │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
│       │                                              │      │
│       ▼                                              ▼      │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ REPORT   │◀──│  REMEDI  │◀──│  FORMAL  │◀──│  DEEP    │  │
│  │ & DELIVER│   │  ATION   │   │  VERIFY  │   │  DIVE    │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
│                                                              │
│  Severity Classification:                                    │
│  CRITICAL  → Direct fund loss possible                       │
│  HIGH      → Fund loss under specific conditions             │
│  MEDIUM    → Unexpected behavior, indirect loss              │
│  LOW       → Best practice violation, minor issue            │
│  INFO      → Gas optimization, code style                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Vulnerability Taxonomy

### 1.1 Critical Vulnerabilities

```
┌─────────────────────────────────────────────────────────┐
│              CRITICAL VULNERABILITIES                    │
│                                                         │
│  1. REENTRANCY                                          │
│     External call before state update                   │
│     Impact: Drain all funds                             │
│     Fix: Checks-Effects-Interactions pattern            │
│                                                         │
│  2. ACCESS CONTROL                                      │
│     Missing or incorrect authorization                  │
│     Impact: Unauthorized state changes                  │
│     Fix: onlyOwner, role-based access, multi-sig        │
│                                                         │
│  3. ORACLE MANIPULATION                                 │
│     Price feed manipulation via flash loans             │
│     Impact: Exploit pricing, drain funds                │
│     Fix: TWAP, multiple oracles, sanity checks          │
│                                                         │
│  4. FLASH LOAN ATTACKS                                  │
│     Borrow massive capital to manipulate state          │
│     Impact: Governance takeover, price manipulation     │
│     Fix: Time-weighted voting, snapshot mechanisms      │
│                                                         │
│  5. INTEGER OVERFLOW/UNDERFLOW                          │
│     Arithmetic overflow (Solidity <0.8)                 │
│     Impact: Incorrect balances, mint infinite tokens    │
│     Fix: Solidity 0.8+ (built-in checks), SafeMath      │
│                                                         │
│  6. UNCHECKED EXTERNAL CALLS                            │
│     Low-level call without success check                │
│     Impact: Silent failures, lost funds                 │
│     Fix: require(call(), "failed")                      │
│                                                         │
│  7. SELFDESTRUCT / DELEGATECALL                         │
│     Unexpected code execution                           │
│     Impact: Storage corruption, fund theft              │
│     Fix: Never use delegatecall with untrusted targets  │
│                                                         │
│  8. FRONT-RUNNING                                       │
│     Transaction ordering manipulation                   │
│     Impact: MEV extraction, sandwich attacks            │
│     Fix: Commit-reveal, private mempools                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 1.2 High Severity Vulnerabilities

| Vulnerability | Description | Impact | Fix |
|--------------|-------------|--------|-----|
| **Signature Replay** | Same signature used multiple times | Unauthorized actions | Nonce, chainId, contract address in hash |
| **Missing Input Validation** | No bounds checking on inputs | Unexpected state | Require statements, custom errors |
| **Precision Loss** | Integer division truncation | Incorrect calculations | Multiply before divide, use decimals |
| **Denial of Service** | Loop over unbounded array | Contract stuck | Pagination, pull over push |
| **Block Timestamp Dependence** | Using block.timestamp for logic | Miner manipulation | Use block numbers, oracles |
| **tx.origin Authentication** | Using tx.origin instead of msg.sender | Phishing attacks | Always use msg.sender |
| **Uninitialized Storage** | Proxy contract without initialization | Storage collision | Initialize in constructor, use initializer modifier |
| **Cross-Function Reentrancy** | Reentrancy across multiple functions | State corruption | Mutex, CEI pattern |

### 1.3 Medium Severity Vulnerabilities

| Vulnerability | Description | Impact |
|--------------|-------------|--------|
| **Centralization Risk** | Single point of control | Rug pull potential |
| **Missing Event Emission** | No events for state changes | Poor transparency |
| **Hardcoded Addresses** | Addresses in code | Inflexible, risky |
| **Deprecated Functions** | Using old Solidity patterns | Potential bugs |
| **Missing Zero-Address Check** | No validation on address(0) | Token burn, lost funds |
| **Floating Pragma** | `pragma solidity ^0.8.0` | Unexpected compiler behavior |

---

## 2. Audit Methodology

### 2.1 Pre-Audit Phase

```
┌─────────────────────────────────────────────────────────┐
│              PRE-AUDIT CHECKLIST                         │
│                                                         │
│  □ Scope defined: contracts, functions, external calls  │
│  □ Documentation reviewed: specs, whitepaper, docs      │
│  □ Architecture understood: contracts, dependencies     │
│  □ Threat model created: actors, assets, attack vectors │
│  □ Tools configured: Slither, Mythril, Echidna, Foundry │
│  □ Test coverage assessed: >90% target                  │
│  □ Previous audits reviewed: fixes verified             │
│  □ Dependencies audited: libraries, oracles, bridges    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Static Analysis Phase

**Automated Tools:**

| Tool | Type | Strengths | Limitations |
|------|------|-----------|-------------|
| **Slither** | Static analyzer | Fast, comprehensive, custom detectors | False positives |
| **Mythril** | Symbolic execution | Finds complex bugs | Slow, limited depth |
| **Echidna** | Fuzzing | Property-based testing | Requires invariants |
| **Manticore** | Symbolic execution | Deep analysis | Very slow |
| **Semgrep** | Pattern matching | Custom rules, fast | Pattern-based only |
| **Aderyn** | Static analyzer | Solidity-specific, fast | Newer, fewer detectors |

**Slither Usage:**
```bash
# Basic analysis
slither .

# Print human-readable summary
slither . --print human-summary

# Detect specific vulnerability classes
slither . --detect reentrancy,tx-origin,delegatecall

# Generate JSON report
slither . --json slither-report.json

# Custom detector
slither . --detect my-custom-detector
```

**Slither Custom Detector Template:**
```python
from slither.core.declarations import Function
from slither.analyses.data_dependency.data_dependency import is_tainted
from slither.detectors.abstract_detector import AbstractDetector, DetectorClassification

class ReentrancyCustom(AbstractDetector):
    ARGUMENT = 'my-reentrancy'
    HELP = 'Detect reentrancy vulnerabilities'
    IMPACT = DetectorClassification.HIGH
    CONFIDENCE = DetectorClassification.MEDIUM

    WIKI = 'https://github.com/crytic/slither/wiki/Detector-Documentation'
    WIKI_TITLE = 'Reentrancy'

    def _detect(self):
        results = []
        for contract in self.compilation_unit.contracts_derived:
            for function in contract.functions:
                if self._has_reentrancy(function):
                    results.append([contract, function])
        return results

    def _has_reentrancy(self, function: Function):
        # Custom reentrancy detection logic
        pass
```

### 2.3 Dynamic Analysis Phase

**Foundry Fuzz Testing:**
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/Vault.sol";

contract VaultTest is Test {
    Vault public vault;

    function setUp() public {
        vault = new Vault();
    }

    // Invariant: Total balance should always equal sum of user balances
    function invariant_totalBalance() public {
        uint256 total = vault.totalBalance();
        uint256 sum = 0;
        // Calculate sum of all user balances
        assertEq(total, sum, "Total balance mismatch");
    }

    // Fuzz test: deposit and withdraw should preserve balance
    function testFuzz_DepositWithdraw(uint256 amount) public {
        amount = bound(amount, 1, 1000 ether);
        vm.deal(address(this), amount);

        vault.deposit();
        assertEq(vault.balanceOf(address(this)), amount);

        vault.withdraw(amount);
        assertEq(vault.balanceOf(address(this)), 0);
    }

    // Invariant: No user should be able to withdraw more than deposited
    function invariant_noOverWithdraw() public {
        // Check all users
    }
}
```

**Echidna Property Testing:**
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../src/Token.sol";

contract EchidnaTest {
    Token public token;
    address public user = address(0x1234);

    constructor() {
        token = new Token();
        token.mint(user, 1000);
    }

    // Property: Total supply should never exceed max supply
    function echidna_totalSupplyCap() public view returns (bool) {
        return token.totalSupply() <= token.MAX_SUPPLY();
    }

    // Property: No user should have negative balance
    function echidna_noNegativeBalance() public view returns (bool) {
        return token.balanceOf(user) >= 0;
    }

    // Property: Transfer should preserve total supply
    function echidna_transferPreservesSupply(uint256 amount) public returns (bool) {
        uint256 before = token.totalSupply();
        token.transfer(address(0x5678), amount);
        return token.totalSupply() == before;
    }
}
```

### 2.4 Manual Review Phase

**Line-by-Line Review Checklist:**

```
┌─────────────────────────────────────────────────────────┐
│              MANUAL REVIEW CHECKLIST                     │
│                                                         │
│  FOR EACH FUNCTION:                                     │
│  □ Access control: who can call?                        │
│  □ Input validation: are inputs bounded?                │
│  □ State changes: are they correct?                     │
│  □ External calls: are they safe?                       │
│  □ Events: are they emitted?                            │
│  □ Gas: is it bounded?                                  │
│  □ Edge cases: zero values, max values, empty arrays    │
│                                                         │
│  FOR EACH EXTERNAL CALL:                                │
│  □ Reentrancy risk: state updated before call?          │
│  □ Return value: is it checked?                         │
│  □ Gas limit: is it specified?                          │
│  □ Callback: can the called contract call back?         │
│                                                         │
│  FOR EACH STATE VARIABLE:                               │
│  □ Visibility: is it appropriate?                       │
│  □ Mutability: can it be changed unexpectedly?          │
│  □ Initialization: is it set correctly?                 │
│  □ Upgrade: is it preserved across upgrades?            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Vulnerability Deep Dives

### 3.1 Reentrancy — Complete Analysis

```solidity
// ❌ VULNERABLE
contract VulnerableVault {
    mapping(address => uint256) public balances;

    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount);

        // External call BEFORE state update
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success);

        // State update AFTER external call
        balances[msg.sender] -= amount;
    }
}

// ✅ SECURE — Checks-Effects-Interactions
contract SecureVault {
    mapping(address => uint256) public balances;

    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount);

        // State update BEFORE external call
        balances[msg.sender] -= amount;

        // External call AFTER state update
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success);
    }
}

// ✅ SECURE — Reentrancy Guard
contract GuardedVault {
    mapping(address => uint256) public balances;
    bool private locked;

    modifier nonReentrant() {
        require(!locked, "Reentrant call");
        locked = true;
        _;
        locked = false;
    }

    function withdraw(uint256 amount) public nonReentrant {
        require(balances[msg.sender] >= amount);
        balances[msg.sender] -= amount;
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success);
    }
}
```

**Cross-Function Reentrancy:**
```solidity
// ❌ VULNERABLE — Reentrancy across functions
contract CrossFunctionVulnerable {
    mapping(address => uint256) public balances;

    function transfer(address to, uint256 amount) public {
        require(balances[msg.sender] >= amount);
        (bool success, ) = to.call{value: amount}("");
        require(success);
        balances[msg.sender] -= amount;
        balances[to] += amount;
    }

    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount);
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success);
        balances[msg.sender] -= amount;
    }
}
// Attack: withdraw() → calls back to transfer() → drains funds
```

### 3.2 Oracle Manipulation

```solidity
// ❌ VULNERABLE — Spot price oracle
contract VulnerableLending {
    IUniswapV2Pair public pair;

    function getPrice() public view returns (uint256) {
        (uint256 reserve0, uint256 reserve1, ) = pair.getReserves();
        return (reserve1 * 1e18) / reserve0; // Spot price
    }

    function borrow(uint256 amount) public {
        uint256 price = getPrice();
        uint256 collateralValue = balanceOf(msg.sender) * price;
        require(collateralValue >= amount * 1.5, "Insufficient collateral");
        // Send loan
    }
}
// Attack: Flash loan → manipulate reserves → borrow at inflated price → repay flash loan

// ✅ SECURE — TWAP Oracle
contract SecureLending {
    IUniswapV2Pair public pair;

    function getTWAP(uint32 window) public view returns (uint256) {
        uint32[] memory secondsAgos = new uint32[](2);
        secondsAgos[0] = window;
        secondsAgos[1] = 0;

        (uint256[] memory prices, ) = pair.observe(secondsAgos);
        return (prices[1] - prices[0]) / window;
    }

    function borrow(uint256 amount) public {
        uint256 price = getTWAP(1800); // 30-minute TWAP
        uint256 collateralValue = balanceOf(msg.sender) * price;
        require(collateralValue >= amount * 1.5, "Insufficient collateral");
    }
}
```

### 3.3 Flash Loan Attack Patterns

```
┌─────────────────────────────────────────────────────────┐
│              FLASH LOAN ATTACK FLOW                      │
│                                                         │
│  Step 1: Borrow 10,000 ETH via flash loan               │
│  Step 2: Deposit into lending protocol as collateral    │
│  Step 3: Borrow other tokens against inflated collateral│
│  Step 4: Manipulate governance token price              │
│  Step 5: Execute governance proposal                    │
│  Step 6: Drain protocol funds                           │
│  Step 7: Repay flash loan + fee                         │
│  Step 8: Keep profit                                    │
│                                                         │
│  DEFENSES:                                              │
│  • Time-weighted voting (snapshot at proposal time)     │
│  • TWAP for price feeds                                 │
│  • Deposit/withdrawal delays                            │
│  • Maximum borrow limits per block                      │
│  • Flash loan detection (check tx.origin)               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 3.4 Access Control Vulnerabilities

```solidity
// ❌ VULNERABLE — tx.origin authentication
contract VulnerableWallet {
    address public owner;

    function withdraw(address to, uint256 amount) public {
        require(tx.origin == owner, "Not owner");
        payable(to).transfer(amount);
    }
}
// Attack: User calls malicious contract → malicious contract calls withdraw()
// tx.origin = user (not malicious contract) → passes check

// ❌ VULNERABLE — Missing access control
contract VulnerableMint {
    function mint(address to, uint256 amount) public {
        totalSupply += amount;
        balances[to] += amount;
    }
}
// Anyone can mint infinite tokens

// ✅ SECURE — Role-based access control
contract SecureMint {
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");

    function mint(address to, uint256 amount) public onlyRole(MINTER_ROLE) {
        totalSupply += amount;
        balances[to] += amount;
    }
}
```

### 3.5 Upgradeable Contract Vulnerabilities

```solidity
// ❌ VULNERABLE — Uninitialized proxy
contract VulnerableProxy {
    address public owner;
    uint256 public value;

    function initialize(address _owner) public {
        owner = _owner;
    }

    function setValue(uint256 _value) public onlyOwner {
        value = _value;
    }
}
// Attack: Call initialize() yourself to become owner

// ✅ SECURE — Initialized proxy
contract SecureProxy {
    address public owner;
    uint256 public value;
    bool private initialized;

    function initialize(address _owner) public {
        require(!initialized, "Already initialized");
        require(_owner != address(0), "Invalid owner");
        owner = _owner;
        initialized = true;
    }
}

// ✅ SECURE — OpenZeppelin Initializable
import "@openzeppelin/upgradeable-contracts/proxy/utils/Initializable.sol";

contract SecureProxy is Initializable {
    address public owner;

    function initialize(address _owner) public initializer {
        __Ownable_init();
        transferOwnership(_owner);
    }
}
```

**Storage Collision in Upgrades:**
```
┌─────────────────────────────────────────────────────────┐
│              STORAGE COLLISION                           │
│                                                         │
│  Original Contract:          Upgraded Contract:         │
│  Slot 0: address owner       Slot 0: uint256 version    │
│  Slot 1: uint256 value       Slot 1: address owner      │
│                                                         │
│  Problem: owner and version share Slot 0!               │
│  Setting version overwrites owner address               │
│                                                         │
│  FIX: Use storage gap or OpenZeppelin storage pattern   │
│  uint256[50] private __gap; // Reserve slots            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Gas Optimization

### 4.1 Gas Optimization Patterns

| Pattern | Before | After | Savings |
|---------|--------|-------|---------|
| **Storage vs Memory** | Read storage multiple times | Cache in memory | ~2100 gas per read |
| **Packed Storage** | Separate uint256 variables | Pack into single slot | ~20000 gas per slot |
| **Custom Errors** | `require(cond, "message")` | `if (!cond) revert CustomError()` | ~50 gas per call |
| **Unchecked Arithmetic** | `a + b` (with overflow check) | `unchecked { a + b }` | ~30 gas per op |
| **Short-Circuit** | `a && b` (both evaluated) | Order by likelihood | Variable |
| **External vs Public** | `function foo() public` | `function foo() external` | ~20 gas per call |
| **Calldata vs Memory** | `function foo(uint[] memory arr)` | `function foo(uint[] calldata arr)` | ~100 gas per call |
| **Increment Operator** | `i++` | `++i` | ~5 gas per loop |

### 4.2 Gas Optimization Examples

```solidity
// ❌ GAS INEFFICIENT
contract GasInefficient {
    uint256 public total;
    uint256 public count;

    function update(uint256[] memory values) public {
        for (uint256 i = 0; i < values.length; i++) {
            total += values[i]; // Storage write in loop
        }
        count += values.length;
    }
}

// ✅ GAS OPTIMIZED
contract GasOptimized {
    uint256 public total;
    uint256 public count;

    function update(uint256[] calldata values) public {
        uint256 _total = total; // Cache storage
        uint256 len = values.length;

        for (uint256 i = 0; i < len; ++i) { // ++i, calldata
            _total += values[i]; // Memory operation
        }

        total = _total; // Single storage write
        count += len;
    }
}
```

---

## 5. Formal Verification

### 5.1 Invariant Specification

```solidity
// Invariants for a Token contract
// 1. Total supply = sum of all balances
// 2. No balance can be negative
// 3. Transfer preserves total supply
// 4. Mint increases total supply
// 5. Burn decreases total supply

// Certora Specification
import "certora/spec/Token.spec";

rule totalSupplyEqualsSumOfBalances(address[] memory users) {
    uint256 sum = 0;
    for (uint256 i = 0; i < users.length; i++) {
        sum += token.balanceOf(users[i]);
    }
    enforce token.totalSupply() == sum;
}

rule noNegativeBalance(address user) {
    // In Solidity, uint can't be negative, but conceptually:
    enforce token.balanceOf(user) >= 0;
}

rule transferPreservesSupply(address from, address to, uint256 amount) {
    uint256 before = token.totalSupply();
    token.transfer(from, to, amount);
    enforce token.totalSupply() == before;
}
```

### 5.2 Common Invariants by Protocol Type

| Protocol Type | Invariants |
|--------------|------------|
| **Token** | Total supply = sum of balances, no negative balances |
| **AMM** | Constant product invariant (x * y = k), reserves never negative |
| **Lending** | Total borrows ≤ total deposits, collateralization ratio maintained |
| **Staking** | Total staked = sum of user stakes, rewards distributed correctly |
| **Vault** | Total shares = sum of user shares, price per share never decreases |
| **Bridge** | Total locked = total minted, no double spending |
| **Governance** | Voting power = token balance, quorum reached before execution |

---

## 6. DeFi Protocol Audit Checklist

### 6.1 Token Audit

```
┌─────────────────────────────────────────────────────────┐
│              TOKEN AUDIT CHECKLIST                       │
│                                                         │
│  □ ERC-20 compliance: transfer, approve, allowance      │
│  □ Total supply: capped? mintable? burnable?            │
│  □ Access control: who can mint/burn/pause?             │
│  □ Transfer hooks: before/after transfer callbacks      │
│  □ Permit: EIP-2612 support? Replay protection?         │
│  □ Tax/fee: transfer tax? Max tax? Fee recipient?       │
│  □ Blacklist: can addresses be blocked?                 │
│  □ Upgradeable: proxy pattern? Storage layout?          │
│  □ Events: Transfer, Approval emitted correctly?        │
│  □ Edge cases: transfer to self, zero amount, max uint  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 6.2 AMM Audit

```
┌─────────────────────────────────────────────────────────┐
│              AMM AUDIT CHECKLIST                         │
│                                                         │
│  □ Invariant: x * y = k maintained?                     │
│  □ Price calculation: correct formula?                  │
│  □ Slippage: protected against MEV?                     │
│  □ Fees: calculated correctly? Distributed correctly?   │
│  □ Liquidity: mint/burn shares correct?                 │
│  □ Oracle: price feed manipulation resistant?           │
│  □ Flash loan: attack resistant?                        │
│  □ Rounding: direction favors protocol?                 │
│  □ Reentrancy: swap callbacks handled?                  │
│  □ Edge cases: zero liquidity, extreme ratios           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 6.3 Lending Protocol Audit

```
┌─────────────────────────────────────────────────────────┐
│              LENDING PROTOCOL AUDIT CHECKLIST            │
│                                                         │
│  □ Collateralization: ratio enforced?                   │
│  □ Liquidation: threshold correct? Penalty fair?        │
│  □ Interest rate: model correct? Updates frequently?    │
│  □ Oracle: price feed reliable? Manipulation resistant? │
│  □ Flash loan: attack resistant?                        │
│  □ Bad debt: handled? Socialized or insured?            │
│  □ Supply cap: per asset? Enforced?                     │
│  □ Borrow cap: per asset? Enforced?                     │
│  □ Pause: emergency pause? Who can pause?               │
│  □ Upgrade: proxy safe? Storage preserved?              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 7. Audit Report Template

```markdown
# Smart Contract Audit Report

## Project Information
- **Project**: [Name]
- **Repository**: [URL]
- **Commit**: [Hash]
- **Audit Date**: [Date]
- **Auditor**: [Name/Team]

## Executive Summary
[Brief overview of findings, overall risk assessment]

## Scope
| Contract | Lines of Code | Complexity |
|----------|--------------|------------|
| ContractA.sol | 250 | Medium |
| ContractB.sol | 180 | High |

## Findings Summary
| Severity | Count | Status |
|----------|-------|--------|
| Critical | 0 | — |
| High | 1 | Fixed |
| Medium | 3 | 2 Fixed, 1 Acknowledged |
| Low | 5 | 3 Fixed, 2 Acknowledged |
| Info | 8 | 5 Fixed, 3 Acknowledged |

## Detailed Findings

### [H-01] High — [Title]
**Description**: [What the issue is]
**Impact**: [What an attacker can do]
**Proof of Concept**: [Code demonstrating the exploit]
**Recommendation**: [How to fix]
**Status**: Fixed/Acknowledged/Rejected

## Code Quality
[General observations about code structure, readability, best practices]

## Gas Optimizations
[Gas improvement suggestions]

## Conclusion
[Final assessment, recommendations for future audits]
```

---

## 8. Tool Configuration

### 8.1 Foundry Setup for Auditing

```bash
# Initialize project
forge init audit-project
cd audit-project

# Install dependencies
forge install OpenZeppelin/openzeppelin-contracts
forge install foundry-rs/forge-std

# Run tests
forge test -vvv

# Run with fuzzing
forge test --fuzz-runs 10000

# Run invariant tests
forge test --match-contract InvariantTest

# Generate coverage
forge coverage

# Gas report
forge test --gas-report
```

### 8.2 Slither Configuration

```bash
# Install
pip3 install slither-analyzer

# Run with config
slither . --config-file slither.config.json

# slither.config.json
{
  "detectors_to_exclude": "solc-version,naming-convention",
  "filter_paths": "(lib/|test/|node_modules/)",
  "solc_remaps": [
    "@openzeppelin/=lib/openzeppelin-contracts/"
  ]
}
```

### 8.3 Echidna Configuration

```yaml
# echidna.yaml
testMode: "assertion"
testLimit: 100000
seqLen: 100
shrinkLimit: 5000
coverage: true
corpusDir: "echidna-corpus"
cryticArgs: ["--solc-remaps", "@openzeppelin/=lib/openzeppelin-contracts/"]
```

---

## 9. Common Attack Vectors — Real Examples

### 9.1 Historical Exploits

| Exploit | Date | Loss | Vulnerability |
|---------|------|------|---------------|
| **The DAO** | 2016 | $60M | Reentrancy |
| **Parity Wallet** | 2017 | $31M | Access control (init) |
| **bZx** | 2020 | $8M | Flash loan + oracle manipulation |
| **Wormhole** | 2022 | $326M | Signature verification |
| **Ronin Bridge** | 2022 | $625M | Validator compromise |
| **Harmony Horizon** | 2022 | $100M | Multisig compromise |
| **Euler Finance** | 2023 | $200M | Flash loan + donation attack |
| **Mango Markets** | 2022 | $115M | Oracle manipulation |

### 9.2 Attack Pattern Library

```
┌─────────────────────────────────────────────────────────┐
│              ATTACK PATTERN: Donation Attack             │
│                                                         │
│  Target: Lending protocol with donation-based accounting│
│  Vulnerability: Shares calculated as totalAssets/totalShares│
│  Attack:                                                │
│  1. Donate small amount to inflate share price          │
│  2. Deposit → get fewer shares than expected            │
│  3. Withdraw → receive more assets than deposited       │
│                                                         │
│  Fix: Use virtual shares/offset to prevent manipulation │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 10. Auditor's Mindset

### 10.1 Thinking Like an Attacker

```
┌─────────────────────────────────────────────────────────┐
│              ATTACKER'S CHECKLIST                        │
│                                                         │
│  1. Where are the funds?                                │
│     → Can I withdraw more than I should?                │
│                                                         │
│  2. Who controls what?                                  │
│     → Can I call functions I shouldn't?                 │
│                                                         │
│  3. What data is trusted?                               │
│     → Can I manipulate oracles, prices, timestamps?     │
│                                                         │
│  4. What assumptions are made?                          │
│     → What if they're wrong?                            │
│                                                         │
│  5. What's the worst that can happen?                   │
│     → Can I drain all funds?                            │
│     → Can I brick the contract?                         │
│     → Can I manipulate governance?                      │
│                                                         │
│  6. What's the cheapest attack?                         │
│     → Minimum capital required                          │
│     → Minimum complexity                                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 10.2 Audit Quality Checklist

- [ ] **All external functions reviewed**: Access control, input validation
- [ ] **All external calls analyzed**: Reentrancy, return values, gas
- [ ] **All state variables checked**: Visibility, mutability, initialization
- [ ] **All math operations verified**: Overflow, underflow, precision
- [ ] **All oracles assessed**: Manipulation resistance, TWAP
- [ ] **All upgrade paths tested**: Storage layout, initialization
- [ ] **All edge cases considered**: Zero, max, empty, overflow
- [ ] **Static analysis run**: Slither, Mythril, custom detectors
- [ ] **Fuzz testing completed**: Invariants, property-based tests
- [ ] **Formal verification done**: Critical invariants proven
- [ ] **Gas optimization reviewed**: Storage, memory, calldata
- [ ] **Report generated**: Findings, PoC, recommendations
