import unittest
import tkinter as tk
from gui import ShapePackingGUI


class TestGUI(unittest.TestCase):
    """测试 GUI 界面中的数据计算与更新逻辑。"""

    def setUp(self):
        self.app = ShapePackingGUI()
        # 隐藏窗口以防在运行测试时弹出界面
        self.app.withdraw()

    def tearDown(self):
        self.app.destroy()

    def test_board_area_initial(self):
        """测试初始状态下棋盘总面积是否计算正确。"""
        # 默认容器网格：行 2<=r<=6，列 3<=c<=5 处于可用状态，共 5 * 3 = 15 个格子
        self.assertEqual(self.app.board_area_var.get(), "棋盘总面积: 15")

    def test_board_area_unlock_all(self):
        """测试解锁全部格子后棋盘总面积是否为 81。"""
        self.app.unlock_all_cells()
        self.assertEqual(self.app.board_area_var.get(), "棋盘总面积: 81")

    def test_board_area_toggle(self):
        """测试手动点击/切换格子状态时，棋盘总面积是否同步更新。"""
        # 切换 (2, 3) 状态（原为 1，切换后应为 0，面积减 1）
        self.app.toggle_container_cell(2, 3)
        self.assertEqual(self.app.board_area_var.get(), "棋盘总面积: 14")

        # 再次切换 (2, 3) 状态（原为 0，切换后应为 1，面积加 1）
        self.app.toggle_container_cell(2, 3)
        self.assertEqual(self.app.board_area_var.get(), "棋盘总面积: 15")


if __name__ == "__main__":
    unittest.main()
