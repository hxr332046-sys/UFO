#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MiMo → OpenAI Compatible Proxy Server for UFO²

Key features:
1. Intercepts json_schema requests → returns 400 (UFO auto-falls back to text mode)
2. Injects JSON format enforcement into system prompt
3. Post-processes MiMo's natural language response to extract/convert to valid JSON
4. Uses MiMo's native /v1/chat/completions endpoint for OpenAI-format passthrough

Usage:
    python mimo_openai_proxy.py [--port 11434] [--mimo-base http://localhost:5678]
"""

import argparse
import json
import logging
import re
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mimo-proxy")

# Global config
MIMO_BASE = "http://localhost:5678"
PROXY_PORT = 11434

# JSON enforcement prompt suffix - added to system messages
JSON_ENFORCE_PROMPT = """

CRITICAL OUTPUT FORMAT RULE: You MUST respond with ONLY a valid JSON object. No markdown, no explanation outside JSON, no code fences. 
The JSON object must use these exact keys (lowercase): "observation", "thought", "status", "plan", "comment".
For HostAgent responses also include: "currentsubtask", "message", "questions".
For AppAgent responses also include: "function", "args", "savescreenshot".
- "status" must be one of: "FINISH", "CONTINUE", "PENDING", "ASSIGN"
- "plan" and "message" must be arrays of strings
- "savescreenshot" must be {"save": false, "reason": ""}
Example: {"observation": "...", "thought": "...", "status": "CONTINUE", "plan": ["step1"], "comment": "...", "currentsubtask": "...", "message": [], "questions": []}
"""


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON object from text that may contain markdown or extra content."""
    # Try 1: Direct parse
    try:
        result = json.loads(text.strip())
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Try 2: Extract from ```json ... ``` code block
    patterns = [
        r'```json\s*\n?(.*?)\n?\s*```',
        r'```\s*\n?(.*?)\n?\s*```',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1).strip())
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, ValueError):
                continue

    # Try 3: Find first balanced { ... } in text
    brace_count = 0
    start_idx = -1
    for i, ch in enumerate(text):
        if ch == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif ch == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx >= 0:
                candidate = text[start_idx:i + 1]
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict):
                        return result
                except (json.JSONDecodeError, ValueError):
                    start_idx = -1

    return None


def convert_text_to_json_via_llm(raw_text: str, original_messages: List[Dict]) -> Dict[str, Any]:
    """
    Two-pass strategy: Use mimo-v2-flash to convert MiMo's natural language
    response into a structured JSON object that UFO² expects.
    Always outputs union of HostAgent + AppAgent fields to satisfy both validators.
    """
    # First try to extract existing JSON from the response
    extracted = extract_json_from_text(raw_text)
    if extracted:
        result = {k.lower() if isinstance(k, str) else k: v for k, v in extracted.items()}
        # Ensure all required fields exist
        return _ensure_all_fields(result, raw_text)

    # Full schema - union of HostAgent and AppAgent fields
    schema_desc = '''{
  "observation": "string (REQUIRED, non-empty) - what you observe on the desktop/application",
  "thought": "string (REQUIRED, non-empty) - your reasoning process",
  "currentsubtask": "string - current sub-task to assign to AppAgent, or empty string if done",
  "message": ["string - tips/instructions for the AppAgent"],
  "status": "string - one of: FINISH, CONTINUE, PENDING, ASSIGN",
  "plan": ["string - future sub-tasks or actions"],
  "questions": ["string - questions for user"],
  "comment": "string - summary of current progress",
  "function": "string - API function name (e.g. click_input, set_text, run_shell) or empty string if no action needed",
  "args": "string - JSON string of function arguments, e.g. '{\"bash_command\": \"notepad\"}' or empty '{}'",
  "savescreenshot": {"save": false, "reason": ""}
}'''

    converter_prompt = f"""You are a JSON converter. Convert the following AI assistant response into a valid JSON object.

REQUIRED SCHEMA (all fields must be present):
{schema_desc}

CRITICAL RULES:
1. Output ONLY the JSON object, no markdown, no code fences, no extra text
2. All keys must be lowercase as shown in the schema
3. "observation" and "thought" MUST be non-empty strings - describe what the AI observed and reasoned
4. If the AI suggests running a command like "notepad" or "start notepad", set: "function": "run_shell", "args": "{{\\"bash_command\\": \\"notepad\\"}}"
5. If the AI suggests clicking something, set: "function": "click_input"
6. "status" should be "ASSIGN" if there are sub-tasks to delegate, "CONTINUE" if more steps needed, "FINISH" if done
7. "plan" and "message" must be arrays of strings (can be empty [])
8. "savescreenshot" must be {{"save": false, "reason": ""}}

AI RESPONSE TO CONVERT:
{raw_text}

OUTPUT (JSON only):"""

    payload = {
        "model": "mimo-v2-flash",
        "messages": [{"role": "user", "content": converter_prompt}],
        "stream": False,
    }

    data = json.dumps(payload).encode("utf-8")
    req = Request(
        f"{MIMO_BASE}/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            logger.info(f"Converter LLM response: len={len(content)}, preview={content[:200]}")
            
            # Try to extract JSON from the converter's response
            converted = extract_json_from_text(content)
            if converted:
                normalized = {k.lower() if isinstance(k, str) else k: v for k, v in converted.items()}
                return _ensure_all_fields(normalized, raw_text)
    except Exception as e:
        logger.warning(f"LLM JSON conversion failed: {e}, falling back to heuristic")

    # Fallback: heuristic conversion
    return _heuristic_convert(raw_text)


def _ensure_all_fields(d: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
    """Ensure all required fields for both HostAgent and AppAgent exist and are non-empty."""
    # Ensure observation and thought are non-empty (critical for validation)
    if not d.get("observation"):
        d["observation"] = raw_text[:500] if raw_text else "No observation available."
    if not d.get("thought"):
        d["thought"] = raw_text[:500] if raw_text else "Processing request."
    
    # Fill missing HostAgent fields
    d.setdefault("currentsubtask", "")
    d.setdefault("message", [])
    d.setdefault("status", d.get("status") or "CONTINUE")
    d.setdefault("plan", d.get("plan") or [])
    d.setdefault("questions", [])
    d.setdefault("comment", d.get("comment") or "")
    
    # Fill missing AppAgent fields
    d.setdefault("function", d.get("function") or "")
    d.setdefault("args", d.get("args") or "{}")
    d.setdefault("savescreenshot", d.get("savescreenshot") or {"save": False, "reason": ""})
    
    # Ensure savescreenshot has correct structure
    ss = d.get("savescreenshot", {})
    if isinstance(ss, dict):
        ss.setdefault("save", False)
        ss.setdefault("reason", "")
        d["savescreenshot"] = ss
    
    return d


def _heuristic_convert(text: str) -> Dict[str, Any]:
    """Fallback heuristic conversion when LLM conversion fails."""
    action = "NoAction"
    action_args = {}

    shell_match = re.search(r'run_shell\s*\(\s*(?:bash_command\s*=\s*)?["\']([^"\']+)["\']', text)
    if shell_match:
        action = "run_shell"
        action_args = {"bash_command": shell_match.group(1)}
    else:
        cmd_match = re.search(r'(?:execute|run|start|open|launch)\s+(?:the\s+)?(?:command\s+)?[`"\']?(\w+(?:\.\w+)?)[`"\']?', text, re.IGNORECASE)
        if cmd_match:
            action = "run_shell"
            action_args = {"bash_command": cmd_match.group(1)}

    plan_items = []
    for line in text.split('\n'):
        line = line.strip()
        if re.match(r'^\d+[\.\)]\s+', line) or re.match(r'^[-*]\s+', line):
            plan_items.append(re.sub(r'^[\d\.\)\-\*]+\s*', '', line).strip())

    return {
        "observation": text[:500],
        "thought": text[:500],
        "currentsubtask": plan_items[0] if plan_items else "",
        "message": [],
        "status": "ASSIGN" if plan_items else "CONTINUE",
        "plan": plan_items[:5],
        "questions": [],
        "comment": "Auto-converted from natural language (heuristic fallback).",
        "function": action,
        "args": json.dumps(action_args) if action_args else "{}",
        "savescreenshot": {"save": False, "reason": ""},
    }


def forward_to_mimo_native(messages: List[Dict], model: str = "mimo-v2-flash", 
                           stream: bool = False, thinking: bool = False) -> dict:
    """Forward request to MiMo's native /v1/chat/completions endpoint."""
    # Map model names
    model_mapping = {
        "gpt-4o": "mimo-v2-pro",
        "gpt-4": "mimo-v2-pro",
        "gpt-3.5-turbo": "mimo-v2-flash",
        "gpt-4o-mini": "mimo-v2-flash",
    }
    mimo_model = model_mapping.get(model, model)

    payload = {
        "model": mimo_model,
        "messages": messages,
        "stream": False,  # Always non-stream to proxy, we handle streaming ourselves
    }
    if thinking:
        payload["thinking"] = True

    data = json.dumps(payload).encode("utf-8")
    req = Request(
        f"{MIMO_BASE}/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error(f"MiMo API HTTP error {e.code}: {body[:500]}")
        raise
    except URLError as e:
        logger.error(f"MiMo API connection error: {e}")
        raise


class OpenAICompatHandler(BaseHTTPRequestHandler):
    """HTTP handler that translates OpenAI API calls to MiMo calls with JSON enforcement."""

    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} - {format % args}")

    def _send_json(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str, error_type: str = "server_error"):
        self._send_json(code, {
            "error": {
                "message": message,
                "type": error_type,
                "code": code,
            }
        })

    def do_GET(self):
        if self.path in ("/v1/models", "/models"):
            self._handle_models()
        elif self.path in ("/health", "/v1/health"):
            self._handle_health()
        else:
            self._send_error(404, f"Not found: {self.path}")

    def do_POST(self):
        if self.path in ("/v1/chat/completions", "/chat/completions"):
            self._handle_chat_completions()
        else:
            self._send_error(404, f"Not found: {self.path}")

    def _handle_health(self):
        try:
            req = Request(f"{MIMO_BASE}/health", method="GET")
            with urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            self._send_json(200, {"status": "ok", "mimo": result})
        except Exception as e:
            self._send_json(503, {"status": "degraded", "error": str(e)})

    def _handle_models(self):
        models = [
            {"id": "mimo-v2-flash", "object": "model", "owned_by": "mimo"},
            {"id": "mimo-v2-pro", "object": "model", "owned_by": "mimo"},
            {"id": "mimo-v2-omni", "object": "model", "owned_by": "mimo"},
            {"id": "gpt-4o", "object": "model", "owned_by": "mimo-alias"},
            {"id": "gpt-4", "object": "model", "owned_by": "mimo-alias"},
            {"id": "gpt-3.5-turbo", "object": "model", "owned_by": "mimo-alias"},
        ]
        self._send_json(200, {"object": "list", "data": models})

    def _handle_chat_completions(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            request_data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, ValueError) as e:
            self._send_error(400, f"Invalid JSON: {e}", "invalid_request_error")
            return

        # Intercept json_schema / response_format requests → return 400
        # This makes UFO² automatically fall back to text mode
        response_format = request_data.get("response_format")
        if response_format:
            rf_type = response_format if isinstance(response_format, str) else response_format.get("type", "")
            if rf_type in ("json_schema", "json_object"):
                logger.info(f"Rejecting response_format={rf_type} → 400 (UFO will fall back to text mode)")
                self._send_error(400,
                    "'response_format' of type 'json_schema' is not supported for this model",
                    "invalid_request_error")
                return

        messages = request_data.get("messages", [])
        model = request_data.get("model", "mimo-v2-flash")
        stream = request_data.get("stream", False)

        if not messages:
            self._send_error(400, "messages is required", "invalid_request_error")
            return

        # Inject JSON enforcement into system message
        enhanced_messages = []
        system_injected = False
        for msg in messages:
            msg_copy = dict(msg)
            role = msg_copy.get("role", "user")
            content = msg_copy.get("content", "")

            if role == "system" and isinstance(content, str):
                msg_copy["content"] = content + JSON_ENFORCE_PROMPT
                system_injected = True
            elif role == "system" and isinstance(content, list):
                # Handle list-type system content
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                combined = "\n".join(text_parts) + JSON_ENFORCE_PROMPT
                msg_copy["content"] = [{"type": "text", "text": combined}]
                system_injected = True

            enhanced_messages.append(msg_copy)

        # If no system message, add one
        if not system_injected:
            enhanced_messages.insert(0, {
                "role": "system",
                "content": "You are a Windows desktop automation assistant." + JSON_ENFORCE_PROMPT
            })

        logger.info(f"Chat request: model={model}, msgs={len(messages)}, stream={stream}")

        try:
            start_time = time.time()
            mimo_response = forward_to_mimo_native(enhanced_messages, model=model)
            elapsed = time.time() - start_time

            # Extract content from MiMo's OpenAI-format response
            raw_content = ""
            if "choices" in mimo_response and mimo_response["choices"]:
                msg = mimo_response["choices"][0].get("message", {})
                raw_content = msg.get("content", "")
            mimo_model = mimo_response.get("model", model)

            logger.info(f"MiMo raw response: model={mimo_model}, len={len(raw_content)}, time={elapsed:.1f}s")

            # Post-process: two-pass strategy - try extract JSON, or use LLM to convert
            json_content = convert_text_to_json_via_llm(raw_content, messages)
            final_content = json.dumps(json_content, ensure_ascii=False)

            logger.info(f"Converted to JSON: keys={list(json_content.keys())}, status={json_content.get('status', 'N/A')}")

            # Token estimation
            prompt_tokens = sum(len(str(m.get("content", ""))) // 4 for m in messages)
            completion_tokens = len(final_content) // 4
            total_tokens = prompt_tokens + completion_tokens

            completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
            created = int(time.time())

            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                # Send content chunk
                chunk_data = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": mimo_model,
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant", "content": final_content},
                        "finish_reason": None,
                    }],
                }
                self.wfile.write(f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n".encode("utf-8"))

                # Finish chunk
                finish_data = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": mimo_model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                self.wfile.write(f"data: {json.dumps(finish_data, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.write(b"data: [DONE]\n\n")
            else:
                response = {
                    "id": completion_id,
                    "object": "chat.completion",
                    "created": created,
                    "model": mimo_model,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": final_content},
                        "finish_reason": "stop",
                    }],
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    },
                }
                self._send_json(200, response)

        except HTTPError as e:
            self._send_error(502, f"MiMo API error: {e.code}", "upstream_error")
        except URLError as e:
            self._send_error(502, f"MiMo API connection failed: {e}", "upstream_error")
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            self._send_error(500, f"Internal error: {e}")


def run_server(port: int, mimo_base: str):
    global MIMO_BASE
    MIMO_BASE = mimo_base

    server = HTTPServer(("127.0.0.1", port), OpenAICompatHandler)
    logger.info(f"MiMo→OpenAI Proxy (UFO² Enhanced) started on http://127.0.0.1:{port}")
    logger.info(f"  MiMo backend: {MIMO_BASE}")
    logger.info(f"  OpenAI endpoint: http://127.0.0.1:{port}/v1/chat/completions")
    logger.info(f"  Features: json_schema rejection, JSON enforcement, text→JSON conversion")
    logger.info(f"  Models: mimo-v2-flash, mimo-v2-pro, mimo-v2-omni")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MiMo OpenAI-Compatible Proxy for UFO²")
    parser.add_argument("--port", type=int, default=11434, help="Proxy port (default: 11434)")
    parser.add_argument("--mimo-base", type=str, default="http://localhost:5678", help="MiMo AI Bridge URL")
    args = parser.parse_args()
    run_server(args.port, args.mimo_base)
