"""
Страница-редирект для deep link в мобильное приложение.
Принимает query-параметры и отдаёт HTML.
Android: Intent URL (работает в WebView Telegram), iOS: taxiapp://
"""
import json
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from urllib.parse import urlencode
from app.core.config import settings

router = APIRouter()


@router.api_route("/auth", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def app_auth_redirect(request: Request):
    """
    Страница для открытия мобильного приложения.
    Режимы:
    1) token + state — новый флоу (кнопка из бота): редирект на taxiapp://auth?token=&state=
    2) telegram_id, phone... — старый флоу
    """
    params = dict(request.query_params)
    base = str(settings.APP_REDIRECT_BASE_URL).rstrip("/")
    current_url = f"{base}/app/auth" + ("?" + urlencode(params) if params else "")

    # Режим: code (одноразовый код) + state — новый флоу
    code = params.get("code")
    state = params.get("state")
    if code:
        taxiapp_params = {"code": code}
        if state:
            taxiapp_params["state"] = state
        qs = urlencode(taxiapp_params)
        taxiapp_uri = "taxiapp://auth?" + qs
        # Intent для Android
        package = settings.ANDROID_PACKAGE or "com.example.taxi_app"
        fallback_url = current_url + ("&" if "?" in current_url else "?") + "fallback=1"
        intent_uri = (
            f"intent://auth?{qs}#Intent;scheme=taxiapp;package={package};"
            f"S.browser_fallback_url={fallback_url};end"
        )
    else:
        # Старый флоу: telegram_id, phone, name...
        taxiapp_params = {k: v for k, v in params.items() if k in ("telegram_id", "phone", "name", "username", "photo_id")}
        qs = urlencode(taxiapp_params)
        taxiapp_uri = "taxiapp://auth" + ("?" + qs if qs else "")
        package = settings.ANDROID_PACKAGE or "com.example.taxi_app"
        fallback_url = current_url + ("&" if "?" in current_url else "?") + "fallback=1"
        intent_uri = (
            f"intent://auth" + ("?" + qs if qs else "") +
            f"#Intent;scheme=taxiapp;package={package};"
            f"S.browser_fallback_url={fallback_url};end"
        )

    urls_js = json.dumps({"intent": intent_uri, "taxiapp": taxiapp_uri})

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Открытие приложения</title>
  <style>
    body {{ font-family: system-ui, sans-serif; padding: 24px; text-align: center; }}
    a {{ display: inline-block; margin: 12px; padding: 14px 24px; background: #2481cc; color: white; text-decoration: none; border-radius: 8px; }}
    a.secondary {{ background: #555; }}
  </style>
</head>
<body>
  <p>Открываем приложение...</p>
  <p><a href="#" id="openAppBtn">Открыть приложение</a></p>
  <p><a href="{current_url}" target="_blank" rel="noopener" class="secondary">Открыть в Chrome</a></p>
  <script>
    (function() {{
      var urls = {urls_js};
      var isAndroid = /Android/i.test(navigator.userAgent || "");
      document.getElementById("openAppBtn").href = isAndroid ? urls.intent : urls.taxiapp;
      var isFallback = new URLSearchParams(window.location.search).get("fallback") === "1";
      if (!isFallback) {{
        if (isAndroid) {{ try {{ window.location.href = urls.intent; }} catch (e) {{}} }}
        else {{ try {{ window.location.href = urls.taxiapp; }} catch (e) {{}} }}
      }}
    }})();
  </script>
</body>
</html>"""

    return HTMLResponse(content=html)
