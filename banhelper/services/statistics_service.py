from __future__ import annotations

from banhelper.infrastructure.repositories import BanRepository
from banhelper.domain.models import Statistics


class StatisticsService:
    """Use-case boundary for SQL-backed statistics and counter epochs."""

    def __init__(self, repository: BanRepository):
        self.repository = repository

    def snapshot(self) -> Statistics:
        return self.repository.statistics()

    def reset_week(self) -> Statistics:
        return self.repository.reset_week()

    def reset_promotion(self) -> Statistics:
        return self.repository.reset_promotion()

    def set_counts(self, total: int, week: int) -> Statistics:
        return self.repository.set_statistics_counts(total, week)
