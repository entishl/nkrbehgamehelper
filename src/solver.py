import os
from collections import defaultdict
from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import CpSolverSolutionCallback
from typing import Dict, List, Optional, Tuple

from .data_models import Shape, PlacedShape, PackingResult, PackingStatus

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


def generate_unique_orientations(points: List[Point], allow_rotation: bool = True) -> List[Dict]:
    """Return unique orientations for a shape (only 0-degree if allow_rotation is False)."""
    orientations = []
    seen = set()

    rotations = (0, 90, 180, 270) if allow_rotation else (0,)
    for rotation in rotations:
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
            }
        )

    return orientations


def extract_solution_from_provider(shape_vars: List[Dict], value_provider) -> Tuple[List[PlacedShape], List[str]]:
    """从求解器或回调函数中提取放置结果。"""
    placed_shapes = []
    unplaced_shapes = []
    for s in shape_vars:
        if not value_provider.Value(s["is_used"]):
            unplaced_shapes.append(s["original_shape"].name)
            continue

        selected_orientation = None
        for orientation in s["orientations"]:
            if value_provider.Value(orientation["is_used"]):
                selected_orientation = orientation
                break

        if selected_orientation is None:
            unplaced_shapes.append(s["original_shape"].name)
            continue

        # Find the specific placement that was selected
        x, y = 0, 0
        for b_pos, px, py in selected_orientation["placements"]:
            if value_provider.Value(b_pos):
                x, y = px, py
                break

        placed_shapes.append(
            PlacedShape(
                name=s["name"],
                x=x,
                y=y,
                points=selected_orientation["points"],
                color=s["color"],
                rotation=selected_orientation["rotation"],
            )
        )
    return placed_shapes, unplaced_shapes


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
            placed_shapes, unplaced_shapes = extract_solution_from_provider(self._shape_vars, self)
            self.solution = {
                "placed_shapes": placed_shapes,
                "unplaced_shapes": unplaced_shapes,
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
        allow_rotation: bool = True,
    ):
        self.shapes_to_pack = shapes_to_pack
        self.board_width, self.board_height = board_size
        self.allowed_cells = allowed_cells
        self.must_place_names = must_place_names if must_place_names is not None else []
        self.time_limit_sec = time_limit_sec
        self.allow_rotation = allow_rotation

        self.model = cp_model.CpModel()
        self.shape_vars: List[Dict] = []
        self.orientation_cache: Dict[Tuple[Point, ...], List[Dict]] = {}
        self.valid_position_cache: Dict[Tuple[Point, ...], List[Tuple[int, int]]] = {}
        self.allowed_cells_set = {tuple(cell) for cell in self.allowed_cells} if self.allowed_cells else set()

    def _valid_positions_for_orientation(self, points: List[Point], width: int, height: int) -> List[Tuple[int, int]]:
        valid = []
        for x in range(self.board_width - width + 1):
            for y in range(self.board_height - height + 1):
                if all((x + dx, y + dy) in self.allowed_cells_set for dx, dy in points):
                    valid.append((x, y))
        return valid

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

        # 确定策略
        total_shape_area = sum(s.area for s in self.shapes_to_pack)
        board_area = len(self.allowed_cells)
        strategy = "P0" if total_shape_area <= board_area else "P1"
        print(f"预处理: 形状总面积={total_shape_area}, 棋盘面积={board_area}. 采用策略: {strategy}")

        # 计算线程数
        num_cores = os.cpu_count() or 1
        num_workers = max(1, num_cores // 2)

        # ==========================================
        # 阶段 1: 尝试寻找完美解 (Feasibility Pass)
        # ==========================================
        # 设定一个较短的超时时间，例如最长 2 秒且不超过总时间限制的一半
        feasibility_time_limit = min(2, self.time_limit_sec // 2)

        if feasibility_time_limit > 0:
            print(f"--- 阶段 1: 尝试寻找完美解 (限时 {feasibility_time_limit} 秒) ---")

            # 构建阶段 1 的临时模型
            self.model = cp_model.CpModel()
            self.shape_vars = []
            self._create_variables()
            self._add_constraints()

            # 强加完美解的强制约束
            if strategy == "P0":
                for s in self.shape_vars:
                    self.model.Add(s["is_used"] == 1)
            else:  # P1
                total_area = sum(s["area"] * s["is_used"] for s in self.shape_vars)
                self.model.Add(total_area == board_area)
                
            # ---- 新增：精确覆盖的强制全网格覆盖约束 ----
            if (strategy == "P0" and total_shape_area == board_area) or strategy == "P1":
                for c_var in self.cell_covered_vars.values():
                    self.model.Add(c_var == 1)
            # ------------------------------------------

            # 不设 Objective
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = feasibility_time_limit
            solver.parameters.num_search_workers = num_workers
            print(f"第一阶段求解器将使用 {num_workers} 个逻辑核心。")

            status = solver.Solve(self.model)

            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                print("阶段 1 成功：找到完美解！")
                placed_shapes, unplaced_shape_names = extract_solution_from_provider(self.shape_vars, solver)
                status_map = {
                    cp_model.OPTIMAL: PackingStatus.OPTIMAL,
                    cp_model.FEASIBLE: PackingStatus.FEASIBLE,
                }
                return PackingResult(
                    placed_shapes=placed_shapes,
                    unplaced_shapes=unplaced_shape_names,
                    board_size=(self.board_width, self.board_height),
                    status=status_map.get(status, PackingStatus.FEASIBLE),
                )

            print("阶段 1 未能在限制时间内找到完美解或已确定无完美解。")

        # ==========================================
        # 阶段 2: 标准的最大化面积优化求解
        # ==========================================
        print(f"--- 阶段 2: 最大化面积优化 (限时 {self.time_limit_sec} 秒) ---")

        # 重置并重新构建模型
        self.model = cp_model.CpModel()
        self.shape_vars = []
        self._create_variables()
        self._add_constraints()
        self._set_objective()

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_sec
        solver.parameters.num_search_workers = num_workers
        print(f"第二阶段求解器将使用 {num_workers} 个逻辑核心。")

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
                self.orientation_cache[cache_key] = generate_unique_orientations(
                    normalized_points, allow_rotation=self.allow_rotation
                )

    def _get_shape_orientations(self, shape: Shape) -> List[Dict]:
        normalized_points = normalize_points([tuple(p) for p in shape.points])
        return self.orientation_cache[tuple(normalized_points)]

    def _create_variables(self):
        """为模型创建变量。"""
        self.cell_to_placement_vars = {cell: [] for cell in self.allowed_cells_set}
        
        # 预先计算中心对称性 (Point Symmetry / 180-degree rotation)
        # 我们不能使用水平或垂直镜像，因为形状本身不一定允许镜像翻转，只允许旋转。
        # 180度旋转始终是安全的，因为它不改变任何形状的手性。
        point_sym = True
        for x, y in self.allowed_cells_set:
            if (self.board_width - 1 - x, self.board_height - 1 - y) not in self.allowed_cells_set:
                point_sym = False
                break
                
        anchor_idx = -1
        max_area = -1
        if point_sym:
            for i, shape in enumerate(self.shapes_to_pack):
                if shape.area > max_area:
                    max_area = shape.area
                    anchor_idx = i

        for i, shape in enumerate(self.shapes_to_pack):
            is_used = self.model.NewBoolVar(f"is_used_{i}")
            orientation_vars = []

            for j, orientation_data in enumerate(self._get_shape_orientations(shape)):
                shape_width = orientation_data["width"]
                shape_height = orientation_data["height"]

                # 该朝向在棋盘尺寸内完全不可能放下时，不创建候选变量。
                if shape_width > self.board_width or shape_height > self.board_height:
                    continue

                cache_key = tuple(orientation_data["points"])
                if cache_key not in self.valid_position_cache:
                    self.valid_position_cache[cache_key] = self._valid_positions_for_orientation(
                        orientation_data["points"],
                        shape_width,
                        shape_height,
                    )
                valid_positions = self.valid_position_cache[cache_key]

                # ----- 对称性破坏 (仅针对面积最大的 anchor shape) -----
                if i == anchor_idx:
                    filtered_positions = []
                    board_center_x = (self.board_width - 1) / 2.0
                    board_center_y = (self.board_height - 1) / 2.0
                    for px, py in valid_positions:
                        center_x = px + (shape_width - 1) / 2.0
                        center_y = py + (shape_height - 1) / 2.0
                        
                        # 在中心对称的棋盘上，限制锚点形状只能出现在上半部分，
                        # 或者刚好在中轴线上时，限制在左半部分。
                        # 这样安全地砍掉恰好一半的搜索空间。
                        if center_y < board_center_y or (center_y == board_center_y and center_x <= board_center_x):
                            filtered_positions.append((px, py))
                    valid_positions = filtered_positions
                # ----------------------------------------

                if not valid_positions:
                    continue

                orientation_is_used = self.model.NewBoolVar(f"is_used_{i}_rot_{orientation_data['rotation']}")

                # 为这个朝向的每个合法位置创建一个布尔变量 (Boolean Grid Model)
                placement_bools = []
                placements = []
                
                for px, py in valid_positions:
                    b_pos = self.model.NewBoolVar(f"pos_{i}_rot_{orientation_data['rotation']}_{px}_{py}")
                    placement_bools.append(b_pos)
                    placements.append((b_pos, px, py))
                    
                    # 将这个摆法添加到它覆盖的格子列表中
                    for dx, dy in orientation_data["points"]:
                        cx, cy = px + dx, py + dy
                        if (cx, cy) in self.cell_to_placement_vars:
                            self.cell_to_placement_vars[(cx, cy)].append(b_pos)

                # 将位置布尔变量与兼容旧 API 的整数变量关联
                self.model.Add(orientation_is_used == sum(placement_bools))

                orientation_vars.append(
                    {
                        "rotation": orientation_data["rotation"],
                        "points": orientation_data["points"],
                        "width": shape_width,
                        "height": shape_height,
                        "is_used": orientation_is_used,
                        "placements": placements,
                        "valid_positions": valid_positions,
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

        # --- 新的不重叠约束 (基于布尔网格) ---
        self.cell_covered_vars = {}
        for cell, pos_vars in self.cell_to_placement_vars.items():
            if pos_vars:
                # 每个格子最多被一个形状的一个位置覆盖
                self.model.AddAtMostOne(pos_vars)
                # 定义 CellCovered 布尔变量 (用于死角预防和完整覆盖验证)
                c_var = self.model.NewBoolVar(f"cell_covered_{cell[0]}_{cell[1]}")
                self.model.Add(c_var == sum(pos_vars))
                self.cell_covered_vars[cell] = c_var
            else:
                # 没有任何形状可以覆盖到这个格子
                c_var = self.model.NewBoolVar(f"cell_covered_{cell[0]}_{cell[1]}")
                self.model.Add(c_var == 0)
                self.cell_covered_vars[cell] = c_var



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
            placed_shapes = callback.solution["placed_shapes"]
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
    allow_rotation: bool = True,
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
        allow_rotation=allow_rotation,
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
