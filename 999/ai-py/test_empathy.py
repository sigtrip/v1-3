import unittest
from empathy_engine import EmpathyEngine, gen_key

class TestEmpathyEngine(unittest.TestCase):
    def test_analyze_intent_safe(self):
        engine = EmpathyEngine()
        status, msg = engine.analyze_intent("test", "print('hello')")
        self.assertEqual(status, "Safe")

    def test_analyze_intent_critical(self):
        engine = EmpathyEngine()
        status, msg = engine.analyze_intent("test", "os.remove('file')")
        self.assertEqual(status, "Critical")

    def test_gen_key(self):
        key = gen_key()
        self.assertEqual(len(key), 64)

if __name__ == "__main__":
    unittest.main()
