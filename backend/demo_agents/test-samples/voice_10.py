# demo-agents/test-samples/voice_10.py


class Agent:
    def __init__(self, name="Voice10"):
        self.name = name

    def respond(self, message):
        return f"{self.name}: Echo -> {message}"


if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("Echo this message"))
