"""External provider interfaces and adapters."""

from app.providers.object_storage import ObjectStorage, ObjectStorageError
from app.providers.supabase_storage import SupabaseObjectStorage

__all__ = ["ObjectStorage", "ObjectStorageError", "SupabaseObjectStorage"]
