import abc
from typing import Literal, Tuple

type Language = Literal[
    "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru", "ja", "zh", "ko", "ar"
]


class Translator(abc.ABC):
    @abc.abstractmethod
    async def translate(
        self,
        parts: str | list[str],
        to_lang: Language,
        from_lang: Language | None = None,
    ) -> list[Tuple[str, Language | None]]:
        ...
