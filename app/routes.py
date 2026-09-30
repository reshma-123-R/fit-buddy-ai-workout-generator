"""All HTTP routes: JSON APIs (1-4) and HTML pages (5-8)."""
import logging

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from . import config
from .database import (
    delete_user,
    get_all_users_with_plans,
    get_current_plan,
    get_user,
    save_plan,
    save_user,
    update_plan,
)
from .gemini_client import GeminiError
from .gemini_generator import generate_workout_gemini
from .nutrition import get_nutrition_tip, get_nutrition_tip_with_source
from .schemas import FeedbackRequest, UserInput, WorkoutRequest
from .updated_plan import update_workout_plan

logger = logging.getLogger("fitbuddy.routes")

router = APIRouter()
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))

_FIELD_LABELS = {
    "username": "Name", "user_id": "User ID", "age": "Age", "weight": "Weight",
    "goal": "Fitness goal", "intensity": "Workout intensity", "feedback": "Feedback",
}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _format_validation_error(exc: ValidationError) -> str:
    messages = []
    for err in exc.errors():
        field = str(err["loc"][-1]) if err["loc"] else "input"
        message = err["msg"].removeprefix("Value error, ")
        messages.append(f"{_FIELD_LABELS.get(field, field)}: {message}")
    return "; ".join(messages)


def _render_index(request: Request, *, form: dict | None = None, error: str | None = None,
                  status_code: int = 200):
    return templates.TemplateResponse(
        request, "index.html", {"form": form or {}, "error": error}, status_code=status_code
    )


def _render_result(request: Request, info: dict, plan: str, nutrition_tip: str, *,
                   plan_title: str = "Workout Plan", success_message: str | None = None,
                   error: str | None = None, status_code: int = 200):
    context = {
        **info,                       # username, user_id, age, weight, goal, intensity
        "workout_plan": plan,
        "nutrition_tip": nutrition_tip,
        "plan_title": plan_title,
        "success_message": success_message,
        "error": error,
    }
    return templates.TemplateResponse(request, "result.html", context, status_code=status_code)


def _user_info(user) -> dict:
    return {"username": user.name, "user_id": user.id, "age": user.age,
            "weight": user.weight, "goal": user.goal, "intensity": user.intensity}


# ----------------------------------------------------------------------------
# JSON API
# Plain `def` (not `async def`) on purpose: the Gemini SDK call blocks, and FastAPI
# runs sync routes in a thread pool so one slow request cannot freeze the server.
# ----------------------------------------------------------------------------

# 1. API: Generate workout using Gemini Pro (nothing is saved)
@router.post("/generate-workout/gemini", tags=["API"])
def generate_gemini_workout(request: WorkoutRequest):
    try:
        result = generate_workout_gemini({"goal": request.goal, "intensity": request.intensity})
        return {"model": "gemini-pro", "workout_plan": result}
    except GeminiError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# 2. API: Generate nutrition tip using Gemini Flash (falls back to a built-in tip)
@router.get("/nutrition-tip", tags=["API"])
def get_flash_tip(goal: str):
    goal = goal.strip()
    if len(goal) < 2 or len(goal) > 200:
        raise HTTPException(status_code=422, detail="goal must be between 2 and 200 characters")
    tip, source = get_nutrition_tip_with_source(goal)
    return {"goal": goal, "nutrition_tip": tip, "source": source}


# 3. API: Save user info & generate plan
@router.post("/generate-plan", tags=["API"])
def generate_plan(user_data: UserInput):
    try:
        plan = generate_workout_gemini({
            "goal": user_data.goal, "intensity": user_data.intensity,
            "age": user_data.age, "weight": user_data.weight,
        })
        save_user(
            user_id=user_data.user_id, name=user_data.username, age=user_data.age,
            weight=user_data.weight, goal=user_data.goal, intensity=user_data.intensity,
        )
        save_plan(user_data.user_id, plan)
        return {"message": "Workout plan generated and saved successfully!", "workout_plan": plan}
    except GeminiError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except SQLAlchemyError as exc:
        logger.exception("Database error while saving plan")
        raise HTTPException(status_code=500, detail=f"Database error: {exc.__class__.__name__}")


# 4. API: Update workout plan based on user feedback
@router.post("/update-plan/{user_id}", response_model=dict, tags=["API"])
def update_user_plan(user_id: int, data: FeedbackRequest):
    current = get_current_plan(user_id)
    if not current:
        raise HTTPException(status_code=404, detail="Original plan not found for this user.")
    try:
        updated = update_workout_plan(current, data.feedback)
    except GeminiError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    update_plan(user_id, updated)
    return {"updated_plan": updated}


# 5. API: Delete a user and their plans
@router.delete("/users/{user_id}", tags=["API"])
def delete_user_api(user_id: int):
    if not delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found.")
    return {"message": f"User {user_id} and their plans were deleted."}


# ----------------------------------------------------------------------------
# HTML pages
# ----------------------------------------------------------------------------

# 5. Web: Home page with the input form
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request):
    return _render_index(request)


# 6. Web: Form submit -> generate plan + nutrition tip -> result page
@router.post("/generate", response_class=HTMLResponse, include_in_schema=False)
def generate_from_form(
    request: Request,
    username: str = Form(""),
    user_id: str = Form(""),
    age: str = Form(""),
    weight: str = Form(""),
    goal: str = Form(""),
    intensity: str = Form("Low"),
):
    form = {"username": username, "user_id": user_id, "age": age,
            "weight": weight, "goal": goal, "intensity": intensity}
    try:
        data = UserInput(**form)
    except ValidationError as exc:
        return _render_index(request, form=form, error=_format_validation_error(exc), status_code=422)

    try:
        plan = generate_workout_gemini({
            "goal": data.goal, "intensity": data.intensity, "age": data.age, "weight": data.weight,
        })
        save_user(user_id=data.user_id, name=data.username, age=data.age,
                  weight=data.weight, goal=data.goal, intensity=data.intensity)
        save_plan(data.user_id, plan)
    except GeminiError as exc:
        return _render_index(request, form=form, error=str(exc), status_code=502)
    except SQLAlchemyError:
        logger.exception("Database error while saving plan")
        return _render_index(request, form=form,
                             error="Could not save your plan (database error). Please try again.",
                             status_code=500)

    tip = get_nutrition_tip(data.goal)
    info = {"username": data.username, "user_id": data.user_id, "age": data.age,
            "weight": data.weight, "goal": data.goal, "intensity": data.intensity}
    return _render_result(request, info, plan, tip)


# 7. Web: Feedback form -> revise plan -> result page
@router.post("/submit-feedback", response_class=HTMLResponse, include_in_schema=False)
def submit_feedback(
    request: Request,
    user_id: str = Form(""),
    feedback: str = Form(""),
    nutrition_tip: str = Form(""),
):
    try:
        uid = int(user_id.strip())
        if uid < 1:
            raise ValueError
    except ValueError:
        return _render_index(request, error="Please enter the numeric User ID you used to generate your plan.",
                             status_code=422)

    user = get_user(uid)
    current = get_current_plan(uid)
    if not user or not current:
        return _render_index(request, error=f"No plan found for User ID {uid}. Generate a plan first.",
                             status_code=404)

    info = _user_info(user)
    tip = nutrition_tip.strip()[:600] or get_nutrition_tip(user.goal)

    try:
        fb = FeedbackRequest(feedback=feedback)
    except ValidationError as exc:
        return _render_result(request, info, current, tip, error=_format_validation_error(exc), status_code=422)

    try:
        updated = update_workout_plan(current, fb.feedback)
    except GeminiError as exc:
        return _render_result(request, info, current, tip, error=str(exc), status_code=502)

    update_plan(uid, updated)
    return _render_result(request, info, updated, tip, plan_title="Updated Workout Plan",
                          success_message="Your plan has been updated based on your feedback!")


# 8. Web: View all users & their plans (admin page - no login, keep it local!)
@router.get("/view-all-users", response_class=HTMLResponse, include_in_schema=False)
def view_all_users(request: Request):
    return templates.TemplateResponse(request, "all_users.html", {"users": get_all_users_with_plans()})


# 9. Web: Delete one user (Delete button on the admin page), then go back to the table
@router.post("/delete-user/{user_id}", include_in_schema=False)
def delete_user_web(user_id: int):
    delete_user(user_id)
    return RedirectResponse(url="/view-all-users", status_code=303)