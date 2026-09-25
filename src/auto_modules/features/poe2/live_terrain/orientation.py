"""方向变换 for PoE2 native terrain and minimap coordinates.

方向属于 PoE2 数据适配契约，不下沉到通用定位引擎。所有数组、点和
局部位移都必须通过同一个 :class:`TerrainOrientation` 变换，避免展示和
匹配各自采用一套轴向规则。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .terrain_reference import TerrainReference


@dataclass(frozen=True)
class TerrainOrientation:
    """将 native 地图变换到小地图/展示所使用的方向。

    ``rotation`` 表示顺时针旋转角度。水平、垂直翻转发生在旋转之后，
    这样点坐标和数组的语义始终一致。
    """

    rotation: int = 0
    flip_horizontal: bool = False
    flip_vertical: bool = False

    def __post_init__(self) -> None:
        rotation = int(self.rotation) % 360
        if rotation not in (0, 90, 180, 270):
            raise ValueError("rotation must be one of 0, 90, 180, 270")
        object.__setattr__(self, "rotation", rotation)
        object.__setattr__(self, "flip_horizontal", bool(self.flip_horizontal))
        object.__setattr__(self, "flip_vertical", bool(self.flip_vertical))

    @property
    def is_identity(self) -> bool:
        return self.rotation == 0 and not self.flip_horizontal and not self.flip_vertical

    def transform_array(self, value) -> np.ndarray:
        """返回方向变换后的独立数组，不修改输入。"""
        result = np.array(value, copy=True)
        if result.ndim != 2:
            raise ValueError("terrain orientation only accepts 2-D arrays")
        if self.rotation:
            # np.rot90 的正方向是逆时针；负 k 即顺时针。
            result = np.rot90(result, k=-(self.rotation // 90))
        if self.flip_horizontal:
            result = np.fliplr(result)
        if self.flip_vertical:
            result = np.flipud(result)
        return np.ascontiguousarray(result)

    def transformed_shape(self, shape: tuple[int, int]) -> tuple[int, int]:
        height, width = (int(shape[0]), int(shape[1]))
        if self.rotation in (90, 270):
            height, width = width, height
        return height, width

    def transform_point(self, point, shape: tuple[int, int]) -> tuple[float, float]:
        """把原数组坐标 ``(x, y)`` 转成变换后数组坐标。"""
        x, y = float(point[0]), float(point[1])
        height, width = int(shape[0]), int(shape[1])
        if self.rotation == 90:
            x, y = height - 1 - y, x
        elif self.rotation == 180:
            x, y = width - 1 - x, height - 1 - y
        elif self.rotation == 270:
            x, y = y, width - 1 - x
        rotated_height, rotated_width = self.transformed_shape(shape)
        if self.flip_horizontal:
            x = rotated_width - 1 - x
        if self.flip_vertical:
            y = rotated_height - 1 - y
        return x, y

    def transform_delta(self, delta) -> tuple[float, float]:
        """变换局部位移向量；平移常量在这里会被抵消。"""
        dx, dy = float(delta[0]), float(delta[1])
        if self.rotation == 90:
            dx, dy = -dy, dx
        elif self.rotation == 180:
            dx, dy = -dx, -dy
        elif self.rotation == 270:
            dx, dy = dy, -dx
        if self.flip_horizontal:
            dx = -dx
        if self.flip_vertical:
            dy = -dy
        return dx, dy

    def transform_reference(self, reference: TerrainReference) -> TerrainReference:
        if self.is_identity:
            return reference
        shape = self.transformed_shape(reference.shape)
        metadata = dict(reference.metadata)
        metadata["orientation"] = self.as_dict()
        return TerrainReference(
            walkable_mask=self.transform_array(reference.walkable_mask),
            wall_layer=self.transform_array(reference.wall_layer),
            explored_map=self.transform_array(reference.explored_map),
            width=shape[1],
            height=shape[0],
            metadata=metadata,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "rotation": self.rotation,
            "flip_horizontal": self.flip_horizontal,
            "flip_vertical": self.flip_vertical,
        }


__all__ = ["TerrainOrientation"]
