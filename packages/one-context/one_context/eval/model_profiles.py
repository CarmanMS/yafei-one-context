"""Model profile mapping: scenario.provider.model → settings.json path.

Stage 2.X.6: onecxt eval 支持通过 scenario.yaml 的 provider.model 字段
选择不同的 gateway + model 组合，而不是硬编码 CCD2 那份 settings。

Mapping 表维护 5 个已知模型 profile：
  - claude-4.7: idealab gateway, [REDACTED]
  - kimi-2.6:   antchat gateway, Kimi-K2.6
  - kimi-2.5:   antchat gateway, Kimi-K2.5
  - glm-5:      antchat gateway, GLM-5
  - glm-5.1:    antchat gateway, GLM-5.1

当 scenario 没声明 provider.model 时，兜底走 CCD2 默认（Kimi-K2.6）保持向后兼容。
"""

from __future__ import annotations

import os
from pathlib import Path


# 5 个已知 model profile → settings.json 路径映射
MODEL_PROFILES: dict[str, str] = {
    "claude-4.7": "~/.claude/settings.json",
    "kimi-2.6": "~/.claude/settings.json.backup.20260529_153816",
    "kimi-2.5": "~/.claude/settings.theta.kimi.json",
    "glm-5": "~/.claude/settings.theta.glm.json",
    "glm-5.1": "~/.claude/settings.theta.glm51.json",
}

# CCD2 默认（兜底）
DEFAULT_SETTINGS_PATH = "~/.claude/settings.json.backup.20260529_153816"


def resolve_settings_path(model_name: str | None) -> str | None:
    """根据 scenario.provider.model 解析 settings.json 路径。

    Args:
        model_name: scenario.yaml 中 provider.model 字段值（如 "glm-5.1"）；
                    None 时走 CCD2 默认。

    Returns:
        展开后的绝对路径字符串；找不到 profile 或文件不存在时返回 None。

    Raises:
        ValueError: model_name 在 MODEL_PROFILES 中但文件不存在。
    """
    if not model_name or not model_name.strip():
        # 兜底：scenario 没声明 model → 走 CCD2 默认
        path = Path(DEFAULT_SETTINGS_PATH).expanduser()
        if not path.is_file():
            raise ValueError(
                f"Default settings not found: {DEFAULT_SETTINGS_PATH}. "
                "Please ensure CCD2 settings backup exists."
            )
        return str(path)

    model_key = model_name.strip()
    if model_key not in MODEL_PROFILES:
        raise ValueError(
            f"Unknown model profile: {model_key!r}. "
            f"Available profiles: {', '.join(sorted(MODEL_PROFILES.keys()))}. "
            "Add new profiles to MODEL_PROFILES in model_profiles.py."
        )

    raw_path = MODEL_PROFILES[model_key]
    path = Path(raw_path).expanduser()
    if not path.is_file():
        raise ValueError(
            f"Settings file for model profile {model_key!r} not found: {path}. "
            f"Expected at: {raw_path}"
        )

    return str(path)
