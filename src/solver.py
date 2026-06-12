import os
from collections import defaultdict
from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import CpSolverSolutionCallback
from typing import Dict, List, Optional, Tuple

from .data_models import Shape, PlacedShape, PackingResult, PackingStatus
from .decomposition import decompose_shape_to_rectangles

Point = Tuple[int, int]


def normalize_points(points: List[Point]) -> List[Point]:
    """Normalize points so the shape's top-left occupied cell is (0, 0)."""
    if not points:
        return []

    min_x = min(x for x, _ in points)
    min_y = min(y for _, y in points)
    return sorted((x - min_x, y - min_y) for x, y in points)


def rotate_points(points: List[Point], rotation: int) -> List[Point]:
    """Rotate points clockwise by 0/90/180/270 degrees and normalize them."""
    normalized_points = normalize_points(points)

    if rotation == 0:
        rotated = normalized_points
    elif rotation == 90:
        rotated = [(y, -x) for x, y in normalized_points]
    elif rotation == 180:
        rotated = [(-x, -y) for x, y in normalized_points]
    elif rotation == 270:
        rotated = [(-y, x) for x, y in normalized_points]
    else:
        raise ValueError("rotation must be one of 0, 90, 180, or 270")

    return normalize_points(rotated)


def generate_unique_orientations(points: List[Point]) -> List[Dict]:
    """Return unique 0/90/180/270-degree orientations for a shape."""
    orientations = []
    seen = set()

    for rotation in (0, 90, 180, 270):
        rotated_points = rotate_points(points, rotation)
        key = tuple(rotated_points)
        if key in seen:
            continue

        seen.add(key)
        width = max((x for x, _ in rotated_points), default=-1) + 1
        height = max((y for _, y in rotated_points), default=-1) + 1
        orientations.append(
            {
                "rotation": rotation,
                "points": rotated_points,
                "width": width,
                "height": height,
                "rectangles": decompose_shape_to_rectangles(rotated_points),
            }
        )

    return orientations


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

        # 仅当当前解更优时，才保存它
        if current_area > self._best_objective_value:
            self._best_objective_value = current_area
            print(f"找到更优解: 面积 = {current_area}。已保存。")
            placed_shapes = []
            for s in self._shape_vars:
                if not self.Value(s["is_used"]):
                    continue

                selected_orientation = None
                for orientation in s["orientations"]:
                    if self.Value(orientation["is_used"]):
                        selected_orientation = orientation
                        break

                if selected_orientation is None:
                    continue

                placed_shapes.append(
                    {
                        "name": s["name"],
                        "x": self.Value(selected_orientation["x"]),
                        "y": self.Value(selected_orientation["y"]),
                        "points": selected_orientation["points"],
                        "color": s["color"],
                        "rotation": selected_orientation["rotation"],
                    }
                )

            self.solution = {
                "placed_shapes": placed_shapes,
                "unplaced_shapes": [
                    s["original_shape"].name for s in self._shape_vars if not self.Value(s["is_used"])
                ],
            }

        # 检查是否达成了“完美解”并提前停止
        if self._strategy == "P0":  # 策略：装下所有形状
            if placed_shapes_count == self._total_shapes_count:
                print("完美解达成 (P0): 所有形状已装入。停止搜索。")
                self.StopSearch()

        elif self._strategy == "P1":  # 策略：占满棋盘
            if current_area == self._board_area:
                print("完美解达成 (P1): 棋盘已占满。停止搜索。")
                self.StopSearch()


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
        self.orientation_cache: Dict[Tuple[Point, ...], List[Dict]] = {}

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

        # --- 步骤 6 & 7: 实例化回调并求解 ---
        solution_callback = SolutionCallback(
            self.shape_vars, board_area, len(self.shapes_to_pack), strategy
        )
        status = solver.Solve(self.model, solution_callback)

        return self._process_solution(solver, status, solution_callback)

    def _prepare_data(self):
        """预处理每个形状的唯一旋转朝向。"""
        for shape in self.shapes_to_pack:
            normalized_points = normalize_points([tuple(p) for p in shape.points])
            cache_key = tuple(normalized_points)
            if cache_key not in self.orientation_cache:
                self.orientation_cache[cache_key] = generate_unique_orientations(normalized_points)

    def _get_shape_orientations(self, shape: Shape) -> List[Dict]:
        normalized_points = normalize_points([tuple(p) for p in shape.points])
        return self.orientation_cache[tuple(normalized_points)]

    def _create_variables(self):
        """为模型创建变量。"""
        for i, shape in enumerate(self.shapes_to_pack):
            is_used = self.model.NewBoolVar(f"is_used_{i}")
            orientation_vars = []

            for j, orientation_data in enumerate(self._get_shape_orientations(shape)):
                shape_width = orientation_data["width"]
                shape_height = orientation_data["height"]

                # 该朝向在棋盘尺寸内完全不可能放下时，不创建候选变量。
                if shape_width > self.board_width or shape_height > self.board_height:
                    continue

                orientation_is_used = self.model.NewBoolVar(f"is_used_{i}_rot_{orientation_data['rotation']}")
                x = self.model.NewIntVar(0, self.board_width - shape_width, f"x_{i}_rot_{orientation_data['rotation']}")
                y = self.model.NewIntVar(0, self.board_height - shape_height, f"y_{i}_rot_{orientation_data['rotation']}")

                orientation_vars.append(
                    {
                        "rotation": orientation_data["rotation"],
                        "points": orientation_data["points"],
                        "rectangles": orientation_data["rectangles"],
                        "width": shape_width,
                        "height": shape_height,
                        "is_used": orientation_is_used,
                        "x": x,
                        "y": y,
                    }
                )

            if orientation_vars:
                self.model.Add(sum(o["is_used"] for o in orientation_vars) == is_used)
            else:
                self.model.Add(is_used == 0)

            self.shape_vars.append(
                {
                    "id": i,
                    "name": shape.name,
                    "area": shape.area,
                    "color": shape.color,
                    "is_used": is_used,
                    "orientations": orientation_vars,
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
            for orientation in s["orientations"]:
                occupied_cells = []
                for p_dx, p_dy in orientation["points"]:
                    cell_var = self.model.NewIntVar(
                        0,
                        self.board_height * self.board_width - 1,
                        f"cell_{s['id']}_{orientation['rotation']}_{p_dx}_{p_dy}",
                    )
                    self.model.Add(
                        cell_var == (orientation["y"] + p_dy) * self.board_width + (orientation["x"] + p_dx)
                    )
                    occupied_cells.append(cell_var)

                for cell in occupied_cells:
                    self.model.AddAllowedAssignments([cell], allowed_indices).OnlyEnforceIf(orientation["is_used"])

        # 不重叠约束
        all_x_intervals = []
        all_y_intervals = []
        for s in self.shape_vars:
            for orientation in s["orientations"]:
                for k, rect in enumerate(orientation["rectangles"]):
                    rect_dx, rect_dy, rect_w, rect_h = rect
                    suffix = f"{s['id']}_{orientation['rotation']}_{k}"

                    x_start = self.model.NewIntVar(0, self.board_width, f"x_start_{suffix}")
                    x_end = self.model.NewIntVar(0, self.board_width, f"x_end_{suffix}")
                    self.model.Add(x_start == orientation["x"] + rect_dx)
                    self.model.Add(x_end == x_start + rect_w)
                    x_interval = self.model.NewOptionalIntervalVar(
                        x_start, rect_w, x_end, orientation["is_used"], f"x_interval_{suffix}"
                    )

                    y_start = self.model.NewIntVar(0, self.board_height, f"y_start_{suffix}")
                    y_end = self.model.NewIntVar(0, self.board_height, f"y_end_{suffix}")
                    self.model.Add(y_start == orientation["y"] + rect_dy)
                    self.model.Add(y_end == y_start + rect_h)
                    y_interval = self.model.NewOptionalIntervalVar(
                        y_start, rect_h, y_end, orientation["is_used"], f"y_interval_{suffix}"
                    )

                    all_x_intervals.append(x_interval)
                    all_y_intervals.append(y_interval)

        if all_x_intervals:
            self.model.AddNoOverlap2D(all_x_intervals, all_y_intervals)

        # 对称性破坏：同名重复形状优先使用前面的实例，减少等价搜索分支。
        grouped_shapes = defaultdict(list)
        for s in self.shape_vars:
            grouped_shapes[s["name"]].append(s)

        for instances in grouped_shapes.values():
            if len(instances) > 1:
                for i in range(len(instances) - 1):
                    s1 = instances[i]
                    s2 = instances[i + 1]
                    self.model.Add(s1["is_used"] >= s2["is_used"])

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
            cp_model.MODEL_INVALID: PackingStatus.UNKNOWN,
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
                    rotation=ps.get("rotation", 0),
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
            area=shape_dict.get("area", len(shape_dict["points"])),
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
                    "rotation": ps.rotation,
                }
            )

    # gui.py 期望一个包含未放置形状名称的列表
    unplaced_shape_names = result.unplaced_shapes

    # 模拟旧的返回格式
    # 注意：旧格式返回一个复杂的字典，而 gui.py 可能只关心其中的一部分。
    # 这里我们返回一个元组 (placed_shapes_dicts, unplaced_shape_names)
    # 这与 gui.py 中 `handle_solution` 的调用签名 `(solution["placed_shapes"], unplaced_names)` 匹配
    return placed_shapes_dicts, unplaced_shape_names, result.status.name
