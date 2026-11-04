import unittest
from app import write_commands

class Client:
    def __init__(self):
        self.sent = []
    async def write_gatt_char(self, uuid, data, response):
        self.sent.append(data[0])

class ReleasePriorityTests(unittest.IsolatedAsyncioTestCase):
    async def test_release_before_presence(self):
        client = Client()
        await write_commands(client, [1, 5], False)
        self.assertEqual(client.sent, [5, 1])

    async def test_emergency_stop_stays_first(self):
        client = Client()
        await write_commands(client, [6, 0, 5], False)
        self.assertEqual(client.sent, [6, 0, 5])
