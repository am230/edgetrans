import asyncio
import itertools
import logging
import time
from typing import Coroutine, Iterable, Tuple, TypedDict

import aiohttp

from .error import TranslationError
from .translator import Language, Translator


class Translation(TypedDict):
    text: str
    to: Language
    sentLen: dict[str, list[int]]


class DetectedLanguage(TypedDict):
    language: Language
    score: float


class TranslationResponse(TypedDict):
    detectedLanguage: DetectedLanguage
    translations: list[Translation]


class Error(TypedDict):
    code: int
    message: str


class ErrorResponse(TypedDict):
    error: Error


class RateLimitError(TranslationError):
    pass


def chunked[T](iterable: Iterable[T], size: int) -> Iterable[list[T]]:
    it = iter(iterable)
    while chunk := list(itertools.islice(it, size)):
        yield chunk


type TranslatedText = tuple[str, Language]
type TranslatedChunk = list[TranslatedText]


class RateLimitter:
    def __init__(self) -> None:
        self._end_time = 0

    def set_end_time(self, end_time: float) -> None:
        self._end_time = time.monotonic() + end_time

    def add_time(self, additional_time: float) -> None:
        time_left = self._end_time - time.monotonic()
        if time_left < 0:
            self._end_time = time.monotonic()
        self._end_time = self._end_time + additional_time

    async def __aenter__(self) -> None:
        self.add_time(0.05)
        time_left = self._end_time - time.monotonic()
        if time_left > 0:
            await asyncio.sleep(time_left)

    async def __aexit__(self, *args) -> None:
        pass


class EdgeTranslator(Translator):
    def __init__(self, session: aiohttp.ClientSession, auth_key: str, /) -> None:
        self._session = session
        self._auth_key = auth_key
        self._rate_limitter = RateLimitter()

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
        parts: str | Iterable[str],
        to_lang: Language,
        from_lang: Language | None = None,
        retry: int = 3,
        chunk_size: int = 100,
    ) -> list[Tuple[str, Language | None]]:
        if isinstance(parts, str):
            parts = [parts]
        url = "https://api-edge.cognitive.microsofttranslator.com/translate"
        headers = {"Authorization": f"Bearer {self._auth_key}"}

        params = {
            "from": from_lang or "",
            "to": to_lang,
            "api-version": "3.0",
            "includeSentenceLength": "true",
        }

        result_chunks: list[TranslatedChunk] = []

        async def fetch(index: int, chunk: list[str], retry: int):
            texts = [{"Text": part} for part in chunk]
            async with self._rate_limitter:
                async with self._session.post(
                    url, headers=headers, params=params, json=texts
                ) as resp:
                    if resp.status != 200:
                        if resp.content_type != "application/json":
                            raise TranslationError(
                                f"HTTP {resp.status} {resp.reason}: {await resp.text()}"
                            )
                        error: ErrorResponse = await resp.json()
                        if error["error"]["code"] == 429001:
                            await self.auth()
                            self._rate_limitter.set_end_time(60)
                            logging.info("Rate limit exceeded. Retrying in 60 seconds.")
                            return await fetch(index, chunk, retry - 1)
                        if retry > 0:
                            await self.auth()
                            return await fetch(index, chunk, retry - 1)
                        if error["error"]["code"] == 429001:
                            raise RateLimitError(error["error"]["message"])
                        else:
                            raise TranslationError(error["error"]["message"])
                    data: list[TranslationResponse] = await resp.json()
            result = result_chunks[index]
            for item in data:
                detected_lang = from_lang or item["detectedLanguage"]["language"]
                translations = item["translations"]
                for translation in translations:
                    text = translation["text"]
                    result.append((text, detected_lang))

        tasks: list[Coroutine] = []
        for i, chunk in enumerate(chunked(parts, chunk_size)):
            result_chunks.append([])
            tasks.append(fetch(i, chunk, retry))
        await asyncio.gather(*tasks)

        return list(itertools.chain.from_iterable(result_chunks))
