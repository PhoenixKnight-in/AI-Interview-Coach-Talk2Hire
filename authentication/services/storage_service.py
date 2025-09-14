import os
import uuid
from typing import Optional
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile
from dotenv import load_dotenv

load_dotenv()

class StorageService:
    def __init__(self):
        self.storage_type = os.getenv("STORAGE_TYPE", "local")
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE", 100 * 1024 * 1024))  # 100MB
        self.allowed_extensions = ['.mp4', '.mov', '.avi', '.mp3', '.wav', '.m4a', '.webm']
        
        if self.storage_type == 's3':
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
            )
            self.bucket_name = os.getenv("AWS_BUCKET_NAME")
    
    def validate_file(self, file: UploadFile) -> bool:
        """Validate file type and size"""
        if not any(file.filename.lower().endswith(ext) for ext in self.allowed_extensions):
            return False
        return True
    
    async def save_file(self, file: UploadFile, user_id: str, session_id: Optional[str] = None) -> dict:
        """Save file and return metadata"""
        if not self.validate_file(file):
            raise ValueError("Invalid file type")
        
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        
        # Generate file path
        if session_id:
            file_path = f"users/{user_id}/sessions/{session_id}/{file_id}{file_extension}"
        else:
            file_path = f"users/{user_id}/uploads/{file_id}{file_extension}"
        
        if self.storage_type == 'local':
            return await self._save_local(file, file_path)
        elif self.storage_type == 's3':
            return await self._save_s3(file, file_path)
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
    
    async def _save_local(self, file: UploadFile, file_path: str) -> dict:
        """Save file locally"""
        full_path = Path("storage") / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        content = await file.read()
        
        # Check file size
        if len(content) > self.max_file_size:
            raise ValueError(f"File too large. Max size: {self.max_file_size} bytes")
        
        with open(full_path, "wb") as f:
            f.write(content)
        
        return {
            'file_path': str(full_path),
            'file_size': len(content),
            'mime_type': file.content_type
        }
    
    async def _save_s3(self, file: UploadFile, file_path: str) -> dict:
        """Save file to S3"""
        try:
            content = await file.read()
            
            # Check file size
            if len(content) > self.max_file_size:
                raise ValueError(f"File too large. Max size: {self.max_file_size} bytes")
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=file.content_type
            )
            
            return {
                'file_path': file_path,
                'file_size': len(content),
                'mime_type': file.content_type
            }
        except ClientError as e:
            raise Exception(f"Failed to upload to S3: {e}")
    
    async def get_file_url(self, file_path: str) -> str:
        """Get file URL for access"""
        if self.storage_type == 'local':
            return f"/files/{file_path}"
        elif self.storage_type == 's3':
            return f"https://{self.bucket_name}.s3.amazonaws.com/{file_path}"
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file from storage"""
        if self.storage_type == 'local':
            try:
                os.remove(file_path)
                return True
            except OSError:
                return False
        elif self.storage_type == 's3':
            try:
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=file_path
                )
                return True
            except ClientError:
                return False