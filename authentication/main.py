from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import List, Optional
from uuid import UUID
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
load_dotenv()

from db import init_db
from auth import fastapi_users, auth_backend, current_active_user, oauth, get_user_manager
from models import (
    UserCreate, UserRead, UserUpdate, UserDB,
    SessionCreate, SessionRead, MediaFileRead, MediaFile 
)
from services.storage_service import StorageService
from services.user_service import UserService
from beanie import PydanticObjectId

# Lifespan event handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown (if you need any cleanup)
    pass

app = FastAPI(
    title="Interview AI Platform", 
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for local storage
if not os.path.exists("storage"):
    os.makedirs("storage")
app.mount("/files", StaticFiles(directory="storage"), name="files")

# Initialize services
storage_service = StorageService()

# Auth routes - ONLY include JWT auth route, not the register/users routes
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)

# Custom auth routes that handle ObjectId properly
@app.post("/auth/register", response_model=UserRead, tags=["auth"])
async def register(user_create: UserCreate, user_manager=Depends(get_user_manager)):
    """Custom registration endpoint that properly handles ObjectId conversion"""
    try:
        user = await user_manager.create(user_create)
        # Convert to dict and handle ObjectId conversion
        user_dict = user.dict()
        user_dict['id'] = str(user.id)  # Convert ObjectId to string
        return UserRead(**user_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/users/me", response_model=UserRead, tags=["users"])
async def get_current_user(current_user: UserDB = Depends(current_active_user)):
    """Get current user with proper ObjectId conversion"""
    user_dict = current_user.dict()
    user_dict['id'] = str(current_user.id)
    return UserRead(**user_dict)

@app.patch("/users/me", response_model=UserRead, tags=["users"])
async def update_current_user(
    user_update: UserUpdate, 
    current_user: UserDB = Depends(current_active_user),
    user_manager=Depends(get_user_manager)
):
    """Update current user with proper ObjectId conversion"""
    try:
        user = await user_manager.update(user_update, current_user)
        user_dict = user.dict()
        user_dict['id'] = str(user.id)
        return UserRead(**user_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Google OAuth routes
@app.get("/auth/google")
async def google_login(request: Request):
    redirect_uri = str(request.url_for('google_callback'))
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/google/callback")
async def google_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')

        if user_info:
            user_manager = await anext(get_user_manager())
            user = await user_manager.oauth_callback(
                "google",
                token.get('access_token'),
                user_info.get('sub'),
                user_info.get('email'),
                name=user_info.get('name'),
                picture=user_info.get('picture')
            )
            # Convert ObjectId to string for response
            return {
                "message": "Google authentication successful", 
                "user_id": str(user.id)
            }

        raise HTTPException(status_code=400, detail="Google authentication failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Session Management
@app.post("/sessions", response_model=SessionRead)
async def create_session(
    session_data: SessionCreate,
    current_user: UserDB = Depends(current_active_user)
):
    session = await UserService.create_user_session(PydanticObjectId(str(current_user.id)), session_data.dict())
    return session

@app.get("/sessions", response_model=List[SessionRead])
async def get_user_sessions(current_user: UserDB = Depends(current_active_user)):
    return await UserService.get_user_sessions(PydanticObjectId(str(current_user.id)))

@app.get("/sessions/{session_id}", response_model=SessionRead)
async def get_session(session_id: PydanticObjectId, current_user: UserDB = Depends(current_active_user)):
    if not await UserService.user_owns_resource(PydanticObjectId(str(current_user.id)), session_id, 'session'):
        raise HTTPException(status_code=404, detail="Session not found")
    return await UserService.get_session_by_id(session_id)

# File Upload and Management
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    current_user: UserDB = Depends(current_active_user)
):
    try:
        if not storage_service.validate_file(file):
            raise HTTPException(status_code=400, detail="Invalid file type")

        file_metadata = await storage_service.save_file(file, str(current_user.id), session_id)

        media_file = MediaFile(
            user_id=PydanticObjectId(str(current_user.id)),
            session_id=PydanticObjectId(session_id) if session_id else None,
            file_type='video' if file.content_type.startswith('video') else 'audio',
            file_path=file_metadata['file_path'],
            file_size=file_metadata['file_size'],
            mime_type=file_metadata['mime_type']
        )
        await media_file.insert()

        return {
            "file_id": str(media_file.id),
            "message": "File uploaded successfully",
            "file_path": file_metadata['file_path']
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/files", response_model=List[MediaFileRead])
async def get_user_files(
    session_id: Optional[PydanticObjectId] = None,
    current_user: UserDB = Depends(current_active_user)
):
    return await UserService.get_user_media_files(PydanticObjectId(str(current_user.id)), session_id)

@app.get("/files/{file_id}")
async def get_file(file_id: PydanticObjectId, current_user: UserDB = Depends(current_active_user)):
    if not await UserService.user_owns_resource(PydanticObjectId(str(current_user.id)), file_id, 'media'):
        raise HTTPException(status_code=404, detail="File not found")

    media_file = await MediaFile.get(file_id)
    file_url = await storage_service.get_file_url(media_file.file_path)

    return {
        "file_id": str(media_file.id),
        "file_url": file_url,
        "file_type": media_file.file_type,
        "file_size": media_file.file_size,
        "created_at": media_file.created_at
    }

@app.delete("/files/{file_id}")
async def delete_file(file_id: PydanticObjectId, current_user: UserDB = Depends(current_active_user)):
    if not await UserService.user_owns_resource(PydanticObjectId(str(current_user.id)), file_id, 'media'):
        raise HTTPException(status_code=404, detail="File not found")

    media_file = await MediaFile.get(file_id)
    await storage_service.delete_file(media_file.file_path)
    await media_file.delete()

    return {"message": "File deleted successfully"}

# User Preferences
@app.get("/preferences")
async def get_user_preferences(current_user: UserDB = Depends(current_active_user)):
    return await UserService.get_user_preferences(PydanticObjectId(str(current_user.id)))

@app.put("/preferences")
async def update_user_preferences(preferences_data: dict, current_user: UserDB = Depends(current_active_user)):
    return await UserService.update_user_preferences(PydanticObjectId(str(current_user.id)), preferences_data)

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)