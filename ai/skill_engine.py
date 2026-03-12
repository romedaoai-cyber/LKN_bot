"""
SkillEngine: orchestrates multiple AI Skills to produce a LinkedIn post.

Flow:
1. crisis_director  — risk assessment first (Claude)
2. selected support skills — run in sequence, collect insights
3. copy_architect   — design structure (Claude, if selected)
4. writing_style    — final post generation using all insights (Claude)
"""
from __future__ import annotations
from typing import Callable

from ai.skills.writing_style import WritingStyleSkill
from ai.skills.trend_radar import TrendRadarSkill
from ai.skills.market_strategist import MarketStrategistSkill
from ai.skills.audience_persona import AudiencePersonaSkill
from ai.skills.content_strategist import ContentStrategistSkill
from ai.skills.crisis_director import CrisisDirectorSkill
from ai.skills.copy_architect import CopyArchitectSkill
from ai.skills.ad_analyzer import AdAnalyzerSkill
from ai.skills.scholar_friend import ScholarFriendSkill


ALL_SKILLS = {
    "writing_style": WritingStyleSkill(),
    "trend_radar": TrendRadarSkill(),
    "market_strategist": MarketStrategistSkill(),
    "audience_persona": AudiencePersonaSkill(),
    "content_strategist": ContentStrategistSkill(),
    "crisis_director": CrisisDirectorSkill(),
    "copy_architect": CopyArchitectSkill(),
    "ad_analyzer": AdAnalyzerSkill(),
    "scholar_friend": ScholarFriendSkill(),
}

# Skills that are always run (not user-selectable as optional)
CORE_SKILLS = {"writing_style", "crisis_director"}

# Skills available for user selection
OPTIONAL_SKILLS = {k: v for k, v in ALL_SKILLS.items() if k not in CORE_SKILLS}


def run_skills(
    topic: str,
    selected_skill_keys: list[str],
    brand_profile: dict | None = None,
    inspiration: str = "",
    on_progress: Callable[[str, str], None] | None = None,
) -> dict:
    """
    Run the skill pipeline.

    Returns:
        {
            "risk": str,           # crisis_director output
            "risk_level": str,     # "low" | "medium" | "high"
            "skill_results": dict, # {skill_key: output}
            "post": str,           # final post from writing_style
        }
    """
    context = {
        "brand_profile": brand_profile or {},
        "inspiration": inspiration,
        "skill_results": {},
    }

    def _progress(step: str, text: str):
        if on_progress:
            on_progress(step, text)

    # ── Step 1: Risk assessment ──
    _progress("crisis_director", "評估發文風險...")
    risk_output = ALL_SKILLS["crisis_director"].generate(topic, context)
    context["skill_results"]["公關危機總監"] = risk_output
    risk_level = _parse_risk_level(risk_output)

    # ── Step 2: Support skills ──
    support_order = [
        "trend_radar", "market_strategist", "audience_persona",
        "content_strategist", "ad_analyzer", "scholar_friend",
    ]
    for key in support_order:
        if key not in selected_skill_keys:
            continue
        skill = ALL_SKILLS[key]
        _progress(key, f"執行 {skill.name}...")
        result = skill.generate(topic, context)
        context["skill_results"][skill.name] = result

    # ── Step 3: Structure (if selected) ──
    if "copy_architect" in selected_skill_keys:
        _progress("copy_architect", "設計文章架構...")
        arch_result = ALL_SKILLS["copy_architect"].generate(topic, context)
        context["skill_results"]["文案架構師"] = arch_result

    # ── Step 4: Final post generation ──
    _progress("writing_style", "產出 LinkedIn 貼文...")
    final_post = ALL_SKILLS["writing_style"].generate(topic, context)

    return {
        "risk": risk_output,
        "risk_level": risk_level,
        "skill_results": context["skill_results"],
        "post": final_post,
    }


def rewrite_with_feedback(current_post: str, feedback: str, brand_profile: dict | None = None) -> str:
    """
    Rewrite a post based on user feedback.
    """
    context = {
        "brand_profile": brand_profile or {},
        "inspiration": "",
        "skill_results": {
            "原始貼文": current_post,
            "用戶反饋": feedback,
        },
    }
    topic = f"根據反饋改寫貼文。反饋：{feedback}"
    return ALL_SKILLS["writing_style"].generate(topic, context)


def _parse_risk_level(risk_output: str) -> str:
    if "🔴" in risk_output or "高風險" in risk_output:
        return "high"
    if "🟡" in risk_output or "中風險" in risk_output:
        return "medium"
    return "low"
