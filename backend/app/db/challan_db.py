import pandas as pd
from app.config import CHALLAN_FINES_CSV

class ChallanDB:
    def __init__(self):
        try:
            self.df = pd.read_csv(CHALLAN_FINES_CSV)
            self.df = self.df.fillna("")  # Replace NaN with empty string
        except Exception as e:
            print(f"Error loading challan CSV: {e}")
            self.df = pd.DataFrame()

    def get_fine(self, violation: str, vehicle_type: str = "all", state: str = "national") -> str:
        if self.df.empty:
            return "Challan database is currently unavailable."
            
        violation_lower = violation.lower()
        
        # 1. Exact match on violation code
        match = self.df[self.df['violation_code'].str.lower() == violation_lower]
        
        # 2. Fuzzy match on description
        if match.empty:
            match = self.df[self.df['violation_description'].str.lower().str.contains(violation_lower, na=False)]
            
        # 3. Fallback: Check if any word in the violation string matches, get best match
        if match.empty:
            words = violation_lower.split()
            stop_words = ["i", "had", "crossed", "the", "a", "an", "is", "for", "not", "wearing", "what", "fine", "my", "without", "party", "about", "tell", "riding", "driving", "rider", "driver", "vehicle", "vehicles", "run", "caused", "causing", "allow", "allowing", "on", "in", "with", "bike", "car", "motorcycle", "than", "old", "older", "year", "years", "more", "one", "two", "three", "four", "five"]
            meaningful_words = [w for w in words if w not in stop_words and len(w) > 2]
            
            best_match_idx = -1
            max_matches = 0
            
            for idx, row in self.df.iterrows():
                desc = str(row['violation_description']).lower()
                code = str(row['violation_code']).lower()
                combined_text = desc + " " + code
                
                matches = 0
                for w in meaningful_words:
                    # Match if the word is in the description/code OR if a significant word from the DB is in the user's word (e.g. 'speed' in 'overspeeding')
                    if w in combined_text or any(cw in w for cw in combined_text.split() if len(cw) > 4):
                        matches += 1
                        
                if matches > max_matches:
                    max_matches = matches
                    best_match_idx = idx
            
            if best_match_idx != -1:
                match = self.df.loc[[best_match_idx]]
            
        if match.empty:
            return f"Could not find exact fines for violation: {violation}"
            
        # Get first match
        row = match.iloc[0]
        
        result = {
            "violation": row["violation_description"],
            "section": row["applicable_section"],
            "act": row["act_name"],
            "first_offence_fine": row["first_offence_fine"],
            "repeat_offence_fine": row["repeat_offence_fine"],
            "imprisonment": row["imprisonment_first"],
            "license_suspension": row["license_suspension"],
            "notes": row["notes"]
        }
        
        # Format for the LLM
        first_fine = f"Rs. {result['first_offence_fine']}" if result['first_offence_fine'] else "Not a fixed fine (See Imprisonment/Notes)"
        repeat_fine = f"Rs. {result['repeat_offence_fine']}" if result['repeat_offence_fine'] else "Not a fixed fine (See Imprisonment/Notes)"
        
        return (
            f"Violation: {result['violation']}\n"
            f"Section: {result['section']} of {result['act']}\n"
            f"First Offence Fine: {first_fine}\n"
            f"Repeat Offence Fine: {repeat_fine}\n"
            f"Imprisonment: {result['imprisonment'] or 'None'}\n"
            f"License Suspension: {result['license_suspension'] or 'None'}\n"
            f"Notes: {result['notes'] or 'None'}"
        )

challan_db = ChallanDB()
