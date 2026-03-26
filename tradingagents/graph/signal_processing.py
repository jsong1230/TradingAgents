"""Signal processing for extracting structured prediction decisions."""

import json
import re


class SignalProcessor:
    """Processes raw LLM output into structured prediction decisions."""

    def __init__(self, quick_thinking_llm):
        self.llm = quick_thinking_llm

    def process_signal(self, full_signal: str) -> str:
        """Extract structured JSON decision from the final decision text."""
        prompt = f"""아래 분석에서 최종 예측 결정을 추출하세요.

규칙:
- "action"은 반드시 분석 내용과 일치해야 합니다. 이벤트 발생 가능성이 높으면 "YES", 낮으면 "NO", 판단 불가하면 "SKIP".
- "reasoning"은 action과 모순되지 않아야 합니다.
- "confidence"는 0.0~1.0 사이 값 (예: 0.7 = 70% 확신)
- "edge"는 내 추정 확률 - 현재 시장가 (양수면 저평가, 음수면 고평가)

JSON 키는 영어, 값(reasoning)은 한국어로 작성하세요.

분석:
{full_signal}

아래 형식의 JSON만 반환하세요:
{{"action": "YES/NO/SKIP", "confidence": 0.0, "edge": 0.0, "position_size": 0.0, "reasoning": "한국어 요약", "time_horizon": "기간"}}"""

        response = self.llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        try:
            json_match = re.search(r'\{[^\{\}]*\}', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                required = ["action", "confidence", "edge", "position_size", "reasoning", "time_horizon"]
                if all(k in parsed for k in required):
                    parsed["action"] = parsed["action"].upper().strip()
                    if parsed["action"] not in ("YES", "NO", "SKIP"):
                        parsed["action"] = "SKIP"
                    return json.dumps(parsed)
        except (json.JSONDecodeError, AttributeError):
            pass

        action = "SKIP"
        text_upper = content.upper()
        if "YES" in text_upper and "NO" not in text_upper:
            action = "YES"
        elif "NO" in text_upper and "YES" not in text_upper:
            action = "NO"

        return json.dumps({
            "action": action,
            "confidence": 0.5,
            "edge": 0.0,
            "position_size": 0.0,
            "reasoning": "Could not parse structured output from LLM response.",
            "time_horizon": "unknown",
        })
