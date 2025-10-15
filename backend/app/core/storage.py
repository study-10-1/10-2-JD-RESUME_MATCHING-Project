"""
File Storage Utilities (Local filesystem for now, S3 later)
"""
import os
import uuid
from pathlib import Path
from typing import Optional
import aiofiles
from fastapi import UploadFile

from app.core.config import settings


class StorageService:
    """File storage service"""
    
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    async def save_file(self, file: UploadFile, subfolder: str = "") -> dict:
        """
        Save uploaded file to local storage
        
        Returns:
            dict with file_name, file_path, file_url, file_size
        """
        # Generate unique filename
        file_ext = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        
        # Create subfolder if specified
        save_dir = self.upload_dir / subfolder
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = save_dir / unique_filename
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        return {
            "file_name": file.filename,
            "stored_name": unique_filename,
            "file_path": str(file_path),
            "file_url": f"/uploads/{subfolder}/{unique_filename}" if subfolder else f"/uploads/{unique_filename}",
            "file_size": file_size,
        }
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file from storage"""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                return True
            return False
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False
    
    def get_file_path(self, filename: str, subfolder: str = "") -> Optional[Path]:
        """Get full path to file"""
        if subfolder:
            file_path = self.upload_dir / subfolder / filename
        else:
            file_path = self.upload_dir / filename
        
        if file_path.exists():
            return file_path
        return None


# Global storage instance
storage = StorageService()

