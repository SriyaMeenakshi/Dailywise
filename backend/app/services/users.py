from sqlalchemy.orm import Session

from app.core.security import AuthUser
from app.models import Category, User

DEFAULT_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("Academic", "#4F6D8F"),
    ("Work", "#8A6F4D"),
    ("Projects", "#5E7F6B"),
    ("Personal", "#9B6B6B"),
    ("Hobbies", "#8B7AA8"),
    ("Content creation", "#B0813F"),
    ("Health and fitness", "#6C9A8B"),
    ("Learning", "#5B7DB1"),
    ("Other", "#7A7A72"),
)


def get_or_create_user(db: Session, auth: AuthUser) -> User:
    """Create the app profile (and default categories) the first time a verified user appears."""
    user = db.get(User, auth.id)
    if user is not None:
        return user
    user = User(id=auth.id, email=auth.email, display_name=auth.display_name)
    user.categories = [
        Category(name=name, color=color, sort_order=i)
        for i, (name, color) in enumerate(DEFAULT_CATEGORIES)
    ]
    db.add(user)
    db.commit()
    return user
