#!/bin/sh
# Каталоги логов и данных могут быть смонтированы с хоста (volume) –
# выдаём права пользователю приложения и запускаем процесс без root-привилегий.
set -e
mkdir -p "$ALPHA_LOG_DIR" "$ALPHA_DATA_DIR"
chown -R alpha:alpha "$ALPHA_LOG_DIR" "$ALPHA_DATA_DIR"
exec setpriv --reuid=alpha --regid=alpha --init-groups "$@"
