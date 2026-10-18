# Одноразовая проверка доступа к YouTube

Скрипт `scripts/check_youtube_connection.py` проверяет OAuth и ответ `channels.list(mine=true)` до установки Postiz. Это **не** проверка загрузки, публикации или планировщика Postiz.

1. В Google Cloud создайте веб-клиент OAuth для своего проекта. Добавьте свой аккаунт в тестовые пользователи приложения External/Testing.
2. Разрешённый адрес возврата: `http://localhost:8789/oauth/callback`. Добавлять адреса сторонних сервисов не нужно.
3. Сохраните JSON клиента вне Git, например в `research/private/youtube-local-client.json`, с правами доступа `600`.
4. Запустите из корня проекта:

   ```sh
   python3 scripts/check_youtube_connection.py --client research/private/youtube-local-client.json
   ```

5. Откройте `http://localhost:8789/`, выберите нужный аккаунт и канал. Запрашивается только `youtube.readonly`.

Сервер слушает только `127.0.0.1`, проверяет OAuth state, применяет PKCE, не пишет URL callback в журнал, не сохраняет коды/токены и отзывает полученный доступ после чтения канала. Результат без секретов сохраняется в `research/private/youtube-read-check.json`. Поле `test_access_revoked` отражает подтверждение отзыва; если оно false, проверьте разрешения Google вручную. Сервер завершается через 15 минут или по Ctrl+C.

Проверка TLS остаётся включённой. Если в Python установлен `certifi`, используется его хранилище корневых сертификатов; иначе — системное хранилище Python. Ошибка `SSLCertVerificationError` требует настройки доверенных сертификатов, а не отключения HTTPS-проверки.

Успешный ответ подтверждает доступ выбранного Google-аккаунта к каналу через API. Для постоянной работы потребуется отдельная настройка исполнителя публикаций и проверка загрузки/видимости/расписания. Тестовый OAuth-клиент не содержит будущего адреса Postiz.

Проверки без сети и настоящих секретов:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Основание для локального callback: [официальный OAuth web-server flow Google](https://developers.google.com/identity/protocols/oauth2/web-server). Localhost допускается для разработки; для рабочего внешнего адреса нужен HTTPS.
