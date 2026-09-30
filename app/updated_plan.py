"""Feedback-based plan updater (Gemini Pro, falling back to Flash)."""
from .gemini_client import generate_with_fallback


def update_workout_plan(original_plan: str, user_feedback: str) -> str:
    """Use Gemini to revise a workout plan based on user feedback. Raises GeminiError on failure."""
    prompt = f"""
You are a professional fitness trainer assistant.

Here's the original 7-day workout plan:
{original_plan}

User Feedback:
"{user_feedback}"

Based on the feedback, revise the relevant parts of the workout plan. Keep the format and rest of the plan unchanged if not needed.
""".strip()
    return generate_with_fallback(prompt)
