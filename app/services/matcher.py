class Matcher:
    def __init__(self, db_service):
        self.db = db_service

    def match_employee(self, extracted_data):
        """
        Match extracted data against database employees.
        Priority: Employee Code/ID -> PAN -> UAN -> Name
        Returns (match_type, employee_record)
        match_type: 'MATCH', 'CONFLICT', 'UNMATCHED'
        """
        ext_code = extracted_data.get("code")
        ext_pan = extracted_data.get("pan")
        ext_uan = extracted_data.get("uan")
        ext_name = extracted_data.get("name")

        employees = self.db.get_all_employees()
        
        # 1. Try Employee Code / ID Match (with whitespace normalization)
        if ext_code:
            norm_code = ext_code.replace(" ", "").lower()
            matches = [
                e for e in employees 
                if e[1] and str(e[1]).replace(" ", "").lower() == norm_code
            ]
            if len(matches) == 1:
                return 'MATCH', matches[0]
            elif len(matches) > 1:
                return 'CONFLICT', matches

        # 2. Try PAN Match
        if ext_pan:
            matches = [e for e in employees if e[5] == ext_pan] # index 5 is pan_number
            if len(matches) == 1:
                return 'MATCH', matches[0]
            elif len(matches) > 1:
                return 'CONFLICT', matches
        
        # 3. Try UAN Match
        if ext_uan:
            matches = [e for e in employees if e[6] == ext_uan] # index 6 is uan_number
            if len(matches) == 1:
                return 'MATCH', matches[0]
            elif len(matches) > 1:
                return 'CONFLICT', matches

        # 4. Try Name Match (Case-insensitive)
        if ext_name:
            norm_ext_name = ext_name.lower().strip()
            matches = [e for e in employees if e[2].lower().strip() == norm_ext_name] # index 2 is name
            if len(matches) == 1:
                return 'MATCH', matches[0]
            elif len(matches) > 1:
                return 'CONFLICT', matches

        return 'UNMATCHED', None
