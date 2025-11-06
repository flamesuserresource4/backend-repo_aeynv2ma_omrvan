import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="CodeBro API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- Utility --------------------

def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out

# -------------------- Schemas --------------------

class CreateConversationRequest(BaseModel):
    title: Optional[str] = None

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    conversation_id: str
    reply: str

# -------------------- Simple CodeBro Brain --------------------

def codebro_brain(user_message: str) -> str:
    """A lightweight rule-based responder to emulate helpful coding assistant."""
    m = user_message.strip().lower()
    # Quick intents
    if any(x in m for x in ["hello", "hi", "hey"]):
        return (
            "Hey! I'm CodeBro 🤖💙 — your coding sidekick. Ask me about React, FastAPI, MongoDB, Tailwind, or deployment!"
        )
    if "deploy" in m or "deployment" in m:
        return (
            "Deployment tips:\n"
            "- Frontend: build with Vite (npm run build) and host static files (Vercel/Netlify).\n"
            "- Backend: use FastAPI + Uvicorn on a server (Railway/Render/Fly.io).\n"
            "- Set DATABASE_URL and DATABASE_NAME env vars.\n"
            "- Enable CORS and point frontend to your backend URL via VITE_BACKEND_URL."
        )
    if "react" in m:
        return (
            "In React with Vite: manage state with hooks (useState/useEffect), fetch from your API using fetch/axios, and use Tailwind for rapid UI.\n"
            "Need a quick example?\n\n"
            "useEffect(() => { fetch('/api').then(r=>r.json()).then(setData); }, []);"
        )
    if "fastapi" in m or "python" in m:
        return (
            "FastAPI quickstart:\n\n"
            "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/')\ndef home(): return {'ok': True}\n\n"
            "Run with: uvicorn main:app --reload"
        )
    if "mongodb" in m or "mongo" in m or "database" in m:
        return (
            "MongoDB patterns:\n- Use a single client and reuse the db handle.\n- Store timestamps (created_at/updated_at).\n- Index frequent query fields.\n- Keep references by storing ObjectId as string if you prefer simple JSON APIs."
        )
    if "tailwind" in m:
        return (
            "Tailwind tip: compose utilities and extract components when repeated. Use container, max-w-*, and prose for long content."
        )
    if "code" in m or "bug" in m or "error" in m or "fix" in m:
        return (
            "Debug flow I recommend:\n1) Reproduce reliably.\n2) Read the exact error and the stack.\n3) Minimize to a tiny snippet.\n4) Add logs/prints.\n5) Fix, then add a test to avoid regressions."
        )
    # Default helpful echo
    return (
        "I hear you! Here's a quick, actionable reply:\n\n"
        f"- Summary: you said → \"{user_message.strip()}\"\n"
        "- Next step: break it into smaller tasks and tackle them one by one.\n"
        "- Want code? Paste a snippet and I'll review it."
    )

# -------------------- Routes --------------------

@app.get("/")
def read_root():
    return {"message": "Hello from CodeBro Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.post("/api/conversations")
def create_conversation(req: CreateConversationRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    title = req.title or "New Chat"
    convo_id = create_document("conversation", {"title": title})
    return {"conversation_id": convo_id, "title": title}

@app.get("/api/conversations")
def list_conversations():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    items = db["conversation"].find({}).sort("created_at", -1).limit(50)
    convos = []
    for it in items:
        d = serialize_doc(it)
        # count messages fast (can be optimized with aggregation/indexes)
        d["messages_count"] = db["message"].count_documents({"conversation_id": d.get("_id")})
        convos.append(d)
    return {"items": convos}

@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    convo = db["conversation"].find_one({"_id": ObjectId(conversation_id)})
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = db["message"].find({"conversation_id": conversation_id}).sort("created_at", 1)
    return {"conversation": serialize_doc(convo), "messages": [serialize_doc(m) for m in msgs]}

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # create conversation if needed
    conversation_id = req.conversation_id
    if not conversation_id:
        conversation_id = create_document("conversation", {"title": req.message[:40] + ("…" if len(req.message) > 40 else "")})

    # persist user message
    create_document(
        "message",
        {
            "conversation_id": conversation_id,
            "role": "user",
            "content": req.message,
        },
    )

    # generate assistant reply
    reply = codebro_brain(req.message)

    # persist assistant message
    create_document(
        "message",
        {
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": reply,
        },
    )

    return ChatResponse(conversation_id=conversation_id, reply=reply)

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
