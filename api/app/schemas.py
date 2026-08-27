from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TargetDepartment(str, Enum):
    """Zamknięta lista adresów docelowych - agent może wybrać wyłącznie jeden z nich."""

    HUMAN_RESOURCES = "human-resources@example.com"
    HELP_DESK = "help-desk@example.com"
    IT = "it@example.com"
    KADRY = "kadry@example.com"
    OTHER = "other@example.com"


class RequestIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    message: str = Field(min_length=1)


class RouteResult(BaseModel):
    target_email: TargetDepartment
    category: str = Field(description="Krótka etykieta kategorii, np. 'IT', 'Kadry' (nie pełny opis działu).")
    reasoning: str = Field(description="Krótkie (1-2 zdania) uzasadnienie wyboru działu.")
