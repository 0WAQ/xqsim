import numpy as np


def aggregate_member_product_position(
    position, member,
    pi_by_ii, real_contract_mask,
    member_count, product_count,
):
    """将单边 ``rank x ii`` 榜单聚合成 ``member x product`` 持仓。"""

    valid = (
        (member >= 0)
        & np.isfinite(position)
        & (position > 0.0)
        & real_contract_mask[np.newaxis, :]
        & (pi_by_ii[np.newaxis, :] >= 0)
    )

    rank_index, ii_index = np.nonzero(valid)
    member_id = member[rank_index, ii_index]
    pi_label = pi_by_ii[ii_index]

    bucket = member_id * product_count + pi_label
    return np.bincount(
        bucket,
        weights=position[rank_index, ii_index],
        minlength=member_count * product_count,
    ).reshape(member_count, product_count)
