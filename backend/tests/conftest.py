"""
conftest.py — Test isolation via environment variables and import stubs.

Strategy: We import the real pipeline package BUT stub out the individual
heavy C/GPU-dependent sub-modules BEFORE conftest triggers pipeline/__init__.py.
This way `from pipeline.osint_engine import ...` works with the real code.
"""
from __future__ import annotations
import os
import sys
import types
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1. Set dummy API keys before any app module is imported
# ---------------------------------------------------------------------------
_TEST_ENV = {
    "GROQ_API_KEY": "test-groq-key",
    "SERPAPI_API_KEY": "test-serpapi-key",
    "OPENAI_API_KEY": "test-openai-key",
    "LLM_PROVIDER": "openai",
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "API_BASE_URL": "http://testserver",
    "FRONTEND_URL": "http://localhost:3000",
    "TELEGRAM_BOT_TOKEN": "",
    "TELEGRAM_CHAT_ID": "",
}
for k, v in _TEST_ENV.items():
    os.environ.setdefault(k, v)

# ---------------------------------------------------------------------------
# 2. Stub native / heavy C-extension modules before any real imports run
# ---------------------------------------------------------------------------
_STUB_MODULES = [
    # OpenCV / GPU
    "cv2",
    # PyTorch family
    "torch", "torch.nn", "torch.nn.functional", "torchvision",
    "torchvision.transforms", "torchvision.models",
    "torchvision.transforms.functional",
    # HuggingFace
    "transformers",
    # Face detection
    "facenet_pytorch",
    # TIMM
    "timm",
    # Grad-CAM
    "grad_cam", "ttach",
    # Scipy / sklearn
    "scipy", "scipy.signal", "scipy.fft", "scipy.stats",
    "sklearn", "sklearn.preprocessing",
    # Matplotlib
    "matplotlib", "matplotlib.pyplot", "matplotlib.colors",
    # PIL (only stub if not installed; Pillow should be available)
    # c2pa
    "c2pa", "c2pa_python",
    # LLM SDKs
    "groq", "openai", "anthropic",
    # OSINT
    "serpapi",
    # Download
    "yt_dlp",
    # Blockchain / hash
    "web3", "imagehash",
    # Misc
    "dateparser",
    "supabase",
    # Telegram
    "telegram", "telegram.ext",
    # imageio
    "imageio",
    # numpy (allow real if available)
    # "numpy",
]

for mod_name in _STUB_MODULES:
    parts = mod_name.split(".")
    # Register each level of the dotted path
    for i in range(1, len(parts) + 1):
        full = ".".join(parts[:i])
        if full not in sys.modules:
            sys.modules[full] = MagicMock()

# ---------------------------------------------------------------------------
# 3. Stub telegram_bot (top-level module in backend/)
# ---------------------------------------------------------------------------
if "telegram_bot" not in sys.modules:
    sys.modules["telegram_bot"] = MagicMock()

# ---------------------------------------------------------------------------
# 4. Now pre-stub the pipeline sub-modules that pull in cv2/torch so that
#    pipeline/__init__.py can be imported safely.
#    We do NOT stub pipeline itself — we let it load as a real package.
# ---------------------------------------------------------------------------
_PIPELINE_SUB_STUBS = [
    "pipeline.c2pa_inspector",
    "pipeline.video_processor",
    "pipeline.vision_model",
    "pipeline.temporal_analysis",
    "pipeline.visual_threat_analysis",
    "pipeline.psychological_analysis",
    "pipeline.signal_forensics",
    "pipeline.osint_vision",
    "pipeline.threat_restriction",
    "pipeline.resemble_service",
    "pipeline.social_context",
    "pipeline.blockchain_service",
    "pipeline.telegram_notifier",
    "pipeline.c2pa_checker",
    # orchestrator imports cv2 indirectly — stub it for main.py tests
    # but DON'T stub pipeline.osint_engine or pipeline.credibility_pipeline
    # because those are the actual modules under test.
]
for mod_name in _PIPELINE_SUB_STUBS:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Stub pipeline.orchestrator.run_pipeline so main.py can import without cv2
if "pipeline.orchestrator" not in sys.modules:
    orch_stub = MagicMock()
    orch_stub.run_pipeline = MagicMock(return_value=None)
    sys.modules["pipeline.orchestrator"] = orch_stub

# ---------------------------------------------------------------------------
# 5. Pre-import the real pipeline package (triggers __init__ with our stubs)
# ---------------------------------------------------------------------------
import importlib
import pathlib

# We need pipeline to be importable as a real package, not a MagicMock.
# Do this by adding backend/ to sys.path and importing it properly.
_backend_dir = pathlib.Path(__file__).parent.parent  # .../backend/
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))
