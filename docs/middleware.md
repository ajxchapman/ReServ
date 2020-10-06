# Middleware

## Default middleware
### Logging middleware

The logging middleware logs all DNS and HTTP requests processed by the server to `./files/logs/server.log`.

### Slack Alert middleware

The Slack Alert middleware sends slack messages when matching DNS or HTTP requests are processed by the server.

#### Keys
Adds the following keys to `http` and `dns` routes:

* `slack`: *Optional* If this value is `true` a slack message is sent when the route is processed. If this value is a string, a slack message is sent if the route target matches the string as a regular expression.

#### Configuration
Requires the `slack_webhook_url` configuration variable to be set in `config.json` e.g.
```
{
  "variables" : {
    "slack_webhook_url": "https://hooks.slack.com/services/xxx/yyy/zzz"
  }
}
```