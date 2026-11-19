# -*- coding: utf-8 -*-
"""Kimi (月之暗面 moonshot.cn) 大模型 API 接入
特点:
  - 轻量封装: 仅依赖 requests
  - 自动降级: Key 为空或失败时返回 None, 上层自动回退
  - 对话 + 单轮: 支持多轮对话和简单问答
使用方式:
  kimi = KimiClient()
  reply = kimi.chat("帮我规划长沙3日游")
"""
import sys
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE = os.path.dirname(_THIS_DIR)
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

try:
    import requests
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False

try:
    from config import (KIMI_API_KEY, KIMI_API_BASE, KIMI_MODEL,
                        KIMI_TIMEOUT, KIMI_TEMPERATURE, KIMI_ENABLED,
                        KIMI_PROMPT_PLAN, KIMI_PROMPT_SUMMARY)
except Exception:
    KIMI_API_KEY = ""
    KIMI_API_BASE = "https://api.moonshot.cn/v1"
    KIMI_MODEL = "moonshot-v1-8k"
    KIMI_TIMEOUT = 30
    KIMI_TEMPERATURE = 0.7
    KIMI_ENABLED = False
    KIMI_PROMPT_PLAN = ""
    KIMI_PROMPT_SUMMARY = ""


class KimiClient(object):
    """Kimi 客户端 - 简洁封装 chat completions 接口"""

    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = (api_key or KIMI_API_KEY or "").strip()
        self.base_url = base_url or KIMI_API_BASE
        self.model = model or KIMI_MODEL
        self.timeout = KIMI_TIMEOUT
        self.temperature = KIMI_TEMPERATURE
        self.messages = []  # 多轮对话历史
        self._last_error = None

    # ---------- 基础检查 ----------
    def available(self):
        """检查 Kimi 是否可用 (有 requests + 有 Key + 开关已打开)"""
        if not HAS_REQUESTS:
            self._last_error = "缺少 requests 库 (pip install requests)"
            return False
        if not self.api_key:
            self._last_error = "未配置 KIMI_API_KEY (在 config.py 中填入)"
            return False
        if not KIMI_ENABLED:
            self._last_error = "KIMI_ENABLED=False (在 config.py 中设为 True 启用)"
            return False
        return True

    def get_status(self):
        """返回状态字典, 用于界面显示"""
        return {
            "enabled": KIMI_ENABLED,
            "has_key": bool(self.api_key),
            "has_requests": HAS_REQUESTS,
            "model": self.model,
            "base_url": self.base_url,
            "error": self._last_error,
        }

    # ---------- 核心调用 ----------
    def _post_chat(self, messages, **kwargs):
        """底层 POST 到 /chat/completions"""
        if not self.available():
            return None
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.api_key,
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": False,
        }
        # 可选参数: max_tokens / top_p 等
        for k in ("max_tokens", "top_p"):
            if k in kwargs and kwargs[k] is not None:
                payload[k] = kwargs[k]
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            if resp.status_code != 200:
                self._last_error = "HTTP %s: %s" % (resp.status_code, resp.text[:200])
                return None
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                self._last_error = "无 choices 返回"
                return None
            content = choices[0].get("message", {}).get("content", "")
            self._last_error = None
            return content.strip()
        except Exception as e:
            self._last_error = "请求异常: " + str(e)
            return None

    # ---------- 便捷接口 ----------
    def ask(self, user_message, system_prompt=None, **kwargs):
        """单轮问答 (最简单的使用方式)
        client = KimiClient()
        reply = client.ask("你好")
        """
        if not self.available():
            return None
        messages = []
        sys_prompt = system_prompt or "你是 Kimi，由 Moonshot AI 提供的人工智能助手，你更擅长中文和英文的对话。你会为用户提供安全，有帮助，准确的回答。"
        messages.append({"role": "system", "content": sys_prompt})
        messages.append({"role": "user", "content": user_message})
        return self._post_chat(messages, **kwargs)

    def chat(self, user_message, system_prompt=None, remember=True, **kwargs):
        """多轮对话 - 保留历史
        client = KimiClient()
        client.chat("我想去长沙")
        client.chat("3天2夜大概要花多少钱")
        """
        if not self.available():
            return None
        messages = list(self.messages) if remember else []
        # system_prompt 始终放在最前面（无论是否有历史）
        if system_prompt:
            # 如果历史里已有 system，先移除避免重复
            if messages and messages[0].get("role") == "system":
                messages[0] = {"role": "system", "content": system_prompt}
            else:
                messages.insert(0, {"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        reply = self._post_chat(messages, **kwargs)
        if reply is not None and remember:
            # 只保留最近 20 条对话, 防止上下文爆炸
            self.messages = messages + [{"role": "assistant", "content": reply}]
            if len(self.messages) > 20:
                self.messages = self.messages[-20:]
        return reply

    def reset(self):
        """清空对话历史"""
        self.messages = []

    # ---------- 旅行规划专用接口 ----------
    def generate_plan(self, user_data, attractions, restaurants, hotels,
                      style_name=None):
        """让 Kimi 根据用户需求和 POI 数据生成行程
        参数:
          user_data: dict - 用户基础信息 (departure, destination, days...)
          attractions: list - 景点 POI
          restaurants: list - 餐厅 POI
          hotels: list - 酒店 POI
          style_name: str - 可选方案风格名 (会体现在 prompt 中)
        返回:
          str - Kimi 生成的行程文本, 失败返回 None
        """
        if not self.available():
            return None
        if not KIMI_PROMPT_PLAN:
            return None

        # 数据裁剪: 防止 token 过多, 每种最多取前 10 条
        def _escape_braces(s):
            """转义 { 和 } 字符，避免破坏 .format() 模板"""
            return str(s).replace("{", "{{").replace("}", "}}")

        def _brief(items, limit=10):
            brief = []
            for item in items[:limit]:
                if isinstance(item, dict):
                    name = _escape_braces(item.get("name", ""))
                    price = _escape_braces(str(item.get("ticket_price", "") or
                                item.get("price_per_night", "") or
                                item.get("avg_price", "")))
                    feat = _escape_braces(str(item.get("feature", "") or
                               item.get("features", "") or
                               item.get("tags", "") or ""))
                    rating = _escape_braces(str(item.get("rating", "")))
                    addr = _escape_braces(str(item.get("address", ""))[:40])
                    city_tag = ""
                    city = item.get("_city")
                    if city:
                        city_tag = "[" + _escape_braces(city) + "] "
                    line = "- " + city_tag + name + " (评分:" + str(rating) + " 价格:" + str(price) + "元)"
                    if feat and feat != "[]":
                        line += " [标签] " + str(feat)
                    if addr:
                        line += " [位置] " + str(addr)
                    brief.append(line)
            return "\n".join(brief) if brief else "无"
        # ---------- 构造 city_plan: 城市与天数分配 ----------
        cities = user_data.get("cities") or []
        if cities:
            _parts = []
            for i, c in enumerate(cities, 1):
                _parts.append("%d. %s - %s天" % (
                    i, _escape_braces(c.get("city", "")),
                    _escape_braces(c.get("days", ""))))
            city_plan_str = "\n".join(_parts)
        else:
            city_plan_str = "1. " + _escape_braces(user_data.get("destination", "当地")) + " - " + _escape_braces(user_data.get("days", "")) + "天"

        # ---------- 构造 poi_section: 景点/餐厅/酒店汇总 ----------
        poi_lines = []
        if attractions:
            poi_lines.append("【参考景点】\n" + _brief(attractions))
        if restaurants:
            poi_lines.append("【参考餐厅】\n" + _brief(restaurants))
        if hotels:
            poi_lines.append("【参考酒店】\n" + _brief(hotels))
        poi_section_str = "\n\n".join(poi_lines) if poi_lines else "暂无参考 POI 数据"

        try:
            prompt = KIMI_PROMPT_PLAN.format(
                dep_date=_escape_braces(user_data.get("dep_date", "")),
                days=_escape_braces(user_data.get("days", "")),
                people=_escape_braces(user_data.get("people", "")),
                age_group=_escape_braces(user_data.get("age_group", "")),
                tastes=_escape_braces(user_data.get("tastes", "")),
                hotel_level=_escape_braces(user_data.get("hotel_level", "")),
                transport_pref=_escape_braces(user_data.get("transport_pref", "")),
                budget=_escape_braces(user_data.get("budget", "")),
                city_plan=city_plan_str,
                poi_section=poi_section_str,
            )
        except KeyError as e:                            # ← 和 try 同级
            self._last_error = "Prompt 模板占位符不匹配: " + str(e)
            return None
        if style_name:
            prompt += "\n行程风格: " + _escape_braces(style_name) + "\n"

        return self.ask(prompt)

    def summarize(self, summary_text):
        """文案润色 - 把行程摘要写成一段生动的旅行手记"""
        if not self.available() or not KIMI_PROMPT_SUMMARY:
            return None
        safe_text = str(summary_text).replace("{", "{{").replace("}", "}}")[:1500]
        prompt = KIMI_PROMPT_SUMMARY.format(summary=safe_text)
        return self.ask(prompt)


def quick_ask(question, api_key=None):
    """最便捷的一行调用:
    from apis.kimi_api import quick_ask
    reply = quick_ask("帮我规划北京3日游")
    """
    client = KimiClient(api_key=api_key)
    return client.ask(question)


if __name__ == "__main__":
    # 测试入口: python -m apis.kimi_api
    print("=" * 50)
    print("  Kimi API 快速自检")
    print("=" * 50)
    client = KimiClient()
    status = client.get_status()
    print("  模型    :", status["model"])
    print("  接口    :", status["base_url"])
    print("  有 Key  :", "是" if status["has_key"] else "否")
    print("  已启用  :", "是" if status["enabled"] else "否 (在config.py中设KIMI_ENABLED=True)")
    print("  requests:", "已安装" if status["has_requests"] else "未安装")
    if status["error"]:
        print("  提示    :", status["error"])
    if client.available():
        print("\n  ✓ 尝试发送测试请求...")
        reply = client.ask("用一句话介绍你自己")
        if reply:
            print("  Kimi 回复:", reply[:100])
        else:
            print("  ✗ 调用失败:", client._last_error)
    else:
        print("\n  ○ 跳过测试 (未配置 Key)")
    print("=" * 50)