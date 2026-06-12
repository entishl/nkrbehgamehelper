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
        self.geometry("1000x850")  # Increased height for the new grid

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

        # --- Total Area Display ---
        self.total_area_var = tk.StringVar(value="总面积: 0")

        # --- Shape Quantities ---
        self.shapes_container_parent = left_frame
        self.load_shapes(self.shapes_container_parent)

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
        batch_format_button.pack(side=tk.LEFT, padx=(0, 5))

        manage_shapes_button = ttk.Button(
            button_frame, text="形状管理", command=self.open_manage_shapes_dialog
        )
        manage_shapes_button.pack(side=tk.LEFT)

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
        # 1. Save existing counts and lock states if they exist
        old_counts = {}
        old_locks = {}
        if hasattr(self, "shape_entries"):
            for name, entry in self.shape_entries.items():
                try:
                    old_counts[name] = entry.get()
                except Exception:
                    pass
        if hasattr(self, "shape_lock_vars"):
            for name, var in self.shape_lock_vars.items():
                try:
                    old_locks[name] = var.get()
                except Exception:
                    pass

        # 2. Destroy the existing grid container if it exists
        if hasattr(self, "shapes_grid_container") and self.shapes_grid_container:
            self.shapes_grid_container.destroy()

        shape_file_path = resource_path("shapes.json")
        with open(shape_file_path, "r") as f:
            self.shapes_data = json.load(f)

        # Create a container frame for the grid
        self.shapes_grid_container = ttk.Frame(parent_frame)
        self.shapes_grid_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.shape_entries = {}
        self.shape_lock_vars = {}
        self.shape_lock_labels = {}

        num_columns = 2
        for i, shape_data in enumerate(self.shapes_data):
            row = i // num_columns
            col = i % num_columns

            shape_frame = ttk.Frame(self.shapes_grid_container)
            shape_frame.grid(row=row, column=col, padx=2, pady=1, sticky="nsew")
            self.shapes_grid_container.grid_columnconfigure(col, weight=1)

            # Lock button
            lock_var = tk.BooleanVar()
            lock_var.set(old_locks.get(shape_data["name"], False))
            self.shape_lock_vars[shape_data["name"]] = lock_var

            lock_label = tk.Label(shape_frame, text="🔒")
            lock_label.grid(row=0, column=0, rowspan=2, padx=(0, 5))
            self.shape_lock_labels[shape_data["name"]] = lock_label
            if lock_var.get():
                lock_label.config(fg="blue")
            else:
                lock_label.config(fg="black")
            lock_label.bind(
                "<Button-1>",
                lambda event, s=shape_data["name"]: self.toggle_lock_state(s),
            )

            # Canvas for shape visualization
            canvas = tk.Canvas(shape_frame, width=40, height=40)
            canvas.grid(row=0, column=1, rowspan=2, padx=(0, 5))
            self.draw_shape(canvas, shape_data["points"], shape_data["color"])

            # Shape name
            name_label = ttk.Label(shape_frame, text=shape_data["name"])
            name_label.grid(row=0, column=2, sticky="w")

            # Quantity entry
            entry_frame = ttk.Frame(shape_frame)
            entry_frame.grid(row=1, column=2, sticky="w")

            entry = ttk.Entry(entry_frame, width=5)
            entry.pack(side=tk.LEFT)
            entry.insert(0, old_counts.get(shape_data["name"], "0"))
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

        # Update total area calculation to reflect restored/loaded states
        self._update_total_area()

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

        if hasattr(self, "total_area_var"):
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
        scale = 30 / max(max_x - min_x + 1, max_y - min_y + 1)
        offset_x = (40 - (max_x - min_x) * scale) / 2
        offset_y = (40 - (max_y - min_y) * scale) / 2

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


    def open_manage_shapes_dialog(self):
        """打开形状管理对话框，允许管理和新增形状"""
        dialog = tk.Toplevel(self)
        dialog.title("形状管理")
        dialog.geometry("900x550")
        dialog.transient(self)
        dialog.grab_set()

        # 主布局：左右分栏
        left_pane = ttk.LabelFrame(dialog, text="现有形状列表", padding=10)
        left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        right_pane = ttk.LabelFrame(dialog, text="新增/编辑形状", padding=10)
        right_pane.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- 左侧面板 ---
        columns = ("name", "area", "color")
        tree = ttk.Treeview(left_pane, columns=columns, show="headings", selectmode="browse")
        tree.heading("name", text="形状名称")
        tree.heading("area", text="面积")
        tree.heading("color", text="颜色 Hex")
        
        tree.column("name", width=100, anchor=tk.CENTER)
        tree.column("area", width=80, anchor=tk.CENTER)
        tree.column("color", width=100, anchor=tk.CENTER)
        
        # 加上滚动条
        scrollbar = ttk.Scrollbar(left_pane, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True, pady=5)

        def populate_tree():
            for item in tree.get_children():
                tree.delete(item)
            for shape in self.shapes_data:
                tree.insert("", tk.END, values=(shape["name"], shape["area"], shape["color"]))

        # 绑定点击事件
        def on_tree_select(event):
            selected = tree.selection()
            if not selected:
                return
            item_values = tree.item(selected[0], "values")
            name = item_values[0]
            shape = next((s for s in self.shapes_data if s["name"] == name), None)
            if shape:
                load_shape_into_editor(shape)

        tree.bind("<<TreeviewSelect>>", on_tree_select)

        # 删除按钮
        btn_frame = ttk.Frame(left_pane)
        btn_frame.pack(fill=tk.X, pady=5)

        def delete_selected_shape():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("警告", "请先在列表中选择要删除的形状。", parent=dialog)
                return
            name = tree.item(selected[0], "values")[0]
            if messagebox.askyesno("确认删除", f"确定要删除形状 '{name}' 吗？\n删除后将无法恢复。", parent=dialog):
                self.shapes_data = [s for s in self.shapes_data if s["name"] != name]
                save_shapes_to_file()
                populate_tree()
                self.load_shapes(self.shapes_container_parent)
                clear_editor()

        delete_btn = ttk.Button(btn_frame, text="删除选中形状", command=delete_selected_shape)
        delete_btn.pack(side=tk.LEFT, padx=5)

        # --- 右侧面板 (编辑器) ---
        # 1. 形状名称
        name_frame = ttk.Frame(right_pane)
        name_frame.pack(fill=tk.X, pady=5)
        ttk.Label(name_frame, text="形状名称:").pack(side=tk.LEFT, padx=5)
        name_entry = ttk.Entry(name_frame, width=20)
        name_entry.pack(side=tk.LEFT, padx=5)

        # 2. 颜色选择
        color_frame = ttk.Frame(right_pane)
        color_frame.pack(fill=tk.X, pady=5)
        ttk.Label(color_frame, text="选择颜色:").pack(side=tk.LEFT, padx=5)
        
        current_color = ["#3357FF"]
        
        color_preview = tk.Canvas(
            color_frame, 
            width=30, 
            height=20, 
            bg=current_color[0], 
            highlightthickness=1, 
            highlightbackground="gray"
        )
        color_preview.pack(side=tk.LEFT, padx=5)
        
        def choose_color():
            from tkinter import colorchooser
            color_code = colorchooser.askcolor(title="选择形状颜色", initialcolor=current_color[0], parent=dialog)
            if color_code[1]:
                current_color[0] = color_code[1]
                color_preview.config(bg=current_color[0])
                # 联动更新当前编辑网格中已选格子的颜色
                for r_idx in range(6):
                    for c_idx in range(6):
                        if editor_grid_status[r_idx][c_idx] == 1:
                            editor_grid_cells[r_idx][c_idx].config(bg=current_color[0])
                            
        color_btn = ttk.Button(color_frame, text="调色板", command=choose_color)
        color_btn.pack(side=tk.LEFT, padx=5)

        # 3. 6x6 网格
        grid_container = ttk.Frame(right_pane)
        grid_container.pack(fill=tk.BOTH, expand=True, pady=10)
        
        grid_frame = ttk.LabelFrame(grid_container, text="绘制形状 (点击方块选中/取消)", padding=5)
        grid_frame.pack(anchor=tk.CENTER)

        editor_grid_status = [[0] * 6 for _ in range(6)]
        editor_grid_cells = []
        
        def toggle_editor_cell(r_val, c_val):
            if editor_grid_status[r_val][c_val] == 1:
                editor_grid_status[r_val][c_val] = 0
                editor_grid_cells[r_val][c_val].config(bg="white")
            else:
                editor_grid_status[r_val][c_val] = 1
                editor_grid_cells[r_val][c_val].config(bg=current_color[0])

        cell_size = 30
        for r in range(6):
            row_cells = []
            for c in range(6):
                canvas = tk.Canvas(
                    grid_frame,
                    width=cell_size,
                    height=cell_size,
                    bg="white",
                    highlightthickness=1,
                    highlightbackground="gray",
                )
                canvas.grid(row=r, column=c, padx=1, pady=1)
                canvas.bind(
                    "<Button-1>", lambda e, r_v=r, c_v=c: toggle_editor_cell(r_v, c_v)
                )
                row_cells.append(canvas)
            editor_grid_cells.append(row_cells)

        # 加载形状到编辑器的辅助函数
        def load_shape_into_editor(shape):
            clear_editor()
            name_entry.insert(0, shape["name"])
            current_color[0] = shape["color"]
            color_preview.config(bg=current_color[0])
            for x, y in shape["points"]:
                if 0 <= x < 6 and 0 <= y < 6:
                    editor_grid_status[y][x] = 1
                    editor_grid_cells[y][x].config(bg=current_color[0])

        # 重置编辑器
        def clear_editor():
            name_entry.delete(0, tk.END)
            current_color[0] = choice(["#FF5733", "#33FF57", "#3357FF", "#F3FF33", "#FF33A1", "#A133FF"])
            color_preview.config(bg=current_color[0])
            for r_idx in range(6):
                for c_idx in range(6):
                    editor_grid_status[r_idx][c_idx] = 0
                    editor_grid_cells[r_idx][c_idx].config(bg="white")

        # 4. 控制按钮
        edit_btn_frame = ttk.Frame(right_pane)
        edit_btn_frame.pack(fill=tk.X, pady=5)

        clear_btn = ttk.Button(edit_btn_frame, text="重置编辑器", command=clear_editor)
        clear_btn.pack(side=tk.LEFT, padx=5)

        def save_shapes_to_file():
            shape_file_path = resource_path("shapes.json")
            try:
                with open(shape_file_path, "w", encoding="utf-8") as f_out:
                    json.dump(self.shapes_data, f_out, indent=2, ensure_ascii=False)
            except Exception as ex:
                messagebox.showerror("文件保存失败", f"无法写入 shapes.json:\n{ex}", parent=dialog)

        def save_shape_from_editor():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("错误", "请输入形状名称！", parent=dialog)
                return
            
            # 收集点
            pts = []
            for r_idx in range(6):
                for c_idx in range(6):
                    if editor_grid_status[r_idx][c_idx] == 1:
                        # c是x，r是y
                        pts.append([c_idx, r_idx])
            
            if not pts:
                messagebox.showerror("错误", "请在网格中绘制形状（至少选择一个方块）！", parent=dialog)
                return

            # 归一化
            min_x_val = min(p[0] for p in pts)
            min_y_val = min(p[1] for p in pts)
            normalized_pts = [[p[0] - min_x_val, p[1] - min_y_val] for p in pts]
            normalized_pts.sort(key=lambda p: (p[1], p[0]))

            new_shape = {
                "name": name,
                "area": len(normalized_pts),
                "points": normalized_pts,
                "color": current_color[0]
            }

            # 判断是否已存在
            existing_idx = next((idx for idx, s in enumerate(self.shapes_data) if s["name"] == name), -1)
            if existing_idx != -1:
                if messagebox.askyesno("覆盖确认", f"形状 '{name}' 已存在。是否覆盖修改它？", parent=dialog):
                    self.shapes_data[existing_idx] = new_shape
                else:
                    return
            else:
                self.shapes_data.append(new_shape)

            save_shapes_to_file()
            populate_tree()
            self.load_shapes(self.shapes_container_parent)
            messagebox.showinfo("成功", f"形状 '{name}' 已保存并应用！", parent=dialog)

        save_btn = ttk.Button(edit_btn_frame, text="保存/新增形状", command=save_shape_from_editor)
        save_btn.pack(side=tk.RIGHT, padx=5)

        # 底部关闭按钮
        close_frame = ttk.Frame(dialog)
        close_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        close_btn = ttk.Button(close_frame, text="关闭窗口", command=dialog.destroy)
        close_btn.pack(anchor=tk.CENTER)

        # 初始化树状列表
        populate_tree()
        dialog.wait_window()


if __name__ == "__main__":
    app = ShapePackingGUI()
    app.mainloop()
