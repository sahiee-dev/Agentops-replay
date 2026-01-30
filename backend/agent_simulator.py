import random
import time
from typing import Any

import requests


class AgentSimulator:
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url
        self.session_id: str | None = None
        self._sequence_counter: int = 0

    def _next_sequence(self) -> int:
        """Get next monotonic sequence number."""
        self._sequence_counter += 1
        return self._sequence_counter

    def create_session(
        self, agent_name: str, agent_type: str = "customer_support"
    ) -> str | None:
        """Create a new agent session"""
        # Reset sequence counter for new session
        self._sequence_counter = 0
        
        session_data = {"user_id": 2, "agent_name": agent_name, "status": "running"}

        response = requests.post(f"{self.base_url}/api/v1/sessions/", json=session_data)
        if response.status_code == 200:
            self.session_id = response.json()["id"]
            print(f"Created session #{self.session_id} for {agent_name}")
            return self.session_id
        else:
            print(f"Failed to create session: {response.text}")
            return None

    def log_event(
        self,
        event_type: str,
        tool_name: str | None = None,
        flags: list[str] | None = None,
        delay: float = 1.0,
    ) -> Any:
        """Log a single event with realistic timing"""
        if not self.session_id:
            print(" No active session. Create a session first.")
            return

        event_data = {
            "session_id": self.session_id,
            "event_type": event_type,
            "tool_name": tool_name or "unknown",
            "flags": flags or [],
            "sequence_number": self._next_sequence(),
        }

        try:
            response = requests.post(f"{self.base_url}/api/v1/events/", json=event_data)
            if response.status_code == 200:
                print(f" Logged: {event_type} with {tool_name}")
                time.sleep(delay)  # Realistic timing between events
                return response.json()
            else:
                print(f" Failed to log event: {response.text}")
        except Exception as e:
            print(f" Error logging event: {e}")

    def simulate_customer_support_agent(self):
        """Simulate a complete customer support agent workflow"""
        agent_name = f"CustomerBot-{random.randint(1000, 9999)}"

        if not self.create_session(agent_name):
            return

        print(f"\n Starting {agent_name} simulation...")

        # Realistic customer support workflow
        workflows = [
            {
                "scenario": "Order Status Inquiry",
                "events": [
                    ("user_message", "chat_interface", []),
                    ("intent_classification", "nlp_processor", ["ml_inference"]),
                    ("database_lookup", "order_system", ["external_api"]),
                    ("llm_call", "gpt-4", ["high_cost"]),
                    ("response_generation", "text_processor", []),
                    ("user_response", "chat_interface", []),
                ],
            },
            {
                "scenario": "Billing Issue Resolution",
                "events": [
                    ("user_message", "chat_interface", []),
                    ("sentiment_analysis", "emotion_detector", ["ml_inference"]),
                    ("escalation_check", "rule_engine", ["policy_check"]),
                    (
                        "billing_lookup",
                        "payment_system",
                        ["sensitive_data", "external_api"],
                    ),
                    ("llm_call", "gpt-4", ["high_cost"]),
                    ("refund_processing", "payment_gateway", ["financial_transaction"]),
                    ("confirmation_email", "email_service", ["external_api"]),
                    ("session_summary", "knowledge_base", []),
                ],
            },
            {
                "scenario": "Product Recommendation",
                "events": [
                    ("user_message", "chat_interface", []),
                    ("user_profiling", "analytics_engine", ["user_data"]),
                    ("product_search", "catalog_api", ["external_api"]),
                    ("recommendation_engine", "ml_recommender", ["ml_inference"]),
                    ("llm_call", "gpt-4", ["high_cost"]),
                    ("personalization", "user_preference_engine", ["user_data"]),
                    ("response_generation", "text_processor", []),
                ],
            },
        ]

        # Pick a random scenario
        scenario = random.choice(workflows)
        print(f"Scenario: {scenario['scenario']}")

        # Execute the workflow
        for event_type, tool_name, flags in scenario["events"]:
            delay = random.uniform(0.5, 2.0)  # Random realistic delays
            self.log_event(event_type, tool_name, flags, delay)

        # Mark session as completed
        print(f" {agent_name} completed successfully!")

    def simulate_analytical_agent(self):
        """Simulate a data analysis agent workflow"""
        agent_name = f"DataAnalyst-{random.randint(1000, 9999)}"

        if not self.create_session(agent_name):
            return

        print(f"\n Starting {agent_name} simulation...")

        # Data analysis workflow
        events = [
            ("data_ingestion", "file_processor", ["data_processing"]),
            ("data_validation", "data_validator", ["quality_check"]),
            ("schema_detection", "data_profiler", ["ml_inference"]),
            ("data_cleaning", "pandas_processor", ["data_transformation"]),
            ("statistical_analysis", "scipy_stats", ["computation"]),
            ("llm_call", "gpt-4", ["high_cost"]),
            ("visualization_generation", "plotly_engine", ["chart_creation"]),
            ("insight_extraction", "pattern_detector", ["ml_inference"]),
            ("report_generation", "report_builder", ["document_creation"]),
            ("quality_review", "validation_engine", ["compliance_check"]),
        ]

        for event_type, tool_name, flags in events:
            delay = random.uniform(1, 3)  # Slower for data processing
            self.log_event(event_type, tool_name, flags, delay)

        print(f" {agent_name} analysis completed!")

    def simulate_voice_agent(self):
        """Simulate a voice call agent workflow"""
        agent_name = f"VoiceBot-{random.randint(1000, 9999)}"

        if not self.create_session(agent_name):
            return

        print(f"\n📞 Starting {agent_name} simulation...")

        # Voice agent workflow
        events = [
            ("call_initiation", "telephony_system", ["voice_call"]),
            ("speech_to_text", "whisper_api", ["audio_processing", "external_api"]),
            ("intent_recognition", "voice_nlp", ["ml_inference"]),
            ("context_retrieval", "conversation_memory", ["knowledge_base"]),
            ("llm_call", "gpt-4", ["high_cost"]),
            ("text_to_speech", "elevenlabs_api", ["voice_synthesis", "external_api"]),
            ("call_recording", "storage_system", ["audio_data"]),
            ("call_analysis", "sentiment_detector", ["ml_inference"]),
            ("call_termination", "telephony_system", ["voice_call"]),
        ]

        for event_type, tool_name, flags in events:
            delay = random.uniform(0.8, 2.5)  # Voice timing
            self.log_event(event_type, tool_name, flags, delay)

        print(f" {agent_name} call completed!")


def main():
    """Run multiple agent simulations"""
    simulator = AgentSimulator()

    print("🚀 AgentOps Simulator Starting...")
    print("This will create realistic agent sessions with automated events")
    print("-" * 60)

    # Simulate multiple agent types
    agents_to_run = [
        simulator.simulate_customer_support_agent,
        simulator.simulate_analytical_agent,
        simulator.simulate_voice_agent,
        simulator.simulate_customer_support_agent,  # Run another customer support
    ]

    for i, agent_func in enumerate(agents_to_run, 1):
        print(f"\n Running simulation {i}/{len(agents_to_run)}")
        agent_func()

        if i < len(agents_to_run):
            print(" Waiting before next simulation...")
            time.sleep(2)

    print("\n All simulations completed!")
    print(" Check your frontend at http://localhost:3000 to see the results!")


if __name__ == "__main__":
    main()
