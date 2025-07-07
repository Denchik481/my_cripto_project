import boto3
import os

def get_s3_client(endpoint=None, access_key=None, secret_key=None):
    return boto3.client(
        's3',
        endpoint_url=endpoint or os.getenv('S3_ENDPOINT', 'http://localhost:9000'),
        aws_access_key_id=access_key or os.getenv('S3_ACCESS_KEY', 'minioadmin'),
        aws_secret_access_key=secret_key or os.getenv('S3_SECRET_KEY', 'minioadmin')
    )

def ensure_bucket_exists(s3, bucket):
    buckets = [b['Name'] for b in s3.list_buckets()['Buckets']]
    if bucket not in buckets:
        s3.create_bucket(Bucket=bucket)

def upload_to_s3(local_path, bucket, key, s3=None):
    if s3 is None:
        s3 = get_s3_client()
    ensure_bucket_exists(s3, bucket)
    s3.upload_file(Filename=local_path, Bucket=bucket, Key=key)