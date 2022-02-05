import unittest
from neutrino.main import Neutrino


class TestNeutrino(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neutrino = Neutrino()

    def test_instantiation(self):
        self.assertTrue(type(self.neutrino) == Neutrino)


if __name__ == "__main__":

    unittest.main()
