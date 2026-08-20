import customtkinter as ctk

class DashboardScreen(ctk.CTkFrame):
    def __init__(self, parent, db_service):
        super().__init__(parent, fg_color="transparent")
        self.db = db_service
        self._setup_ui()

    def _setup_ui(self):
        # Header
        header = ctk.CTkLabel(self, text="Dashboard Overview", font=ctk.CTkFont(size=24, weight="bold"))
        header.pack(pady=(0, 20), anchor="w")

        # Stats Grid
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", pady=10)
        
        # Fetch stats
        employees = self.db.get_all_employees()
        logs = self.db.get_logs()
        
        sent_count = len([l for l in logs if l[5] == 'SENT'])
        failed_count = len([l for l in logs if l[5] == 'FAILED'])
        conflict_count = len([l for l in logs if l[5] == 'CONFLICT'])
        unmatched_count = len([l for l in logs if l[5] == 'UNMATCHED'])

        # Create cards
        self.create_stat_card(stats_frame, "Total Employees", len(employees), 0, 0)
        self.create_stat_card(stats_frame, "Emails Sent", sent_count, 0, 1)
        self.create_stat_card(stats_frame, "Failed Emails", failed_count, 0, 2)
        self.create_stat_card(stats_frame, "Conflict Cases", conflict_count, 1, 0)
        self.create_stat_card(stats_frame, "Unmatched Payslips", unmatched_count, 1, 1)
        
        # Recent Activity
        activity_label = ctk.CTkLabel(self, text="Recent Activity", font=ctk.CTkFont(size=18, weight="bold"))
        activity_label.pack(pady=(30, 10), anchor="w")
        
        activity_frame = ctk.CTkFrame(self, corner_radius=10)
        activity_frame.pack(fill="both", expand=True)
        
        if not logs:
            no_data = ctk.CTkLabel(activity_frame, text="No recent activity found.", text_color="gray")
            no_data.pack(pady=40)
        else:
            for log in logs[:5]:
                log_text = f"{log[8]} - {log[5]}: {log[2] or 'Unknown'} (Employee ID: {log[1] or 'N/A'})"
                item = ctk.CTkLabel(activity_frame, text=log_text, anchor="w", padx=20)
                item.pack(fill="x", pady=5)

    def create_stat_card(self, parent, title, value, row, col):
        card = ctk.CTkFrame(parent, width=200, height=100, corner_radius=12)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)
        
        title_lbl = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=14))
        title_lbl.pack(pady=(15, 0))
        
        val_lbl = ctk.CTkLabel(card, text=str(value), font=ctk.CTkFont(size=24, weight="bold"))
        val_lbl.pack(pady=(5, 15))
