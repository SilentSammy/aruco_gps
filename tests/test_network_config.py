import unittest
from network_config import select


class NetworkSelectionTests(unittest.TestCase):
    def setUp(self):
        self.ap = dict(interface='ap0', network='192.168.12.0/24', hotspot=True)
        self.internet = dict(interface='wifi1', network='10.22.128.0/20', hotspot=False)

    def test_hotspot_wins_even_with_remembered_internet(self):
        self.assertIs(select([self.internet, self.ap], remembered=['wifi1', '10.22.128.0/20']), self.ap)

    def test_explicit_interface_overrides_hotspot(self):
        self.assertIs(select([self.internet, self.ap], interface='wifi1'), self.internet)

    def test_ambiguous_lans_require_choice(self):
        other = dict(self.ap, hotspot=False)
        with self.assertRaises(ValueError):
            select([self.internet, other])
        self.assertIs(select([self.internet, other], remembered=['ap0', '192.168.12.0/24']), other)

    def test_stale_saved_subnet_is_not_reused(self):
        with self.assertRaises(ValueError):
            select([self.internet, dict(self.ap, hotspot=False)], remembered=['ap0', '192.168.99.0/24'])

    def test_no_network_does_not_silently_broadcast_on_default_route(self):
        with self.assertRaises(ValueError):
            select([])
