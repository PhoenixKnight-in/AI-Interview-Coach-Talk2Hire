from datetime import datetime
from typing import List, Optional
from uuid import UUID
from models import UserDB, UserSession, MediaFile, LLMConversation, UserPreferences
from beanie import PydanticObjectId

class UserService:
    @staticmethod
    async def get_user_sessions(user_id: PydanticObjectId) -> List[UserSession]:
        """Get all sessions for a specific user"""
        return await UserSession.find(UserSession.user_id == user_id).to_list()
    
    @staticmethod
    async def get_user_media_files(user_id: PydanticObjectId, session_id: Optional[PydanticObjectId] = None) -> List[MediaFile]:
        """Get media files for user, optionally filtered by session"""
        if session_id:
            return await MediaFile.find(
                MediaFile.user_id == user_id,
                MediaFile.session_id == session_id
            ).to_list()
        else:
            return await MediaFile.find(MediaFile.user_id == user_id).to_list()
    
    @staticmethod
    async def create_user_session(user_id: PydanticObjectId, session_data: dict) -> UserSession:
        """Create a new session for user"""
        session = UserSession(
            user_id=user_id,
            session_name=session_data.get('session_name'),
            session_type=session_data.get('session_type'),
            metadata=session_data.get('metadata')
        )
        
        await session.insert()
        return session
    
    @staticmethod
    async def get_session_by_id(session_id: PydanticObjectId) -> Optional[UserSession]:
        """Get session by ID"""
        return await UserSession.get(session_id)
    
    @staticmethod
    async def user_owns_resource(user_id: PydanticObjectId, resource_id: PydanticObjectId, resource_type: str) -> bool:
        """Check if user owns a specific resource"""
        if resource_type == 'session':
            resource = await UserSession.find_one(
                UserSession.id == resource_id,
                UserSession.user_id == user_id
            )
        elif resource_type == 'media':
            resource = await MediaFile.find_one(
                MediaFile.id == resource_id,
                MediaFile.user_id == user_id
            )
        elif resource_type == 'conversation':
            resource = await LLMConversation.find_one(
                LLMConversation.id == resource_id,
                LLMConversation.user_id == user_id
            )
        else:
            return False
        
        return resource is not None
    
    @staticmethod
    async def get_user_preferences(user_id: PydanticObjectId) -> Optional[UserPreferences]:
        """Get user preferences"""
        preferences = await UserPreferences.find_one(UserPreferences.user_id == user_id)
        if not preferences:
            # Create default preferences if none exist
            preferences = UserPreferences(user_id=user_id)
            await preferences.insert()
        return preferences
    
    @staticmethod
    async def update_user_preferences(user_id: PydanticObjectId, preferences_data: dict) -> UserPreferences:
        """Update user preferences"""
        preferences = await UserPreferences.find_one(UserPreferences.user_id == user_id)
        if not preferences:
            preferences = UserPreferences(user_id=user_id, **preferences_data)
            await preferences.insert()
        else:
            for key, value in preferences_data.items():
                if hasattr(preferences, key):
                    setattr(preferences, key, value)
            preferences.updated_at = datetime.utcnow()
            await preferences.save()
        
        return preferences