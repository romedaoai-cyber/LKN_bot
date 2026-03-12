"""
BaseSkill: dual-AI routing — Gemini for simple tasks, Claude for complex ones.
"""
from __future__ import annotations
import os
import sys

# ── Gemini ──
try:
    import google.generativeai as genai
    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False

# ── Claude ──
try:
    import anthropic
    _CLAUDE_AVAILABLE = True
except ImportError:
    _CLAUDE_AVAILABLE = False


class BaseSkill:
    name: str = ""
    role: str = ""
    emoji: str = "🤖"
    description: str = ""
    system_prompt: str = ""
    use_claude: bool = False   # False = Gemini, True = Claude

    # Subclasses may override these models
    gemini_model: str = "gemini-2.0-flash"
    claude_model: str = "claude-sonnet-4-6"

    def generate(self, topic: str, context: dict | None = None) -> str:
        context = context or {}
        prompt = self._build_prompt(topic, context)
        if self.use_claude:
            return self._call_claude(prompt)
        return self._call_gemini(prompt)

    def _build_prompt(self, topic: str, context: dict) -> str:
        parts = [f"主題：{topic}"]
        if context.get("brand_profile"):
            bp = context["brand_profile"]
            parts.append(f"品牌資訊：{bp.get('name', '')} — 語氣：{bp.get('tone', '')} — 受眾：{bp.get('target_audience', '')}")
            if bp.get("product_knowledge"):
                parts.append(f"產品知識：{bp.get('product_knowledge', '')}")
        if context.get("inspiration"):
            parts.append(f"靈感素材：{context['inspiration']}")
        if context.get("skill_results"):
            for skill_name, result in context["skill_results"].items():
                parts.append(f"[{skill_name} 的洞察]：{result}")
        return "\n\n".join(parts)

    def _call_gemini(self, prompt: str) -> str:
        if not _GEMINI_AVAILABLE:
            return "⚠️ google-generativeai 未安裝"
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return "⚠️ 未設定 GEMINI_API_KEY"
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name=self.gemini_model,
                system_instruction=self.system_prompt,
            )
            resp = model.generate_content(prompt)
            return resp.text.strip()
        except Exception as e:
            return f"⚠️ Gemini 錯誤：{e}"

    def _call_claude(self, prompt: str) -> str:
        if not _CLAUDE_AVAILABLE:
            return "⚠️ anthropic 未安裝"
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return "⚠️ 未設定 ANTHROPIC_API_KEY"
        try:
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model=self.claude_model,
                max_tokens=2048,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            return f"⚠️ Claude 錯誤：{e}"
