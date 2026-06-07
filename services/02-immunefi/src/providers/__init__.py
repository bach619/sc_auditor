"""Bounty Provider Protocol + Registry.

Setiap provider mengimplementasi BountyProvider protocol dan didaftarkan
di PROVIDER_REGISTRY. SyncManager akan mengiterasi semua provider
dan merge hasilnya.

Cara tambah provider baru:
  1. Buat class yang implements BountyProvider protocol
  2. Import class di sini
  3. Tambah ke PROVIDER_REGISTRY list
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# ── Provider Protocol ───────────────────────────────────────

@runtime_checkable
class BountyProvider(Protocol):
    """Protocol untuk semua bounty program provider.

    Setiap provider harus mengimplementasi 3 method:
      - fetch_program_list()  → list[dict]
      - fetch_program_detail(slug) → dict | None
      - is_available() → bool
    """

    name: str | None = None
    priority: int = 99  # lower = tried first

    async def fetch_program_list(self) -> list[dict[str, Any]]:
        """Fetch list semua program dari provider ini.

        Returns list of dict dengan keys minimal:
          slug, name, chains, maxBounty, status
        """
        ...

    async def fetch_program_detail(self, slug: str) -> dict[str, Any] | None:
        """Fetch detail satu program.

        Args:
            slug: Program identifier dari fetch_program_list()

        Returns:
            Dict dengan detail lengkap, atau None jika tidak ditemukan.
        """
        ...

    def is_available(self) -> bool:
        """Cek apakah provider siap digunakan.

        Contoh cek: API key ada? Network reachable?
        Returns False = skip provider ini di sync.
        """
        return True


# ── Provider Info Model ─────────────────────────────────────

class ProviderInfo:
    """Informasi dan status sebuah provider."""

    def __init__(
        self,
        name: str,
        priority: int,
        available: bool = False,
        programs_count: int = 0,
        error: str | None = None,
    ) -> None:
        self.name = name
        self.priority = priority
        self.available = available
        self.programs_count = programs_count
        self.error = error

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "priority": self.priority,
            "available": self.available,
            "programs_count": self.programs_count,
            "error": self.error,
        }


# ── Registry ────────────────────────────────────────────────

# Provider classes will be imported and registered here.
# Each is imported lazily to avoid circular imports.
PROVIDER_REGISTRY: list[type] = []


def register_provider(provider_cls: type) -> type:
    """Decorator untuk mendaftarkan provider ke registry."""
    PROVIDER_REGISTRY.append(provider_cls)
    return provider_cls


def get_available_providers() -> list:
    """Return list of provider instances that are available."""
    available = []
    for cls in PROVIDER_REGISTRY:
        try:
            instance = cls() if isinstance(cls, type) else cls
            if instance.is_available():
                available.append(instance)
        except Exception:
            continue
    # Sort by priority
    available.sort(key=lambda p: getattr(p, 'priority', 99))
    return available


def get_provider_statuses() -> list[dict]:
    """Return status info for all registered providers."""
    statuses = []
    for cls in PROVIDER_REGISTRY:
        try:
            instance = cls() if isinstance(cls, type) else cls
            available = instance.is_available()
            statuses.append(ProviderInfo(
                name=getattr(instance, 'name', cls.__name__),
                priority=getattr(instance, 'priority', 99),
                available=available,
            ).to_dict())
        except Exception as e:
            statuses.append(ProviderInfo(
                name=cls.__name__,
                priority=99,
                available=False,
                error=str(e)[:100],
            ).to_dict())
    return statuses


# ── Lazy Imports (dilakukan di akhir untuk avoid circular) ──

from .cantina import CantinaProvider  # noqa: E402, F401
from .code4rena import Code4renaProvider  # noqa: E402, F401

# External providers
from .hackerone import HackerOneProvider  # noqa: E402, F401
from .immunefi_mirror import ImmunefiMirrorProvider  # noqa: E402, F401
from .immunefi_official import ImmunefiOfficialProvider  # noqa: E402, F401

# Immunefi Web Scraper (live site)
from .immunefi_web_scraper import ImmunefiWebScraper  # noqa: E402, F401
from .sherlock import SherlockProvider  # noqa: E402, F401
