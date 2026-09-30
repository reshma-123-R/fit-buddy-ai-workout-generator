"""Nutrition helper: a Gemini Flash tip with a built-in offline fallback."""
import logging

from .gemini_client import GeminiError
from .gemini_flash_generator import generate_nutrition_tip_with_flash

logger = logging.getLogger("fitbuddy.nutrition")

FALLBACK_TIPS = {
    "weight_loss": (
        "Build most meals around lean protein and vegetables, and drink a glass of water before eating - "
        "it keeps you fuller so a modest calorie deficit feels easier to stick to."
    ),
    "muscle_gain": (
        "Include a good protein source (eggs, chicken, fish, beans, lentils, yogurt or tofu) at every meal, "
        "and add a carb-rich snack after training to help your muscles recover."
    ),
    "flexibility": (
        "Stay well hydrated and eat potassium- and magnesium-rich foods such as bananas, leafy greens and nuts - "
        "they support muscle relaxation and recovery."
    ),
    "general": (
        "Aim for a balanced plate - half vegetables, a quarter protein, a quarter whole grains - "
        "and drink water regularly through the day."
    ),
}

_KEYWORDS = {
    "weight_loss": ("lose", "loss", "fat", "slim", "cut", "belly", "weight"),
    "muscle_gain": ("muscle", "gain", "bulk", "strength", "build", "mass"),
    "flexibility": ("flexib", "mobility", "stretch", "yoga"),
}


def categorize_goal(goal: str) -> str:
    """Map free-text goals such as 'i want to lose belly fat' to a fallback-tip category."""
    text = goal.lower()
    for category, words in _KEYWORDS.items():
        if any(word in text for word in words):
            return category
    return "general"


def get_nutrition_tip_with_source(goal: str) -> tuple[str, str]:
    """Return (tip, source) where source is 'gemini-flash' or 'fallback'."""
    try:
        return generate_nutrition_tip_with_flash(goal), "gemini-flash"
    except GeminiError as exc:
        logger.warning("Using fallback nutrition tip: %s", exc)
        return FALLBACK_TIPS[categorize_goal(goal)], "fallback"


def get_nutrition_tip(goal: str) -> str:
    return get_nutrition_tip_with_source(goal)[0]
