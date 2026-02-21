"""
Страница-редирект для deep link в мобильное приложение.
Принимает query-параметры и отдаёт HTML с редиректом на taxiapp://auth?...
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from urllib.parse import urlencode
from app.core.config import settings

router = APIRouter()


@router.get("/auth", response_class=HTMLResponse)
async def app_auth_redirect(request: Request):
    """
    Редирект на taxiapp://auth для открытия мобильного приложения.
    Принимает: telegram_id, phone, name, username (опц.), photo_id (опц.)
    Для Android использует Intent URL если задан ANDROID_PACKAGE.
    """
    params = dict(request.query_params)
    taxiapp_params = {
        k: v for k, v in params.items()
        if k in ("telegram_id", "phone", "name", "username", "photo_id")
    }
    taxiapp_uri = "taxiapp://auth?" + urlencode(taxiapp_params)

    # Intent URL для Android (если задан package)
    taxiapp_escaped = taxiapp_uri.replace("\\", "\\\\").replace('"', '\\"')
    if settings.ANDROID_PACKAGE:
        intent_uri = f"intent://auth?{urlencode(taxiapp_params)}#Intent;scheme=taxiapp;package={settings.ANDROID_PACKAGE};end"
        intent_escaped = intent_uri.replace("\\", "\\\\").replace('"', '\\"')
        script_content = (
            f'  <script>'
            f'(function(){{\n'
            f'  var ua=navigator.userAgent||navigator.vendor||"";\n'
            f'  if(/android/i.test(ua)){{location.href="{intent_escaped}";return;}}\n'
            f'  location.href="{taxiapp_escaped}";\n'
            f'}})();\n'
            f'  </script>'
        )
    else:
        script_content = f'  <script>window.location.href="{taxiapp_escaped}";</script>'

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0;url={taxiapp_uri}">
  <title>Открытие приложения</title>
{script_content}
</head>
<body>
  <p>Открываем приложение...</p>
  <p><a href="{taxiapp_uri}">Открыть приложение</a></p>
</body>
</html>"""

    return HTMLResponse(content=html)
