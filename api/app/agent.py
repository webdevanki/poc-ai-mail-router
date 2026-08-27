from dataclasses import dataclass

from loguru import logger
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider

from app.config import settings
from app.mailer import send_email
from app.schemas import RouteResult, TargetDepartment

SYSTEM_PROMPT = """Jesteś inteligentnym routerem wiadomości firmowych. Twoim zadaniem jest
przeanalizować zgłoszenie pracownika/klienta i przekazać je do WŁAŚCIWEGO działu firmy,
wywołując narzędzie send_email_tool.

Dostępne działy (wybierz DOKŁADNIE JEDEN):
- kadry@example.com: sprawy kadrowo-płacowe pracowników - urlopy, wynagrodzenia,
  umowy o pracę, zwolnienia lekarskie, dokumenty pracownicze.
- human-resources@example.com: pozostałe sprawy HR - rekrutacja, rozwój pracowników,
  sprawy socjalne, ogólna administracja niezwiązana bezpośrednio z płacami/urlopami.
- help-desk@example.com: pytania proceduralne, prośby o reset hasła, pytania
  "jak coś zrobić w systemie", pierwszy kontakt gdy sprzęt DZIAŁA, ale użytkownik
  ma pytanie lub drobny problem z dostępem/procedurą.
- it@example.com: FIZYCZNA awaria sprzętu (np. "nie włącza się", "nie działa",
  "jest zepsuty"), awarie oprogramowania, sieci, poważne problemy techniczne.
- other@example.com: użyj WYŁĄCZNIE, gdy wiadomość nie pasuje jednoznacznie
  do żadnej z powyższych kategorii.

WAŻNA REGUŁA ROZSTRZYGAJĄCA #1: jeśli wiadomość opisuje fizyczną awarię sprzętu
(np. "nie włącza się", "nie działa", "jest zepsuty", "czarny ekran"), ZAWSZE
wybierz it@example.com - nawet jeśli wiadomość wspomina też o logowaniu lub
dostępie do systemu.

WAŻNA REGUŁA ROZSTRZYGAJĄCA #2: help-desk to PIERWSZA LINIA WSPARCIA - to tam
domyślnie trafiają zgłoszenia o dostępie/koncie/haśle (np. "nie mam dostępu do
maila", "nie moge sie zalogowac", "zapomnialem hasla"), NAWET jeśli nie jesteś
pewien czy sprawa jest prosta. Wybierz it@example.com TYLKO gdy zgłoszenie
jednoznacznie wskazuje na: fizyczną awarię sprzętu (patrz reguła #1), awarię
dotyczącą wielu użytkowników/całej infrastruktury, lub wyraźnie techniczny
problem (błąd systemu, konfiguracja, sieć) wykraczający poza prosty reset
dostępu. W razie wątpliwości między it a help-desk - wybierz help-desk.

Zawsze wywołaj send_email_tool dokładnie raz - to jedyny sposób na przekazanie
zgłoszenia dalej. Po wywołaniu narzędzia zakończ krótkim potwierdzeniem
(jedno zdanie), bez powtarzania treści zgłoszenia."""


@dataclass
class RoutingDeps:
    sender_email: str
    original_message: str
    captured_result: RouteResult | None = None


model = OllamaModel(
    settings.ollama_model,
    provider=OllamaProvider(base_url=f"{settings.ollama_host}/v1"),
)

routing_agent = Agent(
    model,
    deps_type=RoutingDeps,
    system_prompt=SYSTEM_PROMPT,
    model_settings={"temperature": 0.1},
)


@routing_agent.tool
async def send_email_tool(
    ctx: RunContext[RoutingDeps],
    target: TargetDepartment,
    category: str,
    reasoning: str,
) -> str:
    """Wysyła e-mail zgłoszenia do wybranego działu firmy, ustawiając Reply-To na oryginalnego nadawcę.

    Args:
        target: adres e-mail wybranego działu, dokładnie jeden z dozwolonej listy.
        category: KRÓTKA etykieta kategorii (jedno lub dwa słowa, np. "IT", "Kadry",
            "HR", "Helpdesk", "Inne") - nigdy pełny opis działu.
        reasoning: krótkie, 1-2 zdaniowe uzasadnienie wyboru działu.
    """

    if ctx.deps.captured_result is not None:
        logger.warning("Agent probowal wywolac send_email_tool ponownie - zignorowano.")
        return "Zgloszenie zostalo juz przekazane wczesniej - nie wysylaj ponownie."

    category = category.strip()
    reasoning = reasoning.strip()

    await send_email(
        to=target.value,
        reply_to=ctx.deps.sender_email,
        subject=f"[AI Router] {category}",
        body=(
            f"Nadawca: {ctx.deps.sender_email}\n"
            f"Kategoria: {category}\n"
            f"Uzasadnienie routingu: {reasoning}\n\n"
            f"Treść zgłoszenia:\n{ctx.deps.original_message}"
        ),
    )

    # Jedyne źródło prawdy dla route_message() - to co faktycznie trafiło do maila,
    # zamiast osobnej (potencjalnie niespójnej) odpowiedzi generowanej przez model.
    ctx.deps.captured_result = RouteResult(target_email=target, category=category, reasoning=reasoning)

    return f"Wyslano do {target.value}"


async def route_message(sender_email: str, message: str) -> RouteResult:
    deps = RoutingDeps(sender_email=sender_email, original_message=message)
    await routing_agent.run(message, deps=deps)

    if deps.captured_result is None:
        raise RuntimeError("Agent nie wywołał send_email_tool - brak wyniku routingu.")

    return deps.captured_result
