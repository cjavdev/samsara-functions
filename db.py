import boto3
import os
import json
import pathlib
from typing import Optional, Dict, Any, List


class LocalStorageClient:
    """A local file system client that mimics the boto3 S3 client interface."""

    def __init__(self, base_dir: str = "storage"):
        self.base_dir = pathlib.Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

    def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str) -> Dict[str, Any]:
        """Store an object in the local file system."""
        file_path = self.base_dir / Key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(Body)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def get_object(self, Bucket: str, Key: str) -> Dict[str, Any]:
        """Retrieve an object from the local file system."""
        file_path = self.base_dir / Key
        if not file_path.exists():
            raise self.exceptions.NoSuchKey(f"No such key: {Key}")

        class ResponseBody:
            def __init__(self, file_path):
                self.file_path = file_path

            def read(self):
                return self.file_path.read_bytes()

        return {
            "Body": ResponseBody(file_path),
            "ContentType": "application/json"
        }

    def delete_object(self, Bucket: str, Key: str) -> Dict[str, Any]:
        """Delete an object from the local file system."""
        file_path = self.base_dir / Key
        if file_path.exists():
            file_path.unlink()
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}

    def list_objects_v2(self, Bucket: str, Prefix: str) -> Dict[str, List[Dict[str, str]]]:
        """List objects in the local file system."""
        prefix_path = self.base_dir / Prefix
        if not prefix_path.exists():
            return {"Contents": []}

        contents = []
        for file_path in prefix_path.rglob("*"):
            if file_path.is_file():
                contents.append({
                    "Key": str(file_path.relative_to(self.base_dir))
                })
        return {"Contents": contents}

    class exceptions:
        class NoSuchKey(Exception):
            pass


def get_storage_client():
    """Get either an S3 client or a local storage client based on environment."""
    if "SamsaraFunctionName" in os.environ:
        sts = boto3.client("sts")
        res = sts.assume_role(
            RoleArn=os.environ["SamsaraFunctionExecRoleArn"],
            RoleSessionName=os.environ["SamsaraFunctionName"],
        )
        credentials = {
            "aws_access_key_id": res["Credentials"]["AccessKeyId"],
            "aws_secret_access_key": res["Credentials"]["SecretAccessKey"],
            "aws_session_token": res["Credentials"]["SessionToken"],
        }
        return boto3.client("s3", **credentials)
    else:
        return LocalStorageClient()


class DB:
    def __init__(self, name: str = ""):
        self.storage = get_storage_client()
        self.bucket = os.environ.get("SamsaraFunctionStorageName", "local")
        self.prefix = name

    def set(self, key: str, value: dict) -> dict:
        """Store a JSON value at the given key. Returns the stored value."""
        json_str = json.dumps(value, indent=2)
        self.storage.put_object(
            Bucket=self.bucket,
            Key=f"{self.prefix}/{key}",
            Body=json_str.encode('utf-8'),
            ContentType='application/json'
        )
        return value

    def get(self, key: str) -> Optional[dict]:
        """Retrieve a JSON value from the given key. Returns None if not found."""
        try:
            response = self.storage.get_object(Bucket=self.bucket, Key=f"{self.prefix}/{key}")
            json_str = response['Body'].read().decode('utf-8')
            return json.loads(json_str)
        except (self.storage.exceptions.NoSuchKey, FileNotFoundError):
            return None

    def delete(self, key: str) -> None:
        """Delete the value at the given key. Returns None."""
        try:
            self.storage.delete_object(Bucket=self.bucket, Key=f"{self.prefix}/{key}")
        except (self.storage.exceptions.NoSuchKey, FileNotFoundError):
            pass
        return None

    def list_keys(self) -> list[str]:
        """List all keys in the store."""
        response = self.storage.list_objects_v2(Bucket=self.bucket, Prefix=self.prefix)
        return [item['Key'].replace(self.prefix + "/", "") for item in response.get('Contents', [])]


def main(event, _):
    """Example usage of the DB class."""
    db = DB(name="demo")
    command = event.get("command", "set")
    key = event.get("key", "test_key")
    value = event.get("value", {"test": "value"})

    if command == "set":
        print("Setting", key, value)
        result = db.set(key, value)
        print(result)
        return result
    elif command == "get":
        print("Getting", key)
        result = db.get(key)
        print(result)
        return result
    elif command == "delete":
        print("Deleting", key)
        result = db.delete(key)
        print(result)
        return result
    elif command == "list":
        print("Listing keys")
        result = db.list_keys()
        print(result)
        return result
    else:
        raise ValueError(f"Unknown command: {command}")


if __name__ == "__main__":
    main(None, None)