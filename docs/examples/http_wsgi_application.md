## Serve a local copy of httpbin.org
`routes.json`
```json
[
  {
    "protocol" : "http",
    "route" : "/httpbin/.*",
    "action" : {
      "handler" : "script",
      "path" : "./scripts/httpbin.py",
      "base" : "/httpbin"
    }
  }
]
```

`./scripts/httpbin.py`
```python
import httpbin

from twisted.internet import reactor
from twisted.web.wsgi import WSGIResource


def get_resource(request):
    return WSGIResource(reactor, reactor.getThreadPool(), httpbin.app)
```