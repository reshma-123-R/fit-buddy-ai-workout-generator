"""End-to-end tests for FitBuddy. Gemini is faked, so they run offline and instantly."""
from conftest import api_error

FORM = {"username": "Asha", "user_id": "7", "age": "22", "weight": "55.5",
        "goal": "muscle gain", "intensity": "High"}
API_USER = {"user_id": 7, "username": "Asha", "age": 22, "weight": 55.5,
            "goal": "muscle gain", "intensity": "High"}


# ---------------------------------------------------------------- pages & static
def test_home_page_renders_form(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "FitBuddy - AI Workout Generator" in r.text
    for field in ("username", "user_id", "age", "weight", "goal", "intensity"):
        assert f'name="{field}"' in r.text


def test_static_files_are_served(client):
    assert client.get("/static/css/style.css").status_code == 200
    img = client.get("/static/images/gym-bg.jpg")
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_admin_page_empty(client):
    r = client.get("/view-all-users")
    assert r.status_code == 200 and "No users yet" in r.text


# ---------------------------------------------------------------- JSON API
def test_generate_workout_api(client, gemini):
    r = client.post("/generate-workout/gemini", json={"goal": "weight loss", "intensity": "low"})
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "gemini-pro"
    assert body["workout_plan"] == "Day 1: Warm-up ... (test-pro)"
    prompt = gemini.prompts_for("test-pro")[0]
    assert "weight loss" in prompt and "Low intensity" in prompt      # intensity normalised


def test_generate_workout_validation(client, gemini):
    assert client.post("/generate-workout/gemini", json={"goal": "x", "intensity": "Low"}).status_code == 422
    assert client.post("/generate-workout/gemini", json={"goal": "fitness", "intensity": "extreme"}).status_code == 422
    assert gemini.calls == []                                          # never reached Gemini


def test_nutrition_tip_api(client, gemini):
    r = client.get("/nutrition-tip", params={"goal": "weight loss"})
    assert r.status_code == 200
    assert r.json() == {"goal": "weight loss", "nutrition_tip": "Eat more protein. (test-flash)",
                        "source": "gemini-flash"}


def test_nutrition_tip_falls_back_when_gemini_fails(client, gemini):
    def boom(model, prompt):
        raise api_error(429, "quota")
    gemini.handler = boom
    r = client.get("/nutrition-tip", params={"goal": "i want to lose belly fat"})
    assert r.status_code == 200
    assert r.json()["source"] == "fallback"
    assert "protein" in r.json()["nutrition_tip"].lower()


def test_generate_plan_saves_user_and_plan(client, gemini):
    r = client.post("/generate-plan", json=API_USER)
    assert r.status_code == 200
    assert r.json()["message"] == "Workout plan generated and saved successfully!"
    prompt = gemini.prompts_for("test-pro")[0]
    assert "Age: 22" in prompt and "55.5 kg" in prompt                 # profile reaches the prompt

    page = client.get("/view-all-users").text
    assert "Asha" in page and "muscle gain" in page and "Day 1: Warm-up" in page
    assert "Not updated" in page


def test_update_plan_api(client, gemini):
    client.post("/generate-plan", json=API_USER)
    r = client.post("/update-plan/7", json={"feedback": "More core exercises please"})
    assert r.status_code == 200 and r.json() == {"updated_plan": "UPDATED PLAN (test-pro)"}
    assert "UPDATED PLAN" in client.get("/view-all-users").text
    assert "Day 1: Warm-up" in gemini.prompts_for("test-pro")[-1]      # original plan was sent for revision


def test_second_feedback_builds_on_the_first_update(client, gemini):
    client.post("/generate-plan", json=API_USER)
    client.post("/update-plan/7", json={"feedback": "first change"})
    client.post("/update-plan/7", json={"feedback": "second change"})
    assert "UPDATED PLAN (test-pro)" in gemini.prompts_for("test-pro")[-1]


def test_update_plan_unknown_user_is_404(client, gemini):
    r = client.post("/update-plan/999", json={"feedback": "anything"})
    assert r.status_code == 404
    assert gemini.calls == []


def test_regenerating_replaces_plan_and_clears_update(client, gemini):
    client.post("/generate-plan", json=API_USER)
    client.post("/update-plan/7", json={"feedback": "make it easier"})
    client.post("/generate-plan", json={**API_USER, "goal": "flexibility"})
    page = client.get("/view-all-users").text
    assert "flexibility" in page and "Not updated" in page
    assert page.count("<tr>") == 2                                     # header + exactly one user row


# ---------------------------------------------------------------- web flow
def test_web_form_flow_end_to_end(client, gemini):
    r = client.post("/generate", data=FORM)
    assert r.status_code == 200
    assert "Your Personalized Workout Plan" in r.text
    assert "Asha" in r.text and "55.5 kg" in r.text and "High" in r.text
    assert "Day 1: Warm-up" in r.text
    assert "Eat more protein." in r.text

    r2 = client.post("/submit-feedback",
                     data={"user_id": "7", "feedback": "Too hard on day 3", "nutrition_tip": "Eat more protein."})
    assert r2.status_code == 200
    assert "Your plan has been updated based on your feedback!" in r2.text
    assert "UPDATED PLAN" in r2.text and "Updated Workout Plan" in r2.text
    assert "Eat more protein." in r2.text                              # tip carried over, no extra Gemini call
    assert len(gemini.prompts_for("test-flash")) == 1


def test_web_form_validation_error_keeps_input(client, gemini):
    r = client.post("/generate", data={**FORM, "age": "abc"})
    assert r.status_code == 422
    assert "Age:" in r.text and 'value="Asha"' in r.text
    assert gemini.calls == []


def test_web_html_is_escaped(client, gemini):
    client.post("/generate", data={**FORM, "username": "<script>alert(1)</script>"})
    page = client.get("/view-all-users").text
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page


def test_web_feedback_unknown_user(client, gemini):
    r = client.post("/submit-feedback", data={"user_id": "404", "feedback": "hello there"})
    assert r.status_code == 404 and "No plan found for User ID 404" in r.text


def test_web_feedback_bad_id(client, gemini):
    r = client.post("/submit-feedback", data={"user_id": "abc", "feedback": "hello there"})
    assert r.status_code == 422 and "numeric User ID" in r.text


def test_web_feedback_too_short_keeps_plan_visible(client, gemini):
    client.post("/generate", data=FORM)
    r = client.post("/submit-feedback", data={"user_id": "7", "feedback": "x"})
    assert r.status_code == 422 and "Feedback:" in r.text and "Day 1: Warm-up" in r.text


# ---------------------------------------------------------------- Gemini failure handling
def test_api_returns_500_with_friendly_message_when_gemini_fails(client, gemini):
    def boom(model, prompt):
        raise api_error(403, "denied")
    gemini.handler = boom
    r = client.post("/generate-plan", json=API_USER)
    assert r.status_code == 500 and "HTTP 403" in r.json()["detail"]
    assert "Asha" not in client.get("/view-all-users").text            # nothing half-saved


def test_web_shows_error_banner_and_saves_nothing(client, gemini):
    def boom(model, prompt):
        raise api_error(401, "bad key")
    gemini.handler = boom
    r = client.post("/generate", data=FORM)
    assert r.status_code == 502 and "rejected the API key" in r.text
    assert 'value="Asha"' in r.text
    assert "No users yet" in client.get("/view-all-users").text
    assert len(gemini.calls) == 1                                      # key errors do not trigger the fallback


def test_web_feedback_gemini_error_keeps_current_plan(client, gemini):
    client.post("/generate", data=FORM)

    def boom(model, prompt):
        raise api_error(429, "quota")
    gemini.handler = boom
    r = client.post("/submit-feedback", data={"user_id": "7", "feedback": "make it easier"})
    assert r.status_code == 502 and "quota" in r.text and "Day 1: Warm-up" in r.text


def test_pro_model_failure_falls_back_to_flash(client, gemini):
    def handler(model, prompt):
        if model == "test-pro":
            raise api_error(404, "model not found")
        return "FLASH PLAN"
    gemini.handler = handler
    r = client.post("/generate-workout/gemini", json={"goal": "fitness", "intensity": "Medium"})
    assert r.status_code == 200 and r.json()["workout_plan"] == "FLASH PLAN"
    assert [m for m, _ in gemini.calls] == ["test-pro", "test-flash"]


def test_both_models_failing_reports_both(client, gemini):
    def boom(model, prompt):
        raise api_error(404, "gone")
    gemini.handler = boom
    r = client.post("/generate-workout/gemini", json={"goal": "fitness", "intensity": "Medium"})
    assert r.status_code == 500
    assert "test-pro" in r.json()["detail"] and "Fallback model 'test-flash'" in r.json()["detail"]


def test_empty_response_is_an_error_not_an_empty_plan(client, gemini):
    gemini.handler = lambda model, prompt: "   "
    r = client.post("/generate-workout/gemini", json={"goal": "fitness", "intensity": "Medium"})
    assert r.status_code == 500 and "empty response" in r.json()["detail"]


def test_missing_api_key_gives_setup_hint(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "your_api_key_here")          # the .env.example placeholder
    r = client.post("/generate", data=FORM)
    assert r.status_code == 502 and "GEMINI_API_KEY is not set" in r.text
