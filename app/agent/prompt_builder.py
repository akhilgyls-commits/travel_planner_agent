"""
Converts a structured TripPlanRequest into a natural-language planning
prompt for the agent. Keeping this separate from schemas.py keeps the
API models free of presentation logic.
"""
from app.models.schemas import TripPlanRequest


def build_planning_prompt(req: TripPlanRequest) -> str:
    interests_str = ", ".join(i.value for i in req.interests) if req.interests else "no specific preferences"
    origin_str = req.origin_city or "not specified"
    notes_str = req.additional_notes or "none"

    return f"""\
Plan a detailed trip with the following requirements:

- Destination: {req.destination}
- Origin city (departure point): {origin_str}
- Travel dates: {req.start_date.isoformat()} to {req.end_date.isoformat()} \
({req.duration_days} days)
- Number of travelers: {req.travelers}
- Total budget: {req.budget_amount} {req.budget_currency} \
(budget tier: {req.budget_level.value})
- Interests: {interests_str}
- Additional notes: {notes_str}

Use your tools to check the weather, find attractions/restaurants/hotels
matching the interests and budget tier, work out transportation, and
compute a total cost estimate. Then produce the full itinerary following
the output format in your instructions.
"""
