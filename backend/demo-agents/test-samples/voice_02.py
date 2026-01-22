# demo-agents/test-samples/voice_02.py

class Agent:
    def __init__(self, name="Voice02"):
        self.name = name

    def respond(self, message):
        return f"{self.name}: I understand '{message}'"

if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("How are you?"))
