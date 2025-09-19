"""
Enhanced Content Generator with Blog Posts and Voice/Tone Customization
"""

import os
import re
from typing import List, Dict, Optional, Tuple
from openai import OpenAI

class ContentGenerator:
    def __init__(self, api_key: Optional[str] = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        
        # Voice and tone templates
        self.voice_templates = {
            "professional": {
                "tone": "professional and authoritative",
                "style": "clear, concise, and business-focused",
                "examples": "Use industry terminology, data-driven insights, and formal language"
            },
            "casual": {
                "tone": "friendly and approachable", 
                "style": "conversational and relaxed",
                "examples": "Use everyday language, personal anecdotes, and informal expressions"
            },
            "expert": {
                "tone": "expert and knowledgeable",
                "style": "detailed and educational",
                "examples": "Use technical terms, in-depth explanations, and expert insights"
            },
            "inspiring": {
                "tone": "motivational and uplifting",
                "style": "energetic and positive",
                "examples": "Use encouraging language, success stories, and call-to-action phrases"
            },
            "analytical": {
                "tone": "thoughtful and analytical",
                "style": "logical and evidence-based",
                "examples": "Use data points, comparisons, and structured reasoning"
            }
        }

    def _estimate_tokens(self, text: str) -> int:
        """Rough estimation of token count (1 token ≈ 4 characters)"""
        return len(text) // 4

    def _split_transcript_into_chunks(self, transcript: str, max_tokens_per_chunk: int = 6000) -> List[str]:
        """Split transcript into chunks that fit within token limits"""
        # Convert token limit to character limit (rough estimate)
        max_chars_per_chunk = max_tokens_per_chunk * 4
        
        if len(transcript) <= max_chars_per_chunk:
            return [transcript]
        
        chunks = []
        current_chunk = ""
        
        # Split by sentences first (preserve meaning)
        sentences = re.split(r'(?<=[.!?])\s+', transcript)
        
        for sentence in sentences:
            # If adding this sentence would exceed the limit
            if len(current_chunk) + len(sentence) > max_chars_per_chunk:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = sentence
                else:
                    # Single sentence is too long, split by words
                    words = sentence.split()
                    for word in words:
                        if len(current_chunk) + len(word) + 1 > max_chars_per_chunk:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                                current_chunk = word
                            else:
                                # Single word is too long, force split
                                chunks.append(word[:max_chars_per_chunk//2])
                                current_chunk = word[max_chars_per_chunk//2:]
                        else:
                            current_chunk += " " + word if current_chunk else word
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    def _generate_from_chunks(self, chunks: List[str], generation_function, *args, **kwargs) -> List[str]:
        """Generate content from chunks and combine results"""
        all_results = []
        
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)} ({len(chunk)} characters)")
            try:
                result = generation_function(chunk, *args, **kwargs)
                if isinstance(result, list):
                    all_results.extend(result)
                else:
                    all_results.append(result)
            except Exception as e:
                print(f"Error processing chunk {i+1}: {e}")
                continue
        
        return all_results

    def generate_linkedin_posts(self, transcript: str, voice: str = "professional", num_posts: int = 3) -> List[str]:
        """Generate LinkedIn posts with specified voice/tone"""
        voice_config = self.voice_templates.get(voice, self.voice_templates["professional"])
        
        prompt = f"""
        Create {num_posts} LinkedIn posts based on this podcast transcript. 
        
        Voice and Tone Requirements:
        - Tone: {voice_config['tone']}
        - Style: {voice_config['style']}
        - Examples: {voice_config['examples']}
        
        Post Requirements:
        - Each post should be 150-300 words
        - Include relevant hashtags (3-5 per post)
        - Make each post unique but related to the same topic
        - Include actionable insights or key takeaways
        - Use engaging hooks to start each post
        
        Transcript:
        {transcript}
        
        Format: Return each post separated by "---POST_BREAK---"
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            posts = [post.strip() for post in content.split("---POST_BREAK---") if post.strip()]
            return posts
            
        except Exception as e:
            print(f"Error generating LinkedIn posts: {e}")
            return []

    def generate_blog_post(self, transcript: str, voice: str = "professional", 
                          title: Optional[str] = None, word_count: int = 1000) -> Dict[str, str]:
        """Generate a complete blog post with specified voice/tone"""
        voice_config = self.voice_templates.get(voice, self.voice_templates["professional"])
        
        prompt = f"""
        Create a comprehensive blog post based on this podcast transcript.
        
        Voice and Tone Requirements:
        - Tone: {voice_config['tone']}
        - Style: {voice_config['style']}
        - Examples: {voice_config['examples']}
        
        Blog Post Requirements:
        - Word count: approximately {word_count} words
        - Include an engaging title (if not provided)
        - Structure with clear headings and subheadings
        - Include an introduction, main content, and conclusion
        - Use bullet points or numbered lists where appropriate
        - Include actionable takeaways
        - Make it SEO-friendly with relevant keywords
        
        Transcript:
        {transcript}
        
        Format: Return in this JSON structure:
        {{
            "title": "Blog Post Title",
            "content": "Full blog post content in clean paragraph format (no HTML tags, just plain text with line breaks)",
            "excerpt": "Short 2-3 sentence summary",
            "tags": ["tag1", "tag2", "tag3"]
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content
            
            # Try to parse as JSON, fallback to plain text
            try:
                import json
                return json.loads(content)
            except:
                return {
                    "title": title or "Blog Post from Podcast",
                    "content": content,
                    "excerpt": content[:200] + "...",
                    "tags": ["podcast", "blog"]
                }
                
        except Exception as e:
            print(f"Error generating blog post: {e}")
            return {
                "title": "Error generating blog post",
                "content": "There was an error generating the blog post. Please try again.",
                "excerpt": "Error occurred",
                "tags": []
            }

    def get_voice_options(self) -> Dict[str, str]:
        """Get available voice options for UI"""
        return {key: config["tone"] for key, config in self.voice_templates.items()}

    def customize_voice(self, voice: str, custom_instructions: str) -> str:
        """Create custom voice prompt with user instructions"""
        base_config = self.voice_templates.get(voice, self.voice_templates["professional"])
        
        custom_prompt = f"""
        Use this voice and tone:
        - Base tone: {base_config['tone']}
        - Base style: {base_config['style']}
        - Custom instructions: {custom_instructions}
        
        Combine the base voice with the custom instructions to create unique content.
        """
        
        return custom_prompt

    def generate_linkedin_posts_custom(self, transcript: str, custom_voice: str, custom_instructions: str = "", num_posts: int = 3) -> List[str]:
        """Generate LinkedIn posts with custom voice and tone description using chunking"""
        
        # Check if transcript needs chunking
        estimated_tokens = self._estimate_tokens(transcript)
        print(f"Transcript estimated tokens: {estimated_tokens}")
        
        if estimated_tokens > 6000:  # Leave room for prompt and response
            print("Transcript too large, using chunking approach...")
            chunks = self._split_transcript_into_chunks(transcript, max_tokens_per_chunk=6000)
            print(f"Split into {len(chunks)} chunks")
            
            all_posts = []
            posts_per_chunk = max(1, num_posts // len(chunks))  # Distribute posts across chunks
            
            for i, chunk in enumerate(chunks):
                print(f"Processing chunk {i+1}/{len(chunks)} for LinkedIn posts")
                chunk_posts = self._generate_linkedin_posts_from_chunk(
                    chunk, custom_voice, custom_instructions, posts_per_chunk, chunk_num=i+1, total_chunks=len(chunks)
                )
                all_posts.extend(chunk_posts)
            
            # Limit to requested number of posts
            return all_posts[:num_posts]
        else:
            # Single chunk processing
            return self._generate_linkedin_posts_from_chunk(
                transcript, custom_voice, custom_instructions, num_posts, chunk_num=1, total_chunks=1
            )

    def _generate_linkedin_posts_from_chunk(self, transcript_chunk: str, custom_voice: str, custom_instructions: str, num_posts: int, chunk_num: int = 1, total_chunks: int = 1) -> List[str]:
        """Generate LinkedIn posts from a single transcript chunk"""
        
        chunk_context = f" (Part {chunk_num} of {total_chunks})" if total_chunks > 1 else ""
        
        prompt = f"""
        Create {num_posts} LinkedIn posts based on this podcast transcript{chunk_context}. 
        
        Voice and Tone Requirements:
        - Custom Voice & Tone: {custom_voice}
        - Additional Instructions: {custom_instructions}
        
        Post Requirements:
        - Each post should be 150-300 words
        - Include relevant hashtags (3-5 per post)
        - Make each post unique but related to the same topic
        - Include actionable insights or key takeaways
        - Use engaging hooks to start each post
        - Match the exact voice and tone described above
        - Focus on the content provided in this transcript section
        
        Transcript{chunk_context}:
        {transcript_chunk}
        
        Format: Return each post separated by "---POST_BREAK---"
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            posts = [post.strip() for post in content.split("---POST_BREAK---") if post.strip()]
            return posts
            
        except Exception as e:
            print(f"Error generating LinkedIn posts from chunk {chunk_num}: {e}")
            return []

    def generate_blog_post_custom(self, transcript: str, custom_voice: str, custom_instructions: str = "", 
                                 title: Optional[str] = None, word_count: int = 1000) -> Dict[str, str]:
        """Generate a complete blog post with custom voice and tone description using chunking"""
        
        # Check if transcript needs chunking
        estimated_tokens = self._estimate_tokens(transcript)
        print(f"Blog post transcript estimated tokens: {estimated_tokens}")
        
        if estimated_tokens > 6000:  # Leave room for prompt and response
            print("Transcript too large for blog post, using chunking approach...")
            chunks = self._split_transcript_into_chunks(transcript, max_tokens_per_chunk=6000)
            print(f"Split into {len(chunks)} chunks")
            
            # Generate blog post sections from each chunk
            blog_sections = []
            for i, chunk in enumerate(chunks):
                print(f"Processing chunk {i+1}/{len(chunks)} for blog post")
                section = self._generate_blog_section_from_chunk(
                    chunk, custom_voice, custom_instructions, chunk_num=i+1, total_chunks=len(chunks)
                )
                if section:
                    blog_sections.append(section)
            
            # Combine sections into final blog post
            if blog_sections:
                return self._combine_blog_sections(blog_sections, title, custom_voice, word_count)
            else:
                return {
                    "title": "Error generating blog post",
                    "content": "There was an error processing the transcript chunks. Please try again.",
                    "excerpt": "Error occurred",
                    "tags": []
                }
        else:
            # Single chunk processing
            return self._generate_blog_post_from_chunk(
                transcript, custom_voice, custom_instructions, title, word_count
            )

    def _generate_blog_section_from_chunk(self, transcript_chunk: str, custom_voice: str, custom_instructions: str, chunk_num: int = 1, total_chunks: int = 1) -> str:
        """Generate a blog post section from a single transcript chunk"""
        
        chunk_context = f" (Part {chunk_num} of {total_chunks})" if total_chunks > 1 else ""
        
        prompt = f"""
        Create a section for a comprehensive blog post based on this podcast transcript{chunk_context}.
        
        Voice and Tone Requirements:
        - Custom Voice & Tone: {custom_voice}
        - Additional Instructions: {custom_instructions}
        
        Section Requirements:
        - Write a coherent section of the blog post (not the full post)
        - Use clean paragraph format (no HTML tags, just plain text)
        - Include relevant headings as plain text (e.g., "## Heading Name")
        - Use bullet points or numbered lists where appropriate
        - Include actionable insights from this section
        - Match the exact voice and tone described above
        - Focus on the content provided in this transcript section
        
        Transcript{chunk_context}:
        {transcript_chunk}
        
        Return only the blog post section content in clean paragraph format (no JSON formatting needed).
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error generating blog section from chunk {chunk_num}: {e}")
            return ""

    def _combine_blog_sections(self, sections: List[str], title: Optional[str], custom_voice: str, word_count: int) -> Dict[str, str]:
        """Combine blog sections into a final blog post"""
        
        combined_content = "\n\n".join(sections)
        
        prompt = f"""
        Create a comprehensive blog post by combining and refining these sections.
        
        Voice and Tone Requirements:
        - Custom Voice & Tone: {custom_voice}
        
        Blog Post Requirements:
        - Word count: approximately {word_count} words
        - Include an engaging title (if not provided)
        - Structure with clear headings and subheadings as plain text (e.g., "## Heading Name")
        - Include an introduction, main content, and conclusion
        - Use bullet points or numbered lists where appropriate
        - Include actionable takeaways
        - Make it SEO-friendly with relevant keywords
        - Ensure smooth transitions between sections
        - Match the exact voice and tone described above
        - Use clean paragraph format (no HTML tags, just plain text with line breaks)
        
        Blog Sections:
        {combined_content}
        
        Format: Return in this JSON structure:
        {{
            "title": "Blog Post Title",
            "content": "Full blog post content in clean paragraph format (no HTML tags, just plain text with line breaks)",
            "excerpt": "Short 2-3 sentence summary",
            "tags": ["tag1", "tag2", "tag3"]
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content
            
            # Try to parse as JSON, fallback to plain text
            try:
                import json
                return json.loads(content)
            except:
                return {
                    "title": title or "Blog Post from Podcast",
                    "content": content,
                    "excerpt": content[:200] + "...",
                    "tags": ["podcast", "blog"]
                }
                
        except Exception as e:
            print(f"Error combining blog sections: {e}")
            return {
                "title": title or "Blog Post from Podcast",
                "content": combined_content,
                "excerpt": "Blog post generated from multiple sections",
                "tags": ["podcast", "blog"]
            }

    def _generate_blog_post_from_chunk(self, transcript: str, custom_voice: str, custom_instructions: str, title: Optional[str], word_count: int) -> Dict[str, str]:
        """Generate a complete blog post from a single transcript chunk"""
        
        prompt = f"""
        Create a comprehensive blog post based on this podcast transcript.
        
        Voice and Tone Requirements:
        - Custom Voice & Tone: {custom_voice}
        - Additional Instructions: {custom_instructions}
        
        Blog Post Requirements:
        - Word count: approximately {word_count} words
        - Include an engaging title (if not provided)
        - Structure with clear headings and subheadings as plain text (e.g., "## Heading Name")
        - Include an introduction, main content, and conclusion
        - Use bullet points or numbered lists where appropriate
        - Include actionable takeaways
        - Make it SEO-friendly with relevant keywords
        - Match the exact voice and tone described above
        - Use clean paragraph format (no HTML tags, just plain text with line breaks)
        
        Transcript:
        {transcript}
        
        Format: Return in this JSON structure:
        {{
            "title": "Blog Post Title",
            "content": "Full blog post content in clean paragraph format (no HTML tags, just plain text with line breaks)",
            "excerpt": "Short 2-3 sentence summary",
            "tags": ["tag1", "tag2", "tag3"]
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content
            
            # Try to parse as JSON, fallback to plain text
            try:
                import json
                return json.loads(content)
            except:
                return {
                    "title": title or "Blog Post from Podcast",
                    "content": content,
                    "excerpt": content[:200] + "...",
                    "tags": ["podcast", "blog"]
                }
                
        except Exception as e:
            print(f"Error generating blog post: {e}")
            return {
                "title": "Error generating blog post",
                "content": "There was an error generating the blog post. Please try again.",
                "excerpt": "Error occurred",
                "tags": []
            }
