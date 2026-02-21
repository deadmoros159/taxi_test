# App Links / Universal Links — настройка

Файлы для прямого открытия приложения по ссылке `https://xhap.ru/app/auth?...` без показа веб-страницы.

## 1. Android (assetlinks.json)

**Получить SHA-256 отпечаток:**
```bash
# Debug-сборка
keytool -list -v -keystore ~/.android/debug.keystore -alias androiddebugkey -storepass android

# Release-сборка
keytool -list -v -keystore /путь/к/release.keystore -alias ваш_alias
```

Скопируйте строку `SHA256:` (формат `AA:BB:CC:DD:...`).

**Отредактировать `assetlinks.json`:**
- `package_name` — applicationId из `build.gradle` (например, `com.yourcompany.taxi`)
- `sha256_cert_fingerprints` — подставьте свой отпечаток (для debug и release можно указать оба в массиве)

## 2. iOS (apple-app-site-association)

**Отредактировать `apple-app-site-association`:**
- `appID` — `TEAM_ID.BUNDLE_ID` (например, `V94H4DWGDW.com.yourcompany.taxi`)
  - Team ID: Xcode → Signing & Capabilities
  - Bundle ID: в настройках проекта
- `paths` — уже настроено для `/app/auth`

## 3. Деплой на сервер

1. Заполните плейсхолдеры в файлах.
2. Скопируйте конфиг nginx и перезагрузите:
   ```bash
   sudo cp /opt/taxi/taxi_back/deploy/nginx/prod.conf /etc/nginx/sites-available/xhap.ru
   # или добавьте location вручную
   nginx -t && nginx -s reload
   ```
3. Проверьте:
   ```bash
   curl https://xhap.ru/.well-known/assetlinks.json
   curl https://xhap.ru/.well-known/apple-app-site-association
   ```

## 4. Flutter-клиент

Настройте intent-filter (Android) и Associated Domains (iOS) — см. инструкции в проекте приложения.
