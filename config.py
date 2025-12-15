import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Base directories
    BASE_DIR = Path(__file__).parent
    OUTPUT_DIR = BASE_DIR / "output"
    DOWNLOADS_DIR = OUTPUT_DIR / "downloads"
    ASR_RESULTS_DIR = OUTPUT_DIR / "asr_results"
    TRANSLATIONS_DIR = OUTPUT_DIR / "translations"
    AUDIO_SEGMENTS_DIR = OUTPUT_DIR / "audio_segments"
    FINAL_DIR = OUTPUT_DIR / "final"

    # API Keys
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")  # Alibaba Cloud DashScope (for Qwen3-ASR)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Google Gemini (for translation & TTS)

    # Proxy settings (for accessing Google services in China)
    HTTP_PROXY = os.getenv("HTTP_PROXY")  # e.g., http://127.0.0.1:7890
    HTTPS_PROXY = os.getenv("HTTPS_PROXY")  # e.g., http://127.0.0.1:7890
    ALL_PROXY = os.getenv("ALL_PROXY")  # Alternative proxy setting

    # Processing settings
    SEGMENT_DURATION_MINUTES = int(os.getenv("SEGMENT_DURATION_MINUTES", "10"))
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "3"))
    SAVE_INTERMEDIATE_RESULTS = os.getenv("SAVE_INTERMEDIATE_RESULTS", "true").lower() == "true"

    # OSS settings (for uploading audio files to support speaker diarization)
    OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID")
    OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET")
    OSS_BUCKET_NAME = os.getenv("OSS_BUCKET_NAME")
    OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "oss-cn-hangzhou.aliyuncs.com")

    @classmethod
    def setup_proxy(cls):
        """Setup proxy environment variables for Google services"""
        if cls.HTTP_PROXY:
            os.environ['HTTP_PROXY'] = cls.HTTP_PROXY
            print(f"✓ HTTP_PROXY set: {cls.HTTP_PROXY}")

        if cls.HTTPS_PROXY:
            os.environ['HTTPS_PROXY'] = cls.HTTPS_PROXY
            print(f"✓ HTTPS_PROXY set: {cls.HTTPS_PROXY}")

        if cls.ALL_PROXY:
            os.environ['ALL_PROXY'] = cls.ALL_PROXY
            print(f"✓ ALL_PROXY set: {cls.ALL_PROXY}")

        if not (cls.HTTP_PROXY or cls.HTTPS_PROXY or cls.ALL_PROXY):
            print("⚠ Warning: No proxy configured. Google services may not be accessible in China.")
            print("  Set HTTP_PROXY or HTTPS_PROXY in .env file to use a proxy.")

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        missing = []

        if not cls.DASHSCOPE_API_KEY:
            missing.append("DASHSCOPE_API_KEY")
        if not cls.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Please copy .env.example to .env and fill in your API keys."
            )

    @classmethod
    def create_directories(cls):
        """Create necessary output directories"""
        for directory in [
            cls.DOWNLOADS_DIR,
            cls.ASR_RESULTS_DIR,
            cls.TRANSLATIONS_DIR,
            cls.AUDIO_SEGMENTS_DIR,
            cls.FINAL_DIR
        ]:
            directory.mkdir(parents=True, exist_ok=True)
