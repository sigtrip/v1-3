package main

import (
	"fmt"
	"net"
)

func main() {
	fmt.Println("Mesh/P2P demo node (Go)")
	// Пример UDP-сервера для обмена сообщениями
	addr := net.UDPAddr{
		Port: 9999,
		IP: net.ParseIP("0.0.0.0"),
	}
	conn, err := net.ListenUDP("udp", &addr)
	if err != nil {
		panic(err)
	}
	defer conn.Close()
	buf := make([]byte, 1024)
	for {
		n, remote, err := conn.ReadFromUDP(buf)
		if err == nil {
			fmt.Printf("Получено от %v: %s\n", remote, string(buf[:n]))
		}
	}
}
