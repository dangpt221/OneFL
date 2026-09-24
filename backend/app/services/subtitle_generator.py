import re
from typing import List, Dict, Any, Optional
from datetime import timedelta
from app.config import settings


def format_timestamp_ass(seconds: float) -> str:
    """Format seconds into ASS timestamp: H:MM:SS.cc (centiseconds)."""
    td = timedelta(seconds=max(0.0, seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def format_timestamp_srt(seconds: float) -> str:
    """Format seconds into SRT timestamp: HH:MM:SS,mmm (milliseconds)."""
    td = timedelta(seconds=max(0.0, seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """Format seconds into WebVTT timestamp: HH:MM:SS.mmm."""
    td = timedelta(seconds=max(0.0, seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


class SubtitleGenerator:
    """Generates ASS, SRT, and VTT subtitles with cinematic styling and bilingual support."""

    PRESETS = {
        "cinema": {
            "font_name": "Arial",
            "font_size": 24,
            "primary_color": "&H00FFFFFF",  # Pure White
            "outline_color": "&H00000000",  # Black Outline
            "back_color": "&H80000000",     # Soft Shadow
            "border_style": 1,              # Outline + Drop Shadow
            "outline_width": 2.2,
            "shadow_depth": 1.2,
            "margin_v": 30,
            "bold": 1
        },
        "box_banner": {
            "font_name": "Arial",
            "font_size": 24,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color": "&HFF000000",     # Opaque Black Box
            "border_style": 3,              # Opaque Box Background
            "outline_width": 12,
            "shadow_depth": 0,
            "margin_v": 36,
            "bold": 1
        },
        "yellow_highlight": {
            "font_name": "Arial",
            "font_size": 24,
            "primary_color": "&H0000FFFF",  # Bright Yellow
            "outline_color": "&H00000000",
            "back_color": "&H80000000",
            "border_style": 1,
            "outline_width": 2.5,
            "shadow_depth": 1.5,
            "margin_v": 30,
            "bold": 1
        }
    }

    @classmethod
    def generate_ass(
        cls,
        cues: List[Dict[str, Any]],
        style_override: Optional[Dict[str, Any]] = None,
        bilingual: bool = False,
        preset: str = "box_banner"
    ) -> str:
        """
        Generates complete ASS format string.
        Supports presets ('cinema', 'box_banner', 'yellow_highlight') and Bilingual Dual Subtitles
        (top line: original source language in elegant silver, bottom line: Vietnamese translation).
        """
        base_cfg = cls.PRESETS.get(preset, cls.PRESETS["box_banner"]).copy()
        if style_override:
            base_cfg.update(style_override)

        font_name = base_cfg.get("font_name", settings.SUB_FONT_NAME)
        font_size = base_cfg.get("font_size", settings.SUB_FONT_SIZE)
        primary_color = base_cfg.get("primary_color", settings.SUB_PRIMARY_COLOR)
        outline_color = base_cfg.get("outline_color", settings.SUB_OUTLINE_COLOR)
        back_color = base_cfg.get("back_color", "&HFF000000")
        border_style = base_cfg.get("border_style", 3)
        outline_width = base_cfg.get("outline_width", settings.SUB_OUTLINE_WIDTH)
        shadow_depth = base_cfg.get("shadow_depth", settings.SUB_SHADOW_DEPTH)
        margin_v = base_cfg.get("margin_v", settings.SUB_MARGIN_BOTTOM)
        bold = base_cfg.get("bold", 1)

        is_bilingual = bilingual or base_cfg.get("bilingual", False)

        ass_header = f"""[Script Info]
Title: OneFl Auto Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},{back_color},{bold},0,0,0,100,100,0,0,{border_style},{outline_width},{shadow_depth},2,20,20,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        for cue in cues:
            start_str = format_timestamp_ass(cue["start_time"])
            end_str = format_timestamp_ass(cue["end_time"])
            
            orig_text = (cue.get("original_text") or "").strip()
            trans_text = (cue.get("translated_text") or orig_text).strip()
            speaker = cue.get("speaker_tag", "")

            if is_bilingual and orig_text and trans_text and orig_text != trans_text:
                # Bilingual Mode: Top line = Original (compact silver), Bottom line = Vietnamese (bold white)
                clean_orig = orig_text.replace("\r\n", " ").replace("\n", " ")
                clean_trans = trans_text.replace("\r\n", "\\N").replace("\n", "\\N")
                ass_text = f"{{\\fs{max(15, font_size - 6)}\\c&H00D4D4D4&}}{clean_orig}\\N{{\\r}}{{\\fs{font_size}\\b1}}{clean_trans}"
            else:
                # Monolingual Mode (Vietnamese)
                ass_text = trans_text.replace("\r\n", "\\N").replace("\n", "\\N")

            event_line = f"Dialogue: 0,{start_str},{end_str},Default,{speaker},0,0,0,,{ass_text}"
            events.append(event_line)

        return ass_header + "\n".join(events) + "\n"

    @classmethod
    def generate_srt(cls, cues: List[Dict[str, Any]]) -> str:
        """Generates standard SRT format string."""
        blocks = []
        for i, cue in enumerate(cues, start=1):
            start_str = format_timestamp_srt(cue["start_time"])
            end_str = format_timestamp_srt(cue["end_time"])
            raw_text = cue.get("translated_text") or cue.get("original_text") or ""
            text = raw_text.replace("\r\n", "\n").strip()
            blocks.append(f"{i}\n{start_str} --> {end_str}\n{text}\n")
        return "\n".join(blocks)

    @classmethod
    def generate_vtt(cls, cues: List[Dict[str, Any]]) -> str:
        """Generates WebVTT format string."""
        lines = ["WEBVTT", ""]
        for i, cue in enumerate(cues, start=1):
            start_str = format_timestamp_vtt(cue["start_time"])
            end_str = format_timestamp_vtt(cue["end_time"])
            raw_text = cue.get("translated_text") or cue.get("original_text") or ""
            text = raw_text.replace("\r\n", "\n").strip()
            speaker = cue.get("speaker_tag")
            speaker_prefix = f"<v {speaker}>" if speaker else ""
            lines.append(f"{i}")
            lines.append(f"{start_str} --> {end_str}")
            lines.append(f"{speaker_prefix}{text}\n")
        return "\n".join(lines)


subtitle_generator = SubtitleGenerator()
