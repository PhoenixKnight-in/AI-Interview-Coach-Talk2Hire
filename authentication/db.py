import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from models import (
    UserDB,
    UserSession,
    MediaFile,
    LLMConversation,
    UserPreferences,
)

# Load environment variables
load_dotenv()

# Fetch MongoDB URL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set in the environment variables.")

# MongoDB client setup
client = AsyncIOMotorClient(DATABASE_URL)

# If DATABASE_URL already includes a default DB, you can use:
# db = client.get_default_database()
# Otherwise, explicitly set your DB name like below:
db = client.get_database("interview_coach")

async def init_db():
    """
    Initializes the database and registers document models with Beanie.
    """
    await init_beanie(
        database=db,
        document_models=[
            UserDB,
            UserSession,
            MediaFile,
            LLMConversation,
            UserPreferences,
        ],
    )
