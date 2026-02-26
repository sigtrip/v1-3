import random

class ArgosQuantum:
    def __init__(self):
        self.states = ["Analytic", "Creative", "Protective", "Unstable", "All-Seeing"]

    def generate_state(self):
        name = random.choice(self.states)
        return {"name": name, "vector": [round(random.random(), 3) for _ in range(3)]}
