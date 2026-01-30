# demo-agents/test-samples/conversational_07.py


class Agent:
    def __init__(self, name="Agent07"):
        self.name = name

    def get_response(self, user_input):
        return f"{self.name}: Echo -> '{user_input.upper()}'"


if __name__ == "__main__":
    agent = Agent()
    while True:
        user_input = input("You: ")
        print(agent.get_response(user_input))
