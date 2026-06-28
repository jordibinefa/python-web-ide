#!/usr/bin/env python3
"""
Descarrega un paquet de Pyodide (i les seves dependències transitives)
al directori vendor/pyodide/0.28.3/, verificant el hash SHA-256.

Ús:
    python3 vendor-package.py numpy
    python3 vendor-package.py pandas
    python3 vendor-package.py matplotlib
"""

import sys
import json
import hashlib
import urllib.request
from pathlib import Path

VENDOR_DIR = Path(__file__).parent / 'vendor' / 'pyodide' / '0.28.3'
LOCK_FILE  = VENDOR_DIR / 'pyodide-lock.json'
CDN_BASE   = 'https://cdn.jsdelivr.net/pyodide/v0.28.3/full/'


def carrega_lock():
    with open(LOCK_FILE) as f:
        return json.load(f)['packages']


def dependències_transitives(nom, paquets, visitats=None):
    """Retorna el conjunt de noms de tots els paquets necessaris (incloent-hi nom)."""
    if visitats is None:
        visitats = set()
    if nom in visitats:
        return visitats
    if nom not in paquets:
        print(f'  AVÍS: "{nom}" no és al pyodide-lock.json; potser fa part de la stdlib.')
        return visitats
    visitats.add(nom)
    for dep in paquets[nom].get('depends', []):
        dependències_transitives(dep, paquets, visitats)
    return visitats


def sha256_fitxer(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for bloc in iter(lambda: f.read(65536), b''):
            h.update(bloc)
    return h.hexdigest()


def descarrega_paquet(nom, paquets):
    """Descarrega el fitxer .whl si no existeix ja; verifica el hash."""
    info     = paquets[nom]
    fitxer   = info['file_name']
    sha_esp  = info['sha256']
    dest     = VENDOR_DIR / fitxer

    if dest.exists():
        sha_real = sha256_fitxer(dest)
        if sha_real == sha_esp:
            print(f'  ✓ {fitxer}  (ja existeix)')
            return True
        else:
            print(f'  ! {fitxer}  (hash incorrecte, es torna a descarregar)')
            dest.unlink()

    url = CDN_BASE + fitxer
    print(f'  ↓ {fitxer}  ({url})')
    try:
        urllib.request.urlretrieve(url, dest)
    except Exception as e:
        print(f'    ERROR en descarregar: {e}')
        return False

    sha_real = sha256_fitxer(dest)
    if sha_real != sha_esp:
        print(f'    ERROR: hash no coincideix!')
        print(f'           esperat:  {sha_esp}')
        print(f'           obtingut: {sha_real}')
        dest.unlink()
        return False

    print(f'    hash OK ({sha_real[:16]}…)')
    return True


def main():
    if len(sys.argv) < 2:
        print('Ús: python3 vendor-package.py <paquet> [<paquet2> ...]')
        sys.exit(1)

    paquets = carrega_lock()
    noms_sol = sys.argv[1:]

    # Valida que tots els noms demanats existeixin
    for nom in noms_sol:
        if nom not in paquets:
            print(f'Error: "{nom}" no s\'ha trobat a pyodide-lock.json.')
            print('Paquets disponibles (mostra):',
                  ', '.join(list(paquets.keys())[:10]), '…')
            sys.exit(1)

    # Calcula el conjunt complet de dependències
    tots = set()
    for nom in noms_sol:
        dependències_transitives(nom, paquets, tots)

    print(f'\nPaquets a vendoritzar ({len(tots)}):')
    for n in sorted(tots):
        print(f'  • {n}')
    print()

    # Descarrega en ordre (les dependències primer, per llegibilitat)
    errors = []
    for nom in sorted(tots):
        ok = descarrega_paquet(nom, paquets)
        if not ok:
            errors.append(nom)

    print()
    if errors:
        print(f'Acabat amb {len(errors)} error(s): {", ".join(errors)}')
        sys.exit(1)
    else:
        print(f'Tot correcte. {len(tots)} paquet(s) a vendor/pyodide/0.28.3/')


if __name__ == '__main__':
    main()
