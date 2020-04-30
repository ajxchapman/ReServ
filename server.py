import logging
import logging.handlers
import os
import sys
import argparse

usage = """python3 server.py <command> [<args>]

Available commands are:
   start      Start the configured servers
   route      Test route matches
"""

# Make sure our working directory is sane
os.chdir(os.path.split(os.path.abspath(__file__))[0])
logger = logging.getLogger()

# Setup logginer
logger.setLevel(logging.DEBUG)
simple_formatter = logging.Formatter("%(levelname)s - %(message)s")
verbose_formatter = logging.Formatter("%(asctime)s [%(levelname)s] <%(module)s>: %(message)s")
stdout_handler = logging.StreamHandler()
stdout_handler.setLevel(logging.INFO)
stdout_handler.setFormatter(simple_formatter)
file_handler = logging.handlers.TimedRotatingFileHandler(os.path.join("files", "logs", "server.log"), when='D', interval=1, utc=True)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(verbose_formatter)
logger.addHandler(stdout_handler)
logger.addHandler(file_handler)


if __name__ == "__main__":
    cmdline = sys.argv[1::]
    parser = argparse.ArgumentParser(description="research servers", usage=usage)
    parser.add_argument("command", help="Subcommand to run")
    args = parser.parse_args(cmdline[0:1])
    cmdline.pop(0)

    if args.command == "start":
        from twisted.internet import reactor
        from twisted.names import dns

        import servers.dns
        import servers.http

        parser = argparse.ArgumentParser()
        parser.add_argument("--ipv4", type=str, default=None, help="the default ipv4 address to response with")
        parser.add_argument("--ipv6", type=str, default=None, help="the default ipv6 address to response with")
        parser.add_argument("domain_name", type=str, default=None, help="the root domain name for the DNS server")
        args = parser.parse_args(cmdline)

        dns_server_factory = servers.dns.DNSJsonServerFactory(args.domain_name, ipv4_address=args.ipv4, ipv6_address=args.ipv6)
        reactor.listenUDP(53, dns.DNSDatagramProtocol(dns_server_factory), interface="0.0.0.0")
        reactor.listenTCP(53, dns_server_factory, interface="0.0.0.0")
        logger.info("DNSJsonServerFactory listening on port 53/udp")
        logger.info("DNSJsonServerFactory listening on port 53/tcp")

        http_resource = servers.http.HTTPJsonResource(args.domain_name)
        reactor.listenTCP(80, servers.http.HTTPSite(http_resource), interface="0.0.0.0")
        logger.info("HTTPJsonResource listening on port 80/tcp")

        try:
            reactor.listenSSL(443, servers.http.HTTPSite(http_resource), servers.http.SSLContextFactory(), interface="0.0.0.0")
            logger.info("HTTPJsonResource listening on port 443/tcp")
        except:
            logger.exception("Unable to start TLS server")
        reactor.run()
    elif args.command == "route":
        from jsonroutes import JsonRoutes

        parser = argparse.ArgumentParser()
        parser.add_argument("--protocol", "-p", type=str, default=None, help="the route protocol to test [dns, http, dns_middleware, http_middleware, ssl_middleware]")
        parser.add_argument("--domain", "-d", type=str, default="example.com", help="the root domain name for this server")
        parser.add_argument("--full", "-f", default=False, action="store_true", help="show the full matching route definition")
        parser.add_argument("route", type=str, default=None, help="the route to match")
        args = parser.parse_args(cmdline)

        routes = JsonRoutes(protocol=args.protocol, domain=args.domain)
        route_files = sorted(routes.json_routes.keys(), key=routes.key)
        for i, route in enumerate(routes.get_descriptors(args.route)):
            route = route[0]
            # Get the file the route is defined in, this is a bit of a hack
            definition_file = None
            for x in route_files:
                if route in routes.json_routes[x]:
                    definition_file = x
                    break

            print("!" if i == 0 else " ", end="")
            if args.full:
                print("[{}] {}:\n\t{}".format(i, definition_file, repr(route)))
            else:
                print("[{}] {}: {}".format(i, definition_file, route["route"]))
    else:
        print("Unrecognized command '{}'".format(command), file=sys.stderr)
        parser.print_help()
        sys.exit(1)
