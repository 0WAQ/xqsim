"""Apply signed power and strictly lagged inverse-volatility weighting."""

import numpy as np

from xqsim.api import OperationBase, simcfg
from xqsim.common_module import log_info


SLOTS_PER_PRODUCT = 50
HOT_DATA_SLOT = 48


class Operation(OperationBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.power = float(simcfg.get(self.cfg, "power", 2.0))
        self.window = int(simcfg.get(self.cfg, "inverse_vol_window", 60))
        self.floor_quantile = float(
            simcfg.get(self.cfg, "inverse_vol_floor_quantile", 0.10)
        )
        self.min_names = int(simcfg.get(self.cfg, "min_names", 15))
        if not np.isfinite(self.power) or self.power <= 0.0:
            raise ValueError("power must be a finite positive number")
        if self.window <= 1:
            raise ValueError("inverse_vol_window must be greater than 1")
        if not 0.0 <= self.floor_quantile < 1.0:
            raise ValueError("inverse_vol_floor_quantile must be in [0, 1)")

        self.ret = self.dr.get_data("k.returns")
        static_di = self.meta.begin_di
        industry = self.dr.get_data("ind.l1")[static_di].astype(np.int64)
        slot = np.arange(self.meta.ii_size) % SLOTS_PER_PRODUCT
        self.hot_data_mask = (slot == HOT_DATA_SLOT) & (industry >= 0)
        self.product_count = int(self.hot_data_mask.sum())
        log_info(
            "PowerInvVol: power %.3f, window %d, products %d",
            self.power,
            self.window,
            self.product_count,
        )

    def apply(self, di, alpha):
        product_alpha = alpha[self.hot_data_mask]
        alpha_valid = np.isfinite(product_alpha)
        if not alpha_valid.any():
            return

        begin = di - self.window
        if begin < max(self.ret.offset_di, self.meta.begin_di):
            alpha[self.hot_data_mask] = np.nan
            return
        returns = self.ret[begin:di][:, self.hot_data_mask]
        complete = np.isfinite(returns).all(axis=0)
        volatility = np.full(self.product_count, np.nan)
        volatility[complete] = returns[:, complete].std(axis=0, ddof=0)
        finite_volatility = np.isfinite(volatility)
        if not finite_volatility.any():
            alpha[self.hot_data_mask] = np.nan
            return

        floor = np.nanquantile(volatility, self.floor_quantile)
        volatility = np.where(
            finite_volatility,
            np.clip(volatility, floor, None),
            np.nan,
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            inverse = 1.0 / volatility
        inverse[volatility == 0.0] = np.nan

        values = product_alpha[alpha_valid]
        transformed = (
            np.sign(values)
            * np.abs(values) ** self.power
            * inverse[alpha_valid]
        )
        finite = np.isfinite(transformed)
        if finite.sum() < self.min_names:
            alpha[self.hot_data_mask] = np.nan
            return

        long_score = np.where(finite, np.clip(transformed, 0.0, None), np.nan)
        short_score = np.where(finite, -np.clip(transformed, None, 0.0), np.nan)
        long_sum = np.nansum(long_score)
        short_sum = np.nansum(short_score)
        if long_sum <= 0.0 or short_sum <= 0.0:
            alpha[self.hot_data_mask] = np.nan
            return

        result = long_score / long_sum - short_score / short_sum
        output = np.full(self.product_count, np.nan)
        output[alpha_valid] = result
        alpha[self.hot_data_mask] = output
