"""
update_bestiary.py - Atualiza o bestiário completo e rebuilda a extensão.

Uso:
    python update_bestiary.py <pdf_ameacas>

Exemplo:
    python update_bestiary.py "D:\\Livros\\T20 - Ameacas de Arton.pdf"
"""

import json
import subprocess
import sys
import os


def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_env()

PDF_AMEACAS = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('PDF_AMEACAS')
ARMAS_JSON = 'data/equipments/Armas.json'
BESTIARY_RAW = 'data/generator/bestiary_raw.txt'
BESTIARY_JSON = 'data/generator/bestiary.json'
AMEACAS_JSON = 'data/generator/ameacas.json'
DB_JSON = 'static/db.json'


def run(cmd, desc):
    print(f'\n>>> {desc}')
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f'ERRO ao executar: {cmd}')
        sys.exit(result.returncode)


def step_generate_jda():
    run(
        f'python data/generator/generate_bestiary.py {BESTIARY_RAW} {BESTIARY_JSON} {ARMAS_JSON}',
        'Gerando bestiary.json (Tormenta JdA)...'
    )


def step_generate_ameacas():
    if not PDF_AMEACAS:
        print('\n>>> [AVISO] PDF do Ameaças de Arton não informado — pulando geração do ameacas.json')
        return
    if not os.path.exists(PDF_AMEACAS):
        print(f'\n>>> [AVISO] PDF não encontrado: {PDF_AMEACAS} — pulando')
        return
    run(
        f'python data/generator/generate_ameacas.py "{PDF_AMEACAS}" {AMEACAS_JSON} {ARMAS_JSON}',
        'Gerando ameacas.json (Ameaças de Arton)...'
    )


def step_merge():
    print('\n>>> Mesclando bestiary.json + ameacas.json...')
    with open(BESTIARY_JSON, 'r', encoding='utf-8') as f:
        bestiary = json.load(f)

    if os.path.exists(AMEACAS_JSON):
        with open(AMEACAS_JSON, 'r', encoding='utf-8') as f:
            ameacas = json.load(f)
        bestiary['items'] = [
            item for item in bestiary['items']
            if item.get('name') not in ('Ameaças de Arton', 'Ameacas de Arton')
        ]
        bestiary['items'].append(ameacas)

    with open(BESTIARY_JSON, 'w', encoding='utf-8') as f:
        json.dump(bestiary, f, ensure_ascii=False, indent=2)

    for item in bestiary['items']:
        print(f'  {item["name"]}: {len(item.get("items", []))} item(s)')


def step_update_db():
    print('\n>>> Atualizando db.json...')
    with open(DB_JSON, 'r', encoding='utf-8') as f:
        db = json.load(f)
    with open(BESTIARY_JSON, 'r', encoding='utf-8') as f:
        bestiary = json.load(f)

    before = len(db['book'])
    db['book'] = [
        item for item in db['book']
        if isinstance(item, dict) and item.get('name') not in ('Bestiário', 'Bestiario', 'Bestiary')
    ]
    db['book'].append(bestiary)

    with open(DB_JSON, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f'  Removidos {before - len(db["book"]) + 1} item(s) antigos')
    print(f'  Total: {len(db["book"])} itens no db.json')


def step_build():
    run('npm run build:dev', 'Buildando extensão (Chrome)...')


if __name__ == '__main__':
    step_generate_jda()
    step_generate_ameacas()
    step_merge()
    step_update_db()
    step_build()
    print('\n✓ Atualização concluída!')