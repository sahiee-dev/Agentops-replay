from datetime import datetime

from sqlalchemy.orm import Session

from app.models.event import Event


class EventGeneratorService:
    def __init__(self, db: Session):
        self.db = db

    def generate_customer_support_scenario(self, session_id: int):
        """Generate realistic customer support agent events"""
        events = [
            {"event_type": "user_message", "tool_name": "chat_interface", "flags": []},
            {"event_type": "intent_classification", "tool_name": "nlp_processor", "flags": ["ml_inference"]},
            {"event_type": "knowledge_search", "tool_name": "vector_db", "flags": ["external_api"]},
            {"event_type": "llm_call", "tool_name": "gpt-4", "flags": ["high_cost"]},
            {"event_type": "database_lookup", "tool_name": "order_system", "flags": ["external_api"]},
            {"event_type": "response_generation", "tool_name": "text_processor", "flags": []},
            {"event_type": "user_feedback", "tool_name": "chat_interface", "flags": []}
        ]

        created_events = []
        for i, event_data in enumerate(events, 1):
            db_event = Event(
                session_id=session_id,
                event_type=event_data["event_type"],
                tool_name=event_data["tool_name"],
                flags=event_data["flags"],
                sequence_number=i,
                timestamp=datetime.utcnow()
            )
            self.db.add(db_event)
            created_events.append(db_event)

        self.db.commit()
        return created_events

    def generate_data_analysis_scenario(self, session_id: int):
        """Generate realistic data analysis agent events"""
        events = [
            {"event_type": "data_ingestion", "tool_name": "file_processor", "flags": ["data_processing"]},
            {"event_type": "data_validation", "tool_name": "pandas", "flags": ["quality_check"]},
            {"event_type": "schema_detection", "tool_name": "data_profiler", "flags": ["ml_inference"]},
            {"event_type": "data_cleaning", "tool_name": "pandas_processor", "flags": ["data_transformation"]},
            {"event_type": "statistical_analysis", "tool_name": "scipy_stats", "flags": ["computation"]},
            {"event_type": "llm_call", "tool_name": "gpt-4", "flags": ["high_cost"]},
            {"event_type": "visualization_generation", "tool_name": "plotly_engine", "flags": ["chart_creation"]},
            {"event_type": "insight_extraction", "tool_name": "pattern_detector", "flags": ["ml_inference"]},
            {"event_type": "report_generation", "tool_name": "report_builder", "flags": ["document_creation"]}
        ]

        created_events = []
        for i, event_data in enumerate(events, 1):
            db_event = Event(
                session_id=session_id,
                event_type=event_data["event_type"],
                tool_name=event_data["tool_name"],
                flags=event_data["flags"],
                sequence_number=i,
                timestamp=datetime.utcnow()
            )
            self.db.add(db_event)
            created_events.append(db_event)

        self.db.commit()
        return created_events

    def generate_voice_agent_scenario(self, session_id: int):
        """Generate realistic voice agent events"""
        events = [
            {"event_type": "call_initiation", "tool_name": "telephony_system", "flags": ["voice_call"]},
            {"event_type": "speech_to_text", "tool_name": "whisper_api", "flags": ["audio_processing", "external_api"]},
            {"event_type": "intent_recognition", "tool_name": "voice_nlp", "flags": ["ml_inference"]},
            {"event_type": "context_retrieval", "tool_name": "conversation_memory", "flags": ["knowledge_base"]},
            {"event_type": "llm_call", "tool_name": "gpt-4", "flags": ["high_cost"]},
            {"event_type": "text_to_speech", "tool_name": "elevenlabs_api", "flags": ["voice_synthesis", "external_api"]},
            {"event_type": "call_recording", "tool_name": "storage_system", "flags": ["audio_data"]},
            {"event_type": "sentiment_analysis", "tool_name": "emotion_detector", "flags": ["ml_inference"]},
            {"event_type": "call_termination", "tool_name": "telephony_system", "flags": ["voice_call"]}
        ]

        created_events = []
        for i, event_data in enumerate(events, 1):
            db_event = Event(
                session_id=session_id,
                event_type=event_data["event_type"],
                tool_name=event_data["tool_name"],
                flags=event_data["flags"],
                sequence_number=i,
                timestamp=datetime.utcnow()
            )
            self.db.add(db_event)
            created_events.append(db_event)

        self.db.commit()
        return created_events

    def generate_complex_workflow(self, session_id: int):
        """Generate a complex multi-step workflow with policy violations"""
        events = [
            {"event_type": "user_authentication", "tool_name": "auth_service", "flags": ["security_check"]},
            {"event_type": "permission_check", "tool_name": "rbac_system", "flags": ["access_control"]},
            {"event_type": "sensitive_data_access", "tool_name": "user_database", "flags": ["sensitive_data", "pii_access"]},
            {"event_type": "external_api_call", "tool_name": "third_party_service", "flags": ["external_api", "rate_limit"]},
            {"event_type": "llm_call", "tool_name": "gpt-4", "flags": ["high_cost"]},
            {"event_type": "data_processing", "tool_name": "ml_pipeline", "flags": ["ml_inference", "high_compute"]},
            {"event_type": "policy_violation", "tool_name": "compliance_checker", "flags": ["security_violation", "policy_breach"]},
            {"event_type": "escalation", "tool_name": "alert_system", "flags": ["security_alert"]},
            {"event_type": "audit_log", "tool_name": "logging_service", "flags": ["compliance_record"]}
        ]

        created_events = []
        for i, event_data in enumerate(events, 1):
            db_event = Event(
                session_id=session_id,
                event_type=event_data["event_type"],
                tool_name=event_data["tool_name"],
                flags=event_data["flags"],
                sequence_number=i,
                timestamp=datetime.utcnow()
            )
            self.db.add(db_event)
            created_events.append(db_event)

        self.db.commit()
        return created_events

    def generate_scenario(self, session_id: int, scenario_type: str):
        """Generate events based on scenario type"""
        scenarios = {
            "customer_support": self.generate_customer_support_scenario,
            "data_analysis": self.generate_data_analysis_scenario,
            "voice_agent": self.generate_voice_agent_scenario,
            "complex_workflow": self.generate_complex_workflow
        }

        if scenario_type not in scenarios:
            raise ValueError(f"Unknown scenario type: {scenario_type}")

        return scenarios[scenario_type](session_id)
