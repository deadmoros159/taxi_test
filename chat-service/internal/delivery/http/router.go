package http

import (
	"github.com/gin-gonic/gin"
	swaggerFiles "github.com/swaggo/files"
	ginSwagger "github.com/swaggo/gin-swagger"
)

func SetupRouter(r *gin.Engine) {
	r.GET("/health", HealthCheck)
	r.GET("/docs/*any", ginSwagger.WrapHandler(swaggerFiles.Handler))
}

// @Summary Проверка состояния сервиса
// @Description Возвращает 200 если сервис запущен
// @Tags System
// @Success 200 {string} string "OK"
// @Router /health [get]
func HealthCheck(c *gin.Context) {
	c.JSON(200, gin.H{"status": "OK", "message": "Chat service is running"})
}
