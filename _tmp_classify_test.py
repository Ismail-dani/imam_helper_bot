import sys
sys.path.insert(0, r"C:\Users\katri\Projects\imam-ai-bot\src")
from transcriber import _fatal_reason, _is_transient

cases = {
    "model_404":  "404 NOT_FOUND gemini-2.5-pro is no longer available to new users",
    "hard_quota": "429 RESOURCE_EXHAUSTED Quota exceeded generate_content_free_tier limit: 0, model gemini-3.1-pro",
    "soft_429":   "429 rate limit exceeded, please retry in 10s",
    "server_503": "503 Service Unavailable, model overloaded",
    "bad_400":    "400 INVALID_ARGUMENT Request contains an invalid argument",
}
for k, s in cases.items():
    e = RuntimeError(s)
    print(k.ljust(11), "| fatal =", str(bool(_fatal_reason(e))).ljust(5), "| transient =", _is_transient(e))
