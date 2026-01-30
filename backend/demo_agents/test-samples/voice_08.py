# demo-agents/test-samples/voice_08.py


class Agent:
    def __init__(self, name="Voice08"):
        self.name = name

    def respond(self, message):
        vowels = sum(1 for c in message if c.lower() in "aeiou")
        return f"{self.name}: Number of vowels = {vowels}"


if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("This is a test"))
