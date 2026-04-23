"""
MongoDB database connection and helpers for VKS Legal AI
"""
import motor.motor_asyncio
from backend.config import settings


class Database:
    client: motor.motor_asyncio.AsyncIOMotorClient = None
    db = None

    @classmethod
    async def connect(cls):
        try:
            cls.client = motor.motor_asyncio.AsyncIOMotorClient(
                settings.MONGODB_URI, serverSelectionTimeoutMS=5000
            )
            cls.db = cls.client[settings.MONGODB_DB]
            await cls.db.api_keys.create_index("key_hash", unique=True)
            await cls.db.api_keys.create_index("is_active")
            await cls.db.usage_logs.create_index("timestamp")
            await cls.db.usage_logs.create_index("api_key_id")
            await cls.db.usage_logs.create_index([("api_key_id", 1), ("timestamp", -1)])
            await cls.db.conversations.create_index("user_id")
            await cls.db.conversations.create_index("updated_at")
            await cls.db.messages.create_index("conversation_id")
            await cls.db.messages.create_index([("conversation_id", 1), ("created_at", 1)])
            await cls.db.documents.create_index("status")
            await cls.client.admin.command("ping")
            print("[OK] Connected to MongoDB:", settings.MONGODB_DB)
        except Exception as e:
            print(f"[WARN] MongoDB connection failed: {e}")

    @classmethod
    async def disconnect(cls):
        if cls.client:
            cls.client.close()

    @classmethod
    async def is_connected(cls) -> bool:
        try:
            if cls.client:
                await cls.client.admin.command("ping")
                return True
        except Exception:
            pass
        return False

    @classmethod
    def api_keys(cls):
        return cls.db.api_keys

    @classmethod
    def usage_logs(cls):
        return cls.db.usage_logs

    @classmethod
    def conversations(cls):
        return cls.db.conversations

    @classmethod
    def messages(cls):
        return cls.db.messages

    @classmethod
    def documents(cls):
        return cls.db.documents

    @classmethod
    def rate_limits(cls):
        return cls.db.rate_limits


db = Database()
