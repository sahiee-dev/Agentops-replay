# demo-agents/test-samples/voice_04.py

class Agent:
    def __init__(self, name="Voice04"):
        self.name = name

    def respond(self, message):
        words = message.split()
        return f"{self.name}: Number of words = {len(words)}"

if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("This is a test message"))
