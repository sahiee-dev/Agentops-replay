# demo-agents/test-samples/voice_05.py


class Agent:
    def __init__(self, name="Voice05"):
        self.name = name

    def respond(self, message):
        return f"{self.name}: Message length = {len(message)} characters"


if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("Count my characters!"))
