"""bpp - a token-efficient text format for feeding structured data to LLMs."""

from .decoder import decode
from .encoder import encode
from .lexer import BppError

__version__ = "0.1.0"
__all__ = ["encode", "decode", "BppError", "__version__"]
