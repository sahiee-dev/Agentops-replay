# demo-agents/test-samples/voice_01.py

class Agent:
    def __init__(self, name="Voice01"):
        self.name = name

    def respond(self, message):
        return f"{self.name}: You said '{message}'"

if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("Hello there!"))
