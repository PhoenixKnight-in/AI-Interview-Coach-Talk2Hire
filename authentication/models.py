from uuid import UUID, uuid4
from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import EmailStr, Field, BaseModel
from beanie import Document, Indexed, PydanticObjectId
from fastapi_users.db import BeanieBaseUser
from fastapi_users import schemas 
from bson import ObjectId


# -------------------------
# User Models
# -------------------------
class UserDB(BeanieBaseUser, Document):
    full_name: Optional[str] = None
    google_id: Optional[str] = Field(None, unique=True)
    avatar_url: Optional[str] = None
    role: str = "interviewee" 
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"
        indexes = [
            [("email", 1)],
            [("google_id", 1)],
        ]
        email_collation = None


# -------------------------
# User Session Model
# -------------------------
class UserSession(Document):
    id: PydanticObjectId = Field(default_factory=PydanticObjectId, alias="_id")
    user_id: PydanticObjectId
    session_name: str
    session_type: str
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None

    class Settings:
        name = "user_sessions"
        indexes = [
            [("user_id", 1)],
            [("created_at", -1)],
        ]


# -------------------------
# Media Files Model
# -------------------------
class MediaFile(Document):
    id: PydanticObjectId = Field(default_factory=PydanticObjectId, alias="_id")
    user_id: PydanticObjectId
    session_id: Optional[PydanticObjectId] = None
    file_type: str
    file_path: str
    file_size: Optional[int] = None
    duration: Optional[int] = None
    mime_type: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processing_status: str = "pending"
    ai_analysis: Optional[Dict[str, Any]] = None

    class Settings:
        name = "media_files"
        indexes = [
            [("user_id", 1)],
            [("session_id", 1)],
            [("created_at", -1)],
        ]


# -------------------------
# LLM Conversations Model
# -------------------------
class LLMConversation(Document):
    id: PydanticObjectId = Field(default_factory=PydanticObjectId, alias="_id")
    user_id: PydanticObjectId
    session_id: Optional[PydanticObjectId] = None
    conversation_type: str

    user_message: Optional[str] = None
    llm_response: Optional[str] = None
    llm_model: Optional[str] = None

    context_data: Optional[Dict[str, Any]] = None
    response_metadata: Optional[Dict[str, Any]] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "llm_conversations"
        indexes = [
            [("user_id", 1)],
            [("session_id", 1)],
            [("created_at", -1)],
        ]


# -------------------------
# User Preferences Model
# -------------------------
class UserPreferences(Document):
    id: PydanticObjectId = Field(default_factory=PydanticObjectId, alias="_id")
    user_id: PydanticObjectId
    preferred_duration: int = 30
    difficulty_level: str = "medium"
    interview_types: List[str] = ["technical", "behavioral"]
    email_notifications: bool = True
    reminder_notifications: bool = True
    data_retention_days: int = 30
    allow_data_analysis: bool = True
    preferences_data: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "user_preferences"
        indexes = [
            [("user_id", 1)],
        ]


# -------------------------
# Pydantic Schemas - Fixed for MongoDB ObjectId compatibility
# -------------------------

# Custom UserRead schema that doesn't inherit from FastAPI-Users base
class UserRead(BaseModel):
    id: str  # Convert ObjectId to string for API responses
    email: EmailStr
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str = "interviewee"
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserCreate(schemas.BaseUserCreate):
    full_name: Optional[str] = None
    role: str = "interviewee"

class UserUpdate(schemas.BaseUserUpdate):
    full_name: Optional[str] = None
    role: Optional[str] = None

# Internal schemas for API responses (using PydanticObjectId)
class SessionCreate(BaseModel):
    session_name: str
    session_type: str
    metadata: Optional[Dict[str, Any]] = None

class SessionRead(BaseModel):
    id: PydanticObjectId
    user_id: PydanticObjectId
    session_name: str
    session_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]]

class MediaFileRead(BaseModel):
    id: PydanticObjectId
    user_id: PydanticObjectId
    session_id: Optional[PydanticObjectId]
    file_type: str
    file_path: str
    file_size: Optional[int]
    duration: Optional[int]
    mime_type: Optional[str]
    created_at: datetime
    processing_status: str
    ai_analysis: Optional[Dict[str, Any]]