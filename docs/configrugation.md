# Configuration

Configuration is read in json format from the `config.json` file. Configuration is split into several sections:

## Services

The services array defines the services and ports to run. Each service defines a `protocol` and a `port`, with HTTP services defining optional `certificate` and `key` options for when TLS is used.

## Variables

Variables definined in the configuration replace variable placeholders in defined routes. Variable place holders can be used in any route string values, and are defined with double handlbars, e.g. `{{variable}}`.

## Anthing else

Any other keys in the configuration object are made available to scripts via the `utils.get_configuration` function.