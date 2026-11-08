"""Exercise verified SNI, bidirectional upgrade bytes and failed-origin behavior."""
import asyncio
from pathlib import Path
import ssl
import subprocess
import tempfile
import unittest

from ingress_bridge import IngressBridge


class BridgeTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.cert, self.key = root / 'cert.pem', root / 'key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(self.key), '-out', str(self.cert), '-days', '1',
                        '-subj', '/CN=secure.vendistri.com', '-addext',
                        'subjectAltName=DNS:secure.vendistri.com'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        self.server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.server_context.load_cert_chain(self.cert, self.key)
        self.client_context = ssl.create_default_context(cafile=str(self.cert))
        self.servers = []

    async def asyncTearDown(self):
        for server in reversed(self.servers):
            server.close()
            await server.wait_closed()

    async def start(self, handler, context=None):
        server = await asyncio.start_server(handler, '127.0.0.1', 0, ssl=context)
        self.servers.append(server)
        return server.sockets[0].getsockname()[1]

    async def test_hostname_verified_origin_preserves_host_query_and_response(self):
        seen = []
        async def origin(reader, writer):
            seen.append(await reader.readuntil(b'\r\n\r\n'))
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nokay')
            await writer.drain()
            writer.close()
        upstream_port = await self.start(origin, self.server_context)
        bridge = IngressBridge('127.0.0.1', 'secure.vendistri.com', upstream_port, self.client_context)
        port = await self.start(bridge.handle)
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        request = b'GET /path?original=yes HTTP/1.1\r\nHost: www.vendistri.com\r\n\r\n'
        writer.write(request); await writer.drain()
        result = await asyncio.wait_for(reader.read(), 5)
        self.assertEqual(seen, [request])
        self.assertTrue(result.endswith(b'okay'))
        writer.close(); await writer.wait_closed()

    async def test_websocket_upgrade_and_binary_bytes_are_bidirectional(self):
        async def origin(reader, writer):
            await reader.readuntil(b'\r\n\r\n')
            writer.write(b'HTTP/1.1 101 Switching Protocols\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n')
            await writer.drain()
            payload = await reader.readexactly(5)
            writer.write(payload); await writer.drain()
            writer.close()
        upstream_port = await self.start(origin, self.server_context)
        bridge = IngressBridge('127.0.0.1', 'secure.vendistri.com', upstream_port, self.client_context)
        port = await self.start(bridge.handle)
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        writer.write(b'GET /ws/ HTTP/1.1\r\nHost: secure.vendistri.com\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n')
        await writer.drain()
        self.assertIn(b'101', await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 5))
        writer.write(b'\x00\x01abc'); await writer.drain()
        self.assertEqual(await asyncio.wait_for(reader.readexactly(5), 5), b'\x00\x01abc')
        writer.close(); await writer.wait_closed()

    async def test_wrong_certificate_hostname_fails_closed(self):
        async def origin(reader, writer):
            writer.close()
        upstream_port = await self.start(origin, self.server_context)
        bridge = IngressBridge('127.0.0.1', 'wrong.vendistri.com', upstream_port, self.client_context)
        port = await self.start(bridge.handle)
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        writer.write(b'GET / HTTP/1.1\r\nHost: secure.vendistri.com\r\n\r\n'); await writer.drain()
        self.assertIn(b'502', await asyncio.wait_for(reader.read(), 5))
        writer.close(); await writer.wait_closed()


if __name__ == '__main__':
    unittest.main()
