# AgentOps Replay

> **Log, visualize & replay agent workflows for debugging & compliance**

A comprehensive AI agent monitoring and observability platform that captures, visualizes, and replays agent interactions for debugging, compliance, and performance optimization.

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat&logo=postgresql&logoColor=white)](https://postgresql.org/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)](https://python.org/)

## 🚀 Overview

AgentOps Replay solves the critical problem of **AI agent observability** by turning opaque AI workflows into transparent, reproducible processes. Perfect for enterprises that need confidence in their AI agents' decision-making, policy compliance, and operational reliability.

### Key Value Propositions
- 🔍 **Complete Visibility** - Every agent action logged and traceable
- 🎬 **Interactive Replay** - Step-through agent workflows like video playback
- 🛡️ **Compliance Monitoring** - Automated policy violation detection
- 🤖 **Live Agent Integration** - Real AI agents with monitoring built-in
- 📊 **Professional Dashboard** - Production-ready monitoring interface

## ✨ Features

### 🎯 Core Features (MVP)
- **Universal Agent Logger** - Records prompts, tool calls, retrievals, outputs, and timestamps
- **Visualization UI** - Timeline view of agent actions with click-through inspection
- **Deterministic Replay** - Visual playback of agent sessions with progress tracking
- **Session Management** - Complete lifecycle management of agent sessions

### 🏆 Advanced Features (Implemented)
- **Compliance Pack** - Policy violation checks and audit report generation
- **Live AI Agent** - Google Gemini-powered customer support agent
- **Real-time Event Capture** - Live monitoring as agents operate
- **Multi-Agent Support** - Customer support, data analysis, voice agents
- **Professional UI** - Bootstrap-based interface with seamless navigation

### 🎪 Demo Features
- **Event Generator** - One-click realistic workflow simulation
- **Live Chat Interface** - Real-time customer support demonstrations
- **Multi-window Monitoring** - Watch replay, compliance, and dashboard simultaneously

## 🏗️ Architecture

graph TB
A[React Frontend] --> B[FastAPI Backend]
B --> C[PostgreSQL Database]
B --> D[Google Gemini AI]
B --> E[Agent Framework]

text
E --> F[Customer Support Agent]
E --> G[Data Analysis Agent] 
E --> H[Voice Call Agent]

F --> I[Event Logger]
G --> I
H --> I

I --> C

subgraph "Monitoring System"
    J[Session Tracker]
    K[Event Replay]
    L[Compliance Monitor]
end

C --> J
C --> K  
C --> L
text

## 🛠️ Tech Stack

### Backend
- **FastAPI** - High-performance Python web framework
- **SQLAlchemy** - Database ORM with PostgreSQL
- **Google Gemini** - AI-powered agent responses
- **Pydantic** - Data validation and settings management
- **Asyncio** - Asynchronous programming for real-time features

### Frontend
- **React** - Modern UI library with hooks
- **React Router** - Client-side routing
- **Bootstrap 5** - Professional styling framework
- **Axios** - HTTP client for API communication

### Database & Infrastructure
- **PostgreSQL** - Primary database for sessions and events
- **Docker** (optional) - Containerization support

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 16+
- PostgreSQL 12+
- Google Gemini API key

### 1. Clone Repository
git clone https://github.com/yourusername/agentops-replay-pro.git
cd agentops-replay-pro

text

### 2. Backend Setup
cd backend

Install dependencies
pip install -r requirements.txt

Create environment file
cp .env.example .env

Edit .env with your configuration
nano .env

text

**Backend Environment Variables (.env):**
Database
POSTGRES_USER=agentops
POSTGRES_PASSWORD=password
POSTGRES_DB=agentops_replay
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

AI Integration
GEMINI_API_KEY=your_gemini_api_key_here

API Configuration
SECRET_KEY=your-super-secret-key
ALLOWED_ORIGINS=["http://localhost:3000"]

text

### 3. Database Setup
Create PostgreSQL database
createdb agentops_replay

Run migrations (if using Alembic)
alembic upgrade head

Or create tables directly
python -c "from app.database import engine; from app.models import Base; Base.metadata.create_all(bind=engine)"

text

### 4. Start Backend Server
uvicorn app.main:app --reload

text
Backend will be available at: http://localhost:8000

### 5. Frontend Setup
cd frontend

Install dependencies
npm install

Start development server
npm run dev

text
Frontend will be available at: http://localhost:3000

## 📖 Usage Guide

### 1. Dashboard Overview
Navigate to the dashboard to see:
- Total sessions and active agents
- Event statistics and system health
- Recent session activity

### 2. Create Agent Sessions
Via API
curl -X POST "http://localhost:8000/api/v1/sessions/"
-H "Content-Type: application/json"
-d '{"user_id": 1, "agent_name": "CustomerBot", "status": "running"}'

Via Frontend
Go to Sessions page → Click "New Session"
text

### 3. Generate Events
Automated event generation
curl -X POST "http://localhost:8000/api/v1/event-generation/generate"
-H "Content-Type: application/json"
-d '{"session_id": 1, "scenario_type": "customer_support"}'

Or use the frontend Event Generator
text

### 4. Watch Session Replay
1. Go to **Replay** page
2. Select a session with events
3. Click **"Start Replay"** 
4. Watch events play step-by-step with timeline visualization

### 5. Live AI Agent Demo
1. Go to **Live Agent** page
2. Click **"Start Agent Session"**
3. Chat with the Gemini-powered customer support bot
4. Open replay in new tab to watch live event logging

### 6. Compliance Monitoring
1. Go to **Compliance** page  
2. Select a session to analyze
3. View policy violations and risk assessment
4. Generate audit reports

## 🤖 Agent Types Supported

### Customer Support Agent
- **Tools**: Order lookup, knowledge search, escalation
- **Use Cases**: E-commerce support, billing inquiries, technical issues
- **Events**: `customer_message`, `intent_analysis`, `llm_call`, `tool_usage`

### Data Analysis Agent  
- **Tools**: Data processing, statistical analysis, visualization
- **Use Cases**: Report generation, data insights, automated analysis
- **Events**: `data_ingestion`, `processing`, `analysis`, `report_generation`

### Voice Call Agent
- **Tools**: Speech-to-text, voice synthesis, call management
- **Use Cases**: Phone support, voice interactions, call center automation
- **Events**: `speech_recognition`, `voice_synthesis`, `call_management`

## 📡 API Documentation

### Sessions API
Get all sessions
GET /api/v1/sessions/

Create session
POST /api/v1/sessions/
{
"user_id": 1,
"agent_name": "CustomerBot",
"status": "running"
}

Get session by ID
GET /api/v1/sessions/{session_id}

text

### Events API
Get events for session
GET /api/v1/events/?session_id={session_id}

Create event
POST /api/v1/events/
{
"session_id": 1,
"event_type": "tool_call",
"tool_name": "order_lookup",
"flags": ["external_api"],
"sequence_number": 1
}

text

### Live Agent API
Start agent session
POST /api/v1/live-agent/start-agent-session

Chat with agent
POST /api/v1/live-agent/chat
{
"message": "I need help with my order",
"session_id": 123
}

End agent session
POST /api/v1/live-agent/end-agent-session/{session_id}

text

### Event Generation API
Generate realistic events
POST /api/v1/event-generation/generate
{
"session_id": 1,
"scenario_type": "customer_support" # or "data_analysis", "voice_agent"
}

Get available scenarios
GET /api/v1/event-generation/scenarios

text

## 🎯 Demo Scenarios

### Hackathon Demo Flow
1. **Dashboard Overview**: "Here's our real-time agent monitoring platform"
2. **Create Session**: "Let me start a new customer support agent"
3. **Live Agent Chat**: "Watch as I interact with our AI customer support"
4. **Real-time Replay**: "See every decision the agent makes, live"
5. **Compliance Check**: "Automatically detect policy violations and assess risk"

### Sample Demo Questions
- "I need help with my order status"
- "I want to request a refund for my recent purchase"  
- "My account login isn't working properly"
- "How do I update my billing information?"

## 🏆 Hackathon Highlights

### Problem Solved
**Enterprise AI Agent Observability** - Making AI agent behavior transparent, debuggable, and compliant for safe enterprise deployment.

### Technical Achievement
- ✅ **Full-stack implementation** with professional UI
- ✅ **Real AI integration** with Google Gemini
- ✅ **Live event capture** and replay system
- ✅ **Compliance monitoring** with automated violation detection
- ✅ **Production-ready architecture** with proper database design

### Business Impact
- **Faster Debugging**: Reduce agent troubleshooting from hours to minutes
- **Regulatory Compliance**: Automated audit trails for enterprise governance  
- **Risk Mitigation**: Early detection of agent behavior anomalies
- **Developer Productivity**: Clear visibility into agent decision-making

## 🔮 Future Roadmap

- [ ] **Multi-tenant Support** - Enterprise customer isolation
- [ ] **Advanced Analytics** - Agent performance metrics and insights
- [ ] **Integration SDK** - Easy integration with existing agent frameworks
- [ ] **Alerting System** - Real-time notifications for policy violations
- [ ] **Export Capabilities** - Audit report generation and data export
- [ ] **Deployment Automation** - Docker compose and Kubernetes support

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Google Gemini** for AI-powered agent responses
- **FastAPI** community for excellent documentation
- **React** ecosystem for modern frontend development
- **PostgreSQL** for reliable data persistence

---

**Built for the AI Agent Observability hackathon** 🚀

> *"Turning opaque AI workflows into transparent, reproducible processes for safer enterprise AI deployment"*
