import asyncio
import logging
import random

import requests

# Default HTTP timeout for event posts (seconds)
HTTP_TIMEOUT = 10.0


class LiveEventGenerator:
    def __init__(self, session_id, base_url="http://localhost:8000"):
        self.session_id = session_id
        self.base_url = base_url
        self.is_running = False

    async def generate_events_continuously(self):
        """Generate realistic events continuously"""
        self.is_running = True
        sequence = 1

        event_patterns = [
            ("user_interaction", "chat_interface", []),
            ("tool_call", "web_search", ["external_api"]),
            ("llm_call", "gpt-4", ["high_cost"]),
            ("database_query", "postgres", ["data_access"]),
            ("api_call", "external_service", ["external_api"]),
            ("processing", "data_processor", ["computation"]),
            ("validation", "rule_engine", ["policy_check"]),
            ("response", "response_generator", []),
        ]

        print(f" Starting live event generation for session {self.session_id}")

        while self.is_running:
            # Pick random event
            event_type, tool_name, flags = random.choice(event_patterns)

            # Add random flags sometimes
            if random.random() < 0.3:  # 30% chance of additional flags
                extra_flags = random.choice(
                    [
                        ["sensitive_data"],
                        ["high_cost"],
                        ["compliance_violation"],
                        ["security_check"],
                    ]
                )
                flags.extend(extra_flags)

            # Create event
            event_data = {
                "session_id": self.session_id,
                "event_type": event_type,
                "tool_name": tool_name,
                "flags": flags,
                "sequence_number": sequence,
            }

            try:
                # Run blocking HTTP call in thread with timeout
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        requests.post,
                        f"{self.base_url}/api/v1/events/",
                        json=event_data,
                        timeout=HTTP_TIMEOUT,
                    ),
                    timeout=HTTP_TIMEOUT + 2.0,
                )
                if response.status_code == 200:
                    print(f" Live event #{sequence}: {event_type} -> {tool_name}")
                    sequence += 1
                else:
                    print(f" Failed to create event: {response.text}")
            except asyncio.TimeoutError:
                logging.getLogger(__name__).warning(
                    "Timeout posting event #%d", sequence
                )
            except requests.RequestException as e:
                logging.getLogger(__name__).exception(
                    "Error generating event: %s", str(e)
                )
            except Exception as e:
                # Re-raise unexpected
                raise e

            # Wait random interval (2-8 seconds)
            await asyncio.sleep(random.uniform(2, 8))

    def stop(self):
        """Stop generating events"""
        self.is_running = False
        print(" Stopped live event generation")


# Usage for demo
async def demo_live_events():
    # Use an existing session ID
    session_id = 9  # Use your existing session
    generator = LiveEventGenerator(session_id)

    try:
        await generator.generate_events_continuously()
    except KeyboardInterrupt:
        generator.stop()
        print("\n Live demo ended")


if __name__ == "__main__":
    asyncio.run(demo_live_events())
