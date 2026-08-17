# AlphaJrx_MemberSkillSectorPower2InvVol60_v001 的 xqsim 真正逐日适配版。
#
# 时间契约:
#   generate(di) 产出归属于目标日 di 的原始因子 v1，只消费信息日 di-1。
#   历史状态由 Simulator 显式 warmup 逐日推进；generate 内禁止回放或补算历史。
#
# v1 依赖:
#   rk.*[di-1] -> 当日会员暴露
#   exposure[di-2] + k.returns[di-1] -> daily score
#   最近 504 个 daily score -> member skill
#   skill[di-1] + exposure[di-1] -> vote -> ffill(3)
#   vote 写入品种 48 合成槽，得到目标日 di 的原始 v1
from collections import deque

import numpy as np

from xqsim.api import *
from xqsim.common_module import log_info
from utils import aggregate_member_product_position


SLOTS_PER_PRODUCT = 50
HOT_DATA_SLOT = 48


class AlphaJrxDaily(AlphaBase):
    def __init__(self, *args):
        super().__init__(*args)
        cfg = self.cfg
        self.skill_window = int(simcfg.get(cfg, "skill_window", 504))          # type: ignore
        self.skill_prior_days = int(simcfg.get(cfg, "skill_prior_days", 40))   # type: ignore
        self.skill_clip = float(simcfg.get(cfg, "skill_clip", 3.0))            # type: ignore
        self.min_contributors = int(simcfg.get(cfg, "min_contributors", 3))    # type: ignore
        self.ffill_limit = int(simcfg.get(cfg, "ffill_limit", 3))              # type: ignore
        if self.skill_window <= 1:
            raise ValueError("skill_window must be greater than 1")
        if self.ffill_limit < 0:
            raise ValueError("ffill_limit must be non-negative")

        # 504-day skill + ffill(3). Operations start at the formal begin_di.
        default_warmup = self.skill_window + self.ffill_limit
        self.warmup_days = int(simcfg.get(cfg, "warmup_days", default_warmup))  # type: ignore

        self.rk_long_pos = self.dr.get_data("rk.long_pos")
        self.rk_short_pos = self.dr.get_data("rk.short_pos")
        self.rk_long_member = self.dr.get_data("rk.long_pos_member")
        self.rk_short_member = self.dr.get_data("rk.short_pos_member")
        self.ret = self.dr.get_data("k.returns")

        static_di = self.meta.begin_di
        self.pi_by_ii = self.dr.get_data("static.pi")[static_di].astype(np.int64)
        industry_l1 = self.dr.get_data("ind.l1")[static_di].astype(np.int64)
        self.n_pi = int(self.pi_by_ii.max()) + 1
        self.member_n = max(
            int(member_id)
            for member_id in self.meta.enum_index_dict["member"]
        ) + 1

        slot = np.arange(self.meta.ii_size) % SLOTS_PER_PRODUCT
        self.hot_data_mask = (
            (slot == HOT_DATA_SLOT)
            & (industry_l1 >= 0)
        )
        self.real_contract_mask = (
            (slot < HOT_DATA_SLOT)
            & (self.pi_by_ii >= 0)
        )
        if self.meta.ii_size % SLOTS_PER_PRODUCT != 0:
            raise ValueError("ii_size must be divisible by slots per product")
        self.active_product_mask = self.hot_data_mask.reshape(
            -1, SLOTS_PER_PRODUCT
        ).any(axis=1)
        if self.active_product_mask.size != self.n_pi:
            raise ValueError("pi and ii product dimensions are inconsistent")
        active_pi_labels = self.pi_by_ii[self.hot_data_mask]
        masked_pi_labels = np.arange(self.n_pi)[self.active_product_mask]
        if not np.array_equal(active_pi_labels, masked_pi_labels):
            raise ValueError("hot data and active product masks are not aligned")

        self.sector_by_product = industry_l1[self.hot_data_mask]
        self.sectors = np.unique(self.sector_by_product)
        self.sector_masks = [
            self.sector_by_product == sector
            for sector in self.sectors
        ]
        self.product_count = int(self.hot_data_mask.sum())

        self._prev_direction = None
        self._prev_share = None
        self._score_buffer = deque(maxlen=self.skill_window)
        self._last_vote = np.full(self.product_count, np.nan)
        self._ffill_age = np.zeros(self.product_count, dtype=np.int64)

        log_info(
            "AlphaJrxDaily created: %d products, %d sectors, %d members, warmup %d",
            self.product_count,
            self.sectors.size,
            self.member_n,
            self.warmup_days,
        )

    def _aggregate_exposure(self, info_di):
        """Build AlphaJrx exposure from the long and short position rankings."""

        long_position = aggregate_member_product_position(
            self.rk_long_pos[info_di], self.rk_long_member[info_di],
            self.pi_by_ii, self.real_contract_mask,
            self.member_n, self.n_pi,
        )

        short_position = aggregate_member_product_position(
            self.rk_short_pos[info_di], self.rk_short_member[info_di],
            self.pi_by_ii, self.real_contract_mask,
            self.member_n, self.n_pi,
        )

        gross = long_position + short_position
        total_gross = gross.sum(axis=0, keepdims=True)

        with np.errstate(invalid="ignore", divide="ignore"):
            direction = (long_position - short_position) / gross
            share = gross / total_gross
        direction[gross <= 0.0] = np.nan
        share[gross <= 0.0] = np.nan

        return direction, share

    def _return_rank_z(self, info_di):
        values = self.ret[info_di][self.hot_data_mask]
        valid = ~np.isnan(values)
        if not np.any(valid):
            return np.full(self.product_count, np.nan)

        ranked = np.full(values.shape, np.nan, dtype=np.float64)
        _, inverse, counts = np.unique(
            values[valid], return_inverse=True, return_counts=True
        )
        average_rank = np.cumsum(counts) - (counts - 1) / 2.0
        ranked[valid] = average_rank[inverse] / valid.sum()

        centered = ranked - np.nanmean(ranked)
        std = np.nanstd(centered, ddof=0)
        if not np.isfinite(std) or std == 0.0:
            return np.full(self.product_count, np.nan)
        return centered / std

    def _daily_score(self, return_rank_z):
        scores = np.full((self.sectors.size, self.member_n), np.nan)
        previous_weight = np.sqrt(np.clip(self._prev_share, 0.0, None))
        active_direction = self._prev_direction[:, self.active_product_mask]
        active_weight = previous_weight[:, self.active_product_mask]
        for sector_index, sector_mask in enumerate(self.sector_masks):
            direction = active_direction[:, sector_mask]
            weight = active_weight[:, sector_mask]
            sector_return = return_rank_z[sector_mask]
            valid = np.isfinite(direction) & (weight > 0.0)

            contribution = (
                direction
                * weight
                * sector_return[np.newaxis, :]
            )
            numerator = np.nansum(contribution, axis=1)
            denominator = np.sum(np.where(valid, weight, 0.0), axis=1)
            with np.errstate(invalid="ignore", divide="ignore"):
                scores[sector_index] = numerator / np.where(
                    denominator == 0.0, np.nan, denominator
                )
        return scores

    def _update_skill(self, daily_scores):
        min_days = max(20, self.skill_window // 3)
        self._score_buffer.append(daily_scores)
        matrix = np.asarray(self._score_buffer, dtype=np.float64)
        finite = np.isfinite(matrix)
        count = finite.sum(axis=0)
        total = np.nansum(matrix, axis=0)
        mean = total / np.where(count == 0, np.nan, count)
        centered = np.where(finite, matrix - mean, 0.0)
        variance = np.sum(centered * centered, axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            std = np.sqrt(variance / (count - 1))
            t_stat = mean / np.where(std == 0.0, np.nan, std) * np.sqrt(count)
        shrink = count / (count + float(self.skill_prior_days))
        skill = np.clip(
            t_stat * shrink,
            -self.skill_clip,
            self.skill_clip,
        )
        skill[count < min_days] = np.nan
        return skill

    def _vote(self, skills, direction, share):
        product_skill = np.full((self.member_n, self.product_count), np.nan)
        for sector_index, sector_mask in enumerate(self.sector_masks):
            product_skill[:, sector_mask] = skills[sector_index, :, np.newaxis]
        product_direction = direction[:, self.active_product_mask]
        product_share = share[:, self.active_product_mask]
        numerator = np.nansum(
            product_skill * product_share * product_direction,
            axis=0,
        )
        denominator = np.nansum(np.abs(product_skill) * product_share, axis=0)
        contributors = np.sum(
            np.isfinite(product_skill)
            & (product_skill != 0.0)
            & (product_share > 0.0),
            axis=0,
        )
        valid = (
            (contributors >= self.min_contributors)
            & np.isfinite(denominator)
            & (denominator != 0.0)
        )
        vote = np.full(self.product_count, np.nan)
        vote[valid] = numerator[valid] / denominator[valid]
        return vote

    def _ffill_vote(self, vote):
        missing = ~np.isfinite(vote)
        can_fill = (
            missing
            & np.isfinite(self._last_vote)
            & (self._ffill_age < self.ffill_limit)
        )
        result = vote.copy()
        result[can_fill] = self._last_vote[can_fill]
        self._ffill_age = np.where(missing, self._ffill_age + 1, 0)
        self._last_vote = np.where(missing, self._last_vote, vote)
        return result

    def generate(self, di: int):

        direction, share = self._aggregate_exposure(di - 1)
        return_rank_z = self._return_rank_z(di - 1)

        vote = np.full(self.product_count, np.nan)
        if self._prev_direction is not None:
            daily_scores = self._daily_score(return_rank_z)
            skills = self._update_skill(daily_scores)
            vote = self._vote(skills, direction, share)
        signal = self._ffill_vote(vote)
        self.alpha[self.hot_data_mask] = signal

        self._prev_direction = direction
        self._prev_share = share


def create(*args):
    return AlphaJrxDaily(*args)
