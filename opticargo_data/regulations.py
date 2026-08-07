from __future__ import annotations
import os
from .config import dataset_root
from .io import load


def upload_regulations() -> int:
    endpoint=os.getenv("MINIO_ENDPOINT","").strip()
    access=os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER")
    secret=os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD")
    bucket=os.getenv("MINIO_DOCUMENTS_BUCKET","opticargo-documents")
    if not endpoint or not access or not secret:
        raise RuntimeError("MINIO_ENDPOINT and MinIO credentials are required")
    import boto3
    scheme="https" if os.getenv("MINIO_SECURE","false").lower()=="true" else "http"
    client=boto3.client("s3",endpoint_url=f"{scheme}://{endpoint}",aws_access_key_id=access,aws_secret_access_key=secret,region_name="us-east-1")
    root=dataset_root()/"regulations"; n=0
    for item in load("regulations"):
        path=root/item["filename"]
        key=f"regulations/competition/{item['filename']}"
        client.upload_file(str(path),bucket,key,ExtraArgs={"ContentType":"application/pdf","Metadata":{"opticargo-source":"competition-dataset"}})
        n += 1
    return n

if __name__ == "__main__":
    print(f"Uploaded {upload_regulations()} regulation files")
