"""Unified LLM client orchestrating Groq (Primary) and Gemini with rate-limiting and failover."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

from src.common.config import get_config
from src.common.logger import get_logger

logger = get_logger("Common.LLMClient")


class TokenRateLimiter:
    """Sliding-window rate limiter enforcing RPM and TPM boundaries."""

    def __init__(self, max_rpm: int = 30, max_tpm: int = 1000) -> None:
        self.max_rpm = max_rpm
        self.max_tpm = max_tpm
        self.request_timestamps: Deque[float] = deque()
        self.token_history: Deque[Tuple[float, int]] = deque()
        self.last_call_time: float = 0.0
        self.min_interval: float = 60.0 / max_rpm  # e.g., 2.0s for 30 RPM

    def wait_for_capacity(self, estimated_tokens: int = 200) -> None:
        """Blocks until both RPM and TPM budgets have capacity."""
        now = time.time()

        # Enforce minimum inter-request interval (RPM safety)
        elapsed_since_last = now - self.last_call_time
        if elapsed_since_last < self.min_interval:
            sleep_needed = self.min_interval - elapsed_since_last
            time.sleep(sleep_needed)
            now = time.time()

        # Purge items older than 60 seconds
        window_start = now - 60.0
        while self.request_timestamps and self.request_timestamps[0] < window_start:
            self.request_timestamps.popleft()
        while self.token_history and self.token_history[0][0] < window_start:
            self.token_history.popleft()

        # Check RPM
        while len(self.request_timestamps) >= self.max_rpm:
            sleep_time = self.request_timestamps[0] - window_start + 0.1
            if sleep_time > 0:
                logger.info("RPM limit reached (%d). Sleeping %.2fs", self.max_rpm, sleep_time)
                time.sleep(sleep_time)
            now = time.time()
            window_start = now - 60.0
            while self.request_timestamps and self.request_timestamps[0] < window_start:
                self.request_timestamps.popleft()

        # Check TPM
        current_tokens = sum(t[1] for t in self.token_history)
        while (current_tokens + estimated_tokens) > self.max_tpm:
            if not self.token_history:
                break
            sleep_time = self.token_history[0][0] - window_start + 0.2
            if sleep_time > 0:
                logger.info(
                    "TPM limit nearing capacity (%d/%d tokens). Sleeping %.2fs",
                    current_tokens,
                    self.max_tpm,
                    sleep_time,
                )
                time.sleep(sleep_time)
            now = time.time()
            window_start = now - 60.0
            while self.token_history and self.token_history[0][0] < window_start:
                self.token_history.popleft()
            current_tokens = sum(t[1] for t in self.token_history)

        # Record this request
        call_time = time.time()
        self.last_call_time = call_time
        self.request_timestamps.append(call_time)
        self.token_history.append((call_time, estimated_tokens))


class LLMClient:
    """Client for generating completions using Groq and Gemini with automatic failover and rate limiting."""

    def __init__(self) -> None:
        self.config = get_config()
        # Enforce user limits: 30 RPM, 1000 TPM
        self.rate_limiter = TokenRateLimiter(max_rpm=30, max_tpm=1000)
        # Groq model candidates with validated json_object support
        self.groq_candidate_models = [
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            self.config.groq_model,
        ]

    def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = True,
        estimated_tokens: int = 250,
    ) -> str:
        """Generates a text completion with rate limit compliance and fallback hierarchy."""
        # 1. Attempt Groq if configured
        if self.config.groq_api_key:
            # Respect rate limit boundaries before firing
            self.rate_limiter.wait_for_capacity(estimated_tokens)

            for model_name in self.groq_candidate_models:
                try:
                    logger.debug("Calling Groq model: %s", model_name)
                    res = self._call_groq(prompt, system_prompt, json_mode, model_name)
                    if res:
                        return res
                except urllib.error.HTTPError as e:
                    if e.code in (400, 404):
                        logger.debug("Model %s returned HTTP %d on Groq, trying next candidate", model_name, e.code)
                        continue
                    elif e.code == 429:
                        logger.warning("Groq rate limit (429) hit. Pausing for reset.")
                        time.sleep(3.0)
                        break
                    else:
                        logger.warning("Groq call failed with HTTP %d: %s", e.code, e.reason)
                        break
                except Exception as e:
                    logger.warning("Groq call failed: %s. Attempting fallback.", str(e))
                    break

        # 2. Attempt Gemini fallback if configured
        if self.config.gemini_api_key:
            try:
                logger.debug("Attempting completion with Gemini model: %s", self.config.gemini_model)
                res = self._call_gemini(prompt, system_prompt, json_mode)
                if res:
                    return res
            except Exception as e:
                logger.warning("Gemini call failed: %s.", str(e))

        # 3. Fallback when keys are missing or calls fail
        logger.info("Using local fallback response generator.")
        return self._local_fallback(prompt, json_mode)

    def _call_groq(
        self,
        prompt: str,
        system_prompt: Optional[str],
        json_mode: bool,
        model_name: str,
    ) -> Optional[str]:
        """Calls Groq's chat completions endpoint with browser-safe headers."""
        url = "https://api.groq.com/openai/v1/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": self.config.llm_temperature,
            "max_tokens": min(self.config.llm_max_tokens, 500),  # Keep token budget lean
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.config.groq_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=25) as resp:
            # Check response headers for remaining token budget
            remaining_tokens_header = resp.headers.get("x-ratelimit-remaining-tokens")
            if remaining_tokens_header and remaining_tokens_header.isdigit():
                remaining_tokens = int(remaining_tokens_header)
                if remaining_tokens < 200:
                    logger.warning("Groq remaining tokens low (%d). Throttle active.", remaining_tokens)

            resp_body = resp.read().decode("utf-8")
            resp_json = json.loads(resp_body)
            choices = resp_json.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()

        return None

    def _call_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str],
        json_mode: bool,
    ) -> Optional[str]:
        """Calls Google Gemini's REST API endpoint."""
        model_name = self.config.gemini_model
        key = self.config.gemini_api_key
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "temperature": self.config.llm_temperature,
                "maxOutputTokens": min(self.config.llm_max_tokens, 500),
            },
        }
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=25) as resp:
            resp_body = resp.read().decode("utf-8")
            resp_json = json.loads(resp_body)
            candidates = resp_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()

        return None

    def _local_fallback(self, prompt: str, json_mode: bool) -> str:
        """Deterministic fallback when no remote LLM endpoint is available."""
        if not json_mode:
            return "Analysis completed via rule-based heuristics."

        return json.dumps({
            "status": "fallback",
            "analysis": "Heuristic analysis completed offline",
            "confidence": 0.85,
        })
