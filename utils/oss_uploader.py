"""Aliyun OSS file uploader for temporary audio storage"""
import oss2
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta


class OSSUploader:
    """Upload files to Aliyun OSS and get public URLs"""

    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        bucket_name: str,
        endpoint: str = "oss-cn-hangzhou.aliyuncs.com"
    ):
        """
        Initialize OSS uploader

        Args:
            access_key_id: OSS Access Key ID
            access_key_secret: OSS Access Key Secret
            bucket_name: OSS Bucket name
            endpoint: OSS endpoint (default: oss-cn-hangzhou.aliyuncs.com)
        """
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.bucket_name = bucket_name
        self.endpoint = endpoint

        # Create auth and bucket objects
        auth = oss2.Auth(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(auth, endpoint, bucket_name)

        print(f"✓ OSS uploader initialized: {bucket_name} @ {endpoint}")

    def upload_file(
        self,
        local_file: Path,
        object_name: Optional[str] = None,
        folder: str = "asr_temp"
    ) -> str:
        """
        Upload a file to OSS and return public URL

        Args:
            local_file: Local file path
            object_name: Object name in OSS (default: timestamp_filename)
            folder: Folder path in OSS (default: asr_temp)

        Returns:
            Public URL of uploaded file

        Raises:
            RuntimeError: If upload fails
        """
        if not local_file.exists():
            raise FileNotFoundError(f"Local file not found: {local_file}")

        # Generate object name with timestamp if not provided
        if object_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            object_name = f"{timestamp}_{local_file.name}"

        # Full object path with folder
        object_path = f"{folder}/{object_name}" if folder else object_name

        try:
            print(f"Uploading {local_file.name} to OSS...")

            # Upload file
            self.bucket.put_object_from_file(object_path, str(local_file))

            # Generate public URL (valid for 1 hour)
            url = self.bucket.sign_url('GET', object_path, 3600)

            print(f"✓ Uploaded to OSS: {object_path}")
            print(f"  URL: {url[:80]}...")

            return url

        except Exception as e:
            raise RuntimeError(f"Failed to upload file to OSS: {str(e)}")

    def delete_file(self, object_path: str):
        """
        Delete a file from OSS

        Args:
            object_path: Object path in OSS
        """
        try:
            self.bucket.delete_object(object_path)
            print(f"✓ Deleted from OSS: {object_path}")
        except Exception as e:
            print(f"⚠ Failed to delete {object_path}: {str(e)}")

    def upload_temp_file(
        self,
        local_file: Path,
        expire_hours: int = 24
    ) -> tuple[str, str]:
        """
        Upload a temporary file to OSS with auto-cleanup path

        Args:
            local_file: Local file path
            expire_hours: Hours until file should be deleted (for reference only)

        Returns:
            Tuple of (public_url, object_path)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        object_name = f"temp_{timestamp}_{local_file.name}"
        folder = "asr_temp"

        url = self.upload_file(local_file, object_name, folder)
        object_path = f"{folder}/{object_name}"

        return url, object_path


if __name__ == "__main__":
    # Example usage
    import argparse
    from config import Config

    parser = argparse.ArgumentParser(description="Upload file to Aliyun OSS")
    parser.add_argument("file", help="Local file to upload")
    parser.add_argument("-n", "--name", help="Object name in OSS (optional)")
    parser.add_argument("-f", "--folder", default="asr_temp", help="Folder in OSS")

    args = parser.parse_args()

    # Check OSS configuration
    if not all([
        Config.OSS_ACCESS_KEY_ID,
        Config.OSS_ACCESS_KEY_SECRET,
        Config.OSS_BUCKET_NAME
    ]):
        print("✗ Error: OSS configuration missing in .env file")
        print("  Required: OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_BUCKET_NAME")
        exit(1)

    try:
        uploader = OSSUploader(
            access_key_id=Config.OSS_ACCESS_KEY_ID,
            access_key_secret=Config.OSS_ACCESS_KEY_SECRET,
            bucket_name=Config.OSS_BUCKET_NAME,
            endpoint=Config.OSS_ENDPOINT
        )

        url = uploader.upload_file(
            Path(args.file),
            object_name=args.name,
            folder=args.folder
        )

        print(f"\n✓ Upload successful!")
        print(f"  URL: {url}")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        exit(1)
