import os
from collections import defaultdict
from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import CpSolverSolutionCallback
from typing import List, Dict, Tuple, Optional

from .data_models import Shape, PlacedShape, PackingResult, PackingStatus
from .decomposition import decompose_shape_to_rectangles


class SolutionCallback(CpSolverSolutionCallback):
    """
    一个回调类，用于在找到满足特定条件的解时提前停止搜索。
    """

    def __init__(self, shape_vars, board_area, total_shapes_count, strategy):
        super().__init__()
        self._shape_vars = shape_vars
        self._board_area = board_area
        self._total_shapes_count = total_shapes_count
        self._strategy = strategy
        self.solution = None
        self._best_objective_value = -1  # 用于记录找到的最佳目标值

    def on_solution_callback(self):
        """在每次找到可行解时被调用。"""
        placed_shapes_count = sum(self.Value(s["is_used"]) for s in self._shape_vars)
        current_area = sum(s["area"] * self.Value(s["is_used"]) for s in self._shape_vars)

        # 检查是否达成了“完美解”并提前停止
        if self._strategy == "P0":  # 策略：装下所有形状
            if placed_shapes_count == self._total_shapes_count:
                print("完美解达成 (P0): 所有形状已装入。停止搜索。")
                self.StopSearch()

        elif self._strategy == "P1":  # 策略：占满棋盘
            if current_area == self._board_area:
                print("完美解达成 (P1): 棋盘已占满。停止搜索。")
                self.StopSearch()

        # 仅当当前解更优时，才保存它
        if current_area > self._best_objective_value:
            self._best_objective_value = current_area
            print(f"找到更优解: 面积 = {current_area}。已保存。")
            self.solution = {
                "placed_shapes": [
                    {
                        "name": s["name"],
                        "x": self.Value(s["x"]),
                        "y": self.Value(s["y"]),
                        "points": s["points"],
                        "color": s["color"],
                    }
                    for s in self._shape_vars if self.Value(s["is_used"])
                ],
                "unplaced_shapes": [
                    s["original_shape"].name for s in self._shape_vars if not self.Value(s["is_used"])
                ],
            }


class PackingSolver:
    """
    使用 CP-SAT 求解器解决二维不规则形状背包问题。
    """

    def __init__(
        self,
        shapes_to_pack: List[Shape],
        board_size: Tuple[int, int],
        allowed_cells: Optional[List[Tuple[int, int]]] = None,
        must_place_names: Optional[List[str]] = None,
        time_limit_sec: int = 30,
    ):
        self.shapes_to_pack = shapes_to_pack
        self.board_width, self.board_height = board_size
        self.allowed_cells = allowed_cells
        self.must_place_names = must_place_names if must_place_names is not None else []
        self.time_limit_sec = time_limit_sec

        self.model = cp_model.CpModel()
        self.shape_vars: List[Dict] = []
        self.decomposed_shapes: Dict[str, List[Tuple[int, int, int, int]]] = {}

    def solve(self) -> PackingResult:
        """
        执行主要的求解逻辑并返回一个 PackingResult 对象。
        """
        if not self.allowed_cells:
            return PackingResult(
                placed_shapes=[],
                unplaced_shapes=[s.name for s in self.shapes_to_pack],
                board_size=(self.board_width, self.board_height),
                status=PackingStatus.INFEASIBLE,
            )

        self._prepare_data()
        self._create_variables()
        self._add_constraints()
        self._set_objective()

        # --- 步骤 5: 预处理和策略选择 ---
        total_shape_area = sum(s.area for s in self.shapes_to_pack)
        board_area = len(self.allowed_cells)
        strategy = "P0" if total_shape_area <= board_area else "P1"
        print(f"预处理: 形状总面积={total_shape_area}, 棋盘面积={board_area}. 采用策略: {strategy}")

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_sec

        num_cores = os.cpu_count() or 1
        num_workers = max(1, num_cores // 2)
        solver.parameters.num_search_workers = num_workers
        print(f"求解器将使用 {num_workers} (共 {num_cores} 个逻辑核心)。")

        # --- 步骤 6 & 7: 实例化回调并使用 SearchForAllSolutions ---
        solution_callback = SolutionCallback(
            self.shape_vars, board_area, len(self.shapes_to_pack), strategy
        )
        status = solver.Solve(self.model, solution_callback)

        return self._process_solution(solver, status, solution_callback)

    def _prepare_data(self):
        """预处理数据，例如分解形状。"""
        for shape in self.shapes_to_pack:
            if shape.name not in self.decomposed_shapes:
                self.decomposed_shapes[shape.name] = decompose_shape_to_rectangles(shape.points)

    def _create_variables(self):
        """为模型创建变量。"""
        for i, shape in enumerate(self.shapes_to_pack):
            max_dx = max(p[0] for p in shape.points) if shape.points else 0
            max_dy = max(p[1] for p in shape.points) if shape.points else 0
            shape_width = max_dx + 1
            shape_height = max_dy + 1

            is_used = self.model.NewBoolVar(f"is_used_{i}")
            x = self.model.NewIntVar(0, self.board_width - shape_width, f"x_{i}")
            y = self.model.NewIntVar(0, self.board_height - shape_height, f"y_{i}")

            self.shape_vars.append(
                {
                    "id": i,
                    "name": shape.name,
                    "points": shape.points,
                    "area": shape.area,
                    "color": shape.color,
                    "is_used": is_used,
                    "x": x,
                    "y": y,
                    "original_shape": shape,
                }
            )

    def _add_constraints(self):
        """向模型添加约束。"""
        # 必须放置的形状
        if self.must_place_names:
            for s in self.shape_vars:
                if s["name"] in self.must_place_names:
                    self.model.Add(s["is_used"] == 1)

        # 单元格必须在允许的范围内
        allowed_cells_set = {tuple(cell) for cell in self.allowed_cells}
        allowed_indices = [(r * self.board_width + c,) for r, c in allowed_cells_set]

        for s in self.shape_vars:
            occupied_cells = []
            for p_dx, p_dy in s["points"]:
                cell_var = self.model.NewIntVar(
                    0, self.board_height * self.board_width - 1, f"cell_{s['id']}_{p_dx}_{p_dy}"
                )
                self.model.Add(cell_var == (s["y"] + p_dy) * self.board_width + (s["x"] + p_dx))
                occupied_cells.append(cell_var)

            for cell in occupied_cells:
                self.model.AddAllowedAssignments([cell], allowed_indices).OnlyEnforceIf(s["is_used"])

        # 不重叠约束
        all_x_intervals = []
        all_y_intervals = []
        for s in self.shape_vars:
            rectangles = self.decomposed_shapes[s["name"]]
            for k, rect in enumerate(rectangles):
                rect_dx, rect_dy, rect_w, rect_h = rect

                x_start = self.model.NewIntVar(0, self.board_width, f"x_start_{s['id']}_{k}")
                x_end = self.model.NewIntVar(0, self.board_width, f"x_end_{s['id']}_{k}")
                self.model.Add(x_start == s["x"] + rect_dx)
                self.model.Add(x_end == x_start + rect_w)
                x_interval = self.model.NewOptionalIntervalVar(
                    x_start, rect_w, x_end, s["is_used"], f"x_interval_{s['id']}_{k}"
                )

                y_start = self.model.NewIntVar(0, self.board_height, f"y_start_{s['id']}_{k}")
                y_end = self.model.NewIntVar(0, self.board_height, f"y_end_{s['id']}_{k}")
                self.model.Add(y_start == s["y"] + rect_dy)
                self.model.Add(y_end == y_start + rect_h)
                y_interval = self.model.NewOptionalIntervalVar(
                    y_start, rect_h, y_end, s["is_used"], f"y_interval_{s['id']}_{k}"
                )

                all_x_intervals.append(x_interval)
                all_y_intervals.append(y_interval)

        self.model.AddNoOverlap2D(all_x_intervals, all_y_intervals)

        # 对称性破坏
        grouped_shapes = defaultdict(list)
        for s in self.shape_vars:
            grouped_shapes[s["name"]].append(s)

        for instances in grouped_shapes.values():
            if len(instances) > 1:
                for i in range(len(instances) - 1):
                    s1 = instances[i]
                    s2 = instances[i + 1]
                    self.model.Add(s1["x"] <= s2["x"]).OnlyEnforceIf([s1["is_used"], s2["is_used"]])

    def _set_objective(self):
        """设置优化目标。"""
        total_area = sum(s["area"] * s["is_used"] for s in self.shape_vars)
        self.model.Maximize(total_area)

    def _process_solution(
        self, solver: cp_model.CpSolver, status: int, callback: SolutionCallback
    ) -> PackingResult:
        """处理求解器的结果并返回 PackingResult。"""
        status_map = {
            cp_model.OPTIMAL: PackingStatus.OPTIMAL,
            cp_model.FEASIBLE: PackingStatus.FEASIBLE,
            cp_model.INFEASIBLE: PackingStatus.INFEASIBLE,
            cp_model.UNKNOWN: PackingStatus.UNKNOWN,
            cp_model.MODEL_INVALID: PackingStatus.MODEL_INVALID,
        }
        packing_status = status_map.get(status, PackingStatus.UNKNOWN)

        placed_shapes = []
        unplaced_shape_names = [s.name for s in self.shapes_to_pack]

        # --- 步骤 8: 调整以适应回调函数 ---
        # 如果回调函数找到了一个解（无论是完美的还是最后的），使用它
        if callback.solution:
            print("从回调函数中处理解决方案。")
            placed_shapes = [
                PlacedShape(
                    name=ps["name"],
                    x=ps["x"],
                    y=ps["y"],
                    points=ps["points"],
                    color=ps["color"],
                )
                for ps in callback.solution["placed_shapes"]
            ]
            unplaced_shape_names = callback.solution["unplaced_shapes"]
        # 如果没有找到解 (INFEASIBLE)
        elif status == cp_model.INFEASIBLE:
            print("未找到可行解。")
            placed_shapes = []
            unplaced_shape_names = [s.name for s in self.shapes_to_pack]

        return PackingResult(
            placed_shapes=placed_shapes,
            unplaced_shapes=unplaced_shape_names,
            board_size=(self.board_width, self.board_height),
            status=packing_status,
        )


def solve_packing(
    shapes_to_pack: List[Dict],
    allowed_cells: Optional[List[Tuple[int, int]]] = None,
    board_size: Tuple[int, int] = (10, 10),
    must_place_names: Optional[List[str]] = None,
    time_limit_sec: int = 30,
) -> Tuple[List[Dict], List[str], str]:
    """
    用于与 gui.py 兼容的包装函数。
    """
    # 1. 将 List[Dict] 转换为 List[Shape]
    shape_objects = [
        Shape(
            name=shape_dict["name"],
            points=shape_dict["points"],
            color=shape_dict["color"],
            area=len(shape_dict["points"]),
        )
        for shape_dict in shapes_to_pack
    ]

    # 2. 实例化并运行求解器
    solver = PackingSolver(
        shapes_to_pack=shape_objects,
        board_size=board_size,
        allowed_cells=allowed_cells,
        must_place_names=must_place_names,
        time_limit_sec=time_limit_sec,
    )
    result = solver.solve()

    # 3. 将 PackingResult 转换回 gui.py 期望的格式
    placed_shapes_dicts = []
    if result.placed_shapes:
        for ps in result.placed_shapes:
            placed_shapes_dicts.append(
                {
                    "name": ps.name,
                    "position": (ps.x, ps.y),
                    "points": ps.points,
                    "color": ps.color,
                }
            )

    # gui.py 期望一个包含未放置形状名称的列表
    unplaced_shape_names = result.unplaced_shapes

    # 模拟旧的返回格式
    # 注意：旧格式返回一个复杂的字典，而 gui.py 可能只关心其中的一部分。
    # 这里我们返回一个元组 (placed_shapes_dicts, unplaced_shape_names)
    # 这与 gui.py 中 `handle_solution` 的调用签名 `(solution["placed_shapes"], unplaced_names)` 匹配
    return placed_shapes_dicts, unplaced_shape_names, result.status.name
