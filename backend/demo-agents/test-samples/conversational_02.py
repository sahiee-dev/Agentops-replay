# demo-agents/test-samples/conversational_02.py

class Agent:
    def __init__(self, name="Agent02"):
        self.name = name

    def get_response(self, user_input):
        if "hello" in user_input.lower():
            return f"{self.name}: Hello! How can I help you today?"
        return f"{self.name}: I heard '{user_input}'. Tell me more."

if __name__ == "__main__":
    agent = Agent()
    while True:
        user_input = input("You: ")
        print(agent.get_response(user_input))
