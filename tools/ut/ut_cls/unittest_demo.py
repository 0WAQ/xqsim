import unittest


class TestDemo(unittest.TestCase):
    def setUp(self) -> None:
        print("set up")

    def test_add(self):
        print("test add ")
        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
