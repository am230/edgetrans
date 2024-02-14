from typing import Tuple, TypedDict

import aiohttp

from .error import TranslationError
from .translator import Language, Translator


class Translation(TypedDict):
    text: str
    to: Language
    sentLen: dict[str, list[int]]


class TranslationResponse(TypedDict):
    detectedLanguage: dict[str, str | float]
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

    async def auth(self, /) -> str:
        self._auth_key = await self.fetch_auth_key(self._session)
        return self._auth_key

    async def translate(
        self,
        parts: str | list[str],
        to_lang: Language,
        from_lang: Language | None = None,
        retry: int = 3,
    ) -> list[Tuple[str, Language | None]]:
        if isinstance(parts, str):
            parts = [parts]
        if len(parts) == 0:
            return []
        url = "https://api-edge.cognitive.microsofttranslator.com/translate"
        headers = {"Authorization": f"Bearer {self._auth_key}"}
        texts = [{"Text": part} for part in parts]
        params = {
            "from": from_lang or "",
            "to": to_lang,
            "api-version": "3.0",
            "includeSentenceLength": "true",
        }
        async with self._session.post(
            url, headers=headers, params=params, json=texts
        ) as resp:
            if resp.status != 200:
                # raise TranslationError(await resp.text())
                if retry > 0:
                    await self.auth()
                    return await self.translate(parts, to_lang, from_lang, retry - 1)
                raise TranslationError(await resp.text())
            data: list[TranslationResponse] = await resp.json()
        result = []
        for item in data:
            detected_lang = from_lang or item["detectedLanguage"]["language"]
            translations = item["translations"]
            for translation in translations:
                text = translation["text"]
                result.append((text, detected_lang))
        return result
