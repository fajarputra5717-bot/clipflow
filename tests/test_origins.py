"""shared/origins.py (138): python3 -m unittest tests.test_origins"""
import unittest

from shared.origins import allowed


class Origins(unittest.TestCase):
    def test_port_80_and_non_default_ports(self):
        self.assertTrue(allowed("http://10.0.0.5", scheme="http", host="10.0.0.5"))
        self.assertTrue(allowed("http://10.0.0.5:80", scheme="http", host="10.0.0.5"))
        self.assertTrue(allowed("http://10.0.0.5:8080", scheme="http", host="10.0.0.5:8080"))   # staging via $http_host
        self.assertFalse(allowed("http://10.0.0.5:8080", scheme="http", host="10.0.0.5"))       # the old bug's input: port lost
        self.assertTrue(allowed("http://10.0.0.5:8080", scheme="http", host="10.0.0.5", forwarded_port="8080"))

    def test_scheme_and_host_must_match(self):
        self.assertFalse(allowed("https://10.0.0.5", scheme="http", host="10.0.0.5"))
        self.assertFalse(allowed("http://evil.example", scheme="http", host="10.0.0.5"))
        self.assertFalse(allowed("http://10.0.0.5.evil.example", scheme="http", host="10.0.0.5"))
        self.assertTrue(allowed("https://clips.example.com", scheme="https", host="clips.example.com:443"))
        self.assertTrue(allowed("HTTP://LOCALHOST:8080/", scheme="http", host="localhost:8080"))

    def test_configured_list_and_junk(self):
        self.assertTrue(allowed("http://tailnet-box:8080", scheme="http", host="10.0.0.5", extra=["http://tailnet-box:8080/"]))
        self.assertFalse(allowed("null", scheme="http", host="10.0.0.5"))
        self.assertFalse(allowed("file://x", scheme="http", host="10.0.0.5"))
        self.assertTrue(allowed("http://[::1]:8080", scheme="http", host="[::1]:8080"))


if __name__ == "__main__":
    unittest.main()
