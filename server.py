import json
import os
import sys

from twisted.internet import error, reactor
from twisted.names import dns
from twisted.web import server

import servers.dns
import servers.http
import utils

# Make sure our working directory is sane
os.chdir(os.path.split(os.path.abspath(__file__))[0])

if __name__ == "__main__":
    service_count = 0
    for service in utils.get_config().get("services", []):
        try:
            protocol = service["protocol"]
            port = service["port"]
            interface = service.get("interface", "0.0.0.0")
        except KeyError:
            print("Service must define a 'port' and a 'protocol'")
            print(json.dumps(service, indent=4))
            sys.exit(1)
        else:
            try:
                if protocol == "http":
                    unknown_arguments = set(service.keys()).difference(["protocol", "port", "interface", "certificate", "key"])
                    if len(unknown_arguments):
                        raise Exception(f"Unknown arguments for service 'http': ", ", ".join(f"'{x}'" for x in unknown_arguments))

                    if "certificate" in service:
                        try:
                            context_factory = servers.http.SSLContextFactory(service["certificate"], service.get("key"))
                        except Exception as e:
                            raise Exception(f"Error starting HTTPS service: '{e}'")
                        else:
                            reactor.listenSSL(port, server.Site(servers.http.HTTPJsonResource()), context_factory, interface=interface)
                            print(f"Starting HTTPS service on port {port}/tcp")
                    else:
                        reactor.listenTCP(port, server.Site(servers.http.HTTPJsonResource()), interface=interface)
                        print(f"Starting HTTP service on port {port}/tcp")
                elif protocol == "dns":
                    unknown_arguments = set(service.keys()).difference(["protocol", "port", "interface"])
                    if len(unknown_arguments):
                        raise Exception(f"Unknown arguments for service 'dns': ", ", ".join(f"'{x}'" for x in unknown_arguments))

                    dns_server_factory = servers.dns.DNSJsonServerFactory()
                    reactor.listenUDP(port, dns.DNSDatagramProtocol(dns_server_factory), interface=interface)
                    reactor.listenTCP(port, dns_server_factory, interface=interface)
                    print(f"Starting DNS service on port {port}/tcp and {port}/udp")
                else:
                    raise Exception(f"Unknown protocol '{protocol}'")
                    
            except Exception as e:
                msg = str(e)
                if isinstance(e, error.CannotListenError):
                    msg = f"Cannot listen on '{interface}:{port}' address already in use"
                print(msg)
                print(json.dumps(service, indent=4))
                sys.exit(1)
            else:
                service_count += 1


    if service_count == 0:
        print("No services defined in 'config.json'")
        sys.exit(1)
    reactor.run()
