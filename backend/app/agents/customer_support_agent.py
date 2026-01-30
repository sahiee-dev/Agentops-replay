import asyncio
from datetime import datetime, timezone

import google.generativeai as genai  # type: ignore
from app.config import settings  # Now you can import settings
from app.models.event import Event
from app.models.session import ChainAuthority, Session as SessionModel, SessionStatus
from app.schemas.session import SessionCreate
from sqlalchemy.orm import Session  # type: ignore


class CustomerSupportAgent:
    def __init__(self, db: Session, session_id: int | None = None):
        self.db = db
        self.session_id = session_id

        # Use centralized settings for API key
        api_key = settings.GEMINI_API_KEY

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not found in settings. Please set it in .env file."
            )

        genai.configure(api_key=api_key)

        # Initialize Gemini model
        self.model = genai.GenerativeModel("gemini-2.0-flash")

        self.conversation_history = []
        self.system_context = """You are a helpful customer support agent for an e-commerce company. You can:
        - Help with order status inquiries
        - Process refund and return requests
        - Answer billing questions
        - Provide product information
        - Escalate complex issues to human agents
        
        Be professional, empathetic, and concise. Always try to resolve customer issues efficiently."""

        self.tools = {
            "order_lookup": self._order_lookup,
            "knowledge_search": self._knowledge_search,
            "escalate_human": self._escalate_human,
            "send_email": self._send_email,
        }

    async def start_session(self, agent_name: str = "GeminiSupportBot") -> int:
        """Start a new customer support session"""
        session_data = SessionCreate(user_id=2, agent_name=agent_name, status="running")

        db_session = SessionModel(
            user_id=session_data.user_id,
            agent_name=session_data.agent_name,
            chain_authority=ChainAuthority.SERVER,
            status=SessionStatus.ACTIVE,
            started_at=datetime.now(timezone.utc),
        )

        self.db.add(db_session)
        self.db.commit()
        self.db.refresh(db_session)

        self.session_id = db_session.id

        # Log session start event
        await self._log_event("session_start", "gemini_agent", [])

        return self.session_id

    async def _log_event(
        self, event_type: str, tool_name: str, flags: list[str], details: str = ""
    ):
        """Log an event to the monitoring system"""
        if not self.session_id:
            return

        # Get current sequence number
        last_event = (
            self.db.query(Event)
            .filter(Event.session_id == self.session_id)
            .order_by(Event.sequence_number.desc())
            .first()
        )

        sequence_number = (last_event.sequence_number + 1) if last_event else 1

        db_event = Event(
            session_id=self.session_id,
            event_type=event_type,
            tool_name=tool_name,
            flags=flags,
            sequence_number=sequence_number,
            timestamp=datetime.utcnow(),
        )

        self.db.add(db_event)
        self.db.commit()

        print(f"📝 Logged: {event_type} -> {tool_name} (Session #{self.session_id})")

    async def process_customer_message(self, message: str) -> str:
        """Process a customer message using real Gemini AI"""
        try:
            # Log incoming message
            await self._log_event("customer_message", "chat_interface", [])

            # Add to conversation history
            self.conversation_history.append(f"Customer: {message}")

            # Analyze intent first
            intent = await self._analyze_intent(message)

            # Generate response using Gemini
            response = await self._generate_gemini_response(message, intent)

            # Add response to history
            self.conversation_history.append(f"Agent: {response}")

            # Log response generation
            await self._log_event("response_sent", "chat_interface", [])

            return response

        except Exception as e:
            await self._log_event("error", "error_handler", ["system_error"])
            print(f"Error processing message: {e}")
            return "I apologize, but I'm experiencing technical difficulties. Let me connect you with a human agent."

    async def _analyze_intent(self, message: str) -> str:
        """Analyze customer intent using Gemini"""
        await self._log_event(
            "intent_analysis", "gemini_1.5_flash", ["ml_inference", "ai_analysis"]
        )

        try:
            intent_prompt = f"""Analyze this customer message and classify the intent. 
            Return only one word from: order, billing, technical, refund, general
            
            Customer message: "{message}"
            Intent:"""

            response = await self.model.generate_content_async(intent_prompt)
            intent = response.text.strip().lower()

            # Validate intent
            valid_intents = ["order", "billing", "technical", "refund", "general"]
            if intent not in valid_intents:
                intent = "general"

            return intent

        except Exception as e:
            print(f"Error analyzing intent: {e}")
            return "general"

    async def _generate_gemini_response(self, message: str, intent: str) -> str:
        """Generate response using real Gemini AI"""
        await self._log_event(
            "llm_call",
            "gemini_1.5_flash",
            ["high_cost", "external_api", "ai_generation"],
        )

        try:
            # Build context with conversation history
            context = f"{self.system_context}\n\n"

            # Add recent conversation history (last 5 exchanges)
            if self.conversation_history:
                context += "Recent conversation:\n"
                for msg in self.conversation_history[-10:]:  # Last 10 messages
                    context += f"{msg}\n"
                context += "\n"

            # Add intent-specific context
            intent_context = {
                "order": "Focus on helping with order-related inquiries. You can look up orders, check shipping status, and provide tracking information.",
                "billing": "Focus on billing and payment issues. You can help with invoices, payment methods, and refund processes.",
                "technical": "Focus on technical support. Help troubleshoot issues and escalate complex technical problems.",
                "refund": "Focus on refund and return processes. Be empathetic and helpful in processing returns.",
                "general": "Provide general customer support assistance.",
            }

            context += (
                f"Customer intent: {intent}\n{intent_context.get(intent, '')}\n\n"
            )

            # Current customer message
            prompt = f"{context}Customer: {message}\n\nProvide a helpful, professional response as a customer support agent:"

            # Generate response
            response = await self.model.generate_content_async(prompt)

            # Simulate tool usage based on intent and response content
            await self._simulate_tool_usage(intent, response.text)

            return response.text

        except Exception as e:
            await self._log_event("llm_error", "gemini_1.5_flash", ["api_error"])
            print(f"Error generating response: {e}")
            return "I understand your concern. Let me help you with that. Could you provide more details so I can assist you better?"

    async def _simulate_tool_usage(self, intent: str, response_text: str):
        """Simulate realistic tool usage based on intent and response"""

        # Order-related responses often require order lookup
        if intent == "order" and any(
            word in response_text.lower() for word in ["order", "tracking", "shipping"]
        ):
            await self._order_lookup(
                "ORD-" + str(abs(hash(response_text[:10])) % 10000)
            )

        # Billing responses might need account lookup
        elif intent == "billing" and any(
            word in response_text.lower() for word in ["account", "billing", "payment"]
        ):
            await self._knowledge_search("billing policies")

        # Technical issues might need escalation
        elif intent == "technical" and any(
            word in response_text.lower() for word in ["technical", "issue", "problem"]
        ):
            await self._escalate_human("technical issue")

        # Refund requests need special handling
        elif intent == "refund" and "refund" in response_text.lower():
            await self._process_refund(
                "REF-" + str(abs(hash(response_text[:10])) % 10000)
            )

    async def _order_lookup(self, order_id: str) -> dict:
        """Simulate order lookup"""
        await self._log_event(
            "order_lookup", "order_system", ["external_api", "customer_data"]
        )
        await asyncio.sleep(0.5)  # Simulate API delay
        return {
            "order_id": order_id,
            "status": "shipped",
            "tracking": "1Z999AA1234567890",
        }

    async def _knowledge_search(self, query: str) -> list[dict]:
        """Simulate knowledge base search"""
        await self._log_event(
            "knowledge_search", "vector_db", ["external_api", "knowledge_base"]
        )
        await asyncio.sleep(0.3)
        return [{"title": "FAQ", "content": "Relevant information..."}]

    async def _escalate_human(self, reason: str) -> bool:
        """Escalate to human agent"""
        await self._log_event(
            "escalation", "human_handoff", ["escalation", "human_required"]
        )
        return True

    async def _process_refund(self, refund_id: str) -> dict:
        """Process refund request"""
        await self._log_event(
            "refund_processing",
            "payment_system",
            ["financial_transaction", "sensitive_data"],
        )
        await asyncio.sleep(0.7)
        return {"refund_id": refund_id, "status": "processing", "amount": "$29.99"}

    async def _send_email(self, recipient: str, subject: str, body: str) -> bool:
        """Send email to customer"""
        await self._log_event(
            "email_sent", "email_service", ["external_api", "communication"]
        )
        return True

    async def end_session(self):
        """End the customer support session"""
        if self.session_id:
            # Update session status
            session = (
                self.db.query(SessionModel)
                .filter(SessionModel.id == self.session_id)
                .first()
            )
            if session:
                session.status = "completed"
                self.db.commit()

            # Log session end
            await self._log_event("session_end", "gemini_agent", [])

            print(f"✅ Gemini Session #{self.session_id} completed")
