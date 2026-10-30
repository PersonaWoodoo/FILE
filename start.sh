#!/bin/bash
set -e

# Запускаем FastAPI сервер в фоне
python server.py &
SERVER_PID=$!

# Запускаем бота (он будет работать в основном потоке)
python bot.py &
BOT_PID=$!

# При завершении работы убиваем оба процесса
trap "kill $SERVER_PID $BOT_PID 2>/dev/null" EXIT

# Ждем завершения любого из процессов
wait -n

# Если один упал, гасим второй
kill $SERVER_PID $BOT_PID 2>/dev/null || true
