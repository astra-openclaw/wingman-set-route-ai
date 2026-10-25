import json
import os
import re
from difflib import SequenceMatcher
from typing import Optional, Dict, List
from services.file import get_custom_skills_dir

class DestinationPhoneticEngine:

    def __init__(self):
        # Carpeta /data dentro de la skill
        self.base_path = os.path.join(get_custom_skills_dir(), "set_route_ai", "data")#os.path.join(os.path.dirname(__file__), "data")

        self.destinations_file = os.path.join(self.base_path, "destinations.json")
        self.learning_file = os.path.join(self.base_path, "phonetic_learning.json")
        self.blacklist_file = os.path.join(self.base_path, "blacklist.json")

        self.destinations: Dict[str, Dict] = self._load_json(self.destinations_file)
        self.learning: Dict[str, str] = self._load_json(self.learning_file)
        self.blacklist: Dict[str, bool] = self._load_json(self.blacklist_file)

    # ------------------------------------------------------------
    #                       JSON HELPERS
    # ------------------------------------------------------------
    def _load_json(self, path: str) -> dict:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_json(self, path: str, data: dict):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------
    #                NORMALIZACIÓN FONÉTICA SIMPLE
    # ------------------------------------------------------------
    def normalize(self, text: str) -> str:
        text = text.lower()

        # eliminar acentos
        text = (
            text.replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
        )

        # eliminar caracteres no útiles
        text = re.sub(r"[^a-z0-9\s-]", "", text)

        # convertir múltiple espacio a uno
        text = re.sub(r"\s+", " ", text).strip()

        return text

    # ------------------------------------------------------------
    #                    DETECCIÓN DE RAÍZ COMÚN
    # ------------------------------------------------------------
    def share_root(self, a: str, b: str) -> bool:
        """Dos nombres son equivalentes si comparten la raíz principal."""

        na = self.normalize(a)
        nb = self.normalize(b)

        # tokens
        ta = na.split()
        tb = nb.split()

        # al menos una palabra en común → misma raíz
        return any(t in tb for t in ta)

    # ------------------------------------------------------------
    #                        SCORE FUZZY
    # ------------------------------------------------------------
    def fuzzy_score(self, a: str, b: str) -> float:
        """Similitud ajustada para ubicaciones SC."""
        na = self.normalize(a)
        nb = self.normalize(b)

        base = SequenceMatcher(None, na, nb).ratio()

        # bonificación por compartir tokens
        ta = set(na.split())
        tb = set(nb.split())
        if ta & tb:
            base += 0.15

        # penalización por diferencia enorme de longitud
        if abs(len(na) - len(nb)) > 10:
            base -= 0.10

        return max(0.0, min(1.0, base))

    # ------------------------------------------------------------
    #                        FASE 1: MATCH EXACTO
    # ------------------------------------------------------------
    def find_exact(self, phrase: str) -> Optional[str]:
        key = self.normalize(phrase)
        if key in self.destinations:
            return key

        # probar nombres sin normalizar (por si usuario guarda nombre con mayúsculas)
        for d in self.destinations:
            if key == self.normalize(d):
                return d

        return None

    # ------------------------------------------------------------
    #                        FASE 2: LEARNING
    # ------------------------------------------------------------
    def find_learning_alias(self, phrase: str) -> Optional[str]:
        key = self.normalize(phrase)
        return self.learning.get(key)

    # ------------------------------------------------------------
    #                        FASE 3: ALIASES DEL USUARIO
    # ------------------------------------------------------------
    def find_alias(self, phrase: str) -> Optional[str]:
        n = self.normalize(phrase)

        for dest, data in self.destinations.items():
            aliases = data.get("aliases", [])
            for a in aliases:
                # alias se guarda ya normalizado, pero normalizamos por seguridad
                if n == self.normalize(a):
                    return dest

        return None

    # ------------------------------------------------------------
    #                 FASE 4: PATRONES ESPECÍFICOS DE SC
    # ------------------------------------------------------------
    def detect_special_patterns(self, phrase: str) -> Optional[str]:
        n = self.normalize(phrase)

        # SPAL-X
        spal = re.search(r"spal\s*-?\s*(\d+)", n)
        if spal:
            num = spal.group(1)
            return f"spal {num}"

        # Lagrange nodes (CRU L1, ARC L2, MIC L5…)
        lagr = re.search(r"(cru|crew|mic|hur|arc)[ -]?l[ -]?(\d+)", n)
        if lagr:
            prefix = lagr.group(1)
            num = lagr.group(2)
            prefix = "cru" if prefix in ["cru", "crew"] else prefix  # crew→cru
            return f"{prefix} l{num}"

        # Astro 042
        astro = re.search(r"(astro|cryastro|crias|crias tro)[ -]?(\d+)", n)
        if astro:
            num = astro.group(2)
            return f"astro {num}"

        return None

    # ------------------------------------------------------------
    #                 FASE 5: FUZZY MATCHING
    # ------------------------------------------------------------
    def fuzzy_match(self, phrase: str) -> Optional[str]:
        scores = []
        for dest in self.destinations:
            score = self.fuzzy_score(phrase, dest)
            scores.append((score, dest))

        if not scores:
            return None

        best_score, best_dest = max(scores)

        # umbral flexible
        if best_score >= 0.60:
            return best_dest

        return None

    # ------------------------------------------------------------
    #                       FUNCIÓN PRINCIPAL
    # ------------------------------------------------------------
    def find_destination(self, phrase: str):
        """
        Devuelve:
           (destino_normalizado, alternativas[])
        Si destino es None y alternativas vacías → destino desconocido.
        """
        if not phrase:
            return None, []

        normalized_phrase = self.normalize(phrase)

        # 1. Coincidencia exacta (nombre definido por el usuario)
        exact = self.find_exact(normalized_phrase)
        if exact:
            return exact, []

        # 2. Alias aprendidos automáticos
        alias_learn = self.find_learning_alias(normalized_phrase)
        if alias_learn:
            return alias_learn, []

        # 3. Alias definidos por el usuario
        alias_user = self.find_alias(normalized_phrase)
        if alias_user:
            return alias_user, []

        # 4. Patrones especiales SC
        special = self.detect_special_patterns(normalized_phrase)
        if special:
            return special, []

        # 5. Fuzzy
        fuzzy = self.fuzzy_match(normalized_phrase)
        if fuzzy and self.share_root(fuzzy, phrase):
            return fuzzy, []

        # 6. No encuentras nada → destino desconocido
        return None, []

    # ------------------------------------------------------------
    #            APRENDIZAJE Y BLACKLIST (AJUSTADO)
    # ------------------------------------------------------------
    def learn(self, phrase: str, destination: str):
        """Añade alias aprendido inteligente."""
        key = self.normalize(phrase)
        dest = self.normalize(destination)

        # protección: si comparten raíz, vincular sin miedo
        if self.share_root(key, dest):
            self.learning[key] = dest
            self._save_json(self.learning_file, self.learning)
            return

        # si no comparten raíz, NO aprender
        return

    def add_to_blacklist(self, phrase: str):
        key = self.normalize(phrase)
        self.blacklist[key] = True
        self._save_json(self.blacklist_file, self.blacklist)

    # ------------------------------------------------------------
    #                  GESTIÓN MANUAL DE ALIASES
    # ------------------------------------------------------------
    def add_alias(self, destination: str, alias: str) -> str:
        """
        Añade un alias a un destino.
        Devuelve:
          - "destination_not_found"
          - "alias_exists"
          - "ok"
        """
        dest_key = self.normalize(destination)
        if dest_key not in self.destinations:
            return "destination_not_found"

        alias_key = self.normalize(alias)

        aliases: List[str] = self.destinations[dest_key].get("aliases", [])
        # evitar duplicados por normalización
        if any(self.normalize(a) == alias_key for a in aliases):
            return "alias_exists"

        aliases.append(alias_key)
        self.destinations[dest_key]["aliases"] = aliases
        self._save_json(self.destinations_file, self.destinations)
        return "ok"

    def remove_alias(self, destination: str, alias: str) -> str:
        """
        Elimina un alias de un destino.
        Devuelve:
          - "destination_not_found"
          - "alias_not_found"
          - "ok"
        """
        dest_key = self.normalize(destination)
        if dest_key not in self.destinations:
            return "destination_not_found"

        alias_key = self.normalize(alias)
        aliases: List[str] = self.destinations[dest_key].get("aliases", [])
        new_aliases = [a for a in aliases if self.normalize(a) != alias_key]

        if len(new_aliases) == len(aliases):
            return "alias_not_found"

        self.destinations[dest_key]["aliases"] = new_aliases
        self._save_json(self.destinations_file, self.destinations)
        return "ok"

    def get_aliases(self, destination: str) -> Optional[List[str]]:
        """
        Devuelve la lista de aliases de un destino,
        o None si el destino no existe.
        """
        dest_key = self.normalize(destination)
        if dest_key not in self.destinations:
            return None
        return self.destinations[dest_key].get("aliases", [])

    def get_all_aliases(self) -> Dict[str, List[str]]:
        """
        Devuelve un diccionario:
          { destino: [aliases...] } solo con los que tienen alias.
        """
        result: Dict[str, List[str]] = {}
        for dest, data in self.destinations.items():
            aliases = data.get("aliases", [])
            if aliases:
                result[dest] = aliases
        return result
