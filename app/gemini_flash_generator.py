"""Gemini Flash - short nutrition / recovery tips."""
from . import config
from .gemini_client import generate_text


def generate_nutrition_tip_with_flash(goal: str) -> str:
    """
    Generate a nutrition or recovery tip using Gemini Flash based on the user's fitness goal.

    Args:
        goal (str): The user's fitness goal, e.g. "weight loss", "muscle gain" or "general fitness".

    Returns:
        str: The generated tip. Raises GeminiError on failure.
    """
    prompt = (
        f"Give one clear, helpful nutrition or recovery tip for someone focused on '{goal}'. "
        "The tip should be practical, friendly, and easy to understand."
    )
    return generate_text(prompt, config.GEMINI_FLASH_MODEL)
