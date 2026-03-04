# Пример теста для криптографии (Rust FFI)
import unittest
from empathy_engine import gen_key

class TestCrypto(unittest.TestCase):
    def test_gen_key_length(self):
        key = gen_key()
        self.assertEqual(len(key), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in key))

if __name__ == "__main__":
    unittest.main()
