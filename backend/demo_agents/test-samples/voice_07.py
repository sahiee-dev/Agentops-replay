# demo-agents/test-samples/voice_07.py


class Agent:
    def __init__(self, name="Voice07"):
        self.name = name

    def respond(self, message):
        lowercase = message.lower()
        return f"{self.name}: {lowercase}"


if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("SHOUTING TEXT"))
