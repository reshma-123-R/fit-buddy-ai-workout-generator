"""Pydantic models used for request validation."""
from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_INTENSITIES = ("Low", "Medium", "High")


def normalize_intensity(value: str) -> str:
    """'high', ' HIGH ' -> 'High'. Anything else is rejected."""
    cleaned = str(value).strip().title()
    if cleaned not in VALID_INTENSITIES:
        raise ValueError("Intensity must be Low, Medium or High")
    return cleaned


class _Base(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class WorkoutRequest(_Base):
    """Body of POST /generate-workout/gemini (stateless: nothing is saved)."""
    goal: str = Field(..., min_length=2, max_length=200)
    intensity: str = "Medium"

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={"example": {"goal": "weight loss", "intensity": "Medium"}},
    )

    @field_validator("intensity")
    @classmethod
    def _check_intensity(cls, value: str) -> str:
        return normalize_intensity(value)


class UserInput(_Base):
    """Body of POST /generate-plan, and the validated form of the web page."""
    user_id: int = Field(..., ge=1, le=2_000_000_000)
    username: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=10, le=100)
    weight: float = Field(..., gt=0, le=500, description="Weight in kg")
    goal: str = Field(..., min_length=2, max_length=200)
    intensity: str

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={"example": {
            "user_id": 1, "username": "Asha", "age": 22, "weight": 55.0,
            "goal": "muscle gain", "intensity": "High",
        }},
    )

    @field_validator("intensity")
    @classmethod
    def _check_intensity(cls, value: str) -> str:
        return normalize_intensity(value)


class FeedbackRequest(_Base):
    """Body of POST /update-plan/{user_id}."""
    feedback: str = Field(..., min_length=3, max_length=1000)

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={"example": {"feedback": "Please add more core exercises and make Day 3 easier."}},
    )
