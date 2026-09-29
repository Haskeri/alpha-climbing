// Адрес REST API серверной части.
// При запуске клиента отдельным dev-сервером (порт 8080) API ищется на том же хосте, порт 8000;
// при работе за обратным прокси (nginx) используется относительный путь /api.
window.ALPHA_API_URL = window.ALPHA_API_URL || (
  location.port === "8080" ? `${location.protocol}//${location.hostname}:8000/api` : "/api"
);
