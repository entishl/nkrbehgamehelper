from typing import List, Tuple
from .data_models import Shape, Rectangle


def decompose_shape_to_rectangles(points):
    """
    将一个由点集定义的形状分解为不重叠的矩形列表。
    使用基于扫描线和合并的贪心算法。
    返回 [(dx, dy, width, height), ...]
    """
    if not points:
        return []

    point_set = {tuple(p) for p in points}
    rectangles = []

    while point_set:
        # 找到 y 最小、然后 x 最小的点作为起始点
        start_point = min(point_set, key=lambda p: (p[1], p[0]))
        x, y = start_point

        # 1. 向右延伸找到最大宽度
        width = 1
        while (x + width, y) in point_set:
            width += 1

        # 2. 将此线段向下延伸找到最大高度
        height = 1
        while True:
            # 检查下一行是否所有点都存在
            next_row_solid = True
            for i in range(width):
                if (x + i, y + height) not in point_set:
                    next_row_solid = False
                    break
            if next_row_solid:
                height += 1
            else:
                break

        # 将生成的矩形添加到列表
        rectangles.append((x, y, width, height))

        # 从点集中移除构成该矩形的所有点
        points_to_remove = set()
        for i in range(width):
            for j in range(height):
                points_to_remove.add((x + i, y + j))

        point_set -= points_to_remove

    return rectangles
