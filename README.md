# AI Mail Router (PoC)

1. Mikroserwisowe API przyjmuje przez HTTP wiadomość od użytkownika 
(e-mail nadawcy + dowolny tekst, np. "nie działa mi komputer").
2. AI Agent, oparty silnik LLM Ollama (model qwen2.5:7b-instruct), decyduje do którego działu
firmy zgłoszenie pasuje i wywołuje narzędzie (function calling).
3. Narzędzie wysyła e-mail do właściwego działu, z nagłówkiem `Reply-To` ustawionym na nadawcę.
4. Wysłane maile trafiają do MailHoga.

## Wymagania

- Docker + Docker Compose.
- ~5 GB wolnego miejsca na dysku (model LLM) i połączenie internetowe przy
  pierwszym uruchomieniu w celu pobrania modelu.

## Szybki start

```bash
git clone https://github.com/webdevanki/poc-ai-mail-router.git
cd poc-ai-mail-router
docker compose up -d
```

Przy pierwszym uruchomieniu kontener `ollama` pobiera model
`qwen2.5:7b-instruct` (ok. 4.7 GB) - w zależności od łącza może to potrwać
od kilku do kilkunastu minut. Kontener `api` czeka, aż model będzie w
pełni gotowy (`depends_on: condition: service_healthy`) - sprawdzenie statusu za pomocą:

```bash
docker compose ps
```

Gdy `api` ma status `Up`, wszystko jest gotowe.

## Endpointy

| Co | Adres |
| :--- | :--- |
| Swagger / OpenAPI | http://localhost:8000/api/v1/docs |
| Health check | http://localhost:8000/health |
| Routing wiadomości | `POST` http://localhost:8000/api/v1/route |
| MailHog (podgląd wysłanych maili) | http://localhost:8025 |
| Panel testowy (do szybkiego ręcznego testowania) | http://localhost:8000/panel |

Panel testowy to prosty formularz HTML - alternatywa dla cURL/Swaggera,
pozwalająca wysłać zgłoszenie (e-mail + wiadomość) i zobaczyć wynik routingu
bezpośrednio w przeglądarce.

## Przykładowy request

```bash
curl -X POST http://localhost:8000/api/v1/route -H "Content-Type: application/json" -d "{\"email\": \"jan.nowak@example.com\", \"message\": \"Drukarka w biurze jest zepsuta, nie dziala i wyswietla blad przy kazdej probie druku.\"}"
```

(Działa w bash/Git Bash i w `cmd.exe`.)

W Windows PowerShell użyj tego:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/route -ContentType "application/json" -Body '{"email": "jan.nowak@example.com", "message": "Drukarka w biurze jest zepsuta, nie dziala i wyswietla blad przy kazdej probie druku."}'
```

Uwaga: powyższy przykład celowo nie zawiera polskich znaków diakrytycznych (ą, ę, ł, ś...) - API w pełni je obsługuje (Ollama i FastAPI działają na UTF-8), ale wpisane bezpośrednio w `-d` w niektórych terminalach Windows (np. Git Bash ze złą stroną kodową) mogą się uszkodzić, zanim curl wyśle request. Bezpieczniej wtedy wysłać payload z pliku UTF-8 (`--data-binary @request.json`) niż wpisywać go bezpośrednio w linii poleceń.

Przykładowa odpowiedź:

```json
{
  "target_email": "it@example.com",
  "category": "IT",
  "reasoning": "Zgloszenie dotyczy fizycznej awarii sprzetu (drukarki)."
}
```

Wiadomość pojawi się w MailHogu (http://localhost:8025) z nagłówkiem
`Reply-To: jan.nowak@example.com` - odpowiedź trafi do pierwotnego nadawcy.

Dozwolone adresy docelowe:
`human-resources@example.com`, `help-desk@example.com`, `it@example.com`,
`kadry@example.com`, `other@example.com`.

## Architektura (skrót)

```
HTTP request → walidacja (Pydantic) → agent AI (pydantic-ai + Ollama) → tool call: send_email_tool → aiosmtplib → MailHog
```

- **`api/app/main.py` + `routers/v1.py`** - warstwa HTTP (FastAPI): przyjmuje
  request, waliduje, deleguje do agenta, mapuje błędy na kody HTTP.
- **`api/app/agent.py`** - warstwa AI: `pydantic-ai` + natywny `OllamaModel`,
  system prompt opisujący 5 kategorii, narzędzie `send_email_tool`
  rejestrowane przez `@agent.tool`. Wynik zwracany do API jest
  budowany z argumentów przekazanych do narzędzia, a nie z
  osobnej generacji modelu - wyklucza to strukturalnie sytuację, w której
  agent wyśle maila do jednego działu, a API zwróci inny.
- **`api/app/mailer.py`** - warstwa mailowa: `aiosmtplib` (asynchroniczne
  SMTP), żeby nie blokować event loopa FastAPI podczas wysyłki.
- **`api/app/schemas.py`** - `RequestIn`, `RouteResult` i
  `TargetDepartment` jako `Enum` 

Trzy warstwy (API / agent / narzędzie mailowe) są od siebie modularnie
oddzielone.

Pełny opis decyzji architektonicznych i ich uzasadnień:
[docs/decyzje_architektoniczne.md](docs/decyzje_architektoniczne.md).

## Testy

Testy są integracyjne - realnie odpytują działającą Ollamę i MailHoga, więc
wymagają uruchomionego stacku (`docker compose up -d`). Obraz produkcyjny
celowo nie zawiera folderu `tests/`, więc testy uruchamia
się przez tymczasowy kontener z zamontowanym kodem:

```bash
docker compose build api
docker run --rm --network ai-mail-router_ai-router-net \
  -v "$(pwd)/api:/app" -w /app \
  ai-mail-router-api python -m pytest tests/ -v
```

Uwaga: testy wywołujące agenta AI odpytują model LLM na CPU i mogą
trwać od kilkudziesięciu sekund do kilku minut na test.

## Ograniczenia PoC

- Model liczony na samym CPU (bez GPU) jest wolny - pojedyncze zapytanie do
  agenta trwa od ok. 1 do kilku minut. W produkcji uzasadniałoby to
  wprowadzenie kolejki (np. Redis/RabbitMQ) między przyjęciem requestu a
  inferencją modelu, zamiast synchronicznego czekania w request-response.
- Kategorie `it`/`help-desk` oraz `human-resources`/`kadry` mogą się
  częściowo pokrywać znaczeniowo dla niejednoznacznych zgłoszeń (np. "nie
  mogę się zalogować" - to problem sprzętowy czy proceduralny?) -
  rozstrzygane jawnymi regułami w system prompcie agenta
  (`api/app/agent.py`), ale przypadki brzegowe pozostają z natury trudne
  dla klasyfikacji opartej o LLM i wymagają doprecyzowania.

## Zmienne środowiskowe

Patrz [`.env.example`](.env.example) - w PoC wartości są wpisane wprost
w `docker-compose.yml`, plik `.env.example` dokumentuje dostępne opcje
(przydatne np. przy lokalnym uruchomieniu bez Dockera).