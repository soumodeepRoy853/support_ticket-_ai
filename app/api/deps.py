from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole

oauth2_schema = OAuth2PasswordBearer(tokenUri="/api/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_schema),
    db: AsyncSession = Depends(get_db),
) -> User:
        credentials_exception = HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload=decode_access_token(token)
            user_id: str = payload.get("sub")
            if user_id is None:
                raise credentials_exception
        except JWTError:
                raise credentials_exception

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise credentials_exception
        return user


def require_role(*allowed_roles: UserRole):
      async def role_checker(current_user: User = Depends(get_current_user)) -> User:
            if current_user.role not in allowed_roles:
                  raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not enough permissions",
                  )
            return current_user
      return role_checker 
        