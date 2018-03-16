# ResearchServers

A set of simple servers (currently HTTP/HTTPS and DNS) which allow configurable and scriptable responses to network requests.

Example uses:
* Use as a local DNS server to intercept and modify IoT device traffic.
* Use as an internet based DNS authority server to test 3rd party websites for SSRF, blind XSS and other vulnerabilities.

Features:
* Simple regex replacements and responses.
* Apply middlewares to all or matching requests (HTTP, SSL and DNS).
* Changes to, or the addition of new configuration files does not require a restart of the server.

Default configuration includes examples for DNS Rebinding attacks ([files/routes/30_dnsrebind.json](files/routes/30_dnsrebind.json)), alerting middleware ([files/routes/30_alert_middleware.json](files/routes/30_alert_middleware.json)) and responding to ACMEv2 dns-01 challenges ([files/routes/10_letsencrypt.json](files/routes/10_letsencrypt.json)).

# Usage
In order to start the servers use the following command:
```bash
$ python3 server.py <domain>
```

In order to enable HTTPS connections certificate and key files must be generated and stored at `files/keys/domain.crt` and `files/keys/domain.key` respectively.

# Basic Examples
## Redirect all DNS A and AAAA queries to a localhost
`dns_localhost.json`
```json
[
  {
    "protocol" : "dns",
    "route" : ".*",
    "type" : "A",
    "response" : "127.0.0.1"
  },
  {
    "protocol" : "dns",
    "route" : ".*",
    "type" : "AAAA",
    "response" : "::1"
  }
]
```

## Respond with a single HTTP page to all requests
`http_static.json`
```json
[
  {
    "protocol" : "http",
    "route" : "/.*",
    "path" : "/wwwroot/static.html"
  }
]
```

## Forward HTTP paths to a remote server and rewrite the response
`http_forward.json`
```json
[
  {
    "protocol" : "http",
    "route" : "/example/.*",
    "forward" : "https://www.example.com/",
    "recreate_url" : false,
    "replace" : [
      {
        "pattern" : "[Ee]xample",
        "replacement" : "Whoot"
      }
    ]
  }
]
```

## Serve a local copy of httpbin.org
`http_httpbin.json`
```json
[
  {
    "protocol" : "http",
    "route" : "/httpbin/.*",
    "path" : "./scripts/httpbin.py"
  }
]
```

## Arbitrary IPv4 address DNS response
`dns_ipv4response.json`
```json
{
  "protocol" : "dns",
  "route" : "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?).ip.{domain}",
  "type" : "A",
  "response" : "$1.$2.$3.$4"
}
```
