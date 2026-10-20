"""Public, synthetic risk-map example for the citizen portal.

The public portal must not publish saved municipal analyses or citizen health
reports by default. This example reuses the same Gi* implementation while
using official public boundaries and fictitious counts, independent of database data.
"""
from functools import lru_cache

from app.modules.vigilancia.risk import analyze, example_files
from app.modules.vigilancia.territory import pernambuco_context


@lru_cache(maxsize=1)
def get_public_risk_demo():
    """Return a cached, deterministic example with no municipal or personal data."""
    territory, history = example_files()
    report = analyze(territory, history)
    report['contexto'] = pernambuco_context()
    return report
