"""Gemini Pro - personalised 7-day workout plan generator."""
from .gemini_client import generate_with_fallback


def build_workout_prompt(user_input: dict) -> str:
    """Build the prompt. `goal` and `intensity` are required; `age` and `weight` are optional extras."""
    profile = []
    if user_input.get("age"):
        profile.append(f"- Age: {user_input['age']}")
    if user_input.get("weight"):
        profile.append(f"- Weight: {user_input['weight']} kg")
    profile_block = ("About the person:\n" + "\n".join(profile) + "\n\n") if profile else ""

    return f"""
You are a professional fitness trainer.

Create a personalized, structured 7-day workout plan for someone with the goal of **{user_input['goal']}**, and prefers **{user_input['intensity']} intensity** workouts.

{profile_block}Each day must include:
- A warm-up (5-10 mins)
- Main workout (targeted exercises, sets & reps)
- Cooldown or recovery tip

Format:
Day 1:
Warm-up: ...
Main Workout: ...
Cooldown: ...
(Repeat for Day 2-7)

Finish with a short "Important Notes" section (progressive overload, form, rest, hydration) and remind the person to check with a doctor before starting a new routine.
""".strip()


def generate_workout_gemini(user_input: dict) -> str:
    """Return a 7-day plan as text. Raises GeminiError on failure (nothing is swallowed into the plan text)."""
    return generate_with_fallback(build_workout_prompt(user_input))
