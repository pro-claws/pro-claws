"""Loopback HTTP/WebSocket byte bridge to a hostname-verified AWS TLS origin."""
import argparse
import asyncio
import logging
import ssl


class IngressBridge:
    def __init__(self, upstream, server_name, upstream_port=443, context=None, maximum=256):
        self.upstream, self.server_name, self.port = upstream, server_name, upstream_port
        self.context = context or ssl.create_default_context()
        if not self.context.check_hostname or self.context.verify_mode != ssl.CERT_REQUIRED:
            raise ValueError('Verified TLS and hostname checking are mandatory')
        self.maximum, self.active = maximum, 0

    async def handle(self, reader, writer):
        if self.active >= self.maximum:
            writer.write(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return
        self.active += 1
        upstream_writer = None
        tasks = []
        try:
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(self.upstream, self.port, ssl=self.context,
                                        server_hostname=self.server_name, limit=65536), 10)

            async def pump(source, target):
                while True:
                    block = await source.read(65536)
                    if not block:
                        return
                    target.write(block)
                    await target.drain()

            tasks = [asyncio.create_task(pump(reader, upstream_writer)),
                     asyncio.create_task(pump(upstream_reader, writer))]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except (OSError, asyncio.TimeoutError) as error:
            # Do not log request paths, headers, cookies, bodies or exception URLs.
            logging.warning('AWS ingress connection failed: %s', type(error).__name__)
            if upstream_writer is None:
                writer.write(b'HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
                await writer.drain()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for connection in (upstream_writer, writer):
                if connection is not None:
                    connection.close()
                    try:
                        await connection.wait_closed()
                    except OSError:
                        pass
            self.active -= 1


async def main(args):
    if not args.upstream.endswith('.elb.amazonaws.com'):
        raise ValueError('Only the reviewed AWS load-balancer DNS origin is supported')
    bridge = IngressBridge(args.upstream, args.server_name)
    server = await asyncio.start_server(bridge.handle, '127.0.0.1', args.port, limit=65536)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', required=True)
    parser.add_argument('--server-name', default='secure.vendistri.com')
    parser.add_argument('--port', type=int, default=18080)
    asyncio.run(main(parser.parse_args()))
