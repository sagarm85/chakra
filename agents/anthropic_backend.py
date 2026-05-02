import anthropic


class AnthropicBackend:
    def __init__(self, api_key: str, model: str):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def call(self, system: str, user: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=8096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
