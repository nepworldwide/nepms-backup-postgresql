# nepms-backup-postgresql
PostgreSQL backup script that creates full backup for configured database, different scenarios can be configured.
- Highly configurable
  - Specify dump binary to be used
  - File output location
  - Dump Data or Schema
- Optional retention period (by count of old backups)
- Optional compression with gzip or pigz
- Optional upload to AWS S3
- Optional metrics push to prometheus pushgateway
## Configuration
### Example configuration
`app/conf.sample.json`
### Configuration
Configuration is in JSON and the script expects it to be in the same directory with name `conf.json`.
Alternatively one can specify the config file with `-c | --config </path/file>`
#### database (mandatory)
_Any unspecified setting, will be taken from default `.pgpass` file locations_
 
__`host`__ Optional. DNS/IP of the database connection. Example: `localhost`.

__`db`__ Optional. Name of the database connection.

__`user`__ Optional. User of the database connection.

__`password`__ Optional. User of the database connection.
#### prometheus (optional)
More info: https://github.com/prometheus/pushgateway.

_All below keys are mandatory_

__`enabled`__   JSON Boolean type. The `prometheus` key dict can be configured, but disabled this way.

__`host`__  DNS/IP of the prometheus pushgateway. Example: `prometheus-pushgateway.pvc.com`.

__`job`__   Job title for prometheus pushgateway. Used in registry creation.
#### aws
_All below keys are mandatory_

__`enabled`__   JSON Boolean type. The `prometheus` key dict can be configured, but disabled this way.

__`bucket`__    AWS bucket name.

__`path`__    AWS path in bucket.

__`access_key`__    AWS access token.

__`secret_key`__    AWS secret key.
#### backup
__`dump_bin`__ Optional. Dump binary full file path. Defaults to `pg_dump`, which must be available in `$PATH`.

__`output_dir`__ Mandatory. Specify the output directory. Each run will have its own timestamped directory within.

__`keep_local_backups`__ Retention of how many latest backups to keep (including current)

__`jobs`__ Mandatory. JSON array of dicts. These dicts describe a backup job. See example.

__`jobs.name`__ Mandatory. Name for the backup job. This will later be used in prometheus push, if enabled.

__`jobs.type`__ Mandatory. See for more info below.

__`jobs.enabled`__ Mandatory. JSON Boolean type. Job can be configured, but disabled this way.

__`jobs.compression`__ Mandatory. JSON Boolean type. The dump for this job can be either enabled or disabled.

__`jobs.compression_with_pigz`__ Optional. JSON Boolean type. If set to true, then compression will be done with `pigz` (https://zlib.net/pigz/). If set to false or not present, will use `gzip`.
### jobs.type
Currently predefined and allowed string values are `schema` or `data`.
#### schema
Will use following dump options: ```--schema-only```
#### data
Will use following dump options: ```--data-only```
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
2019-04-12 15:58:13,299.299 INFO Reading conf file "/etc/nepms-backup-postgresql/mydb_db_conf.json"
2019-04-12 15:58:13,299.299 INFO Running dump for job: mydb_prod_db_schema
2019-04-12 15:58:13,300.300 INFO Creating dump directory: /data/db/backup/2019-04-12_155813
2019-04-12 15:58:13,315.315 INFO Creating dump file: '/data/db/backup/2019-04-12_155813/mydb_prod_db_schema.sql'
2019-04-12 15:58:13,453.453 INFO Finished creating dump file. Size: 35982 bytes. Duration: 138 ms
2019-04-12 15:58:13,453.453 INFO Compressing file: '/data/db/backup/2019-04-12_155813/mydb_prod_db_schema.sql'
2019-04-12 15:58:13,460.460 INFO Finished compressing file. Size: 4464 bytes. Duration: 7 ms
2019-04-12 15:58:13,461.461 INFO Running dump for job: mydb_prod_db_data
2019-04-12 15:58:13,461.461 INFO Creating dump directory: /data/db/backup/2019-04-12_155813
2019-04-12 15:58:13,465.465 INFO Creating dump file: '/data/db/backup/2019-04-12_155813/mydb_prod_db_data.sql'
2019-04-12 15:58:55,425.425 INFO Finished creating dump file. Size: 3116110309 bytes. Duration: 41960 ms
2019-04-12 15:58:55,425.425 INFO Compressing file: '/data/db/backup/2019-04-12_155813/mydb_prod_db_data.sql'
2019-04-12 15:59:08,244.244 INFO Finished compressing file. Size: 428239986 bytes. Duration: 12819 ms
2019-04-12 15:59:08,245.245 INFO Running AWS upload for '/data/db/backup/2019-04-12_155813'
2019-04-12 15:59:08,304.304 INFO Uploading to s3. Bucket: "mybucket", Source: "/data/db/backup/2019-04-12_155813/mydb_prod_db_schema.sql.gz", Destination: "mydb-db-prod/2019-04-12_155813/mydb_prod_db_schema.sql.gz"
2019-04-12 15:59:08,745.745 INFO Uploading to s3. Bucket: "mybucket", Source: "/data/db/backup/2019-04-12_155813/mydb_prod_db_data.sql.gz", Destination: "mydb-db-prod/2019-04-12_155813/mydb_prod_db_data.sql.gz"
2019-04-12 15:59:13,885.885 INFO Successfully uploaded to s3. Time taken: 5641 ms
2019-04-12 15:59:13,886.886 INFO Retention is enabled, checking for old dirs
2019-04-12 15:59:13,887.887 INFO Backup directory has 2 dirs. Starting cleanup.
2019-04-12 15:59:13,887.887 INFO Following directories will be removed: ['/data/db/backup/2019-04-12_154426']
2019-04-12 15:59:14,012.012 INFO Following directory has been removed: '/data/db/backup/2019-04-12_154426'
2019-04-12 15:59:14,012.012 INFO Prometheus is enabled
2019-04-12 15:59:14,013.013 INFO Sending stats to prometheus gateway
2019-04-12 15:59:14,013.013 INFO Sending data to Prometheus host: "prometheus-pushgateway.domain.com", job: "mydb_db_backup"
2019-04-12 15:59:14,038.038 INFO Successfully sent data to Prometheus. Time taken: 0.024816036224365234 seconds
```

## Compatibility
Tested with PostgreSQL BDR 9.4

## TODO
- Add schema include, exclude configurable
- Add schema.table include, exclude configurable
- Job specific custom options for chosen bin
- Job specific custom option override set job.type
- Test with newer releases

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