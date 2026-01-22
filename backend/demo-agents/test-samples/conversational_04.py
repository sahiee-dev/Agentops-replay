# demo-agents/test-samples/conversational_04.py

class Agent:
    def __init__(self, name="Agent04"):
        self.name = name

    def get_response(self, user_input):
        greetings = ["hi", "hello", "hey"]
        if any(greet in user_input.lower() for greet in greetings):
            return f"{self.name}: Hello! Nice to meet you."
        return f"{self.name}: I'm thinking about '{user_input}'..."

if __name__ == "__main__":
    agent = Agent()
    while True:
        user_input = input("You: ")
        print(agent.get_response(user_input))
