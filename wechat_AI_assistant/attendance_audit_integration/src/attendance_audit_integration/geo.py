"""地理空间计算：Haversine 大圆距离（审计用于瞬移检测 F2/E12 与 GPS 围栏 F13/E14）。"""
from __future__ import annotations

import math


def calculate_haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate the great-circle distance between two points in **kilometers**.

    Uses the Haversine formula with Earth's mean radius = 6371 km.
    Coordinates must be in decimal degrees (WGS-84 / GCJ-02 均可,
    两点坐标系须一致).
    """
    R = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return R * c
