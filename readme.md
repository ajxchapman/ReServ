# ResearchServers

A set of simple servers (currently DNS and HTTP) which allow configurable and
scriptable responses to requests.

* Use as a local DNS server to intercept and modify IoT device traffic.
* Use as an internet based DNS authority server to test website for SSRF, blind
XSS and other vulnerabilities.

Changes to, or the addition of new configuration files does not require a restart
of the server.

# Examples
## Redirect all DNS A and AAAA queries to a localhost
`dns_localhost.json`
```json
[
  {
    "route" : ".*",
    "response" : "127.0.0.1"
  },
  {
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
    "route" : "/.*",
    "path" : "/static.html"
  }
]
```

## Forward HTTP paths to a remote server and rewrite the response
`http_forward.json`
```json
[
  {
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
    "route" : "/httpbin/.*",
    "path" : "./httpbin.py"
  }
]
```
