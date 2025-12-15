"""Test script to check speaker diarization support"""
from dashscope.audio.asr import Recognition
import dashscope
from pathlib import Path

# Set API key
dashscope.api_key = "sk-d086548cbf5545c29159fb5bffb2e9e1"

# Test with a short audio segment
test_audio = Path("/var/folders/1z/_svrr3bj5_b245g37xym59840000gn/T/asr_segments_79angg71/segment_0000.mp3")

print("Testing speaker diarization with paraformer-realtime-v2...")

recognizer = Recognition(
    model='paraformer-realtime-v2',
    format='mp3',
    sample_rate=16000,
    callback=None
)

# Test with diarization enabled
result = recognizer.call(
    file=str(test_audio.absolute()),
    diarization_enabled=True,
    speaker_count=2  # Expecting 2 speakers in the video
)

if result.status_code == 200:
    print("\n✓ API call successful!")
    print(f"\nOutput structure:")
    import json
    print(json.dumps(result.output, indent=2, ensure_ascii=False)[:2000])

    # Check if speaker_id is present
    if 'sentence' in result.output:
        sentences = result.output['sentence']
        if sentences and len(sentences) > 0:
            first_sentence = sentences[0]
            print(f"\nFirst sentence speaker_id: {first_sentence.get('speaker_id')}")
            if first_sentence.get('speaker_id') is not None:
                print("✓ Speaker diarization is working!")
            else:
                print("✗ Speaker diarization returned null")
else:
    print(f"✗ API call failed: {result.status_code}")
    print(result)
