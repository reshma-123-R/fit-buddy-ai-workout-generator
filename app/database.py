"""SQLAlchemy models and small data-access helpers (SQLite by default)."""
from sqlalchemy import Float, ForeignKey, Integer, String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from . import config

_is_sqlite = config.DATABASE_URL.startswith("sqlite")
engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},  # FastAPI uses a thread pool
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)  # chosen by the user
    name: Mapped[str] = mapped_column(String(100))
    age: Mapped[int] = mapped_column(Integer)
    weight: Mapped[float] = mapped_column(Float)
    goal: Mapped[str] = mapped_column(String(200))
    intensity: Mapped[str] = mapped_column(String(20))
    schedule: Mapped[int] = mapped_column(Integer, default=7)  # days per plan


class WorkoutPlan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    original_plan: Mapped[str] = mapped_column(Text)
    updated_plan: Mapped[str | None] = mapped_column(Text, nullable=True)


def init_db() -> None:
    """Create the tables if they do not exist yet (called on app startup)."""
    Base.metadata.create_all(bind=engine)


def _latest_plan(db, user_id: int) -> WorkoutPlan | None:
    return db.scalars(
        select(WorkoutPlan).where(WorkoutPlan.user_id == user_id).order_by(WorkoutPlan.id.desc())
    ).first()


def save_user(user_id: int, name: str, age: int, weight: float, goal: str, intensity: str) -> None:
    """Create the user, or update their details if this user_id already exists."""
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user:
            user.name, user.age, user.weight = name, age, weight
            user.goal, user.intensity = goal, intensity
        else:
            db.add(User(id=user_id, name=name, age=age, weight=weight,
                        goal=goal, intensity=intensity, schedule=7))
        db.commit()


def save_plan(user_id: int, plan: str) -> None:
    """Store the generated plan. A user keeps one plan: regenerating replaces it and clears any update."""
    with SessionLocal() as db:
        existing = _latest_plan(db, user_id)
        if existing:
            existing.original_plan = plan
            existing.updated_plan = None
        else:
            db.add(WorkoutPlan(user_id=user_id, original_plan=plan))
        db.commit()


def update_plan(user_id: int, updated_text: str) -> bool:
    """Save the feedback-based revision. Returns False if the user has no plan."""
    with SessionLocal() as db:
        workout = _latest_plan(db, user_id)
        if not workout:
            return False
        workout.updated_plan = updated_text
        db.commit()
        return True


def get_original_plan(user_id: int) -> str | None:
    with SessionLocal() as db:
        plan = _latest_plan(db, user_id)
        return plan.original_plan if plan else None


def get_current_plan(user_id: int) -> str | None:
    """The plan to show/revise: the latest updated version if there is one, else the original."""
    with SessionLocal() as db:
        plan = _latest_plan(db, user_id)
        if not plan:
            return None
        return plan.updated_plan or plan.original_plan


def get_user(user_id: int) -> User | None:
    with SessionLocal() as db:
        return db.get(User, user_id)


def get_all_users_with_plans() -> list[dict]:
    """Everything the admin page needs, in one query."""
    with SessionLocal() as db:
        rows = db.execute(
            select(User, WorkoutPlan)
            .outerjoin(WorkoutPlan, WorkoutPlan.user_id == User.id)
            .order_by(User.id)
        ).all()
        return [
            {
                "id": user.id,
                "name": user.name,
                "age": user.age,
                "weight": user.weight,
                "goal": user.goal,
                "intensity": user.intensity,
                "original_plan": plan.original_plan if plan else "N/A",
                "updated_plan": plan.updated_plan if plan and plan.updated_plan else "Not updated",
            }
            for user, plan in rows
        ]


def delete_user(user_id: int) -> bool:
    """Delete a user and all of their plans. Returns False if the user does not exist."""
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return False
        db.execute(delete(WorkoutPlan).where(WorkoutPlan.user_id == user_id))
        db.delete(user)
        db.commit()
        return True