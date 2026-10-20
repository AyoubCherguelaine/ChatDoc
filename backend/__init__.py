"""Backend package — adds the project root to ``sys.path`` so the existing
RAG modules (``documents``, ``embeddings``, ``agent``, ``chat``) resolve when
this package is imported as ``backend``."""

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
if _root not in sys.path:
    sys.path.insert(0, _root)
