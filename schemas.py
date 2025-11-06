from pydantic import BaseModel, Field
from typing import Optional

# CodeBro database schemas
# Each class name maps to a collection with lowercase name

class Conversation(BaseModel):
    title: str = Field(..., description="Conversation title")

class Message(BaseModel):
    conversation_id: str = Field(..., description="Related conversation id (string)")
    role: str = Field(..., pattern="^(user|assistant)$", description="Message role")
    content: str = Field(..., description="Message content")

# You can add more collections later (users, settings, etc.)
