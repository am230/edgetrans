import pytest

from edgetrans import EdgeTranslator


@pytest.mark.asyncio
async def test_translate():
    translator = await EdgeTranslator.create()
    response = await translator.translate("hello", "ja", from_lang="en")
    assert len(response) == 1
    text, lang = response[0]
    assert text == "こんにちは"
    assert lang == "ja"


if __name__ == "__main__":
    pytest.main()
