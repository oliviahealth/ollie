import boto3
import os
from mypy_boto3_s3 import S3Client


def initialize_lightsail_s3_instance() -> S3Client:
    """
    Initialize an S3 client for Lightsail-related storage work.
    """
    return boto3.client(
        "s3",
        region_name=os.getenv("AWS_DEFAULT_REGION"),
        aws_access_key_id=os.getenv("AWS_S3_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_S3_SECRET_ACCESS_KEY"),
    )