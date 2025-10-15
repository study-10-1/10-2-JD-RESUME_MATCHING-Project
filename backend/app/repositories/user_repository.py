"""
User Repository
"""
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.models.user import User


class UserRepository:
    """User data access layer"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, user: User) -> User:
        """Create user"""
        raise NotImplementedError("create not implemented")
    
    def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID"""
        raise NotImplementedError("get_by_id not implemented")
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        raise NotImplementedError("get_by_email not implemented")
    
    def update(self, user: User) -> User:
        """Update user"""
        raise NotImplementedError("update not implemented")
    
    def delete(self, user_id: UUID) -> bool:
        """Delete user"""
        raise NotImplementedError("delete not implemented")

