# 将完成权威 postprocessor 的品种维 v2[di] 映射到目标日 di 的真实主力合约。
# 这是 xqsim ii 布局适配，不改变品种维 v2 数值。
import numpy as np

from xqsim.api import *
from xqsim.common_module import log_info

SLOTS_PER_PRODUCT = 50
HOT_DATA_SLOT = 48


class Operation(OperationBase):
    def __init__(self, *args):
        super().__init__(*args)
        static_di = self.meta.begin_di
        industry = self.dr.get_data("ind.l1")[static_di].astype(np.int64)
        if self.meta.ii_size % SLOTS_PER_PRODUCT != 0:
            raise ValueError("ii_size must be divisible by slots per product")
        slot = np.arange(self.meta.ii_size) % SLOTS_PER_PRODUCT
        self.hot_data_mask = (
            (slot == HOT_DATA_SLOT)
            & (industry >= 0)
        )
        self.real_contract_mask = (
            (slot < HOT_DATA_SLOT)
            & (industry >= 0)
        )
        self.hot = self.dr.get_data("hot.ii")
        self.universe = self.dr.get_data("uv.all")
        log_info(
            "AlphaJrxDaily MapToHot: products %d",
            int(self.hot_data_mask.sum()),
        )

    def apply(self, di, alpha):
        hot = self.hot[di]
        universe = self.universe[di]
        output = np.full_like(alpha, np.nan)

        hot_contract_mask = (
            self.real_contract_mask
            & universe
            & (hot == np.arange(self.meta.ii_size))
        )
        hot_count_by_product = hot_contract_mask.reshape(
            -1, SLOTS_PER_PRODUCT
        ).sum(axis=1)
        if np.any(hot_count_by_product > 1):
            raise ValueError("a product has more than one hot contract")

        has_hot_by_product = hot_count_by_product == 1
        source_mask = self.hot_data_mask & np.repeat(
            has_hot_by_product,
            SLOTS_PER_PRODUCT,
        )
        if source_mask.sum() != hot_contract_mask.sum():
            raise ValueError("hot data and contract masks are not aligned")
        output[hot_contract_mask] = alpha[source_mask]

        alpha[:] = output
