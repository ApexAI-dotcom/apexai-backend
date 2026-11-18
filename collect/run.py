"""
Lance la collecte et écrit les résultats en « zone d'attente » (fichiers JSON),
sans rien écrire en base. Un humain relit, puis une étape séparée (plus tard)
importera dans Supabase.

    python -m collect.run --out staging --sources ffsa_events,osm_circuits,circuits

Sortie :
  staging/<source>.json   les enregistrements normalisés
  staging/journal.jsonl   chaque requête (lu, cache, refus, robots…)
  staging/resume.json     combien par source, erreurs
Code de sortie 1 si une source attendue revient vide : la page a sans doute
changé de structure, il faut regarder avant d'importer quoi que ce soit.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from collect.polite import PoliteFetcher, Refused
from collect.sources import circuit_page, ffsa_events, osm_circuits

HERE = Path(__file__).parent


def _circuits(fetcher):
    seed = json.loads((HERE / "sources" / "circuits_seed.json").read_text()).get("circuits") or []
    return circuit_page.collect(fetcher, seed), bool(seed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="staging")
    ap.add_argument("--cache", default=".collect-cache")
    ap.add_argument("--sources", default="ffsa_events,osm_circuits,circuits")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fetcher = PoliteFetcher(cache_dir=Path(args.cache))
    summary, failed = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sources": {}}, False

    for name in [s.strip() for s in args.sources.split(",") if s.strip()]:
        expected = True
        try:
            if name == "ffsa_events":
                records = list(ffsa_events.collect(fetcher))
            elif name == "osm_circuits":
                records = list(osm_circuits.collect(fetcher))
            elif name == "circuits":
                gen, expected = _circuits(fetcher)
                records = list(gen)
            else:
                summary["sources"][name] = {"error": "source inconnue"}
                failed = True
                continue
            (out / f"{name}.json").write_text(json.dumps(records, ensure_ascii=False, indent=1))
            summary["sources"][name] = {"count": len(records)}
            if expected and not records:
                summary["sources"][name]["alerte"] = "0 résultat : structure de la source à vérifier"
                failed = True
        except Refused as e:
            summary["sources"][name] = {"refus": str(e)}
            failed = True
        except Exception as e:  # une source qui casse n'arrête pas les autres
            summary["sources"][name] = {"error": f"{type(e).__name__}: {e}"}
            failed = True

    with (out / "journal.jsonl").open("w") as f:
        for line in fetcher.log:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    summary["requests"] = sum(1 for l in fetcher.log if l["event"] == "lu")
    (out / "resume.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
