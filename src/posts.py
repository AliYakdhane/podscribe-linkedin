from __future__ import annotations

from typing import List

from openai import OpenAI


def generate_linkedin_posts(openai_api_key: str, transcript_text: str, episode_title: str) -> List[str]:
    client = OpenAI()

    system_msg = (
        "You are a social media editor who turns transcripts into concise, high-signal LinkedIn posts. "
        "Focus on practical takeaways, use a strong hook, and avoid emojis."
    )

    user_prompt = f"""
Transcribe summary into three distinct LinkedIn-ready posts.
Constraints:
- Each post: 100-180 words, strong hook, 1-2 short paragraphs, skimmable bullets only if essential.
- No hashtags, no emojis, no salesy tone.
- Vary style across the three posts (angles/themes).

Episode title: {episode_title}
Transcript:
{transcript_text[:8000]}

Return exactly three posts, separated by a line with three dashes (---) and nothing else.
"""

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )

    content = completion.choices[0].message.content or ""
    parts = [p.strip() for p in content.split("---") if p.strip()]
    return parts[:3]
