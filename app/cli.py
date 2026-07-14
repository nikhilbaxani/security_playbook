"""CLI del generador de playbooks.

Uso:
    python -m app.cli --incident ransomware --context "servidor on-prem, sin backups"
    python -m app.cli            # modo interactivo
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from generation.generate_playbook import INCIDENT_TYPES, generate_playbook, save_playbook
from providers import PROVIDERS, ProviderError, get_provider


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="playbook-generator",
        description="Genera playbooks de respuesta a incidentes (NIST SP 800-61) con un LLM.",
    )
    parser.add_argument("-i", "--incident", help="Tipo de incidente (ej. ransomware, ddos)")
    parser.add_argument("-c", "--context", help="Contexto de la organización (opcional)")
    parser.add_argument(
        "-p",
        "--provider",
        choices=sorted(PROVIDERS),
        help="Proveedor de LLM (por defecto: LLM_PROVIDER del .env, o gemini)",
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Solo imprime el playbook, no lo guarda en output/"
    )
    parser.add_argument(
        "--rag",
        action="store_true",
        help="Recupera referencias reales (RE&CT, NIST 800-53/800-61) del índice vectorial "
        "y obliga al LLM a citarlas (requiere haber ejecutado: python -m retrieval.ingest)",
    )
    return parser.parse_args()


def ask_interactive() -> tuple[str, str]:
    print("Tipos de incidente sugeridos (puedes escribir otro):")
    for n, name in enumerate(INCIDENT_TYPES, start=1):
        print(f"  {n}. {name}")
    raw = input("\nTipo de incidente (número o texto): ").strip()
    if raw.isdigit() and 1 <= int(raw) <= len(INCIDENT_TYPES):
        incident = INCIDENT_TYPES[int(raw) - 1]
    else:
        incident = raw
    if not incident:
        print("Se necesita un tipo de incidente.", file=sys.stderr)
        sys.exit(1)
    print(
        "\nContexto (opcional pero recomendado): tamaño de la org, on-prem/cloud,"
        "\nestado de backups, qué se sabe del incidente..."
    )
    context = input("Contexto: ").strip()
    return incident, context


def main() -> None:
    load_dotenv()
    args = parse_args()

    incident = args.incident
    context = args.context or ""
    if not incident:
        incident, context = ask_interactive()

    try:
        provider = get_provider(args.provider)
        mode = " + RAG" if args.rag else ""
        print(
            f"\nGenerando playbook para '{incident}' con {type(provider).__name__}{mode}...\n",
            file=sys.stderr,
        )
        playbook = generate_playbook(incident, context, provider=provider, use_rag=args.rag)
    except ProviderError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        from retrieval.search import RetrievalError

        if isinstance(exc, RetrievalError):
            print(f"Error de RAG: {exc}", file=sys.stderr)
            sys.exit(1)
        raise

    print(playbook)

    if not args.no_save:
        path = save_playbook(playbook, incident)
        print(f"\nPlaybook guardado en: {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
