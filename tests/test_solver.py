import unittest
from src.solver import PackingSolver, rotate_points, generate_unique_orientations
from src.data_models import Shape, PackingStatus


class TestSolverRotation(unittest.TestCase):
    """测试求解器的旋转与求解逻辑。"""

    def test_orientation_deduplication(self):
        """测试不同形状在旋转时的去重逻辑。"""
        # 正方形旋转 4 次应只有 1 种唯一方向
        square_points = [(0, 0), (1, 0), (0, 1), (1, 1)]
        square_orientations = generate_unique_orientations(square_points)
        self.assertEqual(len(square_orientations), 1)

        # 1x3 的条形旋转 4 次应只有 2 种唯一方向
        i3_points = [(0, 0), (0, 1), (0, 2)]
        i3_orientations = generate_unique_orientations(i3_points)
        self.assertEqual(len(i3_orientations), 2)

        # 不对称的 SG 形状旋转 4 次应有 4 种唯一方向
        sg_points = [(0, 0), (1, 0), (2, 0), (0, 1)]
        sg_orientations = generate_unique_orientations(sg_points)
        self.assertEqual(len(sg_orientations), 4)

    def test_solve_with_rotation(self):
        """测试当形状必须旋转才能放入棋盘时的求解情况。"""
        # 定义一个 4x2 的条形 (laser)
        laser_points = [(0, 0), (1, 0), (2, 0), (3, 0), (0, 1)]
        shape = Shape(
            name="laser",
            points=laser_points,
            area=5,
            color="#FFFFFF"
        )
        
        # 棋盘大小为 2x4
        # laser 形状默认宽度为 4，高度为 2。如果不允许旋转（或者旋转实现有误），则放不进 2x4 的棋盘。
        # 如果允许旋转，旋转 90 度或 270 度后尺寸变为 2x4，就能装入棋盘。
        board_size = (2, 4)
        allowed_cells = [(r, c) for r in range(4) for c in range(2)]
        
        solver = PackingSolver(
            shapes_to_pack=[shape],
            board_size=board_size,
            allowed_cells=allowed_cells
        )
        result = solver.solve()
        
        self.assertEqual(result.status, PackingStatus.OPTIMAL)
        self.assertEqual(len(result.placed_shapes), 1)
        self.assertEqual(result.placed_shapes[0].name, "laser")
        # 验证旋转角度是否为 90 或 270 度之一
        self.assertIn(result.placed_shapes[0].rotation, [90, 270])


if __name__ == "__main__":
    unittest.main()
