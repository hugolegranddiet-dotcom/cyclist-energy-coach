
# app_energy.py
from dataclasses import dataclass
from typing import List, Literal, Optional
from datetime import date

Sex = Literal["M", "F"]
BmrFormula = Literal["mifflin", "cunningham", "manual"]

def bmr_mifflin(sex: Sex, poids_kg: float, taille_cm: float, age: int) -> float:
    base = 10*poids_kg + 6.25*taille_cm - 5*age
    return round(base + (5 if sex == "M" else -161), 1)
def bmr_tenhaaf(sex: str, poids_kg: float, taille_m: float, age: int) -> float:
    """
    Ten Haaf RMR (kcal/j) :
    (11.936*poids_kg) + (587.728*taille_m) - (8.129*age) + (191.027*sex_M) + 29.279
    sex_M = 1 si homme, 0 si femme
    """
    sex_M = 1 if sex.upper() == "M" else 0
    rmr = (11.936 * float(poids_kg)) + (587.728 * float(taille_m)) - (8.129 * int(age)) + (191.027 * sex_M) + 29.279
    return round(rmr, 1)


def age_from_birthdate(birth: date) -> int:
    today = date.today()
    years = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        years -= 1
    return years

def kcal_from_power_with_eff(watts_avg: float, duree_sec: int, efficacite: float = 0.207) -> int:
    kJ = (watts_avg * duree_sec) / 1000.0
    kcal = kJ / (4.186 * max(efficacite, 1e-6))
    return int(round(kcal))

def training_kcal_from_zone_minutes(zones: list[dict], durations_min: dict, efficacite_default: float = 0.207) -> int:
    total = 0
    for z in zones:
        name = z.get("name")
        if not name: 
            continue
        mins = float(durations_min.get(name, 0) or 0)
        if mins <= 0:
            continue
        watts_mean = z.get("mean_w")
        if watts_mean is None:
            # compute from min/max if present
            lw, hw = z.get("min_w"), z.get("max_w")
            if lw is not None and hw is not None:
                watts_mean = (float(lw) + float(hw)) / 2.0
        if not watts_mean:
            continue
        eff = float(z.get("eff", efficacite_default) or efficacite_default)
        total += kcal_from_power_with_eff(float(watts_mean), int(mins*60), eff)
    return int(round(total))
