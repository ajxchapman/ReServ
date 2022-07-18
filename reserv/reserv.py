import argparse
import json
import os
import sys

from urllib.parse import urlparse

from twisted.internet import error, reactor
from twisted.names import dns


import jsonroutes
import servers.dns
import servers.http
import servers.ssl
import utils

class CommandException(Exception):
    def __init__(self, message, detail=None):
        self.detail = detail
        super().__init__(message)

class Service:
    def __init__(self, interface, port, protocol, factory, *args, factory_wrapper=None, **kwargs):
        self.interface = interface
        self.port = port
        self.protocol = protocol
        self.factory = factory
        self.factory_wrapper = factory_wrapper
        self.listener_args = args
        self.listener_kwargs = kwargs

    def wrap(self, factory):
        if self.factory_wrapper is None:
            return factory
        return self.factory_wrapper(factory)

    def listen(self, reactor):
        if self.protocol == "tcp":
            print(f"Starting {self.factory.proto} service on port {self.interface}:{self.port}/tcp")
            reactor.listenTCP(self.port, self.wrap(self.factory), *self.listener_args, interface=self.interface, **self.listener_kwargs)
        elif self.protocol == "tls":
            print(f"Starting TLS {self.factory.proto} service on port {self.interface}:{self.port}/tcp")
            reactor.listenSSL(self.port, self.wrap(self.factory), *self.listener_args, interface=self.interface, **self.listener_kwargs)
        elif self.protocol == "udp":
            print(f"Starting {self.factory.proto} service on port {self.interface}:{self.port}/udp")
            reactor.listenUDP(self.port, self.wrap(self.factory), *self.listener_args, interface=self.interface, **self.listener_kwargs)
        else:
            raise CommandException(f"Unknown protocol '{self.protocol}'")

    def responds_to(self, port, protocol):
        if self.port == port and self.protocol == protocol:
            return True
        return False

def make_services(config, routes, args):
    services = []
    
    variables = utils.get_variables(config)
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
            if protocol == "http":
                unknown_arguments = set(service.keys()).difference(["protocol", "port", "interface", "certificate", "key"])
                if len(unknown_arguments):
                    raise CommandException(f"Unknown arguments for service 'http': ", ", ".join(f"'{x}'" for x in unknown_arguments))

                if "certificate" in service:
                    try:
                        context_factory = servers.ssl.SSLContextFactory(variables, routes, args, service["certificate"], service.get("key"))
                    except Exception as e:
                        raise CommandException(f"Error starting HTTPS service: '{e}'")
                    else:
                        services.append(Service(interface, port, "tls", servers.http.HTTPJsonServerFactory(variables, routes, args), context_factory))
                else:
                    services.append(Service(interface, port, "tcp", servers.http.HTTPJsonServerFactory(variables, routes, args)))
            
            elif protocol == "dns":
                unknown_arguments = set(service.keys()).difference(["protocol", "port", "interface"])
                if len(unknown_arguments):
                    raise CommandException(f"Unknown arguments for service 'dns': ", ", ".join(f"'{x}'" for x in unknown_arguments))

                dns_server_factory = servers.dns.DNSJsonServerFactory(variables, routes, args)
                services.append(Service(interface, port, "udp", dns_server_factory, factory_wrapper=dns.DNSDatagramProtocol))
                services.append(Service(interface, port, "tcp", dns_server_factory))
            else:
                raise CommandException(f"Unknown protocol '{protocol}'")

    if len(services) == 0:
        raise CommandException("No services defined in 'config.json'")
    return services

def command_export(config, routes, args):
    services = make_services(config, routes, args)

    for uri in args.args:
        if not "://" in uri:
            uri = "dns://" + uri
        parsed_uri = urlparse(uri)

        # TODO: pull these lists from XXXJsonServerFactory classes
        port = parsed_uri.port or {"http" : 80, "https" : 443, "dns" : 53, "smtp" : 25}.get(parsed_uri.scheme)
        protocol = {"http" : "tcp", "https" : "tls", "dns" : "udp", "smtp" : "tcp"}.get(parsed_uri.scheme)

        
        service = None
        for s in services:
            if s.responds_to(port, protocol):
                service = s
                break

        if service is None:
            raise CommandException(f"No service for '{uri}")
        print(service.factory)

def command_serve(config, routes, args):
    for service in make_services(config, routes, args):
        try:
            service.listen(reactor)
        except error.CannotListenError as e:
            raise CommandException(f"Cannot listen on '{service.interface}:{service.port}' address already in use")
    reactor.run()


def dir_path(path):
    _path = os.path.abspath(path)
    if os.path.isdir(_path):
        return _path
    else:
        raise argparse.ArgumentTypeError(f"'{path}' is not a valid directory")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='sum the integers at the command line')
    parser.add_argument("--config", "-c", default=os.path.abspath(os.path.join(os.path.split(__file__)[0], "..", "config.json")), type=str)
    parser.add_argument("--files-root", "-f", default=os.path.abspath(os.path.join(os.path.split(__file__)[0], "..", "files")), type=dir_path)
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

    if args.command == "export":
        command_export(config, routes, args)
    else:
        command_serve(config, routes, args)

    
