# demo-agents/test-samples/support_08.py

class Agent:
    def __init__(self, name="Support08"):
        self.name = name

    def respond(self, query):
        greetings = ["hello", "hi", "hey"]
        if query.lower() in greetings:
            return f"{self.name}: Hello! How can I help you today?"
        return f"{self.name}: Your query has been noted."

if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("Hi"))
