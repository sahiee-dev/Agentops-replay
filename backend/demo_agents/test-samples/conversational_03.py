# demo-agents/test-samples/conversational_03.py


class Agent:
    def __init__(self, name="Agent03"):
        self.name = name

    def get_response(self, user_input):
        return f"{self.name}: Processing your input '{user_input}'..."


if __name__ == "__main__":
    agent = Agent()
    while True:
        user_input = input("You: ")
        print(agent.get_response(user_input))
