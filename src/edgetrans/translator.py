import abc
from typing import Literal, Tuple

type Language = Literal[
    "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru", "ja", "zh", "ko", "ar"
]


class Translator(abc.ABC):
    @abc.abstractmethod
    async def translate(
        self, to_lang: Language, *parts: str, from_lang: Language | None = None
    ) -> list[Tuple[str, Language]]:
        ...
