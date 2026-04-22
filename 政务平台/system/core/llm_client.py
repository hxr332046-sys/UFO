#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LLM 客户端 — 材料审核、表单映射、结果分析
合规：LLM 只做审核和建议，不做认证操作
"""

import json
import os

# LLM 配置（支持 OpenAI 兼容接口）
LLM_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "config", "llm.json")


def load_llm_config():
    if os.path.exists(LLM_CONFIG_FILE):
        with open(LLM_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"provider": "openai", "api_key": "", "model": "gpt-4o", "base_url": "https://api.openai.com/v1"}


def save_llm_config(config):
    os.makedirs(os.path.dirname(LLM_CONFIG_FILE), exist_ok=True)
    with open(LLM_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


class LLMClient:
    """LLM 引擎：材料审核 + 表单映射 + 结果分析"""

    def __init__(self, config=None):
        self.config = config or load_llm_config()

    def _call_llm(self, system_prompt, user_content):
        """调用 LLM API"""
        try:
            import requests as req
            headers = {
                "Authorization": f"Bearer {self.config.get('api_key', '')}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.config.get("model", "gpt-4o"),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }
            base_url = self.config.get("base_url", "https://api.openai.com/v1")
            r = req.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=60)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            return {"error": str(e), "approved": False}

    def review_materials(self, task_type, materials):
        """
        审核客户提交的材料
        返回：{approved, issues, suggestions, form_mapping}
        """
        system_prompt = """你是政务注册材料审核专家。审核客户提交的注册材料，判断是否合规。

合规要求：
1. 材料必须完整，不缺项
2. 信息必须一致，不矛盾
3. 格式必须规范，符合政务平台要求
4. 不得包含虚假信息

返回 JSON：
{
  "approved": true/false,
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"],
  "form_mapping": {"字段名": "值"},
  "risk_level": "low/medium/high",
  "summary": "审核摘要"
}"""

        user_content = f"""业务类型：{task_type}
客户材料：
{json.dumps(materials, ensure_ascii=False, indent=2)}

请审核以上材料是否合规，能否提交到政务平台。"""

        return self._call_llm(system_prompt, user_content)

    def map_form_fields(self, task_type, materials, gov_form_schema=None):
        """
        将客户材料映射到政务平台表单字段
        返回填写方案
        """
        system_prompt = """你是政务注册表单填写专家。将客户材料映射到政务平台的表单字段。

要求：
1. 字段映射必须准确
2. 值必须符合政务平台的格式要求
3. 不确定的字段标记为 needs_confirm
4. 需要客户手动完成的字段标记为 needs_client_input（如签名、认证）

返回 JSON：
{
  "fields": {"字段名": {"value": "值", "auto_fill": true/false, "needs_confirm": true/false}},
  "needs_client_actions": ["需要客户完成的操作"],
  "fill_order": ["字段1", "字段2"]
}"""

        user_content = f"""业务类型：{task_type}
客户材料：{json.dumps(materials, ensure_ascii=False)}
政务表单结构：{json.dumps(gov_form_schema or {}, ensure_ascii=False)}"""

        return self._call_llm(system_prompt, user_content)

    def analyze_gov_response(self, gov_response):
        """
        分析政务平台的审核结果
        """
        system_prompt = """你是政务注册结果分析专家。分析政务平台返回的审核结果。

返回 JSON：
{
  "result": "approved/rejected/supplement_needed",
  "summary": "结果摘要",
  "issues": ["问题1"],
  "actions_needed": ["需要做的操作"],
  "client_message": "发给客户的通知消息"
}"""

        user_content = f"""政务平台返回：
{json.dumps(gov_response, ensure_ascii=False, indent=2)}"""

        return self._call_llm(system_prompt, user_content)

    def generate_client_message(self, task_status, task_data):
        """生成给客户的通知消息"""
        system_prompt = """你是客户服务助手。根据任务状态生成简洁的通知消息。
消息要：准确、简洁、有行动指引。不要多余客套话。
返回 JSON：{"message": "通知内容"}"""

        user_content = f"""任务状态：{task_status}
任务数据：{json.dumps(task_data, ensure_ascii=False)[:1000]}"""

        return self._call_llm(system_prompt, user_content)
