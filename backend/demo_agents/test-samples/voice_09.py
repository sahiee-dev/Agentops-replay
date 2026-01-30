# demo-agents/test-samples/voice_09.py

class Agent:
    def __init__(self, name="Voice09"):
        self.name = name

    def respond(self, message):
        consonants = sum(1 for c in message if c.isalpha() and c.lower() not in "aeiou")
        return f"{self.name}: Number of consonants = {consonants}"

if __name__ == "__main__":
    agent = Agent()
    print(agent.respond("Count consonants in this"))
