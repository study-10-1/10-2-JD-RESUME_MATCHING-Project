"""
Validators
"""
from typing import List


def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
    """Validate file extension"""
    return any(filename.lower().endswith(f".{ext}") for ext in allowed_extensions)


def validate_file_size(file_size: int, max_size: int) -> bool:
    """Validate file size"""
    return file_size <= max_size

