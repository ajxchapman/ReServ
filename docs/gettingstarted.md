This guide will help you get started using ReServ as the authoritative domain name server for a chosen domin name. In order to complete this guide you require a domain name on which to host ReServ.

## 1. Configuration

At a minimum `config.json` needs updating, setting the `variables.defaut_domain` value to the chosen domain name you intened to host ReServ on.

## 2. DNS glue records

In order to use ReServ as the Server of Authority (SOA) for the chosen domain name configured above, DNS glue records need to be configured, pointing to the IP address of the server hosting ReServ.

### Namecheap.com glue records

To configure DNS glue records on namecheap.com go to the domain management page, and select the "Advanced DNS" configuration. Add *two* nameservers, e.g. `ns1.example.com` and `ns2.example.com` (both can point to the same IP address), under the 'PERSONAL DNS SERVER' configuration:
![](/docs/images/namecheap_add_nameservers.png)

Once saved, go back to the main domain configuration, and set the 'NAMESERVERS' option to 'Custom DNS' and add the two nameservers configured above:
![](/docs/images/namecheap_configure_nameservers.png)

**Note**, it may take several hours for the glue records to propogate to nameservers across the internet.

For full instrustions on configuring nameservers on namecheap.com see https://www.namecheap.com/support/knowledgebase/article.aspx/768/10/how-do-i-register-personal-nameservers-for-my-domain

## 3. TLS certificates (optional)

To setup a TLS service certificates can be requested for free from https://letsencrypt.org. Using the `certbot` tool, a TLS certificate can be obtained:
```sh
$ certbot certonly --manual --preferred-challenges dns -d \*.example.com -d example.com
Plugins selected: Authenticator manual, Installer None
Cert is due for renewal, auto-renewing...
Renewing an existing certificate
Performing the following challenges:
dns-01 challenge for example.com
dns-01 challenge for example.com

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Please deploy a DNS TXT record under the name
_acme-challenge.example.com with the following value:

UoX3ewxSj_Xci1mw3aoftKJxJ5kf87wn9I1T6Hnumvo

Before continuing, verify the record is deployed.
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Press Enter to Continue

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Please deploy a DNS TXT record under the name
_acme-challenge.example.com with the following value:

yRdQ025g62FXmYe3VVLqIdAv48LiA67OxppZP0sR1MI

Before continuing, verify the record is deployed.
(This must be set up in addition to the previous challenges; do not remove,
replace, or undo the previous challenge tasks yet. Note that you might be
asked to create multiple distinct TXT records with the same name. This is
permitted by DNS standards.)

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Press Enter to Continue
Waiting for verification...
Cleaning up challenges

IMPORTANT NOTES:
 - Congratulations! Your certificate and chain have been saved at:
   /etc/letsencrypt/live/example.com/fullchain.pem
   Your key file has been saved at:
   /etc/letsencrypt/live/example.com/privkey.pem
```

At each prompt, configure the challenge response in `files/routes/10_letsencrypt.json`, for example the above challenge response would require the following configuration:
```json
{
    "protocol" : "dns",
    "route" : "_acme-challenge\\.{{default_domain}}",
    "type" : "TXT",
    "response" : ["UoX3ewxSj_Xci1mw3aoftKJxJ5kf87wn9I1T6Hnumvo", "yRdQ025g62FXmYe3VVLqIdAv48LiA67OxppZP0sR1MI"]
}
```

Configure a new service to in `config.json`:
```json
"services": [
...
    {
        "port": 443,
        "protocol": "http",
        "certificate": "/etc/letsencrypt/live/example.com/fullchain.pem",
        "key": "/etc/letsencrypt/live/example.com/key.pem"
    }
]
```

Finally restart ReServ for the changes to take effect.
