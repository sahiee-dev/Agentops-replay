import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.customer_support_agent import CustomerSupportAgent
from app.database import get_db

router = APIRouter()

class ChatMessage(BaseModel):
    message: str
    session_id: int | None = None

class ChatResponse(BaseModel):
    response: str
    session_id: int
    agent_name: str

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.agent_sessions: dict[int, CustomerSupportAgent] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    chat_message: ChatMessage,
    db: Session = Depends(get_db)
):
    """Chat with customer support agent"""
    try:
        # Get or create agent session
        if chat_message.session_id:
            # Check if agent session exists
            if chat_message.session_id not in manager.agent_sessions:
                manager.agent_sessions[chat_message.session_id] = CustomerSupportAgent(db, chat_message.session_id)
            agent = manager.agent_sessions[chat_message.session_id]
        else:
            # Create new agent session
            agent = CustomerSupportAgent(db)
            session_id = await agent.start_session("LiveCustomerBot")
            manager.agent_sessions[session_id] = agent

        # Process message
        response = await agent.process_customer_message(chat_message.message)

        return ChatResponse(
            response=response,
            session_id=agent.session_id,
            agent_name="Customer Support Agent"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e!s}")

@router.post("/start-agent-session")
async def start_agent_session(db: Session = Depends(get_db)):
    """Start a new agent session"""
    agent = CustomerSupportAgent(db)
    session_id = await agent.start_session("WebCustomerBot")
    manager.agent_sessions[session_id] = agent

    return {
        "session_id": session_id,
        "message": "Customer support agent session started",
        "agent_name": "Customer Support Agent"
    }

@router.post("/end-agent-session/{session_id}")
async def end_agent_session(session_id: int, db: Session = Depends(get_db)):
    """End an agent session"""
    if session_id in manager.agent_sessions:
        agent = manager.agent_sessions[session_id]
        await agent.end_session()
        del manager.agent_sessions[session_id]

        return {"message": f"Session {session_id} ended successfully"}

    raise HTTPException(status_code=404, detail="Agent session not found")

@router.websocket("/ws/agent/{session_id}")
async def websocket_agent_chat(websocket: WebSocket, session_id: int, db: Session = Depends(get_db)):
    """Real-time WebSocket chat with agent"""
    await manager.connect(websocket)

    # Get or create agent
    if session_id not in manager.agent_sessions:
        agent = CustomerSupportAgent(db, session_id)
        manager.agent_sessions[session_id] = agent
    else:
        agent = manager.agent_sessions[session_id]

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # Process with agent
            response = await agent.process_customer_message(message_data["message"])

            # Send response back
            await websocket.send_text(json.dumps({
                "type": "agent_response",
                "response": response,
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat()
            }))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        # Optionally end agent session
        if session_id in manager.agent_sessions:
            await manager.agent_sessions[session_id].end_session()
