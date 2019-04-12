#!/usr/bin/env python
import argparse
import datetime as dt
import json
import logging as log
import os
import shutil
import sys
import time
from glob import glob
from subprocess import STDOUT, CalledProcessError, check_output

import boto3
from boto3.s3.transfer import S3Transfer
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway


# Helper function to get the script dir
def get_script_path(some_file=None):
    script_directory = os.path.dirname(os.path.realpath(sys.argv[0]))
    if some_file is None:
        # Return just app dir
        return script_directory
    else:
        # Return full file path to specified file, as if it was in app dir
        return os.path.join(script_directory, some_file)


# Set logging level to debug
log.basicConfig(
    level=log.INFO, format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s"
)

# Parse arguments
parser = argparse.ArgumentParser(description="Backup PostgreSQL database")
parser.add_argument(
    "-c",
    "--conf-file",
    type=str,
    required=False,
    default=get_script_path("conf.json"),
    help="default conf.json",
)
parser.add_argument(
    "-l",
    "--log-level",
    type=str,
    required=False,
    default="info",
    help="Log level (default: info [critical, error, warning, info, debug])",
)


# Switches the logging level, depending on the input
def log_level_switch(log_level):
    return {
        "critical": log.CRITICAL,
        "error": log.ERROR,
        "warning": log.WARNING,
        "info": log.INFO,
        "debug": log.DEBUG,
    }[log_level]


# Retention
def delete_old_backups(backup_root_dir, keep_count):

    log.info(f"Retention is enabled, checking for old dirs")
    # get all entries in the directory
    backup_dirs = [
        os.path.join(backup_root_dir, dir_name)
        for dir_name in os.listdir(backup_root_dir)
        if os.path.isdir(os.path.join(backup_root_dir, dir_name))
    ]
    dir_count = len(backup_dirs)
    # Check if there are more directories than we need to keep
    if dir_count > keep_count:
        log.info(f"Backup directory has {dir_count} dirs. Starting cleanup.")
        # Sort directories by modified time
        backup_dirs.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        # Get directories to be removed
        old_backup_dirs = backup_dirs[keep_count:]
        log.info(f"Following directories will be removed: {old_backup_dirs}")
        # For every directory we need to remove
        for d in old_backup_dirs:
            # Remove it
            shutil.rmtree(d, ignore_errors=True)
            log.info(f"Following directory has been removed: '{d}'")
    else:
        log.info(
            f"Backup directory has {dir_count} dirs. Not enough for cleanup to do anything."
        )


# Read JSON file and returns the loaded dict
def get_json_conf(json_file):
    try:
        log.info(f'Reading conf file "{json_file}"')
        with open(json_file, "r") as f:
            configuration = json.load(f)
    except Exception as e:
        log.error(f"Could not read the file: {e}")
        sys.exit(1)

    log.debug(f'Read conf "{json.dumps(configuration)}"')
    return configuration


# Actual backup
def run_job(configuration):

    name = configuration["name"]
    job_backup_dir = configuration["output_dir"]
    dump_bin = configuration["dump_bin"]
    host = configuration["host"]
    db = configuration["db"]
    db_user = configuration["user"]
    db_pass = configuration["password"]
    dump_type = configuration["type"]
    compression = configuration["compression"]
    compression_with_pigz = configuration["compression_with_pigz"]

    create_dir_cmd = f"mkdir -p {job_backup_dir}"

    # Construct dump options string
    dump_opts_args = []
    if dump_type == "schema":
        dump_opts_args.append("--schema-only")
    if dump_type == "data":
        dump_opts_args.append("--data-only")
    dump_opts = " ".join(dump_opts_args)

    # Construct dump connection string
    db_connect_conf_args = []
    if host != "":
        db_connect_conf_args.append(f"-h {host}")
    if db_user != "":
        db_connect_conf_args.append(f"-U {db_user}")
    if db_pass != "":
        db_connect_conf_args.append(f"-p {db_pass}")
    db_connect_conf_args.append(f"-d {db}")
    db_connect_conf = " ".join(db_connect_conf_args)

    # Output file path string
    filename = f"{name}.sql"
    output = f"{job_backup_dir}/{filename}"

    # Construct dump command string
    db_dump_cmd = f"{dump_bin} {db_connect_conf} {dump_opts} > {output}"

    job_start_time = time.time()
    try:
        # Create dir
        log.info(f"Running dump for job: {configuration['name']}")
        log.info(f"Creating dump directory: {job_backup_dir}")
        log.debug(f"Creating dump directory: [{create_dir_cmd}]")
        check_output(create_dir_cmd, stderr=STDOUT, shell=True)
        # Dump
        dump_start_time = time.time()
        log.info(f"Creating dump file: '{output}'")
        log.debug(f"Creating dump file cmd: [{db_dump_cmd}]")
        check_output(db_dump_cmd, stderr=STDOUT, shell=True)
        dump_size = os.stat(output).st_size
        dump_duration = round((time.time() - dump_start_time) * 1000)
        log.info(
            f"Finished creating dump file. "
            f"Size: {dump_size} bytes. "
            f"Duration: {dump_duration} ms"
        )
        compressed_size = None
        compression_duration = None
        # Compression
        if compression:
            if compression_with_pigz:
                compression_cmd = f"pigz {output}"
            else:
                compression_cmd = f"gzip {output}"
            compression_start_time = time.time()
            log.info(f"Compressing file: '{output}'")
            log.debug(f"Compressing file cmd: [{compression_cmd}]")
            check_output(compression_cmd, stderr=STDOUT, shell=True)
            compressed_size = os.stat(f"{output}.gz").st_size
            compression_duration = round((time.time() - compression_start_time) * 1000)
            log.info(
                f"Finished compressing file. "
                f"Size: {compressed_size} bytes. "
                f"Duration: {compression_duration} ms"
            )

        stats = dict(
            name=name,
            duration_dump=dump_duration,
            duration_compression=compression_duration,
            size_dump=dump_size,
            size_compressed=compressed_size,
        )
        return stats
    except CalledProcessError as e:
        log.error(
            f"Backup job has failed after {round((time.time() - job_start_time)*1000)} ms. "
            f"Error: {e.output}"
        )
        raise RuntimeError(f"Quitting due to previous errors")


# Push registry to prometheus
def push_to_prometheus(prometheus_host, prometheus_job, registry):
    try:
        log.info(
            f'Sending data to Prometheus host: "{prometheus_host}", job: "{prometheus_job}"'
        )
        start_time = time.time()
        push_to_gateway(prometheus_host, job=prometheus_job, registry=registry)
        duration = time.time() - start_time
        log.info(
            f"Successfully sent data to Prometheus. Time taken: {duration} seconds"
        )
    except Exception as e:
        raise Exception(f"Failed to send data to Prometheus: {e}")


# Upload to AWS s3
def upload_to_aws(configuration, backup_dir):

    access_key = configuration["access_key"]
    secret_key = configuration["secret_key"]
    bucket_dir_name = f"{configuration['path']}/{os.path.basename(backup_dir)}"
    bucket_name = configuration["bucket"]

    upload_start_time = time.time()
    try:
        log.info(f"Running AWS upload for '{backup_dir}'")
        client = boto3.client(
            "s3", aws_access_key_id=access_key, aws_secret_access_key=secret_key
        )

        # Get files we want to transfer
        uncompressed_files = glob(f"{backup_dir}/*.sql")
        compressed_files = glob(f"{backup_dir}/*.gz")

        files_to_transfer = uncompressed_files + compressed_files
        if files_to_transfer:
            transfer = S3Transfer(client)
            for file in files_to_transfer:
                s3_file = f"{bucket_dir_name}/{os.path.basename(file)}"
                log.info(
                    f'Uploading to s3. Bucket: "{bucket_name}", Source: "{file}", Destination: "{s3_file}"'
                )
                transfer.upload_file(file, bucket_name, s3_file)
        else:
            log.warning("Did not find any *.sql or *.gz files in '{backup_dir}'")

        upload_duration = round((time.time() - upload_start_time) * 1000)
        log.info(f"Successfully uploaded to s3. Time taken: {upload_duration} ms")
    except Exception as e:
        upload_duration = round((time.time() - upload_start_time) * 1000)
        raise Exception(
            f"Upload to s3 has failed after {upload_duration} ms. Error: {e}"
        )

    stats = dict(upload_duration=upload_duration)
    return stats


# App
if __name__ == "__main__":

    args = parser.parse_args()
    log.debug(f'App args "{args}"')

    app_conf = get_json_conf(args.conf_file)
    log.basicConfig(level=log_level_switch(args.log_level))

    backup_db_conf = app_conf["database"]
    backup_conf = app_conf["backup"]

    backup_dir = backup_conf["output_dir"]
    assert os.path.isdir(backup_dir), f"Directory {backup_dir} can't be found."

    ts = dt.datetime.now()
    output_dir = os.path.abspath(
        os.path.join(backup_dir, f"{ts.strftime('%Y-%m-%d_%H%M%S')}")
    )

    job_stats = []
    for job in backup_conf["jobs"]:
        if job["enabled"]:
            job_conf = dict(
                host=backup_db_conf["host"],
                db=backup_db_conf["db"],
                user=backup_db_conf["user"],
                password=backup_db_conf["password"],
                dump_bin=backup_conf["dump_bin"]
                if "dump_bin" in backup_conf
                else "pg_dump",
                output_dir=output_dir,
                name=job["name"],
                type=job["type"],
                compression=job["compression"],
                compression_with_pigz=job["compression_with_pigz"]
                if "compression_with_pigz" in job
                else False,
            )
            log.debug(f"Job params: {job_conf}")
            # Run backup job
            try:
                stats = run_job(job_conf)
                job_stats.append(stats)
            except AssertionError as msg:
                log.error(msg)

    # Get AWS config, if it exists
    aws_enabled = False
    if "aws" in app_conf:
        aws_conf = app_conf["aws"]
        aws_enabled = aws_conf["enabled"]

    upload_stats = []
    if aws_enabled:
        stats = upload_to_aws(app_conf["aws"], output_dir)
        upload_stats.append(stats)
    else:
        log.info("Backup upload is disabled")

    # Cleanup, if configured
    if "keep_local_backups" in backup_conf:
        log.debug("Backup retention has been found in config")
        delete_old_backups(backup_dir, backup_conf["keep_local_backups"])

    if "prometheus" in app_conf:
        prometheus_conf = app_conf["prometheus"]
        log.debug("Prometheus gateway has been found in config")
        try:
            if prometheus_conf["enabled"]:
                log.info("Prometheus is enabled")
                # Prometheus init
                registry = CollectorRegistry()

                if job_stats:
                    log.debug("Found job_stats. Creating gauges")
                    g_size = Gauge(
                        "backup_size", "", ["backup_job", "action"], registry=registry
                    )
                    g_duration = Gauge(
                        "backup_duration",
                        "",
                        ["backup_job", "action"],
                        registry=registry,
                    )
                    for stat in job_stats:
                        log.debug(
                            f"Setting labels: [{stat['name']}, dump], value: [{stat['size_dump']}]"
                        )
                        g_size.labels(stat["name"], "dump").set(stat["size_dump"])

                        log.debug(
                            f"Setting labels: [{stat['name']}, gzip], value: [{stat['size_compressed']}]"
                        )
                        g_size.labels(stat["name"], "gzip").set(stat["size_compressed"])

                        log.debug(
                            f"Setting labels: [{stat['name']}, dump], value: [{stat['duration_dump']}]"
                        )
                        g_duration.labels(stat["name"], "dump").set(
                            stat["duration_dump"]
                        )

                        log.debug(
                            f"Setting labels: [{stat['name']}, gzip], value: [{stat['duration_compression']}]"
                        )
                        g_duration.labels(stat["name"], "gzip").set(
                            stat["duration_compression"]
                        )

                if upload_stats:
                    for stat in upload_stats:
                        log.debug(
                            f"Setting labels: [aws, upload], value: [{stat['upload_duration']}]"
                        )
                        g_duration.labels("aws", "upload").set(stat["upload_duration"])

                if upload_stats or job_stats:
                    log.info("Sending stats to prometheus gateway")
                    log.debug(
                        f"Prometheus pushgateway host '{prometheus_conf['host']}', job '{prometheus_conf['job']}'"
                    )
                    push_to_prometheus(
                        prometheus_conf["host"], prometheus_conf["job"], registry
                    )
                else:
                    log.error(
                        "Upload or Job stats not found! Nothing to send to prometheus."
                    )
            else:
                log.info("Prometheus is disabled, data will not be sent to prometheus")
        except Exception as e:
            log.info(f'Sending data to Prometheus has failed: "{e}"')
