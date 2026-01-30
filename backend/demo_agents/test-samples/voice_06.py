
# demo-agents/test-samples/voice_06.py

class Agent:
    def __init__(self, name="Voice06"):
        self.name = name

    def respond(self, message):
        uppercase = message.upper()
        return f"{self.name}: {uppercase}"

if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("please speak louder"))
