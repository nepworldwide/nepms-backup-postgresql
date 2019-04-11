# nepms-backup-postgresql
```
WIP
```
## Configuration
### Example configuration
`app/conf.sample.json`
#### Use case
```
WIP
```
### Configuration docs
Configuration is in JSON and the script expects it to be in the same directory with name `conf.json`.
#### database (mandatory)
_Any unspecified setting, will be taken from default `.pgpass` file locations_
 
__`host`__ Optional. DNS/IP of the database connection. Example: `localhost`.

__`db`__ Optional. Name of the database connection.

__`user`__ Optional. User of the database connection.

__`password`__ Optional. User of the database connection.
#### prometheus (optional)
More info: https://github.com/prometheus/pushgateway.
```
WIP
```
## Logging
One can choose to enable different levels of log with optional `-l|--log-level <level>`.

Default is going to is `info` level, which will log everything that is "info" and more severe. i.e. warnings, errors etc
Available levels
- debug
- info
- warning
- error
- critical

Sample log with debug level
```
WIP
```

## Compatibility
Tested with PostgreSQL BDR 9.4

## TODO
- WIP

## Development
Pretty straight forward.
- Clone the repo
- ???
- Profit

This repo also includes pre-commit config in `.pre-commit-config.yaml`. If you know what it is and how to use it,
then you will also find useful `requirements-dev.txt`, which includes the packages you need to run pre-commit config included.

## License
MIT

Happy dumping!