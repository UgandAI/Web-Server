from openai import OpenAI

from app.core.config import settings


class RecommendationService:
    def __init__(self, client=None):
        if client is None and not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is required for recommendations")
        self.client = client or OpenAI(
            api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT_SECONDS, max_retries=1
        )

    def generate(self, *, farm_size: float | None, district: str | None, crops: str | None) -> str:
        prompt = (
            f"The user is a farmer in Uganda. Farm size: {farm_size} acres. "
            f"District: {district}. Crops: {crops}. Provide one concise, encouraging initial "
            "piece of farming advice (maximum three sentences)."
        )
        response = self.client.responses.create(
            model=settings.OPENAI_MODEL,
            instructions="You are an expert agronomist providing tailored advice to Ugandan farmers.",
            input=prompt,
        )
        recommendation = response.output_text.strip()
        if not recommendation:
            raise RuntimeError("Recommendation service returned an empty response")
        return recommendation
