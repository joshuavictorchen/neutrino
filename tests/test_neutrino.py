import unittest
import neutrino


class TestNeutrino(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.neutrino = neutrino.Neutrino()

    def test_instantiation(self):
        self.assertTrue(type(self.neutrino) == neutrino.Neutrino)


if __name__ == "__main__":

    unittest.main()
