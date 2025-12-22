"""
Audio generation result caching to avoid duplicate API requests
"""
import json
import hashlib
from pathlib import Path
from typing import Optional


class AudioCache:
    """Cache for TTS-generated audio files"""

    def __init__(self, cache_dir: Path = None):
        """
        Initialize audio cache

        Args:
            cache_dir: Directory to store cache metadata (default: output/audio_cache)
        """
        self.cache_dir = cache_dir or Path("output/audio_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "cache_index.json"
        self.cache_index = self._load_cache_index()

    def _load_cache_index(self) -> dict:
        """Load cache index from disk"""
        if self.cache_file.exists():
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_cache_index(self):
        """Save cache index to disk"""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache_index, f, ensure_ascii=False, indent=2)

    def _generate_cache_key(self, text: str, model: str, voices: dict) -> str:
        """
        Generate unique cache key for text + model + voice config

        Args:
            text: Input text
            model: TTS model name
            voices: Voice configuration dict

        Returns:
            Cache key (hash)
        """
        # Create deterministic hash from inputs
        cache_data = {
            "text": text,
            "model": model,
            "voices": voices
        }
        cache_str = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(cache_str.encode()).hexdigest()[:16]

    def get(self, text: str, model: str, voices: dict) -> Optional[Path]:
        """
        Get cached audio file path if exists

        Args:
            text: Input text
            model: TTS model name
            voices: Voice configuration dict

        Returns:
            Path to cached audio file if exists, None otherwise
        """
        cache_key = self._generate_cache_key(text, model, voices)

        if cache_key in self.cache_index:
            cached_path = Path(self.cache_index[cache_key]["file_path"])
            if cached_path.exists():
                print(f"✓ Cache hit: {cache_key[:8]}... → {cached_path.name}")
                return cached_path
            else:
                # Remove stale cache entry
                del self.cache_index[cache_key]
                self._save_cache_index()

        return None

    def set(self, text: str, model: str, voices: dict, audio_path: Path):
        """
        Store audio file in cache

        Args:
            text: Input text
            model: TTS model name
            voices: Voice configuration dict
            audio_path: Path to generated audio file
        """
        cache_key = self._generate_cache_key(text, model, voices)

        self.cache_index[cache_key] = {
            "file_path": str(audio_path),
            "text_preview": text[:100] + "..." if len(text) > 100 else text,
            "model": model,
            "voices": voices
        }

        self._save_cache_index()
        print(f"✓ Cached: {cache_key[:8]}... → {audio_path.name}")

    def clear(self):
        """Clear all cache entries"""
        self.cache_index = {}
        self._save_cache_index()
        print("✓ Cache cleared")

    def stats(self) -> dict:
        """Get cache statistics"""
        valid_entries = sum(
            1 for entry in self.cache_index.values()
            if Path(entry["file_path"]).exists()
        )

        return {
            "total_entries": len(self.cache_index),
            "valid_entries": valid_entries,
            "cache_dir": str(self.cache_dir)
        }
