"""Phase 2: automatischer Preisabruf. Jeder Fetcher ist optional und darf scheitern."""
from .base import Fetcher, FetchFehler
from .sixt import SixtFetcher
from .europcar import EuropcarFetcher

REGISTRY: dict[str, Fetcher] = {
    "sixt": SixtFetcher(),
    "europcar": EuropcarFetcher(),
}
