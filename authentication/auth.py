import os
import uuid
from typing import Optional
from fastapi import Depends, Request, HTTPException
from fastapi_users import FastAPIUsers, BaseUserManager, UUIDIDMixin
from fastapi_users.db import BeanieUserDatabase
from fastapi_users.authentication.strategy.jwt import JWTStrategy
from fastapi_users.authentication import AuthenticationBackend, BearerTransport
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from models import UserDB, UserCreate, UserUpdate, UserRead, UserPreferences
from beanie import PydanticObjectId
from datetime import datetime

load_dotenv()

SECRET = os.getenv("SECRET")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID") 
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Google OAuth Setup
oauth = OAuth()
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name='google',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid_configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

async def get_user_db():
    yield BeanieUserDatabase(UserDB)


class UserManager(UUIDIDMixin, BaseUserManager[UserDB, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: UserDB, request: Optional[Request] = None):
        """Called after user registration"""
        try:
            await self.create_user_preferences(user.id)
            print(f"User {user.id} has registered.")
        except Exception as e:
            print(f"Error creating user preferences: {e}")
            # Don't raise the exception to avoid breaking registration

    async def on_after_forgot_password(
        self, user: UserDB, token: str, request: Optional[Request] = None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def create_user_preferences(self, user_id: uuid.UUID):
        """
        Create default preferences for a new user.
        Convert UUID → PydanticObjectId for MongoDB
        """
        try:
            # Check if preferences already exist
            existing_preferences = await UserPreferences.find_one(
                UserPreferences.user_id == PydanticObjectId(str(user_id))
            )
            
            if not existing_preferences:
                preferences = UserPreferences(
                    user_id=PydanticObjectId(str(user_id)),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                await preferences.insert()
                print(f"Created preferences for user {user_id}")
        except Exception as e:
            print(f"Failed to create user preferences: {e}")
            raise e

    async def oauth_callback(
        self,
        oauth_name: str,
        access_token: str,
        account_id: str,
        account_email: str,
        **kwargs
    ):
        if oauth_name == "google":
            # Check if user exists by Google ID
            user = await UserDB.find_one(UserDB.google_id == account_id)
            if user:
                return user

            # Check if user exists by email
            user = await UserDB.find_one(UserDB.email == account_email)
            if user:
                user.google_id = account_id
                user.avatar_url = kwargs.get("picture")
                user.full_name = kwargs.get("name")
                user.updated_at = datetime.utcnow()
                await user.save()
                return user

            # Create new user
            user = UserDB(
                email=account_email,
                google_id=account_id,
                full_name=kwargs.get("name"),
                avatar_url=kwargs.get("picture"),
                is_verified=True,
                hashed_password="",  # No password for OAuth users
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            await user.insert()
            await self.create_user_preferences(user.id)
            return user


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[UserDB, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)