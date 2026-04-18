import boto3

_s3 = None


def create_s3(region_name, access_key_id, secret_access_key):
    global _s3
    _s3 = boto3.client(
        "s3",
        region_name=region_name,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )
    return _s3


def get_s3():
    if _s3 is None:
        raise RuntimeError("S3 client has not been initialized")
    return _s3
