"""
User Schemas
"""
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID


# Base schemas
class UserBase(BaseModel):
    email: EmailStr
    name: str
    phone: Optional[str] = None


class UserCreate(UserBase):
    """User creation schema"""
    password: str


class UserUpdate(BaseModel):
    """User update schema"""
    name: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    preferences: Optional[dict] = None


class UserInDB(UserBase):
    """User in database schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    role: str
    is_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserResponse(UserBase):
    """User response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    role: str
    is_verified: bool
    created_at: datetime


# Auth schemas
class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr
    password: str


class RegisterRequest(UserCreate):
    """Register request schema"""
    pass

