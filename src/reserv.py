import argparse
import json
import os
import sys

from twisted.internet import error, reactor
from twisted.names import dns
from twisted.web import server

import jsonroutes
import servers.dns
import servers.http
import servers.ssl
import utils

class CommandException(Exception):
    def __init__(self, message, detail=None):
        self.detail = detail
        super().__init__(message)

def command_export(config, routes, args):
    for url in args.args:
        pass
        # route_descriptor, route_match = self.routes.get_descriptor(*request_parts, rfilter=lambda x: x.get("protocol") == "http")

def command_serve(config, routes, args):
    variables = utils.get_variables(config)
    service_count = 0
    for service in config.get("services", []):
        try:
            protocol = service["protocol"]
            port = service["port"]
            interface = service.get("interface", "0.0.0.0")
        except KeyError:
            raise CommandException(
                "Service must define a 'port' and a 'protocol'", 
                json.dumps(service, indent=4)
            )
        else:
            try:
                if protocol == "http":
                    unknown_arguments = set(service.keys()).difference(["protocol", "port", "interface", "certificate", "key"])
                    if len(unknown_arguments):
                        raise CommandException(f"Unknown arguments for service 'http': ", ", ".join(f"'{x}'" for x in unknown_arguments))

                    if "certificate" in service:
                        try:
                            context_factory = servers.ssl.SSLContextFactory(variables, routes, service["certificate"], service.get("key"))
                        except Exception as e:
                            raise CommandException(f"Error starting HTTPS service: '{e}'")
                        else:
                            reactor.listenSSL(port, server.Site(servers.http.HTTPJsonResource(variables, routes, args.files_root)), context_factory, interface=interface)
                            print(f"Starting HTTPS service on port {port}/tcp")
                    else:
                        reactor.listenTCP(port, server.Site(servers.http.HTTPJsonResource(variables, routes, args.files_root)), interface=interface)
                        print(f"Starting HTTP service on port {port}/tcp")
                elif protocol == "dns":
                    unknown_arguments = set(service.keys()).difference(["protocol", "port", "interface"])
                    if len(unknown_arguments):
                        raise CommandException(f"Unknown arguments for service 'dns': ", ", ".join(f"'{x}'" for x in unknown_arguments))

                    dns_server_factory = servers.dns.DNSJsonServerFactory(variables, routes)
                    reactor.listenUDP(port, dns.DNSDatagramProtocol(dns_server_factory), interface=interface)
                    reactor.listenTCP(port, dns_server_factory, interface=interface)
                    print(f"Starting DNS service on port {port}/tcp and {port}/udp")
                else:
                    raise CommandException(f"Unknown protocol '{protocol}'")       
            except error.CannotListenError as e:
                raise CommandException(
                    f"Cannot listen on '{interface}:{port}' address already in use",
                    json.dumps(service, indent=4)
                )
            else:
                service_count += 1

    if service_count == 0:
        raise CommandException("No services defined in 'config.json'")
    reactor.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='sum the integers at the command line')
    parser.add_argument("--config", "-c", default=os.path.abspath(os.path.join(os.path.split(__file__)[0], "..", "config.json")), type=str)
    parser.add_argument("--files-root", "-f", default=os.path.abspath(os.path.join(os.path.split(__file__)[0], "..", "files")), type=str)
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "export"])
    parser.add_argument("args", nargs="*")
    args = parser.parse_args()
    print(args)

    config = utils.get_config(args.config)
    routes = jsonroutes.JsonRoutes(
        os.path.join(args.files_root, "routes", "**", "*.json"), 
        os.path.join(args.files_root, "scripts", "**", "*routes.json"), 
        variables=utils.get_variables(config)
    )
    if args.command == "serve":
        command_serve(config, routes, args)

    
