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
        allowed_cells = [(c, r) for r in range(4) for c in range(2)]
        
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

    def test_solve_without_rotation(self):
        """测试当不允许旋转时，形状必须以初始方向放入棋盘的逻辑。"""
        # 定义一个 4x2 的条形 (laser)
        laser_points = [(0, 0), (1, 0), (2, 0), (3, 0), (0, 1)]
        shape = Shape(
            name="laser",
            points=laser_points,
            area=5,
            color="#FFFFFF"
        )
        
        # 棋盘大小为 2x4
        # laser 形状默认宽度为 4，高度为 2。如果不允许旋转，它无法装入 2x4 的棋盘（因为 4 > 2 宽度超出）。
        board_size = (2, 4)
        allowed_cells = [(c, r) for r in range(4) for c in range(2)]
        
        solver = PackingSolver(
            shapes_to_pack=[shape],
            board_size=board_size,
            allowed_cells=allowed_cells,
            must_place_names=["laser"],
            allow_rotation=False
        )
        result = solver.solve()
        
        self.assertEqual(result.status, PackingStatus.INFEASIBLE)
        self.assertEqual(len(result.placed_shapes), 0)

    def test_orientation_without_rotation(self):
        """测试 allow_rotation=False 时，生成唯一方向的数量。"""
        # 不对称的 SG 形状，如果允许旋转有 4 种方向，如果不允许旋转应该只有 1 种。
        sg_points = [(0, 0), (1, 0), (2, 0), (0, 1)]
        sg_orientations = generate_unique_orientations(sg_points, allow_rotation=False)
        self.assertEqual(len(sg_orientations), 1)
        self.assertEqual(sg_orientations[0]["rotation"], 0)

    def test_solve_with_duplicate_and_out_of_bounds_cells(self):
        """测试 allowed_cells 中有重复格子和越界格子时的求解行为。"""
        # 定义一个 2x2 的正方形形状
        square_points = [(0, 0), (1, 0), (0, 1), (1, 1)]
        shape = Shape(
            name="square",
            points=square_points,
            area=4,
            color="#FFFFFF"
        )
        
        # 棋盘大小为 2x2
        board_size = (2, 2)
        # 传入的 allowed_cells 包含重复格子 (0, 0) 和越界格子 (2, 2), (-1, 0)
        allowed_cells = [(0, 0), (0, 0), (1, 0), (0, 1), (1, 1), (2, 2), (-1, 0)]
        
        solver = PackingSolver(
            shapes_to_pack=[shape],
            board_size=board_size,
            allowed_cells=allowed_cells
        )
        result = solver.solve()
        
        # 即使有重复和越界格子，由于去重和过滤，实际可用面积应为 4
        # 形状面积也是 4，应该能成功以 OPTIMAL 状态装入
        self.assertEqual(result.status, PackingStatus.OPTIMAL)
        self.assertEqual(len(result.placed_shapes), 1)
        self.assertEqual(result.placed_shapes[0].name, "square")

    def test_symmetry_pruning_with_rotation_disabled(self):
        """测试在禁止旋转的情况下，对称性剪枝不会导致漏掉唯一可行解。"""
        # A: 2x2 正方形 (具有 180 度对称性)，面积为 4
        # B: L型三格板 (不具有 180 度对称性)，面积为 3
        shape_a = Shape(
            name="square_A",
            points=[(0, 0), (1, 0), (0, 1), (1, 1)],
            area=4,
            color="#FF0000"
        )
        shape_b = Shape(
            name="L_B",
            points=[(0, 0), (1, 0), (0, 1)],
            area=3,
            color="#00FF00"
        )
        
        # 3x3 棋盘，全网格可用
        board_size = (3, 3)
        allowed_cells = [(c, r) for r in range(3) for c in range(3)]
        
        # 强制要求两个形状都必须放置
        solver = PackingSolver(
            shapes_to_pack=[shape_a, shape_b],
            board_size=board_size,
            allowed_cells=allowed_cells,
            must_place_names=["square_A", "L_B"],
            allow_rotation=False
        )
        result = solver.solve()
        
        # 如果有对称性剪枝的 bug，这会返回 INFEASIBLE。
        # 修复后应该能找到 OPTIMAL 解。
        self.assertEqual(result.status, PackingStatus.OPTIMAL)
        self.assertEqual(len(result.placed_shapes), 2)


if __name__ == "__main__":
    unittest.main()

