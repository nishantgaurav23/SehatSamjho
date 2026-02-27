"""B2B analytics dashboard endpoints.

Provides aggregated (zero-PHI) metrics: request volume, language distribution,
doc_type breakdown, latency percentiles — all joined from translation_logs.

Integration: registered in main.py at /dashboard/*.
Stub — implementation coming after prototype.
"""

from fastapi import APIRouter

router = APIRouter()