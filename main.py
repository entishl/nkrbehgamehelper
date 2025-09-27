import json
from ortools.sat.python import cp_model

# --- 1. 常量定义 ---
CONTAINER_WIDTH = 9
CONTAINER_HEIGHT = 9


def solve_packing(shapes_data, time_limit_sec=60):
    """
    使用 CP-SAT 求解器解决二维不规则形状背包问题。
    """
    model = cp_model.CpModel()

    # --- 2. 变量定义 ---
    # 为每个形状创建变量
    shape_vars = []
    for i, shape in enumerate(shapes_data):
        # 计算形状的边界框尺寸
        max_dx = max(p[0] for p in shape["points"]) if shape["points"] else 0
        max_dy = max(p[1] for p in shape["points"]) if shape["points"] else 0
        shape_width = max_dx + 1
        shape_height = max_dy + 1

        # is_used: 决定此形状是否被放入容器
        is_used = model.NewBoolVar(f"is_used_{i}")

        # x, y: 形状原点在容器中的位置
        # 变量范围经过优化，确保形状不会超出边界
        x = model.NewIntVar(0, CONTAINER_WIDTH - shape_width, f"x_{i}")
        y = model.NewIntVar(0, CONTAINER_HEIGHT - shape_height, f"y_{i}")

        shape_vars.append(
            {
                "id": i,
                "name": shape["name"],
                "points": shape["points"],
                "area": shape["area"],
                "is_used": is_used,
                "x": x,
                "y": y,
            }
        )

    # --- 3. 约束添加 ---
    # 核心约束：任意两个被使用的形状不能重叠
    # 遍历所有可能的形状对 (i, j)
    for i in range(len(shape_vars)):
        for j in range(i + 1, len(shape_vars)):
            shape1 = shape_vars[i]
            shape2 = shape_vars[j]

            # 我们需要一个布尔变量来表示 shape1 和 shape2 是否都使用了
            both_used = model.NewBoolVar(f"both_used_{i}_{j}")
            # 将 both_used 变量与两个形状是否同时被使用进行绑定。
            # 1. 如果 shape1 和 shape2 都被使用，则 both_used 必须为 true。
            model.AddBoolAnd(
                [shape1["is_used"], shape2["is_used"]]
            ).OnlyEnforceIf(both_used)
            # 2. 如果 both_used 为 false，则 shape1 或 shape2 至少有一个未使用。
            model.AddBoolOr(
                [shape1["is_used"].Not(), shape2["is_used"].Not()]
            ).OnlyEnforceIf(both_used.Not())

            # 遍历两个形状的所有点对
            for p1 in shape1["points"]:
                for p2 in shape2["points"]:
                    # 如果两个形状都被使用，则它们的任意两个点不能在同一坐标
                    # (x1 + dx1 != x2 + dx2) OR (y1 + dy1 != y2 + dy2)
                    # 这个约束只在 both_used 为 true 时生效
                    model.AddBoolOr(
                        [
                            shape1["x"] + p1[0] != shape2["x"] + p2[0],
                            shape1["y"] + p1[1] != shape2["y"] + p2[1],
                        ]
                    ).OnlyEnforceIf(both_used)

    # --- 4. 优化目标定义 ---
    # 目标：最大化所有被使用形状的面积总和
    total_area = sum(s["area"] * s["is_used"] for s in shape_vars)
    model.Maximize(total_area)

    # --- 5. 求解 ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_sec
    status = solver.Solve(model)

    # --- 6. 结果解析 ---
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        placed_shapes = []
        for s in shape_vars:
            if solver.Value(s["is_used"]):
                placed_shapes.append(
                    {
                        "name": s["name"],
                        "position": (solver.Value(s["x"]), solver.Value(s["y"])),
                        "points": s["points"],
                    }
                )

        return {
            "status": solver.StatusName(status),
            "total_filled_area": solver.ObjectiveValue(),
            "computation_time_sec": solver.WallTime(),
            "placed_shapes": placed_shapes,
        }
    else:
        return {"status": solver.StatusName(status), "placed_shapes": []}


def visualize_layout(result):
    """
    将布局结果可视化为文本网格。
    """
    if not result or not result["placed_shapes"]:
        print("No solution found or no shapes placed.")
        return

    grid = [["." for _ in range(CONTAINER_WIDTH)] for _ in range(CONTAINER_HEIGHT)]

    # 使用不同字符标记不同形状
    shape_markers = "XO#*@%&$ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    for i, shape in enumerate(result["placed_shapes"]):
        marker = shape_markers[i % len(shape_markers)]
        pos_x, pos_y = shape["position"]
        for p_dx, p_dy in shape["points"]:
            grid[pos_y + p_dy][pos_x + p_dx] = marker

    print("\n--- Visualization ---")
    for row in grid:
        print(" ".join(row))


def main():
    """
    主函数：加载数据、求解、输出结果。
    """
    try:
        with open("shapes.json", "r") as f:
            data = json.load(f)
        shapes_to_pack = data["shapes"]
    except FileNotFoundError:
        print("Error: shapes.json not found. Please create it.")
        return
    except json.JSONDecodeError:
        print("Error: Could not decode shapes.json. Please check its format.")
        return

    print("Starting layout optimization...")
    result = solve_packing(shapes_to_pack)

    print(f"\nSolver finished with status: {result['status']}")
    if result["placed_shapes"]:
        print(f"Total filled area: {result['total_filled_area']}")
        print(
            f"Empty cells: {CONTAINER_WIDTH * CONTAINER_HEIGHT - result['total_filled_area']}"
        )
        print(f"Computation time: {result['computation_time_sec']:.2f} seconds")

        visualize_layout(result)

        print("\n--- Layout Data (JSON) ---")
        # 简化输出，只包含名称和位置
        output_data = {k: v for k, v in result.items() if k != "placed_shapes"}
        output_data["placed_shapes"] = [
            {"name": s["name"], "position": s["position"]}
            for s in result["placed_shapes"]
        ]
        print(json.dumps(output_data, indent=2))


if __name__ == "__main__":
    main()
