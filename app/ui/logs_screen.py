import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import datetime
import pandas as pd

class LogsScreen(ctk.CTkFrame):
    def __init__(self, parent, db_service):
        super().__init__(parent, fg_color="transparent")
        self.db = db_service
        self._setup_ui()

    def _setup_ui(self):
        # Header
        header = ctk.CTkLabel(self, text="Processing Logs", font=ctk.CTkFont(size=24, weight="bold"))
        header.pack(pady=(0, 20), anchor="w")

        # Filters
        filter_frame = ctk.CTkFrame(self)
        filter_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(filter_frame, text="Status:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 5), pady=10)
        self.status_filter = ctk.StringVar(value="All Status")
        ctk.CTkOptionMenu(filter_frame, values=["All Status", "SENT", "FAILED", "CONFLICT", "UNMATCHED"], 
                          variable=self.status_filter, command=lambda _: self._refresh_table()).pack(side="left", padx=5, pady=10)

        ctk.CTkLabel(filter_frame, text="Period:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(15, 5), pady=10)
        periods = ["All Periods"] + self.db.get_distinct_log_periods()
        self.period_filter = ctk.StringVar(value="All Periods")
        self.period_menu = ctk.CTkOptionMenu(filter_frame, values=periods, variable=self.period_filter, command=lambda _: self._refresh_table())
        self.period_menu.pack(side="left", padx=5, pady=10)
        
        ctk.CTkButton(filter_frame, text="Export Excel", fg_color="green", hover_color="darkgreen", width=100, command=self._export_excel).pack(side="right", padx=10)
        ctk.CTkButton(filter_frame, text="Clear Logs", fg_color="red", hover_color="darkred", width=100, command=self._clear_logs).pack(side="right", padx=10)

        # Table Container
        self.table_frame = ctk.CTkScrollableFrame(self)
        self.table_frame.pack(fill="both", expand=True)
        
        self._refresh_table()

    def _refresh_table(self):
        for widget in self.table_frame.winfo_children():
            widget.destroy()

        # Update available periods in filter dropdown
        periods = ["All Periods"] + self.db.get_distinct_log_periods()
        self.period_menu.configure(values=periods)

        headers = ["Time", "Period", "Employee ID", "Extracted Name", "Status", "Details", "Actions"]
        for i, h in enumerate(headers):
            lbl = ctk.CTkLabel(self.table_frame, text=h, font=ctk.CTkFont(weight="bold"))
            lbl.grid(row=0, column=i, padx=8, pady=5, sticky="w")

        current_period = self.period_filter.get()
        logs = self.db.get_logs(period_filter=current_period)
        current_status = self.status_filter.get()
        
        row_idx = 1
        for log in logs:
            # log: (id, emp_id, ext_name, ext_pan, ext_uan, status, error, pdf_path, sent_at, period)
            status = log[5]
            if current_status != "All Status" and status != current_status:
                continue

            # Color coding status
            color = "#107C41" if status == "SENT" else "#D83B01" if status == "FAILED" else "#EAA300" if status == "CONFLICT" else "gray"
            
            ctk.CTkLabel(self.table_frame, text=str(log[8])[:19]).grid(row=row_idx, column=0, padx=8, pady=2, sticky="w")
            ctk.CTkLabel(self.table_frame, text=log[9] or "—").grid(row=row_idx, column=1, padx=8, pady=2, sticky="w")
            ctk.CTkLabel(self.table_frame, text=log[1] or "-").grid(row=row_idx, column=2, padx=8, pady=2, sticky="w")
            ctk.CTkLabel(self.table_frame, text=log[2] or "Unknown").grid(row=row_idx, column=3, padx=8, pady=2, sticky="w")
            
            status_badge = ctk.CTkLabel(self.table_frame, text=status, text_color=color, font=ctk.CTkFont(weight="bold"))
            status_badge.grid(row=row_idx, column=4, padx=8, pady=2, sticky="w")
            
            ctk.CTkLabel(self.table_frame, text=log[6] or "Success", width=180).grid(row=row_idx, column=5, padx=8, pady=2, sticky="w")
            
            # Action buttons
            actions_f = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            actions_f.grid(row=row_idx, column=6, padx=8, pady=2, sticky="w")

            if log[7] and os.path.exists(log[7]):
                ctk.CTkButton(actions_f, text="PDF", width=45, height=24, fg_color="gray", command=lambda p=log[7]: self._open_pdf(p)).pack(side="left", padx=2)

            btn = ctk.CTkButton(actions_f, text="Details", width=55, height=24, command=lambda l=log: self._show_log_details(l))
            btn.pack(side="left", padx=2)
            
            row_idx += 1

    def _open_pdf(self, path):
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open PDF: {e}")

    def _export_excel(self):
        logs = self.db.get_logs()
        if not logs:
            messagebox.showwarning("Warning", "No logs to export")
            return
            
        file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if not file_path: return
        
        try:
            df = pd.DataFrame(logs, columns=["ID", "Employee ID", "Extracted Name", "Extracted PAN", "Extracted UAN", "Status", "Error", "PDF Path", "Time"])
            df.to_excel(file_path, index=False)
            messagebox.showinfo("Success", "Logs exported successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")

    def _show_log_details(self, log):
        # (id, emp_id, ext_name, ext_pan, ext_uan, status, error, pdf_path, sent_at)
        details = f"""
Time: {log[8]}
Status: {log[5]}
Employee ID: {log[1]}
Extracted Name: {log[2]}
Extracted PAN: {log[3]}
Extracted UAN: {log[4]}
Error Message: {log[6]}
PDF Path: {log[7]}
"""
        messagebox.showinfo("Log Details", details)

    def _clear_logs(self):
        if messagebox.askyesno("Confirm", "Clear all processing logs?"):
            with self.db._get_connection() as conn:
                conn.execute("DELETE FROM email_logs")
                conn.commit()
            self._refresh_table()
