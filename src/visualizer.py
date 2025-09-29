import tkinter as tk

GRID_WIDTH = 9
GRID_HEIGHT = 9


class ResultVisualizer:
    """Handles drawing the results of the shape packing on a canvas."""

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas

    def clear_canvas(self):
        """Clears all items from the canvas."""
        self.canvas.delete("all")

    def _draw_container_background(self, allowed_cells, scale, y_offset=0):
        """Draws the background grid for the container."""
        if not allowed_cells:
            return

        # First, draw all potential cells as unavailable
        for r in range(GRID_HEIGHT):
            for c in range(GRID_WIDTH):
                x0, y0 = c * scale, r * scale + y_offset
                x1, y1 = x0 + scale, y0 + scale
                self.canvas.create_rectangle(
                    x0, y0, x1, y1, fill="black", outline="whitesmoke"
                )
        # Then, draw the allowed cells on top
        for r, c in allowed_cells:
            x0, y0 = c * scale, r * scale + y_offset
            x1, y1 = x0 + scale, y0 + scale
            self.canvas.create_rectangle(
                x0, y0, x1, y1, fill="white", outline="whitesmoke"
            )

    def _draw_placed_shape_outlines(self, shape, scale, y_offset=0):
        """Draws the bold black outline for a single placed shape."""
        pos_x, pos_y = shape["position"]
        shape_points_set = set((pos_x + p_dx, pos_y + p_dy) for p_dx, p_dy in shape["points"])

        for p_dx, p_dy in shape["points"]:
            gx, gy = pos_x + p_dx, pos_y + p_dy
            x0, y0 = gx * scale, gy * scale + y_offset
            x1, y1 = (gx + 1) * scale, (gy + 1) * scale + y_offset

            # Top edge
            if (gx, gy - 1) not in shape_points_set:
                self.canvas.create_line(x0, y0, x1, y0, fill="black", width=2)
            # Bottom edge
            if (gx, gy + 1) not in shape_points_set:
                self.canvas.create_line(x0, y1, x1, y1, fill="black", width=2)
            # Left edge
            if (gx - 1, gy) not in shape_points_set:
                self.canvas.create_line(x0, y0, x0, y1, fill="black", width=2)
            # Right edge
            if (gx + 1, gy) not in shape_points_set:
                self.canvas.create_line(x1, y0, x1, y1, fill="black", width=2)

    def _draw_placed_shapes(self, placed_shapes, scale, y_offset=0):
        """Draws the placed shapes on the canvas."""
        for shape in placed_shapes:
            color = shape["color"]
            pos_x, pos_y = shape["position"]

            # First, draw all the rectangles for the shape without an outline
            for p_dx, p_dy in shape["points"]:
                x0 = (pos_x + p_dx) * scale
                y0 = (pos_y + p_dy) * scale + y_offset
                x1 = x0 + scale
                y1 = y0 + scale
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

            # Now, draw the bold black outline
            self._draw_placed_shape_outlines(shape, scale, y_offset=y_offset)

    def _draw_unplaced_shapes(self, unplaced_shapes, canvas_width, unplaced_area_y_start):
        """Draws the unplaced shapes in a separate area."""
        if not unplaced_shapes:
            return

        self.canvas.create_text(
            10, unplaced_area_y_start - 15, text="Unplaced Shapes:", anchor="nw", font=("Arial", 10, "bold")
        )

        current_x = 10
        current_y = unplaced_area_y_start
        max_h_in_row = 0
        unplaced_scale = 8  # A small, fixed scale for unplaced shapes

        for shape in unplaced_shapes:
            if not shape["points"]:
                continue

            min_x = min(p[0] for p in shape["points"])
            max_x = max(p[0] for p in shape["points"])
            min_y = min(p[1] for p in shape["points"])
            max_y = max(p[1] for p in shape["points"])

            shape_w = (max_x - min_x + 1) * unplaced_scale
            shape_h = (max_y - min_y + 1) * unplaced_scale

            if current_x + shape_w > canvas_width:
                current_x = 10
                current_y += max_h_in_row + 5
                max_h_in_row = 0

            for dx, dy in shape["points"]:
                x0 = current_x + (dx - min_x) * unplaced_scale
                y0 = current_y + (dy - min_y) * unplaced_scale
                x1 = x0 + unplaced_scale
                y1 = y0 + unplaced_scale
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=shape["color"], outline="black")

            current_x += shape_w + 5
            if shape_h > max_h_in_row:
                max_h_in_row = shape_h

    def visualize(self, result, unplaced_shapes=None, allowed_cells=None, status_text=""):
        """Main method to draw the entire result visualization."""
        self.clear_canvas()

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # Display status text at the top
        if status_text:
            self.canvas.create_text(
                canvas_width / 2, 20, text=status_text, font=("Arial", 12, "bold"), fill="blue"
            )

        placed_area_y_offset = 40
        placed_area_height = (canvas_height - placed_area_y_offset) * 0.8
        unplaced_area_y_start = placed_area_height + placed_area_y_offset + 20

        # Draw separator line
        separator_y = placed_area_height + placed_area_y_offset
        self.canvas.create_line(
            0, separator_y, canvas_width, separator_y, fill="gray", dash=(4, 2)
        )

        scale_x = canvas_width / GRID_WIDTH
        scale_y = placed_area_height / GRID_HEIGHT
        scale = min(scale_x, scale_y)

        # Draw container background with offset
        self._draw_container_background(allowed_cells, scale, y_offset=placed_area_y_offset)

        if not result or not result.get("placed_shapes"):
            self.canvas.create_text(
                canvas_width / 2,
                placed_area_height / 2 + placed_area_y_offset,
                text="未找到解决方案",
                font=("Arial", 16),
            )
        else:
            # Draw placed shapes with offset
            self._draw_placed_shapes(result["placed_shapes"], scale, y_offset=placed_area_y_offset)

        self._draw_unplaced_shapes(unplaced_shapes, canvas_width, unplaced_area_y_start)
