import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import json
from random import choice
from collections import Counter
import threading
import webbrowser
from tkinter import font as tkfont

from src.solver import solve_packing
from src.utils import resource_path
from src.visualizer import ResultVisualizer

GRID_WIDTH = 9
GRID_HEIGHT = 9


class ShapePackingGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Shape Packing Calculator")
        self.geometry("1000x800")  # Increased height for the new grid

        self.always_on_top = tk.BooleanVar()
        self.always_on_top.set(False)

        self.shape_lock_vars = {}
        self.shape_lock_labels = {}

        self.time_limit_var = tk.StringVar(value="30")

        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Top frame for input and output
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.BOTH, expand=True)

        # Left frame for inputs
        left_frame = ttk.LabelFrame(top_frame, text="Input")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # --- Container Definition Grid ---
        container_frame = ttk.LabelFrame(left_frame, text="Container Shape (9x9)")
        container_frame.pack(pady=5, padx=5, fill=tk.X)

        self.container_grid_cells = []
        self.container_grid_status = [[0] * 9 for _ in range(9)]
        cell_size = 22
        for r in range(9):
            row_cells = []
            for c in range(9):
                canvas = tk.Canvas(
                    container_frame,
                    width=cell_size,
                    height=cell_size,
                    bg="white",
                    highlightthickness=1,
                    highlightbackground="gray",
                )
                canvas.grid(row=r, column=c)
                canvas.bind(
                    "<Button-1>", lambda e, r=r, c=c: self.toggle_container_cell(r, c)
                )
                row_cells.append(canvas)
            self.container_grid_cells.append(row_cells)

        self.reset_container_grid()  # Set initial default state

        # --- Max Button ---
        max_button = ttk.Button(
            container_frame, text="Max", command=self.unlock_all_cells
        )
        max_button.grid(row=9, column=0, columnspan=9, pady=(5, 0))

        # --- Shape Quantities ---
        self.shape_entries = {}
        self.load_shapes(left_frame)

        # --- Total Area Display ---
        self.total_area_var = tk.StringVar(value="总面积: 0")
        total_area_label = ttk.Label(
            left_frame, textvariable=self.total_area_var, font=("Arial", 10, "bold")
        )
        total_area_label.pack(pady=(5, 2))

        # --- Control Buttons Frame ---
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(pady=2)

        clear_button = ttk.Button(
            button_frame, text="Clear", command=self.clear_shape_entries
        )
        clear_button.pack(side=tk.LEFT, padx=(0, 5))

        batch_format_button = ttk.Button(
            button_frame, text="一键输入", command=self.open_batch_format_dialog
        )
        batch_format_button.pack(side=tk.LEFT)

        # --- AI识图超链接 ---
        ai_vision_link_label = ttk.Label(
            button_frame, text="AI识图(需网络支持)", foreground="blue", cursor="hand2"
        )
        ai_vision_link_label.pack(side=tk.LEFT, padx=(5, 0))

        # 添加下划线
        underline_font = tkfont.Font(
            ai_vision_link_label, ai_vision_link_label.cget("font")
        )
        underline_font.configure(underline=True)
        ai_vision_link_label.configure(font=underline_font)

        # 绑定点击事件
        ai_vision_link_label.bind("<Button-1>", self.open_ai_vision_link)

        # Right frame for results
        right_frame = ttk.LabelFrame(top_frame, text="Output")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        self.result_canvas = tk.Canvas(right_frame, bg="white")
        self.result_canvas.pack(fill=tk.BOTH, expand=True)
        self.visualizer = ResultVisualizer(self.result_canvas)

        # Bottom frame for controls
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(5, 0))

        # Calculate button
        self.calculate_button = ttk.Button(
            bottom_frame, text="Calculate", command=self.start_calculation_thread
        )
        self.calculate_button.pack(side=tk.RIGHT)

        reset_button = ttk.Button(bottom_frame, text="Reset", command=self.reset_ui)
        reset_button.pack(side=tk.RIGHT, padx=(0, 5))

        always_on_top_button = ttk.Checkbutton(
            bottom_frame, text="Always on Top", variable=self.always_on_top, command=self.toggle_always_on_top
        )
        always_on_top_button.pack(side=tk.LEFT, padx=(5, 0))

        time_limit_label = ttk.Label(bottom_frame, text="Time Limit (s):")
        time_limit_label.pack(side=tk.LEFT, padx=(10, 0))
        time_limit_entry = ttk.Entry(
            bottom_frame, textvariable=self.time_limit_var, width=5
        )
        time_limit_entry.pack(side=tk.LEFT, padx=(0, 5))

    def open_ai_vision_link(self, event):
        """在浏览器中打开AI识图的链接"""
        webbrowser.open_new(r"https://aistudio.google.com/app/prompts?state=%7B%22ids%22:%5B%221h-kYgsI_r3o0gKRwpkzA9zwcO33ECEAl%22%5D,%22action%22:%22open%22,%22userId%22:%22116876243841507178556%22,%22resourceKeys%22:%7B%7D%7D&usp=sharing")  # noqa

    def open_batch_format_dialog(self):
        """Opens a dialog to get JSON input for batch formatting."""
        dialog = tk.Toplevel(self)
        dialog.title("一键输入")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="请在此处粘贴JSON文本:").pack(padx=10, pady=(10, 5))

        text_input = tk.Text(dialog, height=10)
        text_input.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        text_input.focus_set()

        def on_apply():
            json_string = text_input.get("1.0", tk.END)
            self.apply_json_input(json_string)
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        apply_button = ttk.Button(button_frame, text="应用", command=on_apply)
        apply_button.pack(side=tk.LEFT, padx=5)

        cancel_button = ttk.Button(button_frame, text="取消", command=dialog.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)

        dialog.wait_window()

    def apply_json_input(self, json_string):
        """Parses JSON from the given string and updates shape quantities."""
        if not json_string.strip():
            return  # Ignore if the input is empty

        try:
            data = json.loads(json_string)
            if not isinstance(data, dict):
                raise TypeError("JSON data must be an object (dictionary).")
        except json.JSONDecodeError:
            messagebox.showerror("错误", "无效的JSON格式。", parent=self)
            return
        except TypeError as e:
            messagebox.showerror("错误", f"JSON格式错误: {e}", parent=self)
            return
        except Exception as e:
            messagebox.showerror("错误", f"发生未知错误: {e}", parent=self)
            return

        # Reset all entries to 0 first
        self.clear_shape_entries()

        # Update entries based on JSON data
        unmatched_keys = []
        for name, count in data.items():
            if name in self.shape_entries:
                try:
                    # Ensure count is a non-negative integer
                    value = int(count)
                    if value < 0:
                        value = 0

                    entry = self.shape_entries[name]
                    entry.delete(0, tk.END)
                    entry.insert(0, str(value))
                except (ValueError, TypeError):
                    # If count is not a valid number, keep it as 0
                    continue
            else:
                unmatched_keys.append(name)

        # Update total area
        self._update_total_area()

        if unmatched_keys:
            messagebox.showwarning(
                "完成",
                f"批量设置成功！\n\n以下形状未在GUI中找到，已忽略：\n{', '.join(unmatched_keys)}",
                parent=self,
            )
        else:
            messagebox.showinfo("完成", "批量设置成功！,请人工核对，特别是RL和SG的数量是否正确！", parent=self)

    def toggle_always_on_top(self):
        """Toggles the always on top status of the window."""
        self.wm_attributes("-topmost", self.always_on_top.get())

    def reset_ui(self):
        """Resets the entire UI to its default state."""
        self.clear_shape_entries()
        self.reset_container_grid()
        self.result_canvas.delete("all")
        for lock_var in self.shape_lock_vars.values():
            lock_var.set(False)
        # Reset lock icon colors to default
        for label in self.shape_lock_labels.values():
            label.config(fg="black")

    def load_shapes(self, parent_frame):
        shape_file_path = resource_path("shapes.json")
        with open(shape_file_path, "r") as f:
            self.shapes_data = json.load(f)

        # Create a container frame for the grid
        grid_container = ttk.Frame(parent_frame)
        grid_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        num_columns = 2
        for i, shape_data in enumerate(self.shapes_data):
            row = i // num_columns
            col = i % num_columns

            shape_frame = ttk.Frame(grid_container)
            shape_frame.grid(row=row, column=col, padx=2, pady=3, sticky="nsew")
            grid_container.grid_columnconfigure(col, weight=1)

            # Canvas for shape visualization
            # Lock button
            lock_var = tk.BooleanVar()
            self.shape_lock_vars[shape_data["name"]] = lock_var

            lock_label = tk.Label(shape_frame, text="🔒")
            lock_label.grid(row=0, column=0, rowspan=2, padx=(0, 5))
            self.shape_lock_labels[shape_data["name"]] = lock_label
            lock_label.bind(
                "<Button-1>",
                lambda event, s=shape_data["name"]: self.toggle_lock_state(s),
            )

            # Canvas for shape visualization
            canvas = tk.Canvas(shape_frame, width=50, height=50)
            canvas.grid(row=0, column=1, rowspan=2, padx=(0, 10))
            self.draw_shape(canvas, shape_data["points"], shape_data["color"])

            # Shape name
            name_label = ttk.Label(shape_frame, text=shape_data["name"])
            name_label.grid(row=0, column=2, sticky="w")

            # Quantity entry
            entry_frame = ttk.Frame(shape_frame)
            entry_frame.grid(row=1, column=2, sticky="w")

            entry = ttk.Entry(entry_frame, width=5)
            entry.pack(side=tk.LEFT)
            entry.insert(0, "0")
            self.shape_entries[shape_data["name"]] = entry
            entry.bind("<KeyRelease>", lambda event: self._update_total_area())

            up_button = ttk.Button(
                entry_frame,
                text="▲",
                width=2,
                command=lambda e=entry: self._increment_value(e),
            )
            up_button.pack(side=tk.LEFT, padx=(2, 0))

            down_button = ttk.Button(
                entry_frame,
                text="▼",
                width=2,
                command=lambda e=entry: self._decrement_value(e),
            )
            down_button.pack(side=tk.LEFT, padx=(2, 0))

    def _increment_value(self, entry):
        try:
            value = int(entry.get())
            entry.delete(0, tk.END)
            entry.insert(0, str(value + 1))
        except ValueError:
            entry.delete(0, tk.END)
            entry.insert(0, "0")
        self._update_total_area()

    def _decrement_value(self, entry):
        try:
            value = int(entry.get())
            if value > 0:
                entry.delete(0, tk.END)
                entry.insert(0, str(value - 1))
        except ValueError:
            entry.delete(0, tk.END)
            entry.insert(0, "0")
        self._update_total_area()

    def _update_total_area(self):
        """Calculates and updates the total area of selected shapes."""
        total_area = 0
        shapes_by_name = {shape["name"]: shape for shape in self.shapes_data}

        for name, entry in self.shape_entries.items():
            try:
                count = int(entry.get())
                if count > 0 and name in shapes_by_name:
                    shape_area = len(shapes_by_name[name]["points"])
                    total_area += count * shape_area
            except (ValueError, KeyError):
                continue  # Ignore invalid entries or shapes not found

        self.total_area_var.set(f"总面积: {total_area}")

    def toggle_lock_state(self, shape_name):
        """Toggles the lock state for a given shape."""
        lock_var = self.shape_lock_vars[shape_name]
        current_state = lock_var.get()
        new_state = not current_state
        lock_var.set(new_state)

        lock_label = self.shape_lock_labels[shape_name]
        if new_state:
            lock_label.config(fg="blue")
        else:
            lock_label.config(fg="black")

    def toggle_container_cell(self, r, c):
        """Toggles the state of a container grid cell."""
        if self.container_grid_status[r][c] == 1:
            self.container_grid_status[r][c] = 0
            self.container_grid_cells[r][c].config(bg="black")
        else:
            self.container_grid_status[r][c] = 1
            self.container_grid_cells[r][c].config(bg="white")

    def unlock_all_cells(self):
        """Unlocks all cells in the container grid."""
        for r in range(9):
            for c in range(9):
                self.container_grid_status[r][c] = 1
                self.container_grid_cells[r][c].config(bg="white")

    def reset_container_grid(self):
        """Resets the container grid to its default state."""
        for r in range(9):
            for c in range(9):
                # Default: rectangle from (2,3) to (6,5) is available
                if 2 <= r <= 6 and 3 <= c <= 5:
                    self.container_grid_status[r][c] = 1
                    self.container_grid_cells[r][c].config(bg="white")
                else:
                    self.container_grid_status[r][c] = 0
                    self.container_grid_cells[r][c].config(bg="black")

    def clear_shape_entries(self):
        """Resets all shape entry values to 0."""
        for entry in self.shape_entries.values():
            entry.delete(0, tk.END)
            entry.insert(0, "0")
        self._update_total_area()

    def draw_shape(self, canvas, points, color):
        if not points:
            return

        # Find bounding box
        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)

        # Scale and center the shape
        scale = 35 / max(max_x - min_x + 1, max_y - min_y + 1)
        offset_x = (50 - (max_x - min_x) * scale) / 2
        offset_y = (50 - (max_y - min_y) * scale) / 2

        for x, y in points:
            x0 = (x - min_x) * scale + offset_x
            y0 = (y - min_y) * scale + offset_y
            x1 = x0 + scale
            y1 = y0 + scale
            canvas.create_rectangle(x0, y0, x1, y1, fill=color)

    def start_calculation_thread(self):
        """Starts the calculation in a separate thread to avoid freezing the GUI."""
        self.calculate_button.config(state=tk.DISABLED)
        self.result_canvas.delete("all")
        self.result_canvas.create_text(
            self.result_canvas.winfo_width() / 2,
            self.result_canvas.winfo_height() / 2,
            text="Calculating...",
            font=("Arial", 16),
        )

        thread = threading.Thread(target=self.calculate_and_update_ui)
        thread.daemon = True  # Allows main window to close even if thread is running
        thread.start()

    def calculate_and_update_ui(self):
        """The core calculation logic, designed to be run in a background thread."""
        try:
            # 1. Collect shape counts from entries
            shape_counts = {}
            for name, entry in self.shape_entries.items():
                try:
                    count = int(entry.get())
                    if count > 0:
                        shape_counts[name] = count
                except ValueError:
                    continue

            # 2. Prepare the list of shapes to be packed
            shapes_to_pack = []
            shapes_by_name = {shape["name"]: shape for shape in self.shapes_data}
            for name, count in shape_counts.items():
                if name in shapes_by_name:
                    for _ in range(count):
                        shapes_to_pack.append(shapes_by_name[name])

            if not shapes_to_pack:
                self.after(0, self.update_ui_with_result, None, [], [])
                return

            # 3. Collect allowed cells from the container grid
            allowed_cells = []
            for r in range(9):
                for c in range(9):
                    if self.container_grid_status[r][c] == 1:
                        allowed_cells.append((r, c))

            if not allowed_cells:
                self.after(0, self.update_ui_with_result, None, [], allowed_cells)
                return

            # 4. Run the packing algorithm
            print("Starting layout optimization in background thread...")
            must_place_names = [
                name for name, var in self.shape_lock_vars.items() if var.get()
            ]

            try:
                time_limit = int(self.time_limit_var.get())
                if not 10 <= time_limit <= 300:
                    raise ValueError("Time limit must be between 10 and 300.")
            except ValueError:
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "Invalid Input",
                        "Time limit must be a number between 10 and 300.",
                    ),
                )
                self.after(0, lambda: self.calculate_button.config(state=tk.NORMAL))
                return

            placed_shapes, unplaced_shape_names, status = solve_packing(
                shapes_to_pack,
                allowed_cells,
                board_size=(GRID_WIDTH, GRID_HEIGHT),
                must_place_names=must_place_names,
                time_limit_sec=time_limit,
            )

            # Reconstruct unplaced_shapes with full data for visualization
            shapes_by_name = {shape["name"]: shape for shape in self.shapes_data}
            unplaced_shapes_full = [
                shapes_by_name[name] for name in unplaced_shape_names if name in shapes_by_name
            ]

            # Create a mock result object for compatibility with update_ui_with_result
            result = {
                "placed_shapes": placed_shapes,
                "status": status,
            }

            print(f"Solver finished with status: {status}")

            # 5. Schedule UI update on the main thread
            self.after(0, self.update_ui_with_result, result, unplaced_shapes_full, allowed_cells)

        except Exception as e:
            print(f"An error occurred during calculation: {e}")
            # Ensure the button is re-enabled even if an error occurs
            self.after(0, lambda: self.calculate_button.config(state=tk.NORMAL))

    def update_ui_with_result(self, result, unplaced_shapes, allowed_cells):
        """Updates the UI with the calculation result. Must be called from the main thread."""
        self.calculate_button.config(state=tk.NORMAL)

        # Check for infeasible solution with locked shapes
        if (
            result and result["status"] in ("INFEASIBLE", "NO_SOLUTION_FOUND")
            and any(var.get() for var in self.shape_lock_vars.values())
        ):
            messagebox.showerror(
                "无法放置",
                "一个或多个被锁定的形状因空间不足无法放入。请尝试减少形状数量或调整容器大小。",
            )
            # Still visualize the empty grid
            self.visualize_result(None, unplaced_shapes, allowed_cells)
            return

        # Visualize the final result
        self.visualize_result(result, unplaced_shapes, allowed_cells)

    def visualize_result(self, result, unplaced_shapes=None, allowed_cells=None):
        """Visualizes the packing result using the dedicated visualizer class."""
        status_map = {
            "OPTIMAL": "找到理论最优解",
            "FEASIBLE": "最长计算时间到，找到可行解（不一定理论最优）",
            "INFEASIBLE": "无解",
            "UNKNOWN": "计算错误",
            "MODEL_INVALID": "计算错误",
        }

        status_text = ""
        if result and result.get("status"):
            status_text = status_map.get(result["status"], result["status"])

        self.visualizer.visualize(result, unplaced_shapes, allowed_cells, status_text)


if __name__ == "__main__":
    app = ShapePackingGUI()
    app.mainloop()
