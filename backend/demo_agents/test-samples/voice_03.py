# demo-agents/test-samples/voice_03.py


class Agent:
    def __init__(self, name="Voice03"):
        self.name = name

    def respond(self, message):
        reversed_msg = message[::-1]
        return f"{self.name}: Your message backwards -> {reversed_msg}"


if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("Hello world"))
