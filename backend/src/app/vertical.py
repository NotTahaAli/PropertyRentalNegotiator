import datetime
import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, create_model

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "vertical.json"

_TYPE_MAP = {
    "number": float,
    "string": str,
    "bool": bool,
    "date": datetime.date,
}


class SpecField(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    required: bool = True
    values: Optional[list[str]] = None
    prompt: Optional[str] = None


class RedFlag(BaseModel):
    model_config = ConfigDict(extra="allow")

    rule: str
    action: str
    threshold: Optional[float] = None


class BenchmarkFallback(BaseModel):
    model_config = ConfigDict(extra="allow")

    per_sqft_low: float
    per_sqft_high: float


class VerticalConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    vertical: str
    currency: str
    spec_schema: dict[str, SpecField]
    fee_taxonomy: list[str]
    benchmark_query: str
    dealer_search_query: str
    benchmark_fallback: BenchmarkFallback
    red_flags: list[RedFlag]
    negotiation_levers: list[str]
    disclosure_policy: str
    estimator_prompt: str
    negotiator_prompt: str
    persona_prompts: dict[str, str]
    first_messages: dict[str, str]
    fee_hints: dict[str, str]


def load_vertical(path: Path = DEFAULT_CONFIG_PATH) -> VerticalConfig:
    data = json.loads(Path(path).read_text())
    return VerticalConfig.model_validate(data)


def build_spec_model(config: VerticalConfig) -> type[BaseModel]:
    fields = {}
    for name, field in config.spec_schema.items():
        if field.type == "enum":
            if not field.values:
                raise ValueError(f"spec_schema field '{name}' is type 'enum' but has no values list")
            py_type = Literal[tuple(field.values)]
        else:
            py_type = _TYPE_MAP[field.type]
        if not field.required:
            py_type = Optional[py_type]
        default = ... if field.required else None
        fields[name] = (py_type, default)

    return create_model(
        "Spec",
        __config__=ConfigDict(extra="allow"),
        **fields,
    )
