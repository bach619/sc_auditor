"""Adversarial AI Battle Engine — Red Agent vs Blue Agent.

Philosophy: Two AI agents fight each other 100 times.
The attacker tries everything to break the contract.
The defender patches after every successful attack.
The contract that survives 100 rounds is BATTLE-HARDENED.

Architecture:
    ┌──────────────────────────────────────────────────────┐
    │              BATTLE ARENA (forked mainnet)            │
    │                                                      │
    │   Round N:                                           │
    │   ┌──────────────┐        ┌──────────────┐          │
    │   │  🔴 RED AGENT │        │  🔵 BLUE AGENT │         │
    │   │  (Attacker)   │        │  (Defender)    │         │
    │   │               │        │                │         │
    │   │  1. Analyze   │        │  1. Analyze    │         │
    │   │  2. Generate  │        │  2. Detect     │         │
    │   │     exploit   │───────▶│     attack     │         │
    │   │  3. Execute   │        │  3. Patch      │         │
    │   │               │        │  4. Recommend  │         │
    │   └──────────────┘        └──────────────┘          │
    │                                                      │
    │   After 100 rounds:                                  │
    │   - All successful attacks → vulnerability report    │
    │   - All patches → security recommendations           │
    │   - Battle-hardened contract → 100% survival cert    │
    └──────────────────────────────────────────────────────┘

Services involved:
- 14-agent (Antonio) → Red + Blue personalities
- 08-exploit (Anvil) → Execution environment
- 06-ai (LLM) → Intelligence
- 07-classifier → Track findings
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger("vyper.adversarial")


class BattleRole(str, Enum):
    RED = "red"       # Attacker — goal: break the contract
    BLUE = "blue"     # Defender — goal: make it unbreakable


class RoundResult(str, Enum):
    ATTACKER_WIN = "attacker_win"       # Exploit succeeded → new vulnerability found
    DEFENDER_WIN = "defender_win"       # Attack blocked → contract is safe
    STALEMATE = "stalemate"              # Neither side succeeded
    CONTRACT_DESTROYED = "destroyed"     # Contract broken beyond repair


@dataclass
class AttackAttempt:
    """A single attack attempt by the Red Agent."""
    attempt_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    round_number: int = 0
    attack_type: str = ""               # reentrancy, oracle, flash_loan, access_control, etc.
    strategy: str = ""                  # AI-generated attack strategy
    exploit_code: str = ""              # Solidity PoC code
    success: bool = False
    profit_wei: str = "0"
    tx_hash: str = ""
    defense_bypassed: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DefenseResponse:
    """Blue Agent's defense against an attack."""
    defense_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    round_number: int = 0
    attack_blocked: bool = False
    patch_code: str = ""                # Solidity fix code
    recommendation: str = ""            # Human-readable recommendation
    additional_guards: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class BattleReport:
    """Complete report of an adversarial battle."""
    contract_address: str = ""
    contract_name: str = ""
    chain: str = "ethereum"
    total_rounds: int = 0
    attacker_wins: int = 0
    defender_wins: int = 0
    stalemates: int = 0
    vulnerabilities_found: list[dict] = field(default_factory=list)
    patches_applied: list[dict] = field(default_factory=list)
    final_verdict: str = ""             # "BATTLE-HARDENED" or "VULNERABLE"
    battle_duration_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AdversarialBattleEngine:
    """Orchestrates Red vs Blue AI battles.

    Usage:
        engine = AdversarialBattleEngine(anvil_url="http://08-exploit:8006")
        report = await engine.fight(
            contract_address="0x...",
            target_rounds=100,
            chain="ethereum",
        )
        print(f"Contract is: {report.final_verdict}")
    """

    def __init__(
        self,
        anvil_url: str = "http://08-exploit:8006",
        ai_url: str = "http://06-ai:8000",
        max_rounds: int = 100,
        profit_threshold_eth: float = 0.01,
    ) -> None:
        self.anvil_url = anvil_url
        self.ai_url = ai_url
        self.max_rounds = max_rounds
        self.profit_threshold = profit_threshold_eth

        # Memory — Red Agent learns from successful attacks
        self._red_memory: list[dict] = []
        # Memory — Blue Agent learns from successful defenses
        self._blue_memory: list[dict] = []
        # All attacks ever attempted (across all battles)
        self._attack_history: list[AttackAttempt] = []

    async def fight(
        self,
        contract_address: str,
        contract_name: str = "",
        chain: str = "ethereum",
        target_rounds: int = 100,
        rpc_url: str = "",
    ) -> BattleReport:
        """Run a full adversarial battle.

        Returns BattleReport with all findings, patches, and final verdict.
        """
        import time
        start_time = time.perf_counter()

        report = BattleReport(
            contract_address=contract_address,
            contract_name=contract_name,
            chain=chain,
            total_rounds=target_rounds,
        )

        logger.info(
            "⚔️ BATTLE START: %s — %d rounds, Red vs Blue",
            contract_name or contract_address[:10], target_rounds,
        )

        for round_num in range(1, target_rounds + 1):
            logger.info("─ Round %d/%d ─", round_num, target_rounds)

            # Phase 1: Red Agent attacks
            attack = await self._red_agent_attack(
                contract_address, contract_name, chain, round_num, rpc_url
            )

            # Phase 2: Blue Agent defends
            defense = await self._blue_agent_defend(
                contract_address, contract_name, attack, round_num
            )

            # Phase 3: Execute attack in Anvil fork
            result = await self._execute_battle_round(
                contract_address, chain, attack, defense, round_num, rpc_url
            )

            # Track results
            if result == RoundResult.ATTACKER_WIN:
                report.attacker_wins += 1
                report.vulnerabilities_found.append({
                    "round": round_num,
                    "attack_type": attack.attack_type,
                    "strategy": attack.strategy,
                    "exploit_code": attack.exploit_code[:500],
                    "profit_wei": attack.profit_wei,
                })
                self._red_memory.append({
                    "attack_type": attack.attack_type,
                    "strategy": attack.strategy,
                    "success": True,
                })

            elif result == RoundResult.DEFENDER_WIN:
                report.defender_wins += 1
                report.patches_applied.append({
                    "round": round_num,
                    "recommendation": defense.recommendation,
                    "patch_code": defense.patch_code[:500],
                    "guards_added": defense.additional_guards,
                })
                self._blue_memory.append({
                    "defense": defense.recommendation,
                    "blocked_attack": attack.attack_type,
                })

            else:
                report.stalemates += 1

            # Phase 4: Both agents learn from the round
            await self._mutual_learning(attack, defense, result, round_num)

        # Final verdict
        vulnerability_rate = report.attacker_wins / target_rounds
        if vulnerability_rate < 0.05:
            report.final_verdict = "🛡️ BATTLE-HARDENED — Survived 95%+ of attacks"
        elif vulnerability_rate < 0.20:
            report.final_verdict = "⚠️ RESILIENT — Minor vulnerabilities remain"
        else:
            report.final_verdict = "🔴 VULNERABLE — Multiple attack vectors found"

        report.battle_duration_seconds = time.perf_counter() - start_time

        logger.info(
            "⚔️ BATTLE END: %s — Red:%d Blue:%d Stale:%d — %s",
            contract_name or contract_address[:10],
            report.attacker_wins, report.defender_wins, report.stalemates,
            report.final_verdict,
        )

        return report

    async def _red_agent_attack(
        self, address: str, name: str, chain: str, round_num: int, rpc: str
    ) -> AttackAttempt:
        """Red Agent generates an attack strategy.

        Uses Antonio with RED personality — creative, aggressive, think like a hacker.
        """
        attack = AttackAttempt(round_number=round_num)

        # Build prompt with Red Agent memory of past successes
        memory_context = ""
        if self._red_memory:
            recent_wins = self._red_memory[-5:]
            memory_context = "\n".join(
                f"- Previous success: {m['attack_type']} — {m['strategy'][:100]}"
                for m in recent_wins
            )

        prompt = f"""You are RED AGENT — an elite smart contract hacker.
Your mission: Find ANY way to break {name} ({address}) on {chain}.

Previous successful attacks (learn from these):
{memory_context}

Think like a blackhat. Consider:
1. Reentrancy via unexpected callbacks (ERC-721, ERC-1155, hooks)
2. Oracle price manipulation (flash loan → TWAP deviation → profit)
3. Access control bypass (delegatecall, selfdestruct, uninitialized proxy)
4. MEV sandwich attack (front-run user txs in mempool)
5. Flash loan attack paths (borrow → manipulate → exploit → repay → profit)
6. Integer overflow/underflow in key accounting functions
7. Storage collision in upgradeable proxies
8. Signature replay or malleability
9. Gas griefing or DoS via unbounded loops
10. Read-only reentrancy (view functions reading stale state)

Generate:
1. ATTACK_TYPE: specific vulnerability class
2. STRATEGY: step-by-step attack plan (3-8 steps)
3. EXPLOIT_CODE: Solidity PoC exploit code
4. EXPECTED_PROFIT: estimated ETH profit
5. TARGET_FUNCTION: which function to call first

Be creative. Be aggressive. FIND THE BUG."""

        # In production, this calls 06-ai service
        try:
            # response = await self._call_ai(prompt)
            # Parse AI response into attack fields
            attack.attack_type = self._red_memory[-1]["attack_type"] if self._red_memory else "reentrancy"
            attack.strategy = "Multi-step attack chain via flash loan → oracle manipulation → liquidation"
            attack.exploit_code = "// AI-generated PoC exploit code"
        except Exception as exc:
            logger.error("Red Agent failed: %s", exc)

        return attack

    async def _blue_agent_defend(
        self, address: str, name: str, attack: AttackAttempt, round_num: int
    ) -> DefenseResponse:
        """Blue Agent generates defense against a specific attack."""
        defense = DefenseResponse(round_number=round_num)

        memory_context = ""
        if self._blue_memory:
            recent_defenses = self._blue_memory[-5:]
            memory_context = "\n".join(
                f"- Defense blocked: {d['blocked_attack']} — {d['defense'][:100]}"
                for d in recent_defenses
            )

        prompt = f"""You are BLUE AGENT — the world's best smart contract security auditor.
Your mission: Protect {name} ({address}) from this attack:

Attack Type: {attack.attack_type}
Attack Strategy: {attack.strategy}

Previous successful defenses:
{memory_context}

Generate:
1. CAN_BLOCK: YES/NO — can this attack be blocked?
2. PATCH_CODE: Solidity fix to prevent this attack
3. RECOMMENDATION: Human-readable security recommendation
4. ADDITIONAL_GUARDS: Extra security measures (modifiers, checks, invariants)
5. ROOT_CAUSE: What design flaw allowed this attack?

Be thorough. LEAVE NO VULNERABILITY."""

        try:
            # AI response parsing
            defense.recommendation = "Implement reentrancy guard + oracle deviation check"
            defense.patch_code = "// AI-generated patch"
            defense.additional_guards = ["ReentrancyGuard", "PriceDeviationCheck"]
            defense.attack_blocked = True
        except Exception as exc:
            logger.error("Blue Agent failed: %s", exc)

        return defense

    async def _execute_battle_round(
        self, address: str, chain: str, attack: AttackAttempt,
        defense: DefenseResponse, round_num: int, rpc: str,
    ) -> RoundResult:
        """Execute attack in Anvil fork and determine winner."""
        # Call 08-exploit to execute the attack
        # If exploit succeeds → ATTACKER_WIN
        # If exploit fails → DEFENDER_WIN
        try:
            # In production: await http_client.post(f"{self.anvil_url}/exploit", json={...})
            attack.success = attack.attack_type != "" and round_num % 3 != 0
            if attack.success:
                return RoundResult.ATTACKER_WIN
            else:
                return RoundResult.DEFENDER_WIN
        except Exception:
            return RoundResult.STALEMATE

    async def _mutual_learning(
        self, attack: AttackAttempt, defense: DefenseResponse,
        result: RoundResult, round_num: int,
    ) -> None:
        """Both agents learn from the round outcome.
        
        Red learns: which attack types work, which defenses are common.
        Blue learns: which attack patterns to watch for, which patches work.
        """
        # Learning is stored in _red_memory and _blue_memory
        # In production, this would update vector embeddings for semantic search
        pass
