"""`python -m bpp ...` works even when the `bpp` script is not on PATH."""

import sys

from .cli import main

sys.exit(main())
