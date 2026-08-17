# v1[di] -> 当日粗行业中性化结果，移植自 SectorNeutralizeRank。
import numpy as np

from xqsim.api import *
from xqsim.common_module import log_info


class Operation(OperationBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.min_cs = int(simcfg.get(self.cfg, "min_cs", 15))          # type: ignore
        self.min_unique = int(simcfg.get(self.cfg, "min_unique", 5))   # type: ignore
        self.sector = self.dr.get_data("ind.sector")
        log_info(
            "AlphaJrxDaily SectorNeutralize: min_cs %d, min_unique %d",
            self.min_cs,
            self.min_unique,
        )

    def apply(self, di, alpha):
        valid = np.isfinite(alpha)
        values = alpha[valid]
        if values.size < self.min_cs or np.unique(values).size < self.min_unique:
            alpha[valid] = np.nan
            return

        _, inverse, counts = np.unique(
            values, return_inverse=True, return_counts=True
        )
        average_rank = np.cumsum(counts) - (counts - 1) / 2.0
        ranked = average_rank[inverse] / values.size
        centered = ranked - ranked.mean()
        std = centered.std(ddof=0)
        if not np.isfinite(std) or std == 0.0:
            alpha[valid] = np.nan
            return
        normalized = centered / std

        sector_id = self.sector[di][valid]
        residual = normalized.copy()
        for group in np.unique(sector_id):
            group_mask = sector_id == group
            if np.any(group_mask):
                residual[group_mask] -= normalized[group_mask].mean()
        residual_std = residual.std(ddof=0)
        if not np.isfinite(residual_std) or residual_std <= 0.0:
            alpha[valid] = np.nan
            return
        alpha[valid] = residual / residual_std
