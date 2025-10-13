from typing import List, Tuple
from openai import OpenAI

from .base import LLMProvider
from .system_prompt import ALWAYS_STRICT_SYSTEM_PROMPT


class YandexGPTProvider(LLMProvider):
    """
    Yandex Cloud OpenAI SDK (Responses API) provider.

    Configure OpenAI client with:
      - api_key (YANDEX_API_KEY) or bearer token (YANDEX_IAM_TOKEN)
      - base_url = 'https://rest-assistant.api.cloud.yandex.net/v1'
      - project = folder_id
    And call client.responses.create(...)
    """

    def __init__(self, *, api_key: str | None, iam_token: str | None, folder_id: str, model: str, api_url: str | None = None):
        base_url = (api_url or 'https://rest-assistant.api.cloud.yandex.net/v1').rstrip('/')
        # Prefer Api-Key if provided, otherwise use Bearer token (OpenAI SDK expects api_key string)
        key = api_key or iam_token or ""
        # project corresponds to folder
        self.client = OpenAI(api_key=key, base_url=base_url, project=folder_id)
        self.model = model
        self.folder_id = folder_id

    def replace_anglicisms(self, text: str, style: str = 'auto', max_alternatives: int = 3) -> Tuple[str, List[str], str]:
        input_text = (
            ALWAYS_STRICT_SYSTEM_PROMPT
            + "\n\n"
            + f"Стиль: {style}. Макс_альтернатив: {max_alternatives}. Текст:\n\n{text}"
        )
        resp = self.client.responses.create(
            model=f"gpt://{self.folder_id}/{self.model}",
            input=input_text,
            temperature=0.1,
            max_output_tokens=600,
        )
        # Extract text
        content = ""
        try:
            if resp.output and len(resp.output) > 0:
                blocks = resp.output[0].content or []
                if blocks:
                    content = blocks[0].text
        except Exception:
            content = ""

        import json
        best, alternatives, explanation = text, [], ""
        if content:
            # Strip markdown code fences if present
            s = content.strip()
            if s.startswith("```"):
                s = s.lstrip("`")
                # remove optional language tag at line start
                if "\n" in s:
                    s = s.split("\n", 1)[1]
                # remove trailing fence if exists
                if s.endswith("```"):
                    s = s[:-3]
                content = s.strip()
            try:
                payload = json.loads(content)
                best = payload.get("best", best)
                alternatives = payload.get("alternatives", alternatives)
                explanation = payload.get("explanation", explanation)
            except Exception:
                best = content
        # Deduplicate and filter alternatives
        if alternatives:
            seen = set()
            uniq = []
            for a in alternatives:
                if not a or a == best or a in seen:
                    continue
                seen.add(a)
                uniq.append(a)
            alternatives = uniq
        return best, alternatives[:max_alternatives], explanation
