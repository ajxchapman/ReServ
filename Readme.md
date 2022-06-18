# ReServ

A set of programmable servers (currently HTTP/HTTPS and DNS) which allow configurable and scriptable responses to network requests.

Example uses:
* Use as a local DNS server to intercept and modify IoT device traffic.
* Use as an internet based DNS authority server to test 3rd party websites for SSRF, blind XSS and other vulnerabilities.

Features:
* Simple regex replacements and responses.
* Apply middlewares to all or matching requests (HTTP, SSL and DNS).
* Changes to, or the addition of new configuration files does not require a restart of the server.

Default configuration includes examples for DNS Rebinding attacks ([files/routes/30_dnsrebind.json](files/routes/30_dnsrebind.json) and [files/scripts/dnsrebind/dnsrebind.py](files/scripts/dnsrebind/dnsrebind.py)), slack alerting middleware ([files/scripts/slack_alert_middleware/](files/scripts/slack_alert_middleware/)) and responding to ACMEv2 dns-01 challenges ([files/routes/10_letsencrypt.json](files/routes/10_letsencrypt.json)).

# Usage
In order to start ReServ with the default configuration simply use the following command:
```bash
$ python3 reserv.py
```

Using Docker:
```bash
docker build --tag reserv .
docker run -d -v `pwd`/config.json:/src/reserv/config.json -v `pwd`/files:/srv/reserv/files/ -p 53:53/udp -p 53:53/tcp -p 80:80/tcp -p 443:443/tcp reserv
```

# [Getting Started](docs/gettingstarted.md)

See the [Getting Started](docs/gettingstarted.md) guide for setting up TLS, DNS glue records and more.

# Running Tests

```bash
python3 -m unittest discover
```