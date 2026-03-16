package main

import (
	"os"

	"github.com/gin-gonic/gin"
	"github.com/rustam/chat-service/internal/delivery/http"
)

// @title Chat Service API
// @version 1.0.0
// @description Сервис чатов и звонков
// @host localhost:8006
// @BasePath /
func main() {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.Use(gin.Recovery())
	http.SetupRouter(r)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8006"
	}
	_ = r.Run(":" + port)
}
