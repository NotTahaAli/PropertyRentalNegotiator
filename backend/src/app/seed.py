import sys

from . import crud
from .vertical import load_vertical

SAMPLE_SPEC_JSON = {
    "area_sqft": 800,
    "location": "Gulberg, Lahore",
    "floor": "ground",
    "business_type": "clothing boutique",
    "frontage_ft": 20,
    "lease_years": 3,
    "parking": True,
    "move_in": "2026-09-01",
    "current_rent": None,
    "budget_monthly_rent": 150000,
}


def seed(user_id: str) -> None:
    config = load_vertical()

    spec = crud.create_spec(
        {
            "vertical": config.vertical,
            "status": "confirmed",
            "spec_json": SAMPLE_SPEC_JSON,
            "confirmed": True,
            "user_id": user_id,
        }
    )
    print(f"seeded spec {spec['id']}")

    for persona in config.persona_prompts:
        dealer = crud.create_dealer(
            {
                "spec_id": spec["id"],
                "name": f"{persona.capitalize()} Dealer",
                "persona": persona,
                "phone_label": f"Dealer ({persona})",
                "source": "seed",
            }
        )
        print(f"seeded dealer {dealer['id']} ({persona})")


if __name__ == "__main__":
    seed(sys.argv[1])
