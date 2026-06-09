import httpx
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from app.db.vector_store import vector_store
from app.db.challan_db import challan_db

# Initialize search instance
ddg_search = DuckDuckGoSearchRun()

@tool
def search_national_laws(query: str) -> str:
    """Search for national-level Indian traffic and motor vehicle laws.
    Use this to find rules, regulations, and legal texts from the MV Act or Central Rules.
    Do NOT use this for exact fine amounts (use calculate_challan instead)."""
    return vector_store.search_national(query)

@tool
def search_state_laws(query: str, state: str) -> str:
    """Search for state-specific traffic laws and rules.
    Provide the state name (e.g. 'Tamil Nadu').
    Use this to find state-specific overrides, taxation rules, or local regulations."""
    return vector_store.search_state(query, state)

@tool
def calculate_challan(violation: str, vehicle_type: str = "all", state: str = "national") -> str:
    """Get exact fine amounts, penalties, and relevant sections for a specific traffic violation.
    ALWAYS use this whenever the user asks about fines, penalties, or challan amounts.
    CRITICAL: Pass ONLY a 1-3 word simple keyword for the violation.
    You MUST normalize the user's words into standard traffic terms before searching (e.g., convert 'overspeeding' to 'speeding', 'without protective headgear' to 'helmet', 'signal jump' to 'signal').
    Do NOT pass the user's full sentence."""
    return challan_db.get_fine(violation, vehicle_type, state)

@tool
def resolve_location(latitude: float, longitude: float) -> str:
    """Resolve GPS coordinates to a state and country using Nominatim API.
    Use this if you are given coordinates and need to figure out which state the user is in."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={latitude}&lon={longitude}&format=json"
        headers = {'User-Agent': 'DriveLegal-Hackathon-App'}
        response = httpx.get(url, headers=headers, timeout=5.0)
        
        if response.status_code == 200:
            data = response.json()
            address = data.get("address", {})
            state = address.get("state", "Unknown")
            country = address.get("country", "Unknown")
            city = address.get("city", address.get("town", address.get("village", "Unknown")))
            return f"Location resolved: State={state}, Country={country}, City={city}"
        return f"Could not resolve location. Status: {response.status_code}"
    except Exception as e:
        return f"Error resolving location: {e}"

@tool
def format_citation(section: str, act_name: str, year: str) -> str:
    """Format a legal citation standardly.
    Use this to ensure citations are consistently formatted."""
    return f"Section {section}, {act_name}, {year}"

@tool
def search_web_fallback(query: str) -> str:
    """Search the web for the latest traffic rules, fines, and road regulations when local database and vector store queries do not have the answer.
    Provide a specific search query.
    Use this tool ONLY when no specific rules are found in the local databases."""
    try:
        # Constrain search to Indian laws/traffic/police to ensure high quality and relevant answers
        refined_query = f"{query} India traffic fine rules"
        return ddg_search.run(refined_query)
    except Exception as e:
        return f"Error performing web search: {e}"
