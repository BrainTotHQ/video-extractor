#!/usr/bin/env python3
"""
MCP Server: Video Content Extractor
Hỗ trợ: YouTube, Facebook Reels, TikTok, Twitter...
Tích hợp: youtube-transcript-api (siêu tốc cho YouTube) + yt-dlp (cho đa nền tảng)
"""

import sys
import re
import urllib.request
from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
import yt_dlp

# Khởi tạo MCP server
mcp = FastMCP("video-content-extractor")

def extract_youtube_id(url: str) -> Optional[str]:
    patterns = [
        r'(?:v=|youtu\.be/|shorts/|embed/|live/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, url.strip())
        if match:
            return match.group(1)
    return None

def clean_srt(srt_text: str) -> str:
    """Loại bỏ số thứ tự và timestamp của định dạng SRT, chỉ giữ lại câu thoại"""
    lines = srt_text.splitlines()
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'^\d+$', line):
            continue
        if re.match(r'^\d{2}:\d{2}:\d{2}', line):
            continue
        cleaned.append(line)
    return " ".join(cleaned)

@mcp.tool()
def get_video_content(url: str) -> Dict[str, Any]:
    """
    Trích xuất tiêu đề, người đăng, thời lượng và nội dung phụ đề/transcript
    từ đường link video (YouTube, Facebook Reel, TikTok, v.v.).
    """
    url = url.strip()
    yt_id = extract_youtube_id(url)
    
    # 1. Nếu là YouTube, thử lấy transcript siêu nhanh qua youtube_transcript_api
    if yt_id:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.list_transcripts(yt_id)
            try:
                transcript = transcript_list.find_transcript(['vi', 'en'])
            except Exception:
                transcript = next(iter(transcript_list))
                
            data = transcript.fetch()
            full_text = " ".join([item['text'] for item in data])
            
            return {
                "success": True,
                "platform": "YouTube",
                "video_id": yt_id,
                "method": "youtube_transcript_api",
                "language": transcript.language_code,
                "transcript": full_text
            }
        except Exception as e:
            pass # Fallback sang yt-dlp bên dưới

    # 2. Sử dụng yt-dlp cho Facebook, TikTok hoặc YouTube không có transcript mở
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['all'],
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            title = info.get('title', '')
            uploader = info.get('uploader', '')
            duration = info.get('duration_string', '')
            
            # Kiểm tra auto captions hoặc subtitles
            captions_data = info.get('automatic_captions') or info.get('subtitles') or {}
            
            transcript_text = ""
            # Tìm subtitle tiếng Việt hoặc tiếng Anh
            target_langs = ['vi', 'en', 'en_US', 'und']
            sub_url = None
            
            for lang in target_langs:
                if lang in captions_data and captions_data[lang]:
                    sub_url = captions_data[lang][0].get('url')
                    break
            
            if not sub_url and captions_data:
                first_lang = next(iter(captions_data))
                if captions_data[first_lang]:
                    sub_url = captions_data[first_lang][0].get('url')
                    
            if sub_url:
                try:
                    req = urllib.request.Request(sub_url, headers={'User-Agent': 'Mozilla/5.0'})
                    raw_sub = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
                    transcript_text = clean_srt(raw_sub)
                except Exception as ex:
                    transcript_text = f"Không tải được link sub: {ex}"
            else:
                transcript_text = "Video không có sẵn subtitle/caption dạng text trực tiếp."
                
            return {
                "success": True,
                "platform": info.get('extractor', 'Unknown'),
                "title": title,
                "uploader": uploader,
                "duration": duration,
                "method": "yt-dlp",
                "has_transcript": bool(sub_url),
                "transcript": transcript_text
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    # Chạy server MCP qua FastMCP stdio
    mcp.run()
