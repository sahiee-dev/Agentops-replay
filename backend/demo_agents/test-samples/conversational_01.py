# demo-agents/test-samples/conversational_01.py

class Agent:
    def __init__(self, name="Agent01"):
        self.name = name
        self.context = []

    def get_response(self, user_input):
        self.context.append(user_input)
        return f"{self.name}: You said '{user_input}'. Interesting!"

if __name__ == "__main__":
    agent = Agent()
    while True:
        user_input = input("You: ")
        print(agent.get_response(user_input))
