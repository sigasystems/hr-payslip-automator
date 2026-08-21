import customtkinter as ctk
from tkinter import messagebox
from ui.dashboard import DashboardScreen
from ui.upload_screen import UploadScreen
from ui.employees_screen import EmployeesScreen
from ui.logs_screen import LogsScreen
from ui.settings_screen import SettingsScreen
from services.database import DatabaseService

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("HR Payslip Automator")
        self.geometry("1100x700")
        
        # Appearance
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Initialize Services & Auto-cleanup records older than 6 months
        self.db = DatabaseService()
        self.db.cleanup_old_data(months=6)

        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="HR PAYSLIP", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(pady=20, padx=20)

        self.nav_buttons = {}
        self.create_nav_button("Dashboard", lambda: self._navigate_to(self.show_dashboard))
        self.create_nav_button("Upload Payslip", lambda: self._navigate_to(self.show_upload))
        self.create_nav_button("Employees", lambda: self._navigate_to(self.show_employees))
        self.create_nav_button("Logs", lambda: self._navigate_to(self.show_logs))
        self.create_nav_button("Settings", lambda: self._navigate_to(self.show_settings))

        # Main Content Area
        self.content_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.current_screen = None
        self.show_dashboard()

    def create_nav_button(self, text, command):
        btn = ctk.CTkButton(self.sidebar_frame, text=text, command=command, corner_radius=8, height=40, anchor="w", fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"))
        btn.pack(pady=5, padx=20, fill="x")
        self.nav_buttons[text] = btn

    def _navigate_to(self, target_show_fn):
        if self.current_screen and getattr(self.current_screen, "is_processing", False):
            msg = (
                "A job (Extraction / Email Sending) is currently in progress.\n\n"
                "Navigating away will abort the running task.\n\n"
                "Do you want to stop the job and navigate away?"
            )
            if not messagebox.askyesno("Confirm Navigation", msg):
                return
            
            # Stop current running job
            if hasattr(self.current_screen, "stop_requested"):
                self.current_screen.stop_requested = True

        target_show_fn()

    def clear_content(self):
        if self.current_screen:
            self.current_screen.destroy()
        for btn in self.nav_buttons.values():
            btn.configure(fg_color="transparent")

    def show_dashboard(self):
        self.clear_content()
        self.nav_buttons["Dashboard"].configure(fg_color=("gray75", "gray25"))
        self.current_screen = DashboardScreen(self.content_frame, self.db)
        self.current_screen.pack(fill="both", expand=True)

    def show_upload(self):
        self.clear_content()
        self.nav_buttons["Upload Payslip"].configure(fg_color=("gray75", "gray25"))
        self.current_screen = UploadScreen(self.content_frame, self.db)
        self.current_screen.pack(fill="both", expand=True)

    def show_employees(self):
        self.clear_content()
        self.nav_buttons["Employees"].configure(fg_color=("gray75", "gray25"))
        self.current_screen = EmployeesScreen(self.content_frame, self.db)
        self.current_screen.pack(fill="both", expand=True)

    def show_logs(self):
        self.clear_content()
        self.nav_buttons["Logs"].configure(fg_color=("gray75", "gray25"))
        self.current_screen = LogsScreen(self.content_frame, self.db)
        self.current_screen.pack(fill="both", expand=True)

    def show_settings(self):
        self.clear_content()
        self.nav_buttons["Settings"].configure(fg_color=("gray75", "gray25"))
        self.current_screen = SettingsScreen(self.content_frame, self.db)
        self.current_screen.pack(fill="both", expand=True)

if __name__ == "__main__":
    app = App()
    app.mainloop()
