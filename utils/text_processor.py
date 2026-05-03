"""Text preprocessing and segmentation module"""
import re
import json
from pathlib import Path
from typing import List, Dict, Any


class TextProcessor:
    def __init__(self, segment_duration_minutes: int = 10):
        """
        Initialize text processor

        Args:
            segment_duration_minutes: Duration of each segment in minutes
        """
        self.segment_duration_ms = segment_duration_minutes * 60 * 1000

    def extract_useful_fields(self, asr_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract only useful fields (text, speaker, timestamps) from ASR result

        Args:
            asr_result: Raw ASR result from Qwen3-ASR

        Returns:
            List of extracted segments
        """
        extracted = []

        # Handle Recognition API output format
        segments = asr_result.get("segments", [])

        for segment in segments:
            transcription = segment.get("transcription")

            # Skip if transcription is None or empty
            if not transcription:
                continue

            # Support both Recognition API ("sentence") and Transcription API ("sentences")
            sentences = transcription.get("sentence", []) or transcription.get("sentences", [])

            # Get segment timing offset
            segment_start_offset = segment.get("start_time_ms", 0)

            for sentence_data in sentences:
                # Extract text and timestamps
                text = sentence_data.get("text", "").strip()

                if not text:
                    continue

                # begin_time and end_time are in milliseconds relative to segment start
                begin_time = sentence_data.get("begin_time", 0)
                end_time = sentence_data.get("end_time", 0)

                # Add segment offset to get absolute timestamps
                absolute_begin = segment_start_offset + begin_time
                absolute_end = segment_start_offset + end_time

                # Get speaker if available
                speaker = sentence_data.get("speaker_id")
                if speaker is None:
                    speaker = "unknown"

                item = {
                    "text": text,
                    "speaker": str(speaker),
                    "begin_time": absolute_begin,
                    "end_time": absolute_end,
                }
                extracted.append(item)

        return extracted

    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text using regex

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)

        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s.,!?;:\'"()-]', '', text)

        # Trim whitespace
        text = text.strip()

        return text

    def segment_by_time(
        self,
        extracted_items: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Segment extracted items by time duration

        Args:
            extracted_items: List of extracted ASR items

        Returns:
            List of segments, each segment is a list of items
        """
        if not extracted_items:
            return []

        segments = []
        current_segment = []
        segment_start_time = extracted_items[0]["begin_time"]

        for item in extracted_items:
            # Check if we should start a new segment
            if item["begin_time"] - segment_start_time >= self.segment_duration_ms:
                if current_segment:
                    segments.append(current_segment)
                current_segment = [item]
                segment_start_time = item["begin_time"]
            else:
                current_segment.append(item)

        # Add the last segment
        if current_segment:
            segments.append(current_segment)

        print(f"Created {len(segments)} segments (each ~{self.segment_duration_ms/60000} minutes)")
        return segments

    def format_segment_for_translation(
        self,
        segment: List[Dict[str, Any]]
    ) -> str:
        """
        Format a segment for translation

        Args:
            segment: List of items in a segment

        Returns:
            Formatted text for translation
        """
        formatted_lines = []

        for item in segment:
            speaker = item.get("speaker", "unknown")
            text = item.get("text", "")

            if text:
                formatted_lines.append(f"[{speaker}]: {text}")

        return "\n".join(formatted_lines)

    def process_asr_result(
        self,
        asr_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Complete processing pipeline for ASR result

        Args:
            asr_result: Raw ASR result

        Returns:
            Processed result with segments
        """
        print("Extracting useful fields...")
        extracted = self.extract_useful_fields(asr_result)
        print(f"Extracted {len(extracted)} items")

        print("Segmenting by time...")
        segments = self.segment_by_time(extracted)

        # Format segments
        formatted_segments = []
        for i, segment in enumerate(segments):
            formatted_segments.append({
                "segment_id": i,
                "start_time_ms": segment[0]["begin_time"],
                "end_time_ms": segment[-1]["end_time"],
                "items": segment,
                "formatted_text": self.format_segment_for_translation(segment)
            })

        return {
            "total_segments": len(formatted_segments),
            "segments": formatted_segments
        }

    def save_processed_result(self, result: Dict[str, Any], output_path: Path):
        """Save processed result to JSON file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Processed result saved to: {output_path}")


if __name__ == "__main__":
    # Example usage
    import argparse

    parser = argparse.ArgumentParser(description="Process ASR results")
    parser.add_argument("input_file", help="Input ASR result JSON file")
    parser.add_argument("-o", "--output", help="Output processed JSON file")
    parser.add_argument(
        "-d", "--duration",
        type=int,
        default=10,
        help="Segment duration in minutes (default: 10)"
    )

    args = parser.parse_args()

    # Load ASR result
    with open(args.input_file, 'r', encoding='utf-8') as f:
        asr_result = json.load(f)

    # Process
    processor = TextProcessor(segment_duration_minutes=args.duration)
    processed = processor.process_asr_result(asr_result)

    # Save or print
    if args.output:
        processor.save_processed_result(processed, Path(args.output))
    else:
        print(json.dumps(processed, ensure_ascii=False, indent=2))
