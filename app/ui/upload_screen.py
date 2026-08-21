import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import re
from datetime import datetime, date
from services.pdf_splitter import PDFSplitter
from services.extractor import Extractor
from services.matcher import Matcher
from services.email_sender import EmailSender

class UploadScreen(ctk.CTkFrame):
    MONTHS = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    def __init__(self, parent, db_service):
        super().__init__(parent, fg_color="transparent")
        self.db = db_service
        self.extractor = Extractor()
        self.matcher = Matcher(self.db)
        
        # State management
        self.is_processing = False
        self.stop_requested = False
        self.extracted_records = []  # list of dicts with extraction, employee match, and sending status
        self.current_filter = "All"
        
        self._setup_ui()
        self._load_saved_period_data()

    def _get_default_month_year(self):
        """Calculates the previous month and corresponding year by default."""
        today = date.today()
        if today.month == 1:
            prev_month_idx = 12
            prev_year = today.year - 1
        else:
            prev_month_idx = today.month - 1
            prev_year = today.year
        return self.MONTHS[prev_month_idx - 1], str(prev_year)

    def _get_splitter(self):
        settings = self.db.get_settings()
        custom_out = settings[11] if settings and len(settings) > 11 and settings[11] else None
        return PDFSplitter(output_dir=custom_out)

    def _on_period_changed(self, *args):
        """Called whenever Month or Year dropdown changes."""
        self._load_saved_period_data()

    def _load_saved_period_data(self):
        """Loads extracted payslips for currently selected Month/Year from the database."""
        period = f"{self.month_var.get()} {self.year_var.get()}"
        rows = self.db.get_extracted_payslips(period)
        self.extracted_records = []

        if rows:
            for r in rows:
                # r: (id, period, page_number, pdf_path, ext_name, ext_code, ext_pan, ext_uan, emp_id, emp_name, email, match_status, send_status, error_msg, created_at)
                self.extracted_records.append({
                    "db_id": r[0],
                    "period": r[1],
                    "index": r[2],
                    "file_path": r[3],
                    "ext_name": r[4] or "Unknown",
                    "ext_code": r[5] or "",
                    "ext_pan": r[6] or "",
                    "ext_uan": r[7] or "",
                    "emp_id": r[8] or "",
                    "emp_name": r[9] or "",
                    "email": r[10] or "",
                    "match_status": r[11] or "UNMATCHED",
                    "send_status": r[12] or "READY",
                    "error_msg": r[13] or "",
                    "selected": True if (r[12] != "SENT" and r[10]) else False
                })

        self._render_table()
        self._update_send_batch_btn_text()

    def _clear_current_period_data(self):
        """Allows HR to start fresh for the selected period by wiping saved records."""
        period = f"{self.month_var.get()} {self.year_var.get()}"
        if not messagebox.askyesno("Confirm Reset", f"Are you sure you want to clear all extracted records for {period} and start fresh?"):
            return

        self.db.delete_extracted_payslips_for_period(period)
        self.extracted_records = []
        self._render_table()
        self._update_send_batch_btn_text()
        self._log(f"Reset: Cleared all extracted records for {period}.")
        messagebox.showinfo("Reset Complete", f"All records for {period} have been cleared.")

    def _start_extraction(self):
        pdf_path = self.file_path_var.get()
        if not pdf_path or pdf_path == "No file selected" or not os.path.exists(pdf_path):
            messagebox.showerror("Error", "Please select a valid PDF file.")
            return

        selected_month = self.month_var.get()
        selected_year = self.year_var.get()
        selected_period = f"{selected_month} {selected_year}"
        file_name = os.path.basename(pdf_path)

        # Check if records already exist for this period
        existing_rows = self.db.get_extracted_payslips(selected_period)
        if existing_rows:
            overwrite = messagebox.askyesno(
                "Existing Records Found",
                f"Found {len(existing_rows)} saved record(s) for {selected_period}.\n\n"
                f"Do you want to overwrite previous records and re-extract fresh from '{file_name}'?"
            )
            if not overwrite:
                return
            # Delete old records to start fresh
            self.db.delete_extracted_payslips_for_period(selected_period)
        else:
            confirm_msg = (
                f"Are you sure you want to extract and preview payslips?\n\n"
                f"• Selected File: {file_name}\n"
                f"• Period: {selected_period}\n\n"
                f"Do you want to proceed?"
            )
            if not messagebox.askyesno("Confirm Extraction", confirm_msg):
                return

        self.is_processing = True
        self.stop_requested = False
        self.extracted_records = []
        self._toggle_controls(enabled=False)
        self.stop_btn.pack(side="left", padx=5)

        self.tabview.set("Live Logs & Output")
        self.log_textbox.delete("1.0", "end")
        self.status_label.configure(text=f"Extracting payslips for {selected_period}...")
        self.progress_bar.set(0)

        threading.Thread(target=self._run_extraction_task, args=(pdf_path, selected_period), daemon=True).start()

    def _run_extraction_task(self, pdf_path, month_year):
        try:
            self._log(f"Starting extraction for: {os.path.basename(pdf_path)}")
            self._log(f"Period: {month_year}")

            splitter = self._get_splitter()
            self.status_label.configure(text=f"Splitting PDF into pages...")
            split_files = splitter.split_pdf(pdf_path, month_year_folder=month_year)
            total = len(split_files)
            self._log(f"Split into {total} pages.")

            for i, file_path in enumerate(split_files):
                if self.stop_requested:
                    self.after(0, lambda: self._log(f"Extraction halted by user at page {i+1}/{total}."))
                    break

                prog = (i + 1) / total
                page_curr = i + 1
                self.after(0, lambda p=prog, pc=page_curr: [
                    self.progress_bar.set(p),
                    self.status_label.configure(text=f"Extracting Page {pc} of {total}...")
                ])

                details = self.extractor.extract_details(file_path)
                ext_name = details.get("name") or "Unknown"
                ext_code = details.get("code") or ""
                ext_pan = details.get("pan") or ""
                ext_uan = details.get("uan") or ""

                match_status, emp = self.matcher.match_employee(details)

                rec = {
                    "index": i + 1,
                    "file_path": file_path,
                    "details": details,
                    "ext_name": ext_name,
                    "ext_code": ext_code,
                    "ext_pan": ext_pan,
                    "ext_uan": ext_uan,
                    "match_status": match_status, # 'MATCH', 'CONFLICT', 'UNMATCHED'
                    "emp": emp,                   # employee tuple or list
                    "emp_id": emp[1] if match_status == 'MATCH' and emp else "",
                    "emp_name": emp[2] if match_status == 'MATCH' and emp else "",
                    "email": emp[3] if match_status == 'MATCH' and emp else "",
                    "send_status": "READY" if match_status == 'MATCH' else match_status, # READY, SENT, FAILED, CONFLICT, UNMATCHED
                    "error_msg": "",
                    "selected": True if match_status == 'MATCH' else False
                }

                # Rename matched file nicely
                if match_status == 'MATCH':
                    clean_emp_name = re.sub(r'[\\/*?:"<>|]', "", rec["emp_name"]).strip()
                    clean_emp_id = re.sub(r'[\\/*?:"<>|]', "", rec["emp_id"]).strip()
                    clean_period = re.sub(r'[\\/*?:"<>|]', "", month_year).strip()
                    renamed_filename = f"{clean_emp_name} - {clean_emp_id} - {clean_period}.pdf"
                    new_pdf_path = os.path.join(os.path.dirname(file_path), renamed_filename)
                    try:
                        if os.path.exists(new_pdf_path) and os.path.abspath(new_pdf_path) != os.path.abspath(file_path):
                            os.remove(new_pdf_path)
                        os.rename(file_path, new_pdf_path)
                        rec["file_path"] = new_pdf_path
                    except Exception as e:
                        self.after(0, lambda err=e: self._log(f"Warning: Could not rename PDF: {err}"))

                self.extracted_records.append(rec)
                matched_label = rec['emp_name'] or 'None'
                self.after(0, lambda pc=page_curr, en=ext_name, ms=match_status, ml=matched_label: 
                    self._log(f"Page {pc}: {en} [{ms}] -> Matched: {ml}")
                )

            # Save batch to Database
            self.db.save_extracted_payslips_batch(month_year, self.extracted_records)
            rec_count = len(self.extracted_records)
            self.after(0, lambda: self._log(f"Saved {rec_count} records to database for {month_year}."))
            self.after(0, lambda: self._log(f"Extraction completed. {rec_count} pages loaded into Preview."))
            self.after(0, lambda: self.status_label.configure(text=f"Extraction Complete ({rec_count} records)"))
            
            # Switch back to preview tab and reload with DB IDs
            self.after(0, self._load_saved_period_data)
            self.after(0, lambda: self.tabview.set("Extracted Payslips Preview"))

        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: self._log(f"Critical Error during extraction: {err_msg}"))
            self.after(0, lambda: self.status_label.configure(text="Extraction Failed"))
        finally:
            self.is_processing = False
            self.stop_requested = False
            self.after(0, lambda: self._toggle_controls(enabled=True))

    def _setup_ui(self):
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))
        
        header = ctk.CTkLabel(header_frame, text="Upload & Process Payslips", font=ctk.CTkFont(size=22, weight="bold"))
        header.pack(side="left", anchor="w")

        # Period & PDF Selection Frame
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", pady=(0, 10), padx=2)

        default_month, default_year = self._get_default_month_year()
        current_year = date.today().year
        year_options = [str(y) for y in range(current_year - 3, current_year + 4)]

        # Controls Row 1: Month, Year, PDF Selection
        row1 = ctk.CTkFrame(top_frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(row1, text="Month:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(5, 5))
        self.month_var = ctk.StringVar(value=default_month)
        self.month_dropdown = ctk.CTkOptionMenu(row1, values=self.MONTHS, variable=self.month_var, width=120, command=self._on_period_changed)
        self.month_dropdown.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(row1, text="Year:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(5, 5))
        self.year_var = ctk.StringVar(value=default_year)
        self.year_dropdown = ctk.CTkOptionMenu(row1, values=year_options, variable=self.year_var, width=90, command=self._on_period_changed)
        self.year_dropdown.pack(side="left", padx=(0, 15))

        self.file_path_var = ctk.StringVar(value="No file selected")
        self.path_entry = ctk.CTkEntry(row1, textvariable=self.file_path_var, width=240, state="disabled")
        self.path_entry.pack(side="left", padx=(0, 10))

        self.browse_btn = ctk.CTkButton(row1, text="Browse PDF", width=85, command=self._browse_file)
        self.browse_btn.pack(side="left", padx=(0, 10))

        self.extract_btn = ctk.CTkButton(
            row1, 
            text="Extract & Preview", 
            fg_color="#0078D4", 
            hover_color="#005A9E",
            command=self._start_extraction
        )
        self.extract_btn.pack(side="left", padx=5)

        self.reset_period_btn = ctk.CTkButton(
            row1,
            text="Reset Period",
            fg_color="#6E6E6E",
            hover_color="#4E4E4E",
            width=85,
            command=self._clear_current_period_data
        )
        self.reset_period_btn.pack(side="left", padx=5)

        self.stop_btn = ctk.CTkButton(
            row1,
            text="Stop",
            fg_color="#D83B01",
            hover_color="#A80000",
            width=70,
            command=self._stop_processing
        )

        # Batch Action & Filter Toolbar
        self.toolbar_frame = ctk.CTkFrame(self)
        self.toolbar_frame.pack(fill="x", pady=(0, 5), padx=2)

        # Filter Segmented / Option
        ctk.CTkLabel(self.toolbar_frame, text="Filter:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 5), pady=8)
        self.filter_var = ctk.StringVar(value="All")
        self.filter_menu = ctk.CTkSegmentedButton(
            self.toolbar_frame,
            values=["All", "Ready", "Sent", "Failed", "Unmatched"],
            variable=self.filter_var,
            command=self._apply_filter
        )
        self.filter_menu.pack(side="left", padx=5, pady=8)

        # Batch Selection Buttons
        ctk.CTkButton(self.toolbar_frame, text="Select All", width=75, height=28, command=self._select_all).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(self.toolbar_frame, text="Deselect All", width=85, height=28, fg_color="gray", hover_color="darkgray", command=self._deselect_all).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(self.toolbar_frame, text="Select Failed", width=85, height=28, fg_color="#D83B01", hover_color="#A80000", command=self._select_failed).pack(side="left", padx=5, pady=8)

        # Batch Send Button
        self.send_batch_btn = ctk.CTkButton(
            self.toolbar_frame,
            text="Send Selected (0)",
            fg_color="green",
            hover_color="darkgreen",
            font=ctk.CTkFont(weight="bold"),
            command=self._start_batch_sending
        )
        self.send_batch_btn.pack(side="right", padx=10, pady=8)

        # Table & Logs Notebook (Tabs)
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.tab_preview = self.tabview.add("Extracted Payslips Preview")
        self.tab_logs = self.tabview.add("Live Logs & Output")

        # Build Preview Table inside Preview Tab
        self._setup_preview_table()

        # Build Logs UI inside Logs Tab
        self._setup_logs_ui()

    def _setup_preview_table(self):
        # Header Row
        self.table_header_frame = ctk.CTkFrame(self.tab_preview, height=32, fg_color=("gray85", "gray20"))
        self.table_header_frame.pack(fill="x", padx=5, pady=(5, 2))

        # Checkbox column header
        self.header_check_var = ctk.BooleanVar(value=True)
        self.header_check = ctk.CTkCheckBox(self.table_header_frame, text="", width=24, variable=self.header_check_var, command=self._toggle_all_check)
        self.header_check.grid(row=0, column=0, padx=(10, 5), pady=5, sticky="w")

        headers = [
            ("#", 40),
            ("Extracted Name / Code", 180),
            ("Matched Employee", 180),
            ("Email Address", 200),
            ("Status", 110),
            ("Actions", 160)
        ]
        
        for col_idx, (text, w) in enumerate(headers, start=1):
            lbl = ctk.CTkLabel(self.table_header_frame, text=text, width=w, anchor="w", font=ctk.CTkFont(size=12, weight="bold"))
            lbl.grid(row=0, column=col_idx, padx=5, pady=5, sticky="w")

        # Scrollable table body
        self.table_scroll = ctk.CTkScrollableFrame(self.tab_preview)
        self.table_scroll.pack(fill="both", expand=True, padx=5, pady=2)

        self.empty_label = ctk.CTkLabel(
            self.table_scroll, 
            text="No payslips extracted yet.\nSelect a PDF and click 'Extract & Preview' to inspect payslips before sending.",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.empty_label.pack(pady=60)

    def _setup_logs_ui(self):
        self.progress_frame = ctk.CTkFrame(self.tab_logs)
        self.progress_frame.pack(fill="x", pady=10, padx=5)

        self.status_label = ctk.CTkLabel(self.progress_frame, text="Ready to extract or send", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=(5, 2))

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=5)

        self.log_textbox = ctk.CTkTextbox(self.tab_logs, height=200)
        self.log_textbox.pack(fill="both", expand=True, padx=5, pady=5)

    def _browse_file(self):
        filename = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if filename:
            self.file_path_var.set(filename)

    def _log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_textbox.insert("end", f"[{timestamp}] {message}\n")
        self.log_textbox.see("end")

    def _stop_processing(self):
        if self.is_processing:
            if messagebox.askyesno("Confirm Stop", "Are you sure you want to stop current processing?"):
                self.stop_requested = True
                self._log("Stop requested by user...")
                self.status_label.configure(text="Stopping...")
                self.stop_btn.configure(state="disabled")

    # ----------------------------------------------------
    # Table Rendering & Filter Logic
    # ----------------------------------------------------
    def _apply_filter(self, val):
        self.current_filter = val
        self._render_table()

    def _render_table(self):
        for widget in self.table_scroll.winfo_children():
            widget.destroy()

        if not self.extracted_records:
            self.empty_label = ctk.CTkLabel(
                self.table_scroll, 
                text="No payslips extracted yet.\nSelect a PDF and click 'Extract & Preview' to inspect payslips before sending.",
                font=ctk.CTkFont(size=14),
                text_color="gray"
            )
            self.empty_label.pack(pady=60)
            return

        visible_records = []
        for rec in self.extracted_records:
            st = rec["send_status"]
            if self.current_filter == "All":
                visible_records.append(rec)
            elif self.current_filter == "Ready" and st == "READY":
                visible_records.append(rec)
            elif self.current_filter == "Sent" and st == "SENT":
                visible_records.append(rec)
            elif self.current_filter == "Failed" and st == "FAILED":
                visible_records.append(rec)
            elif self.current_filter == "Unmatched" and st in ["UNMATCHED", "CONFLICT"]:
                visible_records.append(rec)

        if not visible_records:
            lbl = ctk.CTkLabel(self.table_scroll, text=f"No records matching filter '{self.current_filter}'.", text_color="gray")
            lbl.pack(pady=30)
            return

        for row_idx, rec in enumerate(visible_records):
            row_frame = ctk.CTkFrame(self.table_scroll, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)

            # Checkbox
            check_var = ctk.BooleanVar(value=rec["selected"])
            def on_check(r=rec, v=check_var):
                r["selected"] = v.get()
                self._update_send_batch_btn_text()

            cb = ctk.CTkCheckBox(row_frame, text="", width=24, variable=check_var, command=on_check)
            cb.grid(row=0, column=0, padx=(10, 5), pady=3, sticky="w")

            # Index
            idx_lbl = ctk.CTkLabel(row_frame, text=str(rec["index"]), width=40, anchor="w")
            idx_lbl.grid(row=0, column=1, padx=5, pady=3, sticky="w")

            # Extracted Name / Code
            ext_text = rec["ext_name"]
            if rec["ext_code"]:
                ext_text += f" ({rec['ext_code']})"
            ext_lbl = ctk.CTkLabel(row_frame, text=ext_text, width=180, anchor="w")
            ext_lbl.grid(row=0, column=2, padx=5, pady=3, sticky="w")

            # Matched Employee
            matched_text = f"{rec['emp_id']} - {rec['emp_name']}" if rec['emp_id'] else "—"
            match_lbl = ctk.CTkLabel(row_frame, text=matched_text, width=180, anchor="w")
            match_lbl.grid(row=0, column=3, padx=5, pady=3, sticky="w")

            # Email
            email_text = rec["email"] or "—"
            email_lbl = ctk.CTkLabel(row_frame, text=email_text, width=200, anchor="w")
            email_lbl.grid(row=0, column=4, padx=5, pady=3, sticky="w")

            # Status Badge
            st = rec["send_status"]
            color = "#107C41" if st == "SENT" else "#0078D4" if st == "READY" else "#D83B01" if st == "FAILED" else "#EAA300" if st == "CONFLICT" else "gray"
            st_lbl = ctk.CTkLabel(row_frame, text=st, width=110, text_color=color, font=ctk.CTkFont(weight="bold"), anchor="w")
            st_lbl.grid(row=0, column=5, padx=5, pady=3, sticky="w")

            # Actions Frame
            actions_frame = ctk.CTkFrame(row_frame, fg_color="transparent", width=160)
            actions_frame.grid(row=0, column=6, padx=5, pady=3, sticky="w")

            # View PDF Button
            view_btn = ctk.CTkButton(
                actions_frame, 
                text="View", 
                width=45, 
                height=24, 
                fg_color="gray", 
                hover_color="darkgray", 
                command=lambda p=rec["file_path"]: self._open_pdf(p)
            )
            view_btn.pack(side="left", padx=2)

            # Map / Re-map Button
            map_btn = ctk.CTkButton(
                actions_frame, 
                text="Map", 
                width=45, 
                height=24, 
                fg_color="#5C2E91", 
                hover_color="#3B185F", 
                command=lambda r=rec: self._show_mapping_modal(r)
            )
            map_btn.pack(side="left", padx=2)

            # Single Send Button
            send_btn = ctk.CTkButton(
                actions_frame, 
                text="Send", 
                width=45, 
                height=24, 
                fg_color="green", 
                hover_color="darkgreen", 
                command=lambda r=rec: self._send_single_record(r)
            )
            if not rec["email"]:
                send_btn.configure(state="disabled")
            send_btn.pack(side="left", padx=2)

    def _open_pdf(self, pdf_path):
        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showerror("Error", "PDF file not found.")
            return
        try:
            os.startfile(pdf_path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open PDF: {e}")

    def _show_mapping_modal(self, record):
        """Allows HR to manually select an employee from the database to map to this page."""
        employees = self.db.get_all_employees()
        if not employees:
            messagebox.showwarning("No Employees", "No employees found in the database. Please add employees first.")
            return

        modal = ctk.CTkToplevel(self)
        modal.title(f"Map Employee - Page {record['index']}")
        modal.geometry("520x420")
        modal.grab_set()

        ctk.CTkLabel(
            modal, 
            text=f"Assign Employee for Page {record['index']}", 
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(15, 5))

        info_text = f"Extracted Name: {record['ext_name']} | Extracted PAN: {record['ext_pan'] or 'N/A'}"
        ctk.CTkLabel(modal, text=info_text, text_color="gray", font=ctk.CTkFont(size=12)).pack(pady=(0, 10))

        # Search Bar
        search_frame = ctk.CTkFrame(modal, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=5)
        
        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(search_frame, textvariable=search_var, placeholder_text="Search by Name, Emp Code, PAN, Email...")
        search_entry.pack(fill="x")

        # Scrollable Employee List
        list_frame = ctk.CTkScrollableFrame(modal, height=220)
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        def populate_list(query=""):
            for w in list_frame.winfo_children():
                w.destroy()

            q = query.lower()
            filtered = [
                e for e in employees 
                if q in str(e[1]).lower() or q in str(e[2]).lower() or q in str(e[3]).lower() or q in str(e[5]).lower()
            ]

            if not filtered:
                ctk.CTkLabel(list_frame, text="No matching employees found", text_color="gray").pack(pady=20)
                return

            for emp in filtered:
                # emp: (id, emp_id, name, email, dept, pan, uan, created_at)
                btn_text = f"{emp[1]} - {emp[2]} ({emp[3]})"
                btn = ctk.CTkButton(
                    list_frame, 
                    text=btn_text, 
                    anchor="w", 
                    fg_color=("gray90", "gray25"), 
                    text_color=("gray10", "gray90"),
                    hover_color=("gray75", "gray35"),
                    command=lambda e=emp: assign_and_close(e)
                )
                btn.pack(fill="x", pady=2)

        def assign_and_close(emp):
            record["emp"] = emp
            record["emp_id"] = emp[1]
            record["emp_name"] = emp[2]
            record["email"] = emp[3]
            record["match_status"] = "MATCH"
            record["send_status"] = "READY"
            record["selected"] = True

            # Rename PDF with assigned employee name
            selected_period = f"{self.month_var.get()} {self.year_var.get()}"
            clean_emp_name = re.sub(r'[\\/*?:"<>|]', "", emp[2]).strip()
            clean_emp_id = re.sub(r'[\\/*?:"<>|]', "", emp[1]).strip()
            clean_period = re.sub(r'[\\/*?:"<>|]', "", selected_period).strip()
            renamed_filename = f"{clean_emp_name} - {clean_emp_id} - {clean_period}.pdf"
            
            old_path = record["file_path"]
            new_pdf_path = os.path.join(os.path.dirname(old_path), renamed_filename)
            try:
                if os.path.exists(new_pdf_path) and os.path.abspath(new_pdf_path) != os.path.abspath(old_path):
                    os.remove(new_pdf_path)
                os.rename(old_path, new_pdf_path)
                record["file_path"] = new_pdf_path
            except Exception as e:
                self._log(f"Warning: Could not rename PDF: {e}")

            # Update in DB if existing
            if record.get("db_id"):
                self.db.update_extracted_payslip(
                    record["db_id"], emp[1], emp[2], emp[3], "MATCH", "READY", pdf_path=record["file_path"]
                )

            modal.destroy()
            self._render_table()
            self._update_send_batch_btn_text()

        search_var.trace_add("write", lambda *args: populate_list(search_var.get()))
        populate_list()

    # ----------------------------------------------------
    # Selection Controls
    # ----------------------------------------------------
    def _toggle_all_check(self):
        val = self.header_check_var.get()
        for rec in self.extracted_records:
            if rec["email"]:
                rec["selected"] = val
        self._render_table()
        self._update_send_batch_btn_text()

    def _select_all(self):
        for rec in self.extracted_records:
            if rec["email"]:
                rec["selected"] = True
        self._render_table()
        self._update_send_batch_btn_text()

    def _deselect_all(self):
        for rec in self.extracted_records:
            rec["selected"] = False
        self._render_table()
        self._update_send_batch_btn_text()

    def _select_failed(self):
        for rec in self.extracted_records:
            rec["selected"] = (rec["send_status"] == "FAILED" and bool(rec["email"]))
        self.filter_var.set("Failed")
        self.current_filter = "Failed"
        self._render_table()
        self._update_send_batch_btn_text()

    def _update_send_batch_btn_text(self):
        count = sum(1 for r in self.extracted_records if r.get("selected") and r.get("email"))
        self.send_batch_btn.configure(text=f"Send Selected ({count})")

    # ----------------------------------------------------
    # STAGE 2: Email Sending & Batch Dispatching
    # ----------------------------------------------------
    def _send_single_record(self, record):
        if not record["email"]:
            messagebox.showerror("Error", "No email address assigned to this employee.")
            return

        if not messagebox.askyesno("Confirm Send", f"Send payslip to {record['emp_name']} ({record['email']})?"):
            return

        self._log(f"Sending individual payslip to {record['email']}...")
        settings = self.db.get_settings()
        email_sender = EmailSender(settings, db_service=self.db)
        selected_period = f"{self.month_var.get()} {self.year_var.get()}"

        sent, msg = email_sender.send_payslip(
            record["email"], 
            record["emp_name"], 
            selected_period, 
            record["file_path"],
            emp_id=record["emp_id"]
        )

        if sent:
            record["send_status"] = "SENT"
            record["error_msg"] = ""
            self.db.add_log(record["emp_id"], record["ext_name"], record["ext_pan"], record["ext_uan"], "SENT", pdf_path=record["file_path"], period=selected_period)
            if record.get("db_id"):
                self.db.update_extracted_payslip(record["db_id"], record["emp_id"], record["emp_name"], record["email"], record["match_status"], "SENT", error_message="")
            self._log(f"✓ Successfully sent to {record['email']}")
            messagebox.showinfo("Sent", f"Payslip successfully sent to {record['email']}.")
        else:
            record["send_status"] = "FAILED"
            record["error_msg"] = msg
            self.db.add_log(record["emp_id"], record["ext_name"], record["ext_pan"], record["ext_uan"], "FAILED", error=msg, pdf_path=record["file_path"], period=selected_period)
            if record.get("db_id"):
                self.db.update_extracted_payslip(record["db_id"], record["emp_id"], record["emp_name"], record["email"], record["match_status"], "FAILED", error_message=msg)
            self._log(f"✗ Failed sending to {record['email']}: {msg}")
            messagebox.showerror("Failed", f"Failed to send: {msg}")

        self._render_table()

    def _start_batch_sending(self):
        selected_records = [r for r in self.extracted_records if r.get("selected") and r.get("email")]
        if not selected_records:
            messagebox.showwarning("Warning", "No valid records selected to send.")
            return

        selected_period = f"{self.month_var.get()} {self.year_var.get()}"
        confirm_msg = (
            f"Are you sure you want to send emails for {len(selected_records)} selected employee(s)?\n\n"
            f"• Period: {selected_period}\n\n"
            f"Do you want to proceed?"
        )
        if not messagebox.askyesno("Confirm Batch Sending", confirm_msg):
            return

        self.is_processing = True
        self.stop_requested = False
        self._toggle_controls(enabled=False)
        self.stop_btn.pack(side="left", padx=5)

        self.tabview.set("Live Logs & Output")
        self.status_label.configure(text=f"Sending emails (0/{len(selected_records)})...")
        self.progress_bar.set(0)

        threading.Thread(
            target=self._run_batch_sending_task, 
            args=(selected_records, selected_period), 
            daemon=True
        ).start()

    def _run_batch_sending_task(self, records, month_year):
        try:
            total = len(records)
            success_count = 0
            settings = self.db.get_settings()
            email_sender = EmailSender(settings, db_service=self.db)

            self.after(0, lambda: self._log(f"Starting batch dispatch of {total} emails for {month_year}..."))

            for i, rec in enumerate(records):
                if self.stop_requested:
                    self.after(0, lambda curr=i: self._log(f"Batch dispatch stopped by user at {curr}/{total}."))
                    break

                prog = (i + 1) / total
                curr_idx = i + 1
                curr_name = rec['emp_name']
                self.after(0, lambda p=prog, ci=curr_idx, cn=curr_name: [
                    self.progress_bar.set(p),
                    self.status_label.configure(text=f"Sending ({ci}/{total}): {cn}...")
                ])

                sent, msg = email_sender.send_payslip(
                    rec["email"], 
                    rec["emp_name"], 
                    month_year, 
                    rec["file_path"],
                    emp_id=rec["emp_id"]
                )

                if sent:
                    rec["send_status"] = "SENT"
                    rec["error_msg"] = ""
                    self.db.add_log(rec["emp_id"], rec["ext_name"], rec["ext_pan"], rec["ext_uan"], "SENT", pdf_path=rec["file_path"], period=month_year)
                    if rec.get("db_id"):
                        self.db.update_extracted_payslip(rec["db_id"], rec["emp_id"], rec["emp_name"], rec["email"], rec["match_status"], "SENT", error_message="")
                    self.after(0, lambda en=rec['emp_name'], em=rec['email']: self._log(f"✓ Sent to {en} ({em})"))
                    success_count += 1
                else:
                    rec["send_status"] = "FAILED"
                    rec["error_msg"] = msg
                    self.db.add_log(rec["emp_id"], rec["ext_name"], rec["ext_pan"], rec["ext_uan"], "FAILED", error=msg, pdf_path=rec["file_path"], period=month_year)
                    if rec.get("db_id"):
                        self.db.update_extracted_payslip(rec["db_id"], rec["emp_id"], rec["emp_name"], rec["email"], rec["match_status"], "FAILED", error_message=msg)
                    self.after(0, lambda en=rec['emp_name'], em=rec['email'], m=msg: self._log(f"✗ Failed for {en} ({em}): {m}"))

            if self.stop_requested:
                self.after(0, lambda sc=success_count: [
                    self._log(f"Batch sending stopped. {sc}/{total} sent successfully."),
                    self.status_label.configure(text="Batch Sending Stopped")
                ])
            else:
                self.after(0, lambda sc=success_count: [
                    self._log(f"Batch completed. {sc}/{total} sent successfully."),
                    self.status_label.configure(text=f"Batch Complete: {sc}/{total} Sent")
                ])

        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: [
                self._log(f"Critical error during batch sending: {err_msg}"),
                self.status_label.configure(text="Batch Sending Failed")
            ])
        finally:
            self.is_processing = False
            self.stop_requested = False
            self.after(0, lambda: self._toggle_controls(enabled=True))
            self.after(0, self._render_table)
            self.after(0, self._update_send_batch_btn_text)

    def _toggle_controls(self, enabled=True):
        state = "normal" if enabled else "disabled"
        self.extract_btn.configure(state=state)
        self.browse_btn.configure(state=state)
        self.month_dropdown.configure(state=state)
        self.year_dropdown.configure(state=state)
        self.send_batch_btn.configure(state=state)
        if enabled:
            self.stop_btn.pack_forget()
