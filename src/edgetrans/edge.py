from typing import Tuple, TypedDict

import aiohttp

from .error import TranslationError
from .translator import Language, Translator


class Translation(TypedDict):
    text: str
    to: Language


class Response(TypedDict):
    translations: list[Translation]


class EdgeTranslator(Translator):
    def __init__(self, session: aiohttp.ClientSession, auth_key: str, /) -> None:
        self._session = session
        self._auth_key = auth_key

    @classmethod
    async def fetch_auth_key(cls, /, session: aiohttp.ClientSession) -> str:
        url = "https://edge.microsoft.com/translate/auth"
        async with session.get(url) as resp:
            key = await resp.text()
        return key

    @classmethod
    async def create(
        cls,
        /,
        auth_key: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> "EdgeTranslator":
        session = session or aiohttp.ClientSession()
        auth_key = auth_key or await cls.fetch_auth_key(session)
        return cls(session, auth_key)

    async def translate(
        self, to_lang: Language, *parts: str, from_lang: Language | None = None
    ) -> list[Tuple[str, Language]]:
        url = "https://api-edge.cognitive.microsofttranslator.com/translate"
        headers = {"Authorization": f"Bearer {self._auth_key}"}
        texts = [{"Text": part} for part in parts]
        params = {
            "from": from_lang or "",
            "to": to_lang,
            "api-version": "3.0",
        }
        async with self._session.post(
            url, headers=headers, params=params, json=texts
        ) as resp:
            if resp.status != 200:
                raise TranslationError(await resp.text())
            data: list[Response] = await resp.json()
        if len(data) != 1:
            raise TranslationError("Unexpected response")
        return [(part["text"], part["to"]) for part in data[0]["translations"]]
