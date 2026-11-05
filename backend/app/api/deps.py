from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.security import AuthUser, get_auth_user
from app.db.session import get_db
from app.models import User
from app.services.users import get_or_create_user


def get_current_user(
    auth: AuthUser = Depends(get_auth_user), db: Session = Depends(get_db)
) -> User:
    """The only source of user identity: the verified JWT, never a client-supplied id."""
    return get_or_create_user(db, auth)
