# edgetrans

Describe your project here.

## Installation

```bash
pip install edgetrans
```

## Usage

```python
import asyncio
from edgetrans import EdgeTranslator

async def main():
    translator = await EdgeTranslator.create()
    response = await translator.translate("hello", "ja")
    print(response) # [('こんにちは', 'en')]

asyncio.run(main())
```
