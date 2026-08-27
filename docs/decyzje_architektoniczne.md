# Decyzje architektoniczne

Kluczowe decyzje podjęte przy budowie PoC
wraz z uzasadnieniem.

## Język i framework API: Python + FastAPI

FastAPI generuje dokumentację OpenAPI automatycznie z typów Pydantic, dzięki czemu Swagger jest dostępny pod dedykowaną ścieżką. 
Jest również natywnie asynchroniczny (`async def`), co jest istotne, ponieważ łańcuch przetwarzania (wywołanie LLM, wysyłka maila) jest operacją sieciową - synchroniczny framework blokowałby się na czas jej trwania.

## Biblioteka agenta: pydantic-ai

Lekka biblioteka natywnie oparta o Pydantic - modele danych używane do walidacji requestu/odpowiedzi API to te same, których używa agent AI do function calling. Ma wbudowane wsparcie dla lokalnej Ollamy (`pydantic_ai.models.ollama.OllamaModel` + `pydantic_ai.providers.ollama.OllamaProvider`).

## Model LLM: Ollama + qwen2.5:7b-instruct, lokalnie

Decyzja biznesowa: w zgłoszeniach mogą pojawiać się dane wrażliwe. Lokalny model w kontenerze daje gwarancję, że te dane nie opuszczają infrastruktury.

**Kompromis:** model 7B na samym CPU (bez GPU) jest powolny - pojedyncze zapytanie do agenta trwa od ok. 80 sekund do kilku minut, zależnie od złożoności promptu i liczby rund generowania (patrz sekcja o architekturze agenta niżej). To świadomie zaakceptowany koszt lokalnego, prywatnego przetwarzania w zamian za brak wycieku danych - w produkcie z wieloma równoległymi zgłoszeniami wymagałoby to architektury kolejkowej (Redis/RabbitMQ) zamiast synchronicznego request-response, żeby nie blokować klienta HTTP na czas inferencji.

## Wysyłka maila: aiosmtplib (asynchronicznie)

FastAPI obsługuje wiele requestów na jednym wątku przez jedną pętlę zdarzeń (event loop). Użycie standardowego, blokującego `smtplib` zamroziłoby całą pętlę na czas trwania połączenia SMTP - `aiosmtplib` oddaje kontrolę
event loopowi na czas oczekiwania na sieć, więc serwer pozostaje responsywny.

## Kontrakt danych: Pydantic + zamknięty Enum jako zabezpieczenie

`TargetDepartment` to `Enum` dziedziczący po `str`, zawierający dokładnie 5 dozwolonych adresów działów. Model odpowiedzi agenta(`RouteResult.target_email`) jest tego typu - jeśli model AI spróbuje
zwrócić adres spoza tej listy, Pydantic odrzuci taką
wartość przy walidacji.
## Architektura agenta: "jedyne źródło prawdy" zamiast podwójnej generacji

Pierwsza wersja implementacji ustawiała `output_type=RouteResult` na `Agent`, przez co model wykonywał dwie niezależne czynności: (1) wywoływał narzędzie `send_email_tool` i wysyłał maila, (2) osobno generował końcowy `RouteResult` jako odpowiedź zwracaną z API. Te dwie generacje nie były ze sobą w żaden sposób powiązane - w skrajnym przypadku agent mógł wysłać maila do jednego działu, a zwrócić w odpowiedzi HTTP inny adres.

Ostateczna implementacja eliminuje to ryzyko: narzędzie `send_email_tool` zapisuje własne argumenty (`target`, `category`, `reasoning`) jako wynik przekazywany dalej (przez `RunContext`/`deps` biblioteki pydantic-ai). Funkcja `route_message()` zwraca dokładnie to, co
trafiło do maila - nie osobną odpowiedź modelu. Dodatkowa korzyść: usunięcie drugiej rundy
generowania skróciło czas odpowiedzi agenta.

## Modularność: rozdzielenie API / agenta / narzędzia mailowego

Każda warstwa w osobnym pliku:
- `routers/v1.py` - HTTP: walidacja, wywołanie logiki, mapowanie błędów na kody statusu.
- `agent.py` - logika AI: prompt, narzędzie, decyzja.
- `mailer.py` - wysyłka e-mail przez SMTP
- `schemas.py` - kontrakt danych, używany przez wszystkie warstwy.

Zastosowany podział pozwala np. podmienić dostawcę LLM lub mechanizm wysyłki maila bez modyfikacji pozostałych warstw.

## Healthcheck Ollamy: aktywny polling zamiast `sleep`

Kontener `ollama` uruchamia `ollama serve` w tle, aktywnie odpytuje w pętli, czy serwer odpowiada i wtedy ściąga model. Docker Compose healthcheck sprawdza cyklicznie, czy model widnieje na liście pobranych (`ollama list`) - dopóki nie, kontener `api` nie startuje (`depends_on: condition: service_healthy`).

Pierwotny plan zakładał polling przez `curl`, ale obraz `ollama/ollama` nie ma zainstalowanego `curl` - wykryte i naprawione empirycznie podczas budowy. Polling przerobiony na `ollama list`.

## Logowanie: strukturalne JSON (loguru)

Logi w formacie JSON zamiast `print()`.
Logi z `uvicorn` są przechwytywane i ujednolicane do tego samego formatu. Structured logging to standard w mikroserwisach, ułatwiający analizę.
## Testy: integracyjne

Wszystkie testy (`test_mailer.py`, `test_agent.py`, `test_route.py`) wywołują usługi (Ollama, MailHog) zamiast mockować SMTP czy odpowiedzi LLM. 
Koszt: testy są wolniejsze (sekundy do minut zamiast milisekund) - akceptowalne przy tej skali projektu.