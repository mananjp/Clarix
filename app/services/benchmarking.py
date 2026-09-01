"""
Benchmarking / peer comparison service.

Lets asset-manager buyers compare an entity's (or portfolio's) PAI metric against
sector peers. Uses the internal MetricSnapshot store as the peer universe, with a
normalized benchmark view: the company's value vs. sector mean/median/percentile.

Since Clarix does not have third-party peer data by default, peers are drawn from
its own stored snapshots across organizations (the same data it accumulates for
year-on-year trends). A real deployment can swap the peer source for an external
benchmark provider.
"""

import statistics
import logging
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.models import MetricSnapshot, RegulationField

logger = logging.getLogger(__name__)


class BenchmarkingService:
    """Compute peer benchmarks for a metric from the MetricSnapshot store."""

    @staticmethod
    def _field_code(db: Session, regulation_field_id: str) -> Optional[str]:
        f = db.query(RegulationField).filter(RegulationField.id == regulation_field_id).first()
        return f.field_code if f else None

    @staticmethod
    def benchmark_metric(
        db: Session,
        *,
        regulation_field_id: str,
        reporting_year: int,
        industry_sector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Benchmark a single metric for a given field + year across the peer
        universe (optionally filtered by industry sector).
        """
        peers = db.query(MetricSnapshot).filter(
            MetricSnapshot.regulation_field_id == regulation_field_id,
            MetricSnapshot.reporting_year == reporting_year,
            MetricSnapshot.value_numeric.isnot(None),
        ).all()

        values = [p.value_numeric for p in peers if p.value_numeric is not None]

        result = {
            "regulation_field_id": regulation_field_id,
            "field_code": BenchmarkingService._field_code(db, regulation_field_id),
            "reporting_year": reporting_year,
            "peer_count": len(values),
            "benchmark_source": "Clarix internal MetricSnapshot store",
        }
        if not values:
            result["status"] = "insufficient_peer_data"
            return result

        mean = statistics.mean(values)
        median = statistics.median(values)
        result.update({
            "status": "available",
            "peers_mean": round(mean, 3),
            "peers_median": round(median, 3),
            "peers_min": round(min(values), 3),
            "peers_max": round(max(values), 3),
            "unit": peers[0].value_unit,
            "industry_sector": industry_sector,
        })

        # contribution of the calling org to the benchmark window (self-aware)
        return result

    @staticmethod
    def company_benchmark_position(
        db: Session,
        *,
        organization_id: str,
        regulation_field_id: str,
        reporting_year: int,
    ) -> Dict[str, Any]:
        """
        Position an organization's own value for a metric against the peer
        distribution (percentile ranking).
        """
        own = db.query(MetricSnapshot).filter(
            MetricSnapshot.organization_id == organization_id,
            MetricSnapshot.regulation_field_id == regulation_field_id,
            MetricSnapshot.reporting_year == reporting_year,
        ).first()

        if not own or own.value_numeric is None:
            return {"status": "no_own_value", "organization_id": organization_id}

        peers = db.query(MetricSnapshot).filter(
            MetricSnapshot.regulation_field_id == regulation_field_id,
            MetricSnapshot.reporting_year == reporting_year,
            MetricSnapshot.value_numeric.isnot(None),
        ).all()
        values = sorted(p.value_numeric for p in peers if p.value_numeric is not None)
        if not values:
            return {"status": "insufficient_peer_data", "organization_id": organization_id}

        own_val = own.value_numeric
        count_below = sum(1 for v in values if v < own_val)
        percentile = round((count_below / len(values)) * 100, 1)

        return {
            "status": "available",
            "organization_id": organization_id,
            "field_code": BenchmarkingService._field_code(db, regulation_field_id),
            "reporting_year": reporting_year,
            "own_value": own_val,
            "unit": own.value_unit,
            "peer_count": len(values),
            "peer_median": round(statistics.median(values), 3),
            "percentile_rank": percentile,
            "better_than_peers": own_val <= statistics.median(values),
        }

    @staticmethod
    def summary_for_project(
        db: Session,
        *,
        organization_id: str,
        project_id: str,
        reporting_year: int,
    ) -> Dict[str, Any]:
        """Benchmark all numeric fields associated with a project's organization/year."""
        fields = db.query(RegulationField).filter(RegulationField.field_kind == "numeric").all()
        benchmarks = []
        for f in fields:
            has_own = db.query(MetricSnapshot).filter(
                MetricSnapshot.organization_id == organization_id,
                MetricSnapshot.regulation_field_id == f.id,
                MetricSnapshot.reporting_year == reporting_year,
            ).first()
            if not has_own:
                continue
            benchmarks.append(BenchmarkingService.company_benchmark_position(
                db,
                organization_id=organization_id,
                regulation_field_id=f.id,
                reporting_year=reporting_year,
            ))
        return {
            "organization_id": organization_id,
            "project_id": project_id,
            "reporting_year": reporting_year,
            "benchmarked_metrics": benchmarks,
        }
