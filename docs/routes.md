# Routes

Routes are defined in json files under the `files/routes` and `files/scripts` directories. Any route files under the `files/scripts` directory must be named with the `routes.json` postfix, e.g.`http_routes.json`. Each route file must include an array of objects, with each object defining an individual route.

## Route definitions
### Generic route keys
* `protocol`: The protocol type for the route (`http`, `dns`, `http_middleware`, `dns_middleware`, `ssl_middleware`). Depending on the protocol selected additional route keys will need to be defined.
* `route`: *Optional* The regex to match on for the route, a descriptor without a route will match *all* routes
* `action`: A dictionary defining the protocol specific route keys
* `sort_index`: *Optional* The key for sorting routes. **Default** If the route file filename begins with an integer, e.g. `50_http_routes.json`, the integer will be used for the `sort_index` of all routes which do not define an explicit `sort_index`, otherwise a `sort_index` of 99 is used.
* `comment`: *Optional* A comment for the route

### HTTP routes keys

* `handler`: The handler of the http response (`serve`, `script`, `raw` or `forward`)
* `headers`: *Optional* A dictionary of HTTP headers to return with the request
* `replace`: *Optional* An array of replacement dictionaries with keys `pattern` a regex to match, and `replacement` the value to replace with. `replacement` can include default placeholders (`{hostname}`, `{port}`, `{path}`, `{scheme}`) or regex groups

#### `serve` handler keys
  * `path`: The path to a resource to render within the `files` directory

#### `script` handler keys
  * `path`: The path to a resource to render within the `files` directory
  * `base`: *Optional* The base of the path being requested, everything after the base will be passed to the resource.
  * `rewrite`: *Optional* Regular expression to remap the path passed to the resource.

#### `raw` handler keys
  * `code`: An HTTP code to return
  * `body`: *Optional* The body text to return with the given `code`

#### `forward` handler keys
  * `destination`: A URL to which to forward the HTTP request
  * `recreate_url`: *Optional* Whether to recreate the querystring for the `forward` url, or use the `forward` url as is. **Default** True
  * `request_headers`: *Optional* Additional headers to send with the HTTP request. **Default** None.


### DNS route keys

* `type`: *Optional* The type of the dns request to process, e.g. `A`, `AAAA`, `CNAME`, etc.
* `class`: *Optional* The class of the dns request to process **Default** `IN`
* `record`: *Optional* The record type to respond with **Default** Same as the request type
* `ttl`: *Optional* The TTL of the response **Default** 60
* `random`: *Optional* If more than response is generated, choose a random response instead of sending all of them **Default** false

Route must include one of:
* `response`: The literal response value to return
* `script`: A path to a script within the `files` directory to generate the response
  * `args`: Additional arguments to be passed to the script function
  * `kwargs`: Additional keywork arguments to be passes to the script function

### Middleware routes keys

* `module`: The path to the python module which implements the middleware
* `function`: The function in the python module which implements the middleware
* `args`: Additional arguments to be passed to the middleware function
* `kwargs`: Additional keywork arguments to be passes to the middleware function
