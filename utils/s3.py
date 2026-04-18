import boto3
import os

s3 = None

def create_s3(region_name, access_key_id, secret_access_key):
    s3 = boto3.client(
        "s3",
        region_name=region_name,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )

    return s3