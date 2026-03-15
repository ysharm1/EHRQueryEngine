from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List
from app.models.user import User, UserRole
from app.services.auth import AuthService
from app.database import get_db

security = HTTPBearer()


class RBACService:
    """Role-Based Access Control service."""
    
    @staticmethod
    def verify_role(user: User, allowed_roles: List[UserRole]) -> bool:
        """
        Verify if user has one of the allowed roles.
        
        Args:
            user: User object
            allowed_roles: List of allowed roles
        
        Returns:
            True if user has allowed role, False otherwise
        """
        return user.role in allowed_roles
    
    @staticmethod
    def require_roles(allowed_roles: List[UserRole]):
        """
        Dependency to require specific roles for an endpoint.
        
        Args:
            allowed_roles: List of roles allowed to access the endpoint
        
        Returns:
            Dependency function
        """
        async def role_checker(
            credentials: HTTPAuthorizationCredentials = Depends(security),
            db: Session = Depends(get_db)
        ) -> User:
            # Decode token
            token = credentials.credentials
            payload = AuthService.decode_token(token)
            
            if payload is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            user_id: str = payload.get("sub")
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Get user from database
            user = AuthService.get_user_by_id(db, user_id)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Check role
            if not RBACService.verify_role(user, allowed_roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required roles: {[r.value for r in allowed_roles]}",
                )
            
            return user
        
        return role_checker


# Common role dependencies
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user (any role)."""
    token = credentials.credentials
    payload = AuthService.decode_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = AuthService.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


# Role-specific dependencies
def require_admin(user: User = Depends(RBACService.require_roles([UserRole.ADMIN]))) -> User:
    """Require Admin role."""
    return user


def require_researcher(
    user: User = Depends(RBACService.require_roles([UserRole.ADMIN, UserRole.RESEARCHER]))
) -> User:
    """Require Admin or Researcher role."""
    return user


def require_analyst(
    user: User = Depends(RBACService.require_roles([UserRole.ADMIN, UserRole.RESEARCHER, UserRole.DATA_ANALYST]))
) -> User:
    """Require Admin, Researcher, or Data Analyst role."""
    return user
