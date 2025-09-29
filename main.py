import argparse
import json
from typing import List, Dict, Any, cast

from src.data_models import Shape
from src.solver import PackingSolver
from src.utils import resource_path
# Note: The visualizer is not yet implemented, so we will add it later.
# from src.visualizer import print_board


def main() -> None:
    """Main function to run the packing solver from the command line."""
    parser = argparse.ArgumentParser(description="Pack shapes into a container.")
    parser.add_argument(
        "--shape_counts",
        type=str,
        required=True,
        help="Counts of each shape to pack, e.g., 'shape1=2,shape2=1'",
    )
    parser.add_argument(
        "--board_size",
        type=str,
        default="10,10",
        help="Dimensions of the board, e.g., '10,10'",
    )
    parser.add_argument(
        "--shapes_file",
        type=str,
        default="shapes.json",
        help="Path to the JSON file defining shapes.",
    )
    args = parser.parse_args()

    # --- Load Shapes ---
    with open(resource_path(args.shapes_file)) as f:
        shapes_list: List[Dict[str, Any]] = json.load(f)
    shapes_data: Dict[str, Dict[str, Any]] = {
        shape["name"]: shape for shape in shapes_list
    }

    # --- Parse Shape Counts ---
    shape_counts: Dict[str, int] = {}
    for item in args.shape_counts.split(','):
        name, count = item.split('=')
        shape_counts[name.strip()] = int(count.strip())

    # --- Create Shape Instances ---
    shapes_to_pack: List[Shape] = []
    for name, count in shape_counts.items():
        if name in shapes_data:
            for i in range(count):
                shape_data = shapes_data[name]
                points = shape_data.get("points")
                area = shape_data.get("area")
                color = shape_data.get("color")

                if points is None or area is None or color is None:
                    print(
                        f"Warning: Shape '{name}' is missing required data "
                        f"(points, area, or color) and will be skipped."
                    )
                    continue

                shapes_to_pack.append(
                    Shape(
                        name=f"{name}_{i+1}",
                        points=cast(List[List[int]], points),
                        area=cast(int, area),
                        color=cast(str, color),
                    )
                )
        else:
            print(f"Warning: Shape '{name}' not found in {args.shapes_file}")

    # --- Parse Board Size ---
    try:
        width, height = map(int, args.board_size.split(','))
        board_size = (width, height)
    except ValueError:
        print("Error: Invalid board_size format. Use 'width,height'.")
        return

    # --- Solve ---
    if not shapes_to_pack:
        print("No shapes to pack. Exiting.")
        return

    print(f"Attempting to pack {len(shapes_to_pack)} shapes on a {board_size[0]}x{board_size[1]} board...")

    allowed_cells = [(x, y) for x in range(width) for y in range(height)]
    solver = PackingSolver(shapes_to_pack, board_size, allowed_cells=allowed_cells)
    result = solver.solve()

    # --- Print Results ---
    print("\n--- Packing Result ---")
    print(f"Solver finished with status: {result.status.name}")

    if result.placed_shapes:
        print(f"\nSuccessfully placed {len(result.placed_shapes)} shapes:")
        # TODO: Add call to a text-based visualizer here
        # print_board(result.placed_shapes, board_size)
        for shape in result.placed_shapes:
            print(f"  - {shape.name} at ({shape.x}, {shape.y})")
    else:
        print("\nCould not place any shapes.")

    if result.unplaced_shapes:
        print(f"\nFailed to place {len(result.unplaced_shapes)} shapes:")
        for name in result.unplaced_shapes:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
