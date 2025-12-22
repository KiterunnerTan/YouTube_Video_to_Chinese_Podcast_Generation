"""
ASR Speaker Label Validation Engine

Detects semantic mismatches between speaker labels and content.
Provides general solution to validate speaker assignments across any content.
"""
import re
from typing import List, Dict, Any, Tuple
from collections import Counter


class SpeakerProfile:
    """Speaker communication pattern profile"""

    # Host patterns (typically asks questions, guides conversation, summarizes)
    HOST_INDICATORS = {
        # Question markers (very strong indicator)
        "question_marks": ["？", "?", "吗", "呢"],
        # Host transition phrases
        "transitions": ["那", "好的", "明白了", "我们", "你看看", "是吗"],
        # Host confirmation/follow-up (very strong host indicators)
        "confirmations": ["好嘞", "行", "明白", "懂了"],
        # Host seeking information
        "inquiry": ["怎么", "什么", "怎样", "哪个"],
    }

    # Guest patterns (typically provides analysis, detailed explanations, technical content)
    GUEST_INDICATORS = {
        # Analytical/expert opening markers (very strong indicator)
        "analytical": ["事实上", "实际上", "应该说", "我觉得", "所以你看"],
        # Technical content (very strong indicator)
        "technical": ["算力", "CPU", "GPU", "数据帧", "系统", "占比", "加速计算", "通用计算"],
        # Numbers and statistics (strong indicator)
        "data": ["百分比", "年", "亿", "万", "美元", "数据", "六年", "20年", "90%", "15%"],
        # Expert conclusion markers (strong indicator)
        "conclusions": ["因此", "最后", "总之", "结论", "剩下来"],
        # Guest providing detailed explanations
        "explanations": ["就是说", "就是", "对吧", "的话", "来说", "的是"],
    }

    def __init__(self):
        self.speaker_patterns = {}
        self.content_by_speaker = {}

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze full text to build speaker profiles

        Args:
            text: Full text with speaker markers (speaker_0: content, speaker_1: content)

        Returns:
            Analysis results with speaker profiles
        """
        self.content_by_speaker = self._extract_speaker_content(text)
        self.speaker_patterns = self._build_speaker_patterns(self.content_by_speaker)

        return {
            "speakers_found": list(self.content_by_speaker.keys()),
            "speaker_patterns": self.speaker_patterns,
            "speaker_roles": self._infer_speaker_roles(),
        }

    def _extract_speaker_content(self, text: str) -> Dict[str, str]:
        """Extract all content for each speaker"""
        content_by_speaker = {}

        for line in text.split('\n'):
            if not line.strip():
                continue

            match = re.match(r'^(speaker_\d+):\s*(.*)', line)
            if match:
                speaker, content = match.groups()
                if speaker not in content_by_speaker:
                    content_by_speaker[speaker] = []
                content_by_speaker[speaker].append(content)

        # Join all content per speaker
        return {
            speaker: '\n'.join(lines)
            for speaker, lines in content_by_speaker.items()
        }

    def _build_speaker_patterns(self, content_by_speaker: Dict[str, str]) -> Dict[str, Dict]:
        """Build communication pattern profiles for each speaker"""
        patterns = {}

        for speaker, content in content_by_speaker.items():
            patterns[speaker] = {
                "total_chars": len(content),
                "total_lines": content.count('\n') + 1,
                "avg_line_length": len(content) / (content.count('\n') + 1),
                "question_count": content.count('？') + content.count('?'),
                "pause_count": content.count('……'),
                "host_score": self._calculate_pattern_score(content, self.HOST_INDICATORS),
                "guest_score": self._calculate_pattern_score(content, self.GUEST_INDICATORS),
            }

        return patterns

    def _calculate_pattern_score(self, content: str, indicators: Dict[str, List[str]]) -> float:
        """Calculate how well content matches a pattern"""
        score = 0
        total_weight = 0

        for pattern_type, keywords in indicators.items():
            weight = 1.0 if pattern_type != "data" else 1.5  # Weight data patterns higher

            for keyword in keywords:
                count = content.count(keyword)
                score += count * weight
                total_weight += weight

        return score / max(total_weight, 1)

    def _infer_speaker_roles(self) -> Dict[str, str]:
        """Infer whether each speaker is host or guest"""
        roles = {}

        for speaker, patterns in self.speaker_patterns.items():
            host_score = patterns["host_score"]
            guest_score = patterns["guest_score"]

            if abs(host_score - guest_score) < 1.0:
                role = "ambiguous"
            elif host_score > guest_score:
                role = "host"
            else:
                role = "guest"

            roles[speaker] = {
                "role": role,
                "host_score": host_score,
                "guest_score": guest_score,
                "confidence": abs(host_score - guest_score),
            }

        return roles


class SegmentValidator:
    """Validates individual segments against speaker profile"""

    def __init__(self, profile: SpeakerProfile):
        self.profile = profile

    def validate_segment(self, segment_text: str) -> Dict[str, Any]:
        """
        Validate a segment's speaker labels

        Args:
            segment_text: Segment text with speaker markers

        Returns:
            Validation results with potential issues
        """
        issues = []
        segment_speakers = self._extract_speakers(segment_text)
        segment_content = self._extract_segment_content(segment_text)

        for speaker, content in segment_content.items():
            # Check if this speaker's content matches their inferred role
            validation = self._validate_speaker_content(speaker, content)

            if validation["mismatch_detected"]:
                issues.append({
                    "speaker": speaker,
                    "severity": validation["severity"],
                    "reason": validation["reason"],
                    "expected_speaker": validation["expected_speaker"],
                    "confidence": validation["confidence"],
                })

        return {
            "segment_id": self._extract_segment_id(segment_text),
            "speakers_in_segment": segment_speakers,
            "issues": issues,
            "is_valid": len(issues) == 0,
        }

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker IDs from segment"""
        speakers = set()
        for line in text.split('\n'):
            match = re.match(r'^(speaker_\d+):', line)
            if match:
                speakers.add(match.group(1))
        return sorted(list(speakers))

    def _extract_segment_content(self, text: str) -> Dict[str, str]:
        """Extract content for each speaker in segment"""
        content = {}
        for line in text.split('\n'):
            match = re.match(r'^(speaker_\d+):\s*(.*)', line)
            if match:
                speaker, text_content = match.groups()
                if speaker not in content:
                    content[speaker] = []
                content[speaker].append(text_content)

        return {
            speaker: '\n'.join(lines)
            for speaker, lines in content.items()
        }

    def _validate_speaker_content(self, speaker: str, content: str) -> Dict[str, Any]:
        """Validate if content matches speaker's expected role"""
        # Get speaker's inferred role from profile
        speaker_role_info = self.profile.speaker_patterns.get(
            speaker,
            {"host_score": 0, "guest_score": 0}
        )

        # Calculate this segment's pattern scores
        segment_host_score = self.profile._calculate_pattern_score(
            content, SpeakerProfile.HOST_INDICATORS
        )
        segment_guest_score = self.profile._calculate_pattern_score(
            content, SpeakerProfile.GUEST_INDICATORS
        )

        overall_host_score = speaker_role_info.get("host_score", 0)
        overall_guest_score = speaker_role_info.get("guest_score", 0)

        # Detect mismatch: segment pattern conflicts with overall speaker pattern
        mismatch = False
        severity = "low"
        reason = ""
        expected_speaker = None
        confidence = 0.0

        # Strong indicators for immediate detection (especially for short segments)
        has_strong_analytical = any(
            keyword in content
            for keyword in ["事实上", "实际上", "剩下来", "所以你看"]
        )
        has_strong_technical = any(
            keyword in content
            for keyword in ["算力", "CPU", "GPU", "数据帧", "加速计算", "通用计算"]
        )
        has_strong_question = content.count("？") + content.count("?") > 0

        # For ambiguous speakers, use strong indicator detection
        if abs(overall_host_score - overall_guest_score) < 1.0:
            # Both are ambiguous, use strong indicators
            if (has_strong_analytical or has_strong_technical) and not has_strong_question:
                # Content has strong guest indicators and no strong host indicators
                mismatch = True
                reason = "Content has strong analytical/technical markers, but assigned to ambiguous speaker"

                # Find the other speaker who should have said this
                for other_speaker in sorted(self.profile.speaker_patterns.keys()):
                    if other_speaker != speaker:
                        other_info = self.profile.speaker_patterns[other_speaker]
                        # Prefer the other speaker (likely guest)
                        expected_speaker = other_speaker
                        confidence = 2.0
                        break

        # Regular mismatch detection for clear speaker profiles
        # If speaker is typically guest but segment looks like host speech
        elif overall_guest_score > overall_host_score:
            if has_strong_question and segment_host_score > segment_guest_score:
                mismatch = True
                severity = "high" if abs(segment_host_score - segment_guest_score) > 5 else "medium"
                reason = f"Content has host markers (questions), but speaker is typically guest"

                # Try to identify which speaker should have said this
                for other_speaker, info in self.profile.speaker_patterns.items():
                    if info["host_score"] > overall_host_score:
                        expected_speaker = other_speaker
                        confidence = abs(segment_host_score - segment_guest_score)

        # If speaker is typically host but segment looks like guest speech
        elif overall_host_score > overall_guest_score:
            if (has_strong_analytical or has_strong_technical) and not has_strong_question:
                mismatch = True
                severity = "high" if segment_guest_score > segment_host_score + 2 else "medium"
                reason = f"Content has analytical/technical markers, but speaker is typically host"

                for other_speaker, info in self.profile.speaker_patterns.items():
                    if info["guest_score"] > overall_guest_score:
                        expected_speaker = other_speaker
                        confidence = abs(segment_guest_score - segment_host_score)
                        break

        return {
            "mismatch_detected": mismatch,
            "severity": severity,
            "reason": reason,
            "expected_speaker": expected_speaker,
            "confidence": confidence,
            "segment_host_score": segment_host_score,
            "segment_guest_score": segment_guest_score,
        }

    def _extract_segment_id(self, text: str) -> int:
        """Extract segment ID from text"""
        for line in text.split('\n'):
            if 'segment' in line.lower():
                match = re.search(r'segment_?(\d+)', line)
                if match:
                    return int(match.group(1))
        return -1


def validate_all_segments(
    full_text: str,
    segments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Validate all segments against full text speaker profile

    Args:
        full_text: Complete text with speaker markers
        segments: List of segment dicts with 'segment_id' and 'text' keys

    Returns:
        Validation results for each segment
    """
    # Build speaker profile from full text
    profile = SpeakerProfile()
    profile.analyze_text(full_text)

    print("\n" + "="*60)
    print("Speaker Profile Analysis")
    print("="*60)

    for speaker, role_info in profile._infer_speaker_roles().items():
        print(f"{speaker}: {role_info['role']}")
        print(f"  Host score: {role_info['host_score']:.2f}")
        print(f"  Guest score: {role_info['guest_score']:.2f}")
        print(f"  Confidence: {role_info['confidence']:.2f}")

    # Validate each segment
    validator = SegmentValidator(profile)
    results = []

    print("\n" + "="*60)
    print("Segment Validation Results")
    print("="*60)

    for segment in segments:
        segment_text = segment["text"]
        validation = validator.validate_segment(segment_text)
        results.append(validation)

        print(f"\nSegment {validation['segment_id']}:")
        print(f"  Speakers: {validation['speakers_in_segment']}")
        print(f"  Status: {'✓ Valid' if validation['is_valid'] else '✗ Issues Found'}")

        if validation["issues"]:
            for issue in validation["issues"]:
                print(f"\n  ⚠️  {issue['severity'].upper()}: {issue['speaker']}")
                print(f"     Reason: {issue['reason']}")
                if issue["expected_speaker"]:
                    print(f"     Suggestion: Should be {issue['expected_speaker']} (confidence: {issue['confidence']:.2f})")

    return results


if __name__ == "__main__":
    # Example usage
    test_text = """speaker_0: 这是主持人说的话
speaker_1: 这是嘉宾说的话，包含很多技术分析和数据"""

    profile = SpeakerProfile()
    analysis = profile.analyze_text(test_text)
    print("Profile analysis:", analysis)
