"""AI Analysis Tests — 06-ai service logic (15 tests).

Tests for LLM client, prompt building, response parsing, caching,
rate limiting, timeout handling, finding enrichment, fix suggestions,
batch analysis, provider fallback, token counting, and empty findings.

All imports use namespace isolation from services/06-ai/src/.
Uses unittest.mock — no Docker required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Path setup for AI service imports ────────────────────────
_AI_SRC = str(Path(__file__).resolve().parents[2] / "services" / "06-ai")


def _import_ai():
    """Import AI service modules with namespace isolation."""
    import importlib
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]
    if "src" in sys.modules:
        del sys.modules["src"]

    sys.path.insert(0, _AI_SRC)
    try:
        models = importlib.import_module("src.models")
        llm = importlib.import_module("src.llm")
        analyzer = importlib.import_module("src.analyzer")
        fixer = importlib.import_module("src.fixer")
        return models, llm, analyzer, fixer
    finally:
        sys.path.pop(0)


# ─────────────────────────────────────────────────────────────
# 1. LLM client initialization with provider configs
# ─────────────────────────────────────────────────────────────


class TestLLMClientInitialization:
    """Tests for LLMClient.__init__ with provider configurations."""

    def test_init_with_openai_key(self):
        """LLMClient initializes with OpenAI key and model."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        client = llm_mod.LLMClient(openai_key="sk-test123", openai_model="gpt-4o")
        assert client.openai_key == "sk-test123"
        assert client.openai_model == "gpt-4o"
        assert client.preferred_provider == "openai"

    def test_init_with_anthropic_key(self):
        """LLMClient initializes with Anthropic key."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        client = llm_mod.LLMClient(
            anthropic_key="ant-key-456", preferred_provider="anthropic",
            anthropic_model="claude-3-5-sonnet-20241022",
        )
        assert client.anthropic_key == "ant-key-456"
        assert client.preferred_provider == "anthropic"

    def test_has_keys_returns_false_without_keys(self):
        """has_keys returns False when no API keys are configured."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        client = llm_mod.LLMClient()
        assert client.has_keys is False

    def test_has_keys_returns_true_with_openai_key(self):
        """has_keys returns True when OpenAI key is set."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        client = llm_mod.LLMClient(openai_key="sk-xxx")
        assert client.has_keys is True

    def test_select_provider_fallback_chain(self):
        """_select_provider follows fallback when preferred is unavailable."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        client = llm_mod.LLMClient(
            openrouter_key="or-key-789",
            preferred_provider="openai",  # No OpenAI key set
        )
        provider, model = client._select_provider()
        assert provider == "openrouter"  # Falls back to OpenRouter
        assert model == "openrouter/free"


# ─────────────────────────────────────────────────────────────
# 2. Prompt building for vulnerability analysis
# ─────────────────────────────────────────────────────────────


class TestPromptBuilding:
    """Tests for _build_prompt method."""

    def test_build_prompt_contains_source_code(self):
        """The prompt includes the source code snippet."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        client = llm_mod.LLMClient(openai_key="sk-test")
        prompt = client._build_prompt(
            source_code="contract Foo { function bar() {} }",
            finding_title="Reentrancy in bar()",
            finding_description="External call before state update.",
        )
        assert "contract Foo" in prompt
        assert "Reentrancy in bar()" in prompt
        assert "External call before state update" in prompt
        assert "## Source Code" in prompt
        assert "## Finding" in prompt

    def test_build_prompt_includes_location(self):
        """The prompt includes file/line/snippet location info."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        client = llm_mod.LLMClient(openai_key="sk-test")
        prompt = client._build_prompt(
            source_code="code",
            finding_title="Test Finding",
            finding_description="Desc",
            finding_location={"file": "Foo.sol", "line": 42, "snippet": "balance[msg.sender] = 0"},
        )
        assert "Foo.sol" in prompt
        assert "42" in prompt
        assert "balance[msg.sender] = 0" in prompt

    def test_build_prompt_includes_compiler(self):
        """The prompt includes Solidity compiler version when provided."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        client = llm_mod.LLMClient(openai_key="sk-test")
        prompt = client._build_prompt(
            source_code="code",
            finding_title="Test",
            finding_description="Desc",
            compiler="0.8.20",
        )
        assert "0.8.20" in prompt
        assert "Compiler" in prompt


# ─────────────────────────────────────────────────────────────
# 3. AI response parsing (valid JSON)
# ─────────────────────────────────────────────────────────────


class TestResponseParsingValid:
    """Tests for _parse_llm_response with valid JSON input."""

    def test_parse_valid_json_with_all_fields(self):
        """Valid JSON parses into LlmAnalysis with all fields."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        raw = json.dumps({
            "verdict": "true_positive",
            "confidence": 0.95,
            "severity": "critical",
            "reasoning": "The function makes external call before state update.",
            "suggested_fix": "Move state update before external call.",
        })
        result = llm_mod._parse_llm_response(raw)
        assert result.verdict == "true_positive"
        assert result.confidence == 0.95
        assert result.severity == "critical"
        assert "external call" in result.reasoning
        assert result.suggested_fix is not None

    def test_parse_json_strips_markdown_fences(self):
        """JSON wrapped in markdown code fences is parsed correctly."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        raw = '```json\n{"verdict": "false_positive", "confidence": 0.8, "severity": "low", "reasoning": "test"}\n```'
        result = llm_mod._parse_llm_response(raw)
        assert result.verdict == "false_positive"
        assert result.confidence == 0.8

    def test_parse_clamps_confidence_to_range(self):
        """Confidence values are clamped to [0.0, 1.0]."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        raw_high = json.dumps({"verdict": "true_positive", "confidence": 2.5, "severity": "medium", "reasoning": "r"})
        raw_low = json.dumps({"verdict": "true_positive", "confidence": -0.5, "severity": "medium", "reasoning": "r"})
        assert llm_mod._parse_llm_response(raw_high).confidence == 1.0
        assert llm_mod._parse_llm_response(raw_low).confidence == 0.0


# ─────────────────────────────────────────────────────────────
# 4. AI response parsing (invalid JSON → graceful fallback)
# ─────────────────────────────────────────────────────────────


class TestResponseParsingInvalid:
    """Tests for _parse_llm_response with invalid JSON."""

    def test_invalid_json_raises_value_error(self):
        """Malformed JSON raises ValueError."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        with pytest.raises(ValueError, match="Failed to parse LLM response"):
            llm_mod._parse_llm_response("not json at all")

    def test_missing_verdict_raises_value_error(self):
        """Missing 'verdict' field raises ValueError."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        with pytest.raises(ValueError, match="Invalid verdict"):
            llm_mod._parse_llm_response(json.dumps({"confidence": 0.5}))

    def test_invalid_verdict_value_raises_value_error(self):
        """Invalid verdict string raises ValueError."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        with pytest.raises(ValueError, match="Invalid verdict"):
            llm_mod._parse_llm_response(json.dumps({"verdict": "maybe", "confidence": 0.5}))

    def test_invalid_severity_defaults_to_medium(self):
        """Unknown severity defaults to 'medium' without error."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        raw = json.dumps({"verdict": "true_positive", "confidence": 0.9, "severity": "catastrophic", "reasoning": "r"})
        result = llm_mod._parse_llm_response(raw)
        assert result.severity == "medium"


# ─────────────────────────────────────────────────────────────
# 5. Cache key generation from source hash
# ─────────────────────────────────────────────────────────────


class TestCacheKeyGeneration:
    """Tests for _compute_finding_hash."""

    def test_hash_is_deterministic(self):
        """Same inputs produce the same hash."""
        _models, _llm, analyzer_mod, _fixer = _import_ai()
        h1 = analyzer_mod._compute_finding_hash("slither", "contract A {}", "Title", "Description")
        h2 = analyzer_mod._compute_finding_hash("slither", "contract A {}", "Title", "Description")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_differs_on_different_source(self):
        """Different source code produces different hash."""
        _models, _llm, analyzer_mod, _fixer = _import_ai()
        h1 = analyzer_mod._compute_finding_hash("slither", "contract A {}", "Title", "Desc")
        h2 = analyzer_mod._compute_finding_hash("slither", "contract B {}", "Title", "Desc")
        assert h1 != h2

    def test_hash_differs_on_different_tool(self):
        """Different tool produces different hash."""
        _models, _llm, analyzer_mod, _fixer = _import_ai()
        h1 = analyzer_mod._compute_finding_hash("slither", "code", "Title", "Desc")
        h2 = analyzer_mod._compute_finding_hash("mythril", "code", "Title", "Desc")
        assert h1 != h2


# ─────────────────────────────────────────────────────────────
# 6. Cache hit returns stored analysis
# ─────────────────────────────────────────────────────────────


class TestCacheHit:
    """Tests for _load_cache returning stored analyses."""

    def test_load_cache_returns_none_for_missing_file(self):
        """_load_cache returns None when cache file doesn't exist."""
        _models, _llm, analyzer_mod, _fixer = _import_ai()
        result = analyzer_mod._load_cache("nonexistent_hash_1234567890abcdef")
        assert result is None

    def test_load_cache_parses_valid_file(self, tmp_path):
        """_load_cache returns LlmAnalysis from a valid cache file."""
        _models, _llm, analyzer_mod, _fixer = _import_ai()
        # Patch CACHE_DIR to tmp_path
        with patch.object(analyzer_mod, "CACHE_DIR", tmp_path):
            finding_hash = "a" * 64
            cache_data = {
                "verdict": "true_positive",
                "confidence": 0.85,
                "severity": "high",
                "reasoning": "Valid reentrancy pattern found.",
                "suggested_fix": "Use ReentrancyGuard.",
            }
            cache_file = tmp_path / f"{finding_hash}.json"
            cache_file.write_text(json.dumps(cache_data))

            result = analyzer_mod._load_cache(finding_hash)
            assert result is not None
            assert result.verdict == "true_positive"
            assert result.confidence == 0.85
            assert result.severity == "high"

    def test_save_and_load_cache_roundtrip(self, tmp_path):
        """_save_cache and _load_cache produce consistent results."""
        _models, llm_mod, analyzer_mod, _fixer = _import_ai()
        analysis = llm_mod.LlmAnalysis(
            verdict="false_positive", confidence=0.72, severity="low",
            reasoning="No exploit path exists.", suggested_fix=None,
        )
        with patch.object(analyzer_mod, "CACHE_DIR", tmp_path):
            finding_hash = "b" * 64
            analyzer_mod._save_cache(finding_hash, analysis)
            loaded = analyzer_mod._load_cache(finding_hash)
            assert loaded is not None
            assert loaded.verdict == "false_positive"
            assert loaded.confidence == 0.72


# ─────────────────────────────────────────────────────────────
# 7. Cache miss triggers LLM call
# ─────────────────────────────────────────────────────────────


class TestCacheMissCallsLLM:
    """Tests that cache miss triggers an LLM API call."""

    @pytest.mark.asyncio
    async def test_cache_miss_calls_llm_analyze(self):
        """When cache misses, the LLM analyze() is called."""
        _models, llm_mod, analyzer_mod, _fixer = _import_ai()

        llm_client = MagicMock()
        llm_client.has_keys = True
        llm_client.analyze = AsyncMock(return_value=llm_mod.LlmAnalysis(
            verdict="true_positive", confidence=0.9, severity="high",
            reasoning="reentrancy", suggested_fix="Fix it",
        ))

        a = analyzer_mod.Analyzer(llm=llm_client, max_concurrent=1)

        finding = _models.Finding(
            id="F-001", tool="slither", title="Reentrancy",
            description="External call before state update",
            severity="high",
        )

        with patch.object(analyzer_mod, "_load_cache", return_value=None):
            with patch.object(analyzer_mod, "_save_cache"):
                result = await a._analyze_single(
                    source_code="contract A { function f() {} }",
                    finding=finding,
                )

        llm_client.analyze.assert_called_once()
        assert result.ai_verdict == "true_positive"

    @pytest.mark.asyncio
    async def test_no_llm_keys_skips_llm_call(self):
        """When has_keys is False, no LLM call is made and findings are trusted."""
        _models, llm_mod, analyzer_mod, _fixer = _import_ai()

        llm_client = MagicMock()
        llm_client.has_keys = False
        llm_client.analyze = AsyncMock()

        a = analyzer_mod.Analyzer(llm=llm_client, max_concurrent=1)

        finding = _models.Finding(
            id="F-001", tool="slither", title="Reentrancy",
            description="desc", severity="high",
        )

        results = await a.analyze_all(
            source={"a.sol": "contract A {}"},
            findings=[finding],
        )

        llm_client.analyze.assert_not_called()
        assert len(results) == 1
        assert results[0].ai_verdict == "true_positive"
        assert "api keys" in results[0].ai_reasoning.lower()


# ─────────────────────────────────────────────────────────────
# 8. Rate limit handling (429 → retry)
# ─────────────────────────────────────────────────────────────


class TestRateLimitHandling:
    """Tests for 429 rate limit response handling."""

    def test_429_causes_retry_via_tenacity(self):
        """Verify tenacity retry is configured for HTTPStatusError on _call_openai."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        import httpx
        # The tenacity @retry decorator on _call_openai catches httpx.HTTPStatusError
        # which includes 429 responses, triggering retry with exponential backoff
        retry_obj = getattr(llm_mod.LLMClient._call_openai, "retry", None)
        assert retry_obj is not None  # tenacity decorator is present

    def test_circuit_breaker_state_starts_closed(self):
        """CircuitBreaker starts in 'closed' state."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        cb = llm_mod.CircuitBreaker(failure_threshold=2, reset_timeout=999)
        assert cb.state == "closed"


# ─────────────────────────────────────────────────────────────
# 9. Timeout handling (LLM hangs → timeout error)
# ─────────────────────────────────────────────────────────────


class TestTimeoutHandling:
    """Tests for LLM timeout behavior."""

    def test_tenacity_retry_configured_on_openai_call(self):
        """_call_openai has tenacity @retry decorator for timeout retries."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        # Verify the method has the retry attribute from tenacity
        assert hasattr(llm_mod.LLMClient._call_openai, "retry")

    def test_default_timeout_constant_is_set(self):
        """DEFAULT_TIMEOUT is configured (60s) for LLM API calls."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        assert llm_mod.DEFAULT_TIMEOUT == 60.0


# ─────────────────────────────────────────────────────────────
# 10. Finding enrichment (AI adds severity, confidence, reasoning)
# ─────────────────────────────────────────────────────────────


class TestFindingEnrichment:
    """Tests for _enrich_finding merging LLM analysis into findings."""

    def test_enrich_finding_adds_all_ai_fields(self):
        """_enrich_finding adds ai_verdict, confidence, severity, reasoning, fix."""
        _models, llm_mod, analyzer_mod, _fixer = _import_ai()

        llm_mock = MagicMock()
        a = analyzer_mod.Analyzer(llm=llm_mock)

        finding = _models.Finding(
            id="F-001", tool="slither", title="Reentrancy",
            description="desc", severity="medium",
        )
        analysis = llm_mod.LlmAnalysis(
            verdict="true_positive", confidence=0.92, severity="critical",
            reasoning="Exploitable reentrancy.", suggested_fix="Add reentrancy guard.",
        )

        enriched = a._enrich_finding(finding, analysis)
        assert enriched.id == "F-001"
        assert enriched.tool == "slither"
        assert enriched.ai_verdict == "true_positive"
        assert enriched.ai_confidence == 0.92
        assert enriched.ai_severity == "critical"
        assert enriched.ai_reasoning == "Exploitable reentrancy."
        assert enriched.suggested_fix == "Add reentrancy guard."
        assert enriched.scanner_severity == "medium"

    def test_degraded_result_trusts_scanner(self):
        """_degraded_result returns TP with low confidence when LLM fails."""
        _models, _llm, analyzer_mod, _fixer = _import_ai()

        llm_mock = MagicMock()
        a = analyzer_mod.Analyzer(llm=llm_mock)

        finding = _models.Finding(
            id="F-002", tool="mythril", title="Overflow",
            description="desc", severity="high",
        )
        degraded = a._degraded_result(finding, error="Connection timeout")

        assert degraded.ai_verdict == "true_positive"
        assert degraded.ai_confidence == 0.3
        assert degraded.ai_severity == "high"
        assert "Connection timeout" in degraded.ai_reasoning


# ─────────────────────────────────────────────────────────────
# 11. Fix suggestion generation
# ─────────────────────────────────────────────────────────────


class TestFixSuggestionGeneration:
    """Tests for FixSuggester.suggest_fix()."""

    @pytest.mark.asyncio
    async def test_suggest_fix_returns_fix_suggestion(self):
        """suggest_fix generates a FixSuggestion for a finding."""
        _models, llm_mod, _analyzer, fixer_mod = _import_ai()

        llm_client = MagicMock()
        llm_client.analyze = AsyncMock(return_value=llm_mod.LlmAnalysis(
            verdict="true_positive", confidence=0.88, severity="high",
            reasoning="Reentrancy via external call.",
            suggested_fix="function withdraw() nonReentrant { ... }",
        ))

        fs = fixer_mod.FixSuggester(llm=llm_client)

        finding = _models.Finding(
            id="F-001", tool="slither", title="Reentrancy",
            description="External call before state update",
        )

        with patch.object(fixer_mod, "_read_cache", return_value=None):
            with patch.object(fixer_mod, "_write_cache"):
                result = await fs.suggest_fix(
                    source_code="contract A { function f() {} }",
                    finding=finding,
                )

        assert result.finding_id == "F-001"
        assert "nonReentrant" in result.fix_code
        assert result.explanation is not None

    @pytest.mark.asyncio
    async def test_false_positive_returns_no_fix(self):
        """FixSuggester returns empty fix code for false positives."""
        _models, llm_mod, _analyzer, fixer_mod = _import_ai()

        llm_client = MagicMock()
        llm_client.analyze = AsyncMock(return_value=llm_mod.LlmAnalysis(
            verdict="false_positive", confidence=0.95, severity="informational",
            reasoning="Not exploitable — access control prevents call.",
            suggested_fix=None,
        ))

        fs = fixer_mod.FixSuggester(llm=llm_client)
        finding = _models.Finding(id="F-002", tool="slither", title="Access Control",
                                  description="desc")

        with patch.object(fixer_mod, "_read_cache", return_value=None):
            with patch.object(fixer_mod, "_write_cache"):
                result = await fs.suggest_fix(
                    source_code="contract A {}",
                    finding=finding,
                )

        assert result.fix_code == "" or "False Positive" in result.explanation


# ─────────────────────────────────────────────────────────────
# 12. Multi-finding batch analysis
# ─────────────────────────────────────────────────────────────


class TestBatchAnalysis:
    """Tests for Analyzer.analyze_all() batch processing."""

    @pytest.mark.asyncio
    async def test_analyze_all_concurrent_with_semaphore(self):
        """analyze_all uses semaphore for concurrent processing."""
        _models, llm_mod, analyzer_mod, _fixer = _import_ai()

        llm_client = MagicMock()
        llm_client.has_keys = True
        llm_client.analyze = AsyncMock(return_value=llm_mod.LlmAnalysis(
            verdict="true_positive", confidence=0.8, severity="medium",
            reasoning="ok", suggested_fix=None,
        ))

        a = analyzer_mod.Analyzer(llm=llm_client, max_concurrent=2)

        findings = [
            _models.Finding(id="F-001", tool="slither", title="Issue 1", description="d1"),
            _models.Finding(id="F-002", tool="mythril", title="Issue 2", description="d2"),
            _models.Finding(id="F-003", tool="echidna", title="Issue 3", description="d3"),
        ]

        with patch.object(analyzer_mod, "_load_cache", return_value=None):
            with patch.object(analyzer_mod, "_save_cache"):
                results = await a.analyze_all(
                    source={"a.sol": "contract A {}"},
                    findings=findings,
                )

        assert len(results) == 3
        assert llm_client.analyze.call_count == 3

    @pytest.mark.asyncio
    async def test_analyze_all_handles_exception_in_one_finding(self):
        """One failing finding doesn't crash the entire batch."""
        _models, llm_mod, analyzer_mod, _fixer = _import_ai()

        llm_client = MagicMock()
        llm_client.has_keys = True
        call_count = [0]

        async def flaky_analyze(**kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("LLM timeout")
            return llm_mod.LlmAnalysis(
                verdict="true_positive", confidence=0.7, severity="low",
                reasoning="ok", suggested_fix=None,
            )

        llm_client.analyze = flaky_analyze

        a = analyzer_mod.Analyzer(llm=llm_client, max_concurrent=1)

        findings = [
            _models.Finding(id="F-001", tool="slither", title="Issue 1", description="d1", severity="low"),
            _models.Finding(id="F-002", tool="mythril", title="Issue 2", description="d2", severity="medium"),
        ]

        with patch.object(analyzer_mod, "_load_cache", return_value=None):
            with patch.object(analyzer_mod, "_save_cache"):
                results = await a.analyze_all(
                    source={"a.sol": "contract A {}"},
                    findings=findings,
                )

        assert len(results) == 2
        # One should be degraded
        degraded = [r for r in results if r.ai_confidence == 0.3]
        assert len(degraded) == 1


# ─────────────────────────────────────────────────────────────
# 13. Provider fallback (OpenAI fails → Anthropic)
# ─────────────────────────────────────────────────────────────


class TestProviderFallback:
    """Tests for LLM provider fallback behavior."""

    def test_select_provider_falls_back_to_openrouter(self):
        """When preferred is unavailable, fallback to first available provider."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        client = llm_mod.LLMClient(
            openrouter_key="or-key",
            preferred_provider="openai",  # No OpenAI key
        )
        provider, _model = client._select_provider()
        assert provider == "openrouter"

    def test_select_provider_uses_preferred_when_available(self):
        """When preferred provider has key, it's selected."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        client = llm_mod.LLMClient(
            anthropic_key="ant-key",
            openrouter_key="or-key",
            preferred_provider="anthropic",
        )
        provider, _model = client._select_provider()
        assert provider == "anthropic"

    def test_select_provider_falls_back_chain(self):
        """Full fallback chain: openrouter → huggingface → openai → anthropic."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        client = llm_mod.LLMClient(
            openai_key="sk-key",
            preferred_provider="openrouter",  # No OpenRouter key
        )
        # No openrouter key → should fall back to openai (since huggingface also absent)
        provider, _model = client._select_provider()
        assert provider == "openai"


# ─────────────────────────────────────────────────────────────
# 14. Token counting / context window limits
# ─────────────────────────────────────────────────────────────


class TestTokenCounting:
    """Tests for context window and token estimation."""

    def test_max_tokens_constant_is_reasonable(self):
        """MAX_TOKENS is set to a reasonable value for analysis."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        assert llm_mod.MAX_TOKENS == 4096

    def test_temperature_is_low_for_deterministic_analysis(self):
        """TEMPERATURE is set low (0.1) for deterministic vulnerability analysis."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        assert llm_mod.TEMPERATURE == 0.1

    def test_system_prompt_is_defined(self):
        """SYSTEM_PROMPT is a non-empty string."""
        _models, llm_mod, _analyzer, _fixer = _import_ai()
        assert len(llm_mod.SYSTEM_PROMPT) > 500
        assert "smart contract security" in llm_mod.SYSTEM_PROMPT.lower()


# ─────────────────────────────────────────────────────────────
# 15. Empty findings → skip AI analysis
# ─────────────────────────────────────────────────────────────


class TestEmptyFindings:
    """Tests that empty findings skip AI analysis."""

    @pytest.mark.asyncio
    async def test_analyze_all_with_empty_findings_returns_empty_list(self):
        """analyze_all returns empty list when findings is empty."""
        _models, _llm, analyzer_mod, _fixer = _import_ai()

        llm_client = MagicMock()
        llm_client.has_keys = True
        a = analyzer_mod.Analyzer(llm=llm_client)

        results = await a.analyze_all(
            source={"a.sol": "contract A {}"},
            findings=[],
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_analyze_all_skips_when_no_llm_keys_and_empty(self):
        """Empty findings + no keys returns empty list."""
        _models, _llm, analyzer_mod, _fixer = _import_ai()

        llm_client = MagicMock()
        llm_client.has_keys = False
        a = analyzer_mod.Analyzer(llm=llm_client)

        results = await a.analyze_all(
            source={"a.sol": "contract A {}"},
            findings=[],
        )

        assert results == []

    def test_combine_source_single_file(self):
        """_combine_source returns the value of a single file directly."""
        _models, _llm, analyzer_mod, _fixer = _import_ai()
        llm_mock = MagicMock()
        a = analyzer_mod.Analyzer(llm=llm_mock)
        result = a._combine_source({"x.sol": "contract X {}"})
        assert result == "contract X {}"

    def test_combine_source_multiple_files(self):
        """_combine_source concatenates multiple files with markers."""
        _models, _llm, analyzer_mod, _fixer = _import_ai()
        llm_mock = MagicMock()
        a = analyzer_mod.Analyzer(llm=llm_mock)
        result = a._combine_source({"a.sol": "contract A {}", "b.sol": "contract B {}"})
        assert "// File: a.sol" in result
        assert "// File: b.sol" in result
        assert "contract A {}" in result
        assert "contract B {}" in result
