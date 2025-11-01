"""
Adaptive LLM handler that dynamically adjusts to model limitations.

This module provides intelligent workarounds for slow or resource-constrained LLMs:
- Dynamic timeout scaling based on prompt size
- Progressive context reduction on failures
- Chunked processing for large contexts
- Fallback to simplified prompts
- Partial result recovery
"""

import os
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from myai.llm_manager import LLMManager

logger = logging.getLogger("myai.adaptive_llm")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(h)
    logger.setLevel(os.environ.get("MYAI_LOG_LEVEL", "INFO"))


class AdaptiveLLMHandler:
    """
    Handles LLM calls with adaptive strategies for slow or limited models.
    """
    
    def __init__(
        self,
        llm_manager: LLMManager,
        base_timeout: int = 180,
        max_timeout: int = 600,
        min_timeout: int = 120,
        max_retries: int = 2
    ):
        """
        Initialize the adaptive handler.
        
        Args:
            llm_manager: The LLM manager instance
            base_timeout: Base timeout in seconds (auto-adjusted for CPU-only)
            max_timeout: Maximum timeout allowed (auto-adjusted for CPU-only)
            min_timeout: Minimum timeout allowed (auto-adjusted for CPU-only)
            max_retries: Maximum retry attempts
        """
        self.llm_manager = llm_manager
        
        # Detect CPU-only mode and adjust timeouts
        self.cpu_only_mode = self._detect_cpu_only_mode()
        if self.cpu_only_mode:
            logger.info("CPU-only mode detected - using extended timeouts")
            # CPU inference is ~10-50x slower than GPU
            base_timeout = max(base_timeout, 600)  # 10min base for CPU
            max_timeout = max(max_timeout, 1200)   # 20min max for CPU
            min_timeout = max(min_timeout, 300)    # 5min min for CPU
        
        self.base_timeout = base_timeout
        self.max_timeout = max_timeout
        self.min_timeout = min_timeout
        self.max_retries = max_retries
        
        # Track performance metrics
        self.avg_response_time = base_timeout
        self.successful_calls = 0
        self.failed_calls = 0
    
    def _detect_cpu_only_mode(self) -> bool:
        """
        Detect if running in CPU-only mode by checking environment hints.
        
        Returns:
            True if CPU-only mode is detected
        """
        # Check explicit flag
        if os.environ.get("CPU_ONLY_MODE", "").lower() in ("1", "true", "yes"):
            return True
        
        # Check GPU layers setting (0 = CPU-only)
        gpu_layers = os.environ.get("GPU_LAYERS", "")
        if gpu_layers == "0":
            return True
        
        # Check if VRAM is very low (< 1GB suggests integrated GPU / CPU fallback)
        vram_mb = os.environ.get("GPU_VRAM_MB", "")
        if vram_mb and vram_mb.isdigit() and int(vram_mb) < 1024:
            return True
        
        return False
    
    def _calculate_dynamic_timeout(self, prompt_length: int) -> int:
        """
        Calculate timeout based on prompt length and historical performance.
        
        Args:
            prompt_length: Length of the prompt in characters
            
        Returns:
            Calculated timeout in seconds
        """
        # Base calculation depends on CPU vs GPU mode
        if self.cpu_only_mode:
            # CPU-only: ~5-10 seconds per 100 chars, highly dependent on context
            estimated = max(300, (prompt_length // 100) * 7 + 120)
        else:
            # GPU mode: ~1-3 seconds per 100 chars
            estimated = max(120, (prompt_length // 100) * 3 + 60)
        
        # Adjust based on average performance
        if self.successful_calls > 0:
            estimated = int(self.avg_response_time * 1.5)
        
        # Apply bounds
        timeout = max(self.min_timeout, min(estimated, self.max_timeout))
        
        mode_str = "CPU-only" if self.cpu_only_mode else "GPU"
        logger.info(f"Dynamic timeout: {timeout}s (prompt_len={prompt_length}, avg={self.avg_response_time:.1f}s, mode={mode_str})")
        return timeout
    
    def _truncate_context(self, text: str, max_chars: int) -> Tuple[str, bool]:
        """
        Intelligently truncate text to fit within max_chars.
        
        Tries to preserve complete sentences when possible.
        
        Args:
            text: Text to truncate
            max_chars: Maximum characters allowed
            
        Returns:
            Tuple of (truncated_text, was_truncated)
        """
        if len(text) <= max_chars:
            return text, False
        
        # Try to find last complete sentence
        truncated = text[:max_chars]
        last_period = truncated.rfind('.')
        last_newline = truncated.rfind('\n\n')
        
        cutoff = max(last_period, last_newline)
        if cutoff > max_chars * 0.7:  # Only use if we keep >70% of content
            truncated = text[:cutoff + 1]
        
        logger.warning(f"Truncated context from {len(text)} to {len(truncated)} chars")
        return truncated, True
    
    def _create_simplified_prompt(self, original_prompt: str, context: str) -> str:
        """
        Create a simplified version of the prompt with reduced context.
        
        Args:
            original_prompt: Original prompt text
            context: Context to summarize
            
        Returns:
            Simplified prompt
        """
        # Extract key sentences (first and last paragraphs)
        paragraphs = context.split('\n\n')
        if len(paragraphs) > 4:
            simplified_context = '\n\n'.join(paragraphs[:2] + ['...[content abbreviated]...'] + paragraphs[-2:])
        else:
            simplified_context = context
        
        simplified, _ = self._truncate_context(simplified_context, 5000)
        
        # Rebuild prompt with simplified context
        if "Articles:" in original_prompt or "articles" in original_prompt.lower():
            return f"{original_prompt.split('Articles:')[0]}Articles:\n{simplified}\n\n[NOTE: Context was simplified to reduce processing time]"
        
        return simplified
    
    def _chunk_articles(self, articles: List[Dict[str, Any]], max_chunk_size: int = 10000) -> List[str]:
        """
        Split articles into processable chunks.
        
        Args:
            articles: List of article dictionaries
            max_chunk_size: Maximum characters per chunk
            
        Returns:
            List of article text chunks
        """
        chunks = []
        current_chunk = []
        current_size = 0
        
        for article in articles:
            article_text = article.get("text", "") or article.get("summary", "")
            article_size = len(article_text)
            
            if current_size + article_size > max_chunk_size and current_chunk:
                # Save current chunk and start new one
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_size = 0
            
            current_chunk.append(article_text)
            current_size += article_size
        
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
        
        logger.info(f"Split {len(articles)} articles into {len(chunks)} chunks")
        return chunks
    
    def get_completion_adaptive(
        self,
        messages: List[Dict[str, str]],
        fallback_on_timeout: bool = True,
        enable_chunking: bool = False,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Get LLM completion with adaptive strategies.
        
        Args:
            messages: List of message dictionaries
            fallback_on_timeout: Whether to try simplified prompt on timeout
            enable_chunking: Whether to enable chunked processing
            **kwargs: Additional arguments passed to LLM
            
        Returns:
            LLM response or None on failure
        """
        prompt_content = messages[-1].get("content", "") if messages else ""
        prompt_length = len(prompt_content)
        
        # Calculate dynamic timeout
        timeout = self._calculate_dynamic_timeout(prompt_length)
        
        # Set environment variable for LLM manager to use
        os.environ['LLM_TIMEOUT'] = str(timeout)
        
        start_time = time.time()
        attempt = 0
        
        while attempt <= self.max_retries:
            try:
                logger.info(f"Attempt {attempt + 1}/{self.max_retries + 1} with timeout={timeout}s")
                
                # Don't pass timeout directly to avoid conflict - use env var instead
                response = self.llm_manager.get_completion(messages, **kwargs)
                
                if response:
                    # Success - update metrics
                    elapsed = time.time() - start_time
                    self._update_metrics(elapsed, success=True)
                    return response
                
                # None response indicates failure
                logger.warning(f"LLM returned None on attempt {attempt + 1}")
                
            except Exception as e:
                error_str = str(e).lower()
                logger.warning(f"LLM error on attempt {attempt + 1}: {e}")
                
                # Check if it's a timeout
                if 'timeout' in error_str:
                    # Increase timeout for next attempt
                    timeout = min(timeout * 1.5, self.max_timeout)
                    os.environ['LLM_TIMEOUT'] = str(int(timeout))
            
            attempt += 1
            
            # On last attempt, try fallback strategies
            if attempt > self.max_retries and fallback_on_timeout:
                logger.info("Attempting fallback with simplified prompt")
                return self._fallback_completion(messages, timeout)
            
            # Exponential backoff between retries
            if attempt <= self.max_retries:
                sleep_time = 2 ** (attempt - 1)
                logger.info(f"Waiting {sleep_time}s before retry...")
                time.sleep(sleep_time)
        
        # All attempts failed
        self._update_metrics(0, success=False)
        return None
    
    def _fallback_completion(
        self,
        messages: List[Dict[str, str]],
        timeout: int
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt completion with fallback strategies.
        
        Args:
            messages: Original messages
            timeout: Timeout to use
            
        Returns:
            LLM response or None
        """
        if not messages:
            return None
        
        original_content = messages[-1].get("content", "")
        
        # Strategy 1: Reduce context size
        if len(original_content) > 10000:
            logger.info("Fallback strategy: reducing context size")
            truncated, _ = self._truncate_context(original_content, 8000)
            
            fallback_messages = messages[:-1] + [{"role": messages[-1]["role"], "content": truncated}]
            
            try:
                # Set timeout via environment variable
                os.environ['LLM_TIMEOUT'] = str(timeout)
                response = self.llm_manager.get_completion(fallback_messages)
                if response:
                    return response
            except Exception as e:
                logger.warning(f"Fallback with truncation failed: {e}")
        
        # Strategy 2: Simplify prompt structure
        if "Articles:" in original_content or "Report:" in original_content:
            logger.info("Fallback strategy: simplifying prompt")
            
            # Extract just the question/topic
            lines = original_content.split('\n')
            topic_line = lines[0] if lines else original_content[:200]
            
            simple_prompt = f"{topic_line}\n\nProvide a brief summary based on the key information available."
            simple_messages = [{"role": "user", "content": simple_prompt}]
            
            try:
                # Set reduced timeout
                os.environ['LLM_TIMEOUT'] = str(timeout // 2)
                response = self.llm_manager.get_completion(simple_messages)
                if response:
                    return response
            except Exception as e:
                logger.warning(f"Fallback with simplified prompt failed: {e}")
        
        return None
    
    def _update_metrics(self, response_time: float, success: bool):
        """Update performance tracking metrics."""
        if success:
            self.successful_calls += 1
            # Exponential moving average
            alpha = 0.3
            self.avg_response_time = (alpha * response_time) + ((1 - alpha) * self.avg_response_time)
        else:
            self.failed_calls += 1
        
        total = self.successful_calls + self.failed_calls
        success_rate = (self.successful_calls / total * 100) if total > 0 else 0
        
        logger.info(f"LLM Metrics: success_rate={success_rate:.1f}%, avg_time={self.avg_response_time:.1f}s")
    
    def synthesize_with_chunking(
        self,
        topic: str,
        articles: List[Dict[str, Any]],
        max_chunk_chars: int = 8000
    ) -> str:
        """
        Synthesize a report by processing articles in chunks.
        
        This is useful when the total context is too large for the LLM.
        
        Args:
            topic: Research topic
            articles: List of article dictionaries
            max_chunk_chars: Maximum characters per chunk (auto-adjusted for CPU)
            
        Returns:
            Synthesized report
        """
        if not articles:
            return f"[No articles available to synthesize for topic: {topic}]"
        
        # Adjust chunk size for CPU-only mode
        if self.cpu_only_mode and max_chunk_chars > 5000:
            max_chunk_chars = 4000
            logger.info(f"CPU-only mode: reducing chunk size to {max_chunk_chars} chars")
        
        # Split articles into chunks
        chunks = self._chunk_articles(articles, max_chunk_chars)
        
        if len(chunks) == 1:
            # Single chunk - process normally
            article_text = chunks[0]
            messages = [{
                "role": "user",
                "content": f"Based on the following articles, write a research report on: {topic}\n\nArticles:\n{article_text}"
            }]
            response = self.get_completion_adaptive(messages)
            return self.llm_manager.extract_assistant_text(response) if response else f"[Synthesis failed for topic: {topic}. Please try again with fewer articles or a faster model.]"
        
        # Multiple chunks - process each and combine
        logger.info(f"Processing {len(chunks)} chunks for topic: {topic}")
        summaries = []
        failed_chunks = 0
        
        for i, chunk in enumerate(chunks, 1):
            logger.info(f"Processing chunk {i}/{len(chunks)}")
            messages = [{
                "role": "user",
                "content": f"Summarize the key points from these articles about {topic}:\n\n{chunk}"
            }]
            
            response = self.get_completion_adaptive(messages)
            if response:
                summary = self.llm_manager.extract_assistant_text(response)
                if summary and isinstance(summary, str) and len(summary) > 20:
                    summaries.append(f"**Section {i}:**\n{summary}")
                else:
                    summaries.append(f"**Section {i}:** [No content generated]")
                    failed_chunks += 1
            else:
                summaries.append(f"**Section {i}:** [Processing timed out - skipping this section]")
                failed_chunks += 1
        
        # If all chunks failed, return a helpful error message
        if failed_chunks == len(chunks):
            return f"[Unable to synthesize report on '{topic}'. All {len(chunks)} sections timed out. Try enabling CPU-only optimizations or using a faster model.]"
        
        # Combine summaries into final report
        combined = "\n\n".join(summaries)
        
        # Final synthesis if combined is reasonable size and not all chunks failed
        if len(combined) < 10000 and failed_chunks < len(chunks) / 2:
            logger.info("Attempting final synthesis of chunk summaries")
            messages = [{
                "role": "user",
                "content": f"Combine these summaries into a cohesive research report on {topic}:\n\n{combined}"
            }]
            final_response = self.get_completion_adaptive(messages)
            if final_response:
                final_text = self.llm_manager.extract_assistant_text(final_response)
                if final_text and isinstance(final_text, str) and len(final_text) > 50:
                    return final_text
        
        # Return combined summaries if final synthesis fails
        success_note = f" ({len(chunks) - failed_chunks}/{len(chunks)} sections completed successfully)" if failed_chunks > 0 else ""
        return f"# Research Report: {topic}\n\n{combined}\n\n---\n*Note: Report synthesized from {len(chunks)} sections{success_note}*"
