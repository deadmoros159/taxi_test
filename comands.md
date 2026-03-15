# ============ ДЕПЛОЙ ============
# 1. Закоммитить и запушить изменения
git add . && git commit -m "feat: ценообразование Узбекистан + OSRM" && git push

# 2. На сервере: обновить код и пересобрать
ssh root@102.214.69.160
cd /opt/taxi/deploy
./update-from-github.sh prod

# 3. Пересобрать order-service (применяет изменения ценообразования)
./deploy.sh prod rebuild order-service

# 4. Или пересобрать всё
./deploy.sh prod rebuild

# 5. Проверка
curl https://xhap.ru/order/health

# ============ ЛОГИ ============
# Все сервисы
docker-compose -f docker-compose.prod.yml -p taxi-prod logs -f

# Auth
docker logs --tail=50 taxi-auth-service-prod

# Driver
docker logs --tail=50 taxi-driver-service-prod

# Order
docker logs --tail=50 taxi-order-service-prod

# Admin
docker logs --tail=50 taxi-admin-service-prod

# Media
docker logs --tail=50 taxi-media-service-prod

# Telegram Bot
docker logs --tail=50 taxi-telegram-bot-service-prod