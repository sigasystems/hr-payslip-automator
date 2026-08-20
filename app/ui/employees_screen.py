import customtkinter as ctk
from tkinter import filedialog, messagebox
import pandas as pd

class EmployeesScreen(ctk.CTkFrame):
    def __init__(self, parent, db_service):
        super().__init__(parent, fg_color="transparent")
        self.db = db_service
        self.selected_ids = set()
        self.row_checkbox_vars = {}
        self._setup_ui()

    def _setup_ui(self):
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(header_frame, text="Employee Management", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        
        ctk.CTkButton(header_frame, text="+ Add Employee", command=self._add_employee_dialog).pack(side="right", padx=5)
        ctk.CTkButton(header_frame, text="Import Excel", fg_color="green", hover_color="darkgreen", command=self._import_excel).pack(side="right", padx=5)
        
        # Batch Delete button in header
        self.batch_delete_btn = ctk.CTkButton(
            header_frame, 
            text="Delete Selected (0)", 
            fg_color="#D32F2F", 
            hover_color="#B71C1C", 
            state="disabled",
            command=self._delete_selected_employees
        )
        self.batch_delete_btn.pack(side="right", padx=5)

        # Search and controls
        search_frame = ctk.CTkFrame(self)
        search_frame.pack(fill="x", pady=10)
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._refresh_table())
        ctk.CTkEntry(search_frame, placeholder_text="Search by name, ID or Email...", textvariable=self.search_var, width=400).pack(pady=10, padx=10, side="left")
        
        self.select_all_var = ctk.BooleanVar(value=False)
        self.select_all_chk = ctk.CTkCheckBox(
            search_frame, 
            text="Select All Visible", 
            variable=self.select_all_var, 
            command=self._toggle_select_all,
            width=130
        )
        self.select_all_chk.pack(side="right", padx=15, pady=10)

        # Table Container
        self.table_frame = ctk.CTkScrollableFrame(self)
        self.table_frame.pack(fill="both", expand=True)
        
        self._refresh_table()

    def _update_batch_delete_btn(self):
        count = len(self.selected_ids)
        self.batch_delete_btn.configure(
            text=f"Delete Selected ({count})",
            state="normal" if count > 0 else "disabled"
        )

    def _toggle_select_all(self):
        is_checked = self.select_all_var.get()
        for emp_id_db, var in self.row_checkbox_vars.items():
            var.set(is_checked)
            if is_checked:
                self.selected_ids.add(emp_id_db)
            else:
                self.selected_ids.discard(emp_id_db)
        self._update_batch_delete_btn()

    def _on_row_check_changed(self, emp_id_db, var):
        if var.get():
            self.selected_ids.add(emp_id_db)
        else:
            self.selected_ids.discard(emp_id_db)
            
        # Update select all checkbox state
        if self.row_checkbox_vars and all(v.get() for v in self.row_checkbox_vars.values()):
            self.select_all_var.set(True)
        else:
            self.select_all_var.set(False)
            
        self._update_batch_delete_btn()

    def _refresh_table(self):
        # Clear existing widgets
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        self.row_checkbox_vars.clear()

        # Headers
        headers = ["", "ID", "Name", "Email", "Dept", "PAN", "UAN", "Actions"]
        for i, h in enumerate(headers):
            lbl = ctk.CTkLabel(self.table_frame, text=h, font=ctk.CTkFont(weight="bold"))
            lbl.grid(row=0, column=i, padx=8, pady=5, sticky="w")

        # Data
        employees = self.db.get_all_employees()
        search_term = self.search_var.get().lower()
        
        row_idx = 1
        visible_ids = set()
        for emp in employees:
            # Filter
            if search_term and not any(str(val).lower().find(search_term) != -1 for val in emp[1:4]):
                continue

            emp_db_id = emp[0]
            visible_ids.add(emp_db_id)
            
            # Row Checkbox
            var = ctk.BooleanVar(value=(emp_db_id in self.selected_ids))
            self.row_checkbox_vars[emp_db_id] = var
            chk = ctk.CTkCheckBox(
                self.table_frame, 
                text="", 
                width=24, 
                variable=var,
                command=lambda eid=emp_db_id, v=var: self._on_row_check_changed(eid, v)
            )
            chk.grid(row=row_idx, column=0, padx=(10, 2), pady=2, sticky="w")

            # (id, emp_id, name, email, dept, pan, uan, created_at)
            ctk.CTkLabel(self.table_frame, text=emp[1]).grid(row=row_idx, column=1, padx=8, pady=2, sticky="w")
            ctk.CTkLabel(self.table_frame, text=emp[2]).grid(row=row_idx, column=2, padx=8, pady=2, sticky="w")
            ctk.CTkLabel(self.table_frame, text=emp[3]).grid(row=row_idx, column=3, padx=8, pady=2, sticky="w")
            ctk.CTkLabel(self.table_frame, text=emp[4] or "-").grid(row=row_idx, column=4, padx=8, pady=2, sticky="w")
            ctk.CTkLabel(self.table_frame, text=emp[5] or "-").grid(row=row_idx, column=5, padx=8, pady=2, sticky="w")
            ctk.CTkLabel(self.table_frame, text=emp[6] or "-").grid(row=row_idx, column=6, padx=8, pady=2, sticky="w")
            
            actions_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            actions_frame.grid(row=row_idx, column=7, padx=8, pady=2)
            
            ctk.CTkButton(actions_frame, text="Edit", width=55, height=25, command=lambda e=emp: self._edit_employee_dialog(e)).pack(side="left", padx=2)
            ctk.CTkButton(actions_frame, text="Del", width=55, height=25, fg_color="red", hover_color="darkred", command=lambda id=emp[0]: self._delete_employee(id)).pack(side="left", padx=2)
            
            row_idx += 1

        # Remove deleted/unmatched IDs from selection if no longer in db
        all_db_ids = {e[0] for e in employees}
        self.selected_ids = {sid for sid in self.selected_ids if sid in all_db_ids}

        # Update Select All checkbox state
        if self.row_checkbox_vars and all(v.get() for v in self.row_checkbox_vars.values()):
            self.select_all_var.set(True)
        else:
            self.select_all_var.set(False)

        self._update_batch_delete_btn()

    def _delete_selected_employees(self):
        if not self.selected_ids:
            return
        
        count = len(self.selected_ids)
        if messagebox.askyesno("Confirm Multiple Delete", f"Are you sure you want to delete {count} selected employee(s)?\nThis action cannot be undone."):
            self.db.delete_employees(list(self.selected_ids))
            self.selected_ids.clear()
            self._refresh_table()
            messagebox.showinfo("Success", f"{count} employee(s) deleted successfully.")

    def _add_employee_dialog(self):
        dialog = EmployeeForm(self, "Add Employee", self.db, self._refresh_table)

    def _edit_employee_dialog(self, emp):
        dialog = EmployeeForm(self, "Edit Employee", self.db, self._refresh_table, emp)

    def _delete_employee(self, id):
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this employee?"):
            self.db.delete_employee(id)
            self.selected_ids.discard(id)
            self._refresh_table()

    def _import_excel(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if not file_path: return
        
        try:
            df = pd.read_excel(file_path)
            # Expecting columns: Employee ID, Name, Email, Department, PAN, UAN
            for _, row in df.iterrows():
                try:
                    self.db.add_employee(
                        str(row.get('Employee ID', row.get('ID', ''))),
                        str(row.get('Name', '')),
                        str(row.get('Email', '')),
                        str(row.get('Department', '')),
                        str(row.get('PAN', '')),
                        str(row.get('UAN', ''))
                    )
                except Exception as e:
                    print(f"Error importing row: {e}")
            self._refresh_table()
            messagebox.showinfo("Success", "Employees imported successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import: {e}")

class EmployeeForm(ctk.CTkToplevel):
    def __init__(self, parent, title, db, callback, emp=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x540")
        self.db = db
        self.callback = callback
        self.emp = emp # (id, emp_id, name, email, dept, pan, uan, created_at)
        
        self.attributes("-topmost", True)
        self._setup_ui()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        
        fields = [
            ("Employee ID", "emp_id"),
            ("Employee Name", "name"),
            ("Email", "email"),
            ("Department", "dept"),
            ("PAN Number", "pan"),
            ("UAN Number", "uan")
        ]
        
        self.entries = {}
        for i, (label, key) in enumerate(fields):
            ctk.CTkLabel(self, text=label).grid(row=i*2, column=0, padx=20, pady=(10, 0), sticky="w")
            entry = ctk.CTkEntry(self, width=300)
            entry.grid(row=i*2+1, column=0, padx=20, pady=(0, 10))
            self.entries[key] = entry
            
            if self.emp:
                val = self.emp[i+1] if self.emp[i+1] else ""
                entry.insert(0, val)

        btn_text = "Update" if self.emp else "Save"
        ctk.CTkButton(self, text=btn_text, command=self._save).grid(row=12, column=0, pady=20)

    def _save(self):
        data = {k: v.get() for k, v in self.entries.items()}
        if not data['emp_id'] or not data['name'] or not data['email']:
            messagebox.showwarning("Warning", "ID, Name and Email are required")
            return
            
        try:
            if self.emp:
                self.db.update_employee(self.emp[0], data['emp_id'], data['name'], data['email'], data['dept'], data['pan'], data['uan'])
            else:
                self.db.add_employee(data['emp_id'], data['name'], data['email'], data['dept'], data['pan'], data['uan'])
            
            self.callback()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))
