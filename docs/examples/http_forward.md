## Forward HTTP paths to a remote server and rewrite the response
`routes.json`
```json
[
  {
    "protocol" : "http",
    "route" : "/example/.*",
    "action" : {
      "handler" : "forward",
      "destination" : "https://www.example.com/",
      "recreate_url" : false,
      "replace" : [
        {
          "pattern" : "[Ee]xample",
          "replacement" : "Whoot"
        }
      ]
    }
  }
]
```