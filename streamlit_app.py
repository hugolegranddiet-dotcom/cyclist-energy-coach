# streamlit_app.py
import json
import copy
from pathlib import Path
from datetime import date
import pandas as pd
import streamlit as st

from app_energy import (
    bmr_tenhaaf, age_from_birthdate, training_kcal_from_zone_minutes
)

st.set_page_config(page_title="Cyclist Energy Coach", layout="wide")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
PROFILES_PATH = DATA_DIR / "profiles.json"
DIARY_PATH   = DATA_DIR / "diary.json"

# ---------------- Helpers d'images (logos) ----------------
def show_image_if_exists(path_candidates, place="main", width=None):
    """
    Affiche la première image existante parmi path_candidates.
    Anti-crash :
      - Force width >= 1
      - Pas de use_column_width / use_container_width
      - Try/except pour éviter l'erreur 'Invalid image width: 0'
    """
    safe_width = 160
    if isinstance(width, (int, float)) and width and width > 0:
        safe_width = int(width)
    safe_width = max(1, safe_width)

    for p in path_candidates:
        pth = Path(p)
        if pth.exists() and pth.is_file():
            try:
                if place == "sidebar":
                    st.sidebar.image(str(pth), width=safe_width)
                else:
                    st.image(str(pth), width=safe_width)
            except Exception as e:
                where = "sidebar" if place == "sidebar" else "page"
                st.warning(f"Logo désactivé ({where}) : {pth.name} – {e}")
                return False
            return True
    return False

# ---------------- Helpers JSON ----------------
def load_json(path, default):
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

# ---------------- Full recovery helpers ----------------
def ensure_full_recovery_zone(profile: dict):
    """
    Crée/maintient une zone 'Full recovery' (0 -> min Active recovery)
    et la positionne juste avant 'Active recovery'.
    """
    if not profile:
        return
    zones = profile.get("zones", [])
    act_idx = None
    for i, z in enumerate(zones):
        name = (z.get("name") or "").lower()
        if "active" in name and "recovery" in name:
            act_idx = i
            break
    if act_idx is None:
        profile["zones"] = zones
        return

    try:
        active_min = float(zones[act_idx].get("min_w") or 0.0)
    except Exception:
        active_min = 0.0

    full_idx = None
    for i, z in enumerate(zones):
        nm = (z.get("name") or "").lower()
        if nm.startswith("full") and "recovery" in nm:
            full_idx = i
            break

    if full_idx is None:
        full_zone = {
            "name": "Full recovery",
            "min_w": 0,
            "max_w": active_min,
            "mean_w": 60.0,
            "eff": 0.207,
        }
        zones.insert(act_idx, full_zone)
    else:
        zones[full_idx]["min_w"] = 0
        zones[full_idx]["max_w"] = active_min
        if full_idx > act_idx:
            z = zones.pop(full_idx)
            zones.insert(act_idx, z)

    profile["zones"] = zones

# ---------------- Données ----------------
profiles = load_json(PROFILES_PATH, {})
diary    = load_json(DIARY_PATH, {})

# ---------------- Barre latérale (toggle logos) ----------------
authenticated = True
with st.sidebar:
    st.header("Profil")
    disable_logos = st.checkbox("Désactiver les logos (debug)", value=False)

# ---------------- Haut de page principal (logo ColorCode) ----------------
if not disable_logos:
    _ = show_image_if_exists(
        ["assets/colorcode.png", "colorcode.png", "image.png"],
        place="main", width=160
    )

st.title("Cyclist Energy Coach — Profil, Zones & Journal")

# ---------------- Sidebar suite ----------------
with st.sidebar:
    if not disable_logos:
        show_image_if_exists(
            ["assets/HLD-LG3.png", "assets/hl.png", "HLD-LG3.png", "hl.png"],
            place="sidebar", width=140
        )

    profile_names = sorted(profiles.keys())
    mode = st.radio("Mode", ["Sélectionner un profil", "Créer / Modifier un profil"], horizontal=False)

    if mode == "Sélectionner un profil" and profile_names:
        selected = st.selectbox("Choisir", profile_names)
    else:
        selected = st.text_input("Nom du profil (ex: Test 1)", value="")

    st.divider()
    st.caption("Crée/enregistre un profil puis utilise le Journal pour saisir les durées par zone.")

    # Vérification du PIN
    if mode == "Sélectionner un profil" and selected and selected in profiles:
        pin_saved = str(profiles[selected].get("pin", "") or "")
        if pin_saved:
            pin_input = st.text_input("Entrer PIN (4 chiffres)", type="password", max_chars=4, key="pin_enter")
            if pin_input != pin_saved:
                authenticated = False
                st.warning("PIN incorrect")

    # Suppression profil
    if mode == "Sélectionner un profil" and selected:
        st.markdown("### Supprimer ce profil")
        st.caption("Cette action supprime aussi l'historique (journal) associé.")
        confirm = st.text_input("Confirmer en tapant : SUPPRIMER", key="confirm_del")

        if st.button("Supprimer définitivement"):
            if confirm.strip().upper() == "SUPPRIMER":
                profiles.pop(selected, None)
                diary.pop(selected, None)
                save_json(PROFILES_PATH, profiles)
                save_json(DIARY_PATH, diary)
                st.success(f"Profil '{selected}' supprimé.")
                st.rerun()
            else:
                st.error("Saisie invalide. Tape exactement : SUPPRIMER")

# ---------------- Defaults profil ----------------
def init_profile_dict():
    return {
        "name": "",
        "sex": "M",
        "birth": None,
        "height_cm": 170,
        "weight_kg": 60.0,
        "bmr_manual": None,
        "pal": 1.4,
        "pin": "",
        "zones": [
            {"name": "Full recovery",       "min_w": 0,   "max_w": 120,  "mean_w": 60.0,  "eff": 0.207},
            {"name": "Active recovery",     "min_w": 120, "max_w": 180,  "mean_w": 100,   "eff": 0.207},
            {"name": "RE Génération",       "min_w": 180, "max_w": 220,  "mean_w": 200,   "eff": 0.207},
            {"name": "FAT MAX",             "min_w": 250, "max_w": 285,  "mean_w": 267.5, "eff": 0.207},
            {"name": "Aerobic capacity",    "min_w": 285, "max_w": 310,  "mean_w": 297.5, "eff": 0.207},
            {"name": "Threshold zone",      "min_w": 310, "max_w": 350,  "mean_w": 330,   "eff": 0.207},
            {"name": "VO2 Max zone",        "min_w": 350, "max_w": 440,  "mean_w": 395,   "eff": 0.207},
            {"name": "Anaerobic capacity",  "min_w": 440, "max_w": 550,  "mean_w": 495,   "eff": 0.207},
            {"name": "CP/NP Neuromuscular", "min_w": 550, "max_w": 1400, "mean_w": 975,   "eff": 0.207},
        ]
    }

# Sélection du profil courant
if 'selected' in locals() and selected and selected in profiles:
    profile = profiles[selected]
elif 'selected' in locals() and selected:
    profile = init_profile_dict()
    profile["name"] = selected
else:
    profile = None

# Toujours garder Full = 0 -> min(Active)
if profile:
    ensure_full_recovery_zone(profile)

# ---------------- Onglets ----------------
tabs = st.tabs(["🧾 Profil & Zones", "📅 Journal (durées par zone)", "📈 Historique"])

# ---------- Onglet 1 : Profil & Zones ----------
with tabs[0]:
    st.subheader("Mes infos")
    if not profile or ('selected' in locals() and selected in profiles and not authenticated):
        st.info("Choisis un profil existant (et entre le PIN s'il est défini) ou entre un nom dans la barre latérale pour créer un profil.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            profile["sex"] = st.selectbox("Sexe", ["M", "F"], index=0 if profile.get("sex", "M") == "M" else 1)
        with c2:
            birth = profile.get("birth")
            bval = pd.to_datetime(birth).date() if birth else date(2007, 10, 10)
            new_birth = st.date_input("Date de naissance", value=bval, format="DD/MM/YYYY")
            profile["birth"] = new_birth.isoformat()
        with c3:
            profile["height_cm"] = st.number_input("Taille (cm)", min_value=120, max_value=220, value=int(profile.get("height_cm", 170)))
        with c4:
            profile["weight_kg"] = st.number_input(
                "Poids (kg)", min_value=35.0, max_value=120.0,
                value=float(profile.get("weight_kg", 60.0)), step=0.1
            )

        c5, c6, c7 = st.columns(3)
        with c5:
            st.write("Âge")
            try:
                age = age_from_birthdate(pd.to_datetime(profile["birth"]).date())
            except Exception:
                age = 18
            st.metric(label="Âge (années)", value=age)
        with c6:
            profile["pal"] = st.selectbox("PAL (activité hors entraînement)", options=[1.3, 1.35, 1.4, 1.45, 1.5, 1.6, 1.7], index=2)
        with c7:
            profile["bmr_manual"] = st.number_input("RMR (kcal/j) manuel optionnel", min_value=0, value=int(profile.get("bmr_manual") or 0))

        profile["pin"] = st.text_input("PIN (4 chiffres)", value=str(profile.get("pin", "")), max_chars=4)

        if profile.get("bmr_manual"):
            bmr_val = float(profile["bmr_manual"])
            bmr_src = "RMR manuel"
        else:
            bmr_val = bmr_tenhaaf(profile["sex"], float(profile["weight_kg"]), float(profile["height_cm"]) / 100.0, age)
            bmr_src = "Ten Haaf"

        st.success(f"BMR ({bmr_src}) : {bmr_val:.0f} kcal/j  |  Base hors entraînement (PAL de profil) = {bmr_val*float(profile['pal']):.0f} kcal/j")

        st.divider()
        st.subheader("Mes Zones (W) — min / max / moyenne / efficacité")
        df = pd.DataFrame(profile["zones"])
        want_cols = ["name", "min_w", "max_w", "mean_w", "eff"]
        for col in want_cols:
            if col not in df.columns:
                df[col] = None
        edited = st.data_editor(
            df[want_cols], num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "name": st.column_config.TextColumn("Zone"),
                "min_w": st.column_config.NumberColumn("Min W"),
                "max_w": st.column_config.NumberColumn("Max W"),
                "mean_w": st.column_config.NumberColumn("Moy W"),
                "eff":  st.column_config.NumberColumn("Efficacité (0.183–0.226)", step=0.001),
            },
        )
        profile["zones"] = edited.fillna("").to_dict(orient="records")
        ensure_full_recovery_zone(profile)

        if st.button("Enregistrer le profil", type="primary"):
            profiles[profile["name"]] = profile
            save_json(PROFILES_PATH, profiles)
            st.success("Profil enregistré.")

# ---------- Onglet 2 : Journal ----------
with tabs[1]:
    st.subheader("Journal : Durée passée dans chaque zone")
    if not profile or ('selected' in locals() and selected in profiles and not authenticated):
        st.info("Crée/enregistre d'abord un profil (et entre le PIN s'il est défini) dans l'onglet 'Profil & Zones'.")
    else:
        day = st.date_input("Choisir la date", value=date.today(), format="DD/MM/YYYY")

        pal_options = [
            (1.3,  "1.3 — Repos (presque rien)"),
            (1.35, "1.35 — Très sédentaire"),
            (1.4,  "1.4 — Minimum actif (un peu de marche)"),
            (1.45, "1.45 — Calme + petites activités"),
            (1.5,  "1.5 — Actif léger"),
            (1.6,  "1.6 — Actif modéré"),
            (1.7,  "1.7 — Actif soutenu"),
        ]
        labels = [txt for _, txt in pal_options]
        default_pal = float(profile.get("pal", 1.4))
        try:
            default_index = [v for v, _ in pal_options].index(default_pal)
        except ValueError:
            default_index = 2
        pal_label  = st.selectbox("PAL du jour (activité hors entraînement)", labels, index=default_index)
        pal_du_jour = float(pal_options[labels.index(pal_label)][0])

        # Copie des zones du jour (pour overrides sans toucher au profil)
        zones_for_day = copy.deepcopy(profile["zones"])
        tmp_prof = {"zones": zones_for_day}
        ensure_full_recovery_zone(tmp_prof)
        zones_for_day = tmp_prof["zones"]

        # Saisie minutes + W moyen du jour (optionnel) pour chaque zone
        cols = st.columns(2)
        durations = {}
        zone_w_overrides = {}  # ne stocke que les overrides > 0

        for i, z in enumerate(zones_for_day):
            nm = z.get("name") or f"Zone {i+1}"
            with cols[i % 2]:
                minutes = st.number_input(f"{nm} — minutes", min_value=0, value=0, step=1, key=f"min_{i}")
                w_day   = st.number_input(f"{nm} — W moyen du jour (optionnel)", min_value=0, value=0, step=5, key=f"w_{i}")
            durations[nm] = int(minutes)
            if w_day and w_day > 0:
                zone_w_overrides[nm] = float(w_day)

        # Appliquer les overrides (sans modifier le profil)
        zones_for_calc = copy.deepcopy(zones_for_day)
        if zone_w_overrides:
            for z in zones_for_calc:
                nm = z.get("name")
                if nm in zone_w_overrides:
                    z["mean_w"] = zone_w_overrides[nm]

        # Calculs énergie
        if profile.get("bmr_manual"):
            bmr_val = float(profile["bmr_manual"])
        else:
            age = age_from_birthdate(pd.to_datetime(profile["birth"]).date())
            bmr_val = bmr_tenhaaf(
                profile["sex"],
                float(profile["weight_kg"]),
                float(profile["height_cm"]) / 100.0,
                age,
            )

        base       = int(round(bmr_val * pal_du_jour))
        train_kcal = training_kcal_from_zone_minutes(zones_for_calc, durations, 0.207)
        tdee       = base + train_kcal

        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("BMR (kcal/j)", f"{int(round(bmr_val))}")
        c2.metric("Base hors entraînement (BMR × PAL du jour)", f"{base}")
        c3.metric("Entraînement (kcal)", f"{train_kcal}")
        st.metric("TDEE (Total journée)", f"{tdee} kcal")

        if st.button("Enregistrer cette journée"):
            key = profile["name"]
            diary.setdefault(key, {})
            day_str = day.isoformat()
            diary[key][day_str] = {
                "durations_min": durations,
                "pal": pal_du_jour,
                "bmr": int(round(bmr_val)),
                "base": base,
                "training_kcal": train_kcal,
                "tdee": tdee,
                "zone_w_overrides": zone_w_overrides,  # <-- sauvegarde des W moyens saisis
            }
            save_json(DIARY_PATH, diary)
            st.success("Journée enregistrée.")

# ---------- Onglet 3 : Historique ----------
with tabs[2]:
    st.subheader("Historique")
    if not profile or ('selected' in locals() and selected in profiles and not authenticated):
        st.info("Aucune journée visible (profil non sélectionné ou PIN incorrect).")
    else:
        rows = []
        for d, entry in diary.get(profile["name"], {}).items():
            rows.append(
                {
                    "date": d,
                    "BMR": entry.get("bmr"),
                    "Base": entry.get("base"),
                    "Entrainement": entry.get("training_kcal"),
                    "TDEE": entry.get("tdee"),
                }
            )
        if rows:
            hist = pd.DataFrame(rows).sort_values("date")
            st.dataframe(hist, use_container_width=True)
            st.download_button(
                "Export CSV",
                data=hist.to_csv(index=False).encode("utf-8"),
                file_name="historique.csv",
                mime="text/csv",
            )
        else:
            st.info("Pas encore d'enregistrements pour ce profil.")
