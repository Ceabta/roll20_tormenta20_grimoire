"""
generate_ameacas.py - Gerador do Bestiário de Ameaças de Arton
Usa PyMuPDF para extrair texto por página baseado no sumário do PDF.

Uso:
    python generate_ameacas.py <pdf_path> <output_json> [armas_json]
"""

import json
import os
import re
import sys

import fitz  # PyMuPDF

# ---------------------------------------------------------------------------
# Seções a ignorar completamente
# ---------------------------------------------------------------------------
IGNORE_SECTIONS = {
    'Fichas de Criaturas', 'Tipos de Criaturas', 'Habilidades Gerais',
    'Novos Perigos', 'Chefe Final', 'Criando um Chefe Final', 'Rei da Arena',
    'Arenas', 'Regras Avançadas de Ameaças', 'Regras Adicionais',
    'Manual de Criação de Ameaças', 'Como Modificar Criaturas',
    'Como Criar Bandos', 'Bazar Monstruoso', 'Armas', 'Armaduras e Escudos',
    'Itens Gerais', 'Itens Superiores', 'Novas Melhorias', 'Materiais Especiais',
    'Recursos Naturais', 'Tipos de Recursos', 'Novos Itens Mágicos',
    'Novos Artefatos', 'Novas Magias', 'Lista de Apoiadores',
    'Apêndice A: Raças e Parceiros', 'Apêndice B: Criaturas por Ordem Alfabética',
    'Apêndice C: Criaturas por ND', 'Apêndice D: Encontros Aleatórios',
    'O Que É uma "Ameaça"?', 'Construindo Desafios',
    'Modificando Dragões', 'Habilidades de Raça', 'Golens Despertos',
    'Armadilhas Kobolds', 'Ezzayn Especiais',
}

# Capítulos de nível 1 a ignorar
IGNORE_CHAPTERS = {
    'Capa', 'Créditos', 'Sumário',
    'Prefácio: Sonho Monstruoso', 'Introdução: Mundo Ameaçador',
    'Capítulo 2: Regras Avançadas de Ameaças',
    'Capítulo 3: Bazar Monstruoso',
    'Lista de Apoiadores', '4ª Capa',
}

# ---------------------------------------------------------------------------
# Mapeamento de alcance T20 → metros
# ---------------------------------------------------------------------------
RANGE_MAP = {
    'Curto': '9m', 'Médio': '18m', 'Longo': '36m', 'Personal': '1,5m',
}

# ---------------------------------------------------------------------------
# Carregar armas à distância
# ---------------------------------------------------------------------------
def load_ranged_weapons(armas_path):
    if not armas_path or not os.path.exists(armas_path):
        return {}
    with open(armas_path, encoding='utf-8') as f:
        data = json.load(f)
    armas = data['items'] if isinstance(data, dict) else data
    result = {}
    for arma in armas:
        if arma.get('purpose', '').lower() != 'ataque à distância':
            continue
        name = arma.get('name', '').lower().strip()
        range_m = RANGE_MAP.get(arma.get('range', ''), '')
        if name and range_m:
            result[name] = range_m
    return result

# ---------------------------------------------------------------------------
# Extração de texto do PDF por página
# ---------------------------------------------------------------------------
def extract_page_text(doc, page_num):
    """Extrai texto de uma página (1-indexed)."""
    try:
        page = doc[page_num - 1]
        return page.get_text()
    except Exception:
        return ''

def extract_pages_text(doc, first_page, last_page):
    """Extrai e concatena texto de um range de páginas."""
    parts = []
    for p in range(first_page, last_page + 1):
        parts.append(extract_page_text(doc, p))
    return '\n'.join(parts)

# ---------------------------------------------------------------------------
# Normalização de texto
# ---------------------------------------------------------------------------
def normalize_name(name):
    """Normaliza nome para comparação."""
    return re.sub(r'\s+', ' ', name.strip()).lower()

# ---------------------------------------------------------------------------
# Parser de monstro (reutiliza lógica do generate_bestiary.py adaptada)
# ---------------------------------------------------------------------------
SIZE_NAMES = ['Minúsculo', 'Pequeno', 'Médio', 'Grande', 'Enorme', 'Colossal']
TYPE_NAMES = ['Monstro', 'Humanoide', 'Morto-vivo', 'Construto', 'Animal', 'Espírito']

def parse_nd(text):
    # Captura apenas valores válidos: números, frações (1/2, 1/4), S, S+
    m = re.search(r'\bND\s+(S\+|S|\d+/\d+|\d+)', text)
    return m.group(1) if m else ''

def parse_type_size(text):
    """Extrai tipo e tamanho do bloco de texto."""
    for size in SIZE_NAMES:
        for tname in TYPE_NAMES:
            pattern = rf'{re.escape(tname)}\s*(?:\([^)]+\))?\s*{re.escape(size)}'
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                full = m.group(0)
                subtype_m = re.search(r'\(([^)]+)\)', full)
                subtype = subtype_m.group(1) if subtype_m else ''
                return tname, subtype, size
    return 'Monstro', '', 'Médio'

def parse_stat_line(text, key, pattern):
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else ''

def parse_attributes(text):
    attrs = {'str': None, 'dex': None, 'con': None, 'int': None, 'wis': None, 'cha': None}

    def val(s):
        s = s.strip()
        if s in ('—', '\u2014'):  # em dash = atributo ausente
            return None
        s = s.replace('\u2013', '-')  # en dash → sinal negativo
        s = s.lstrip('+')
        try:
            return int(s)
        except Exception:
            return None

    m = re.search(
        r'For\s+([—\u2014\u2013\-\d]+),\s*Des\s+([—\u2014\u2013\-\d]+),\s*Con\s+([—\u2014\u2013\-\d]+),\s*Int\s+([—\u2014\u2013\-\d]+),\s*Sab\s+([—\u2014\u2013\-\d]+),\s*Car\s+([—\u2014\u2013\-\d]+)',
        text, re.IGNORECASE
    )
    if m:
        attrs['str'] = val(m.group(1))
        attrs['dex'] = val(m.group(2))
        attrs['con'] = val(m.group(3))
        attrs['int'] = val(m.group(4))
        attrs['wis'] = val(m.group(5))
        attrs['cha'] = val(m.group(6))
    return attrs

def parse_attacks(text, ranged_weapons=None):
    attacks = []
    # Corpo a Corpo
    cc_m = re.search(r'Corpo a Corpo\s+(.+?)(?=\n[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇ]|\nÀ Distância|\nFor\s|\Z)', text, re.DOTALL | re.IGNORECASE)
    if cc_m:
        cc_text = cc_m.group(1).strip()
        # Múltiplos ataques separados por 'e' ou ','
        for atk in re.split(r'\se\s(?=[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇ])', cc_text):
            m = re.match(r'^(.+?)\s+(\+\d+)\s+\(([^)]+)\)', atk.strip())
            if m:
                raw_dmg = m.group(3)
                dmg_clean = re.sub(r'^(\d*d\d+(?:[+\-]\d+)?)\s+\w.*$', r'\1', raw_dmg)
                damage = dmg_clean if re.match(r'\d*d\d+', dmg_clean) else raw_dmg
                attacks.append({
                    'name': m.group(1).strip().title(),
                    'bonus': m.group(2),
                    'damage': damage,
                    'type': 'corpo a corpo',
                    'separator': '',
                })

    # À Distância
    dist_m = re.search(r'À Distância\s+(.+?)(?=\n[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇ]|\nFor\s|\Z)', text, re.DOTALL | re.IGNORECASE)
    if dist_m:
        dist_text = dist_m.group(1).strip()
        for atk in re.split(r'\se\s(?=[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇ])', dist_text):
            m = re.match(r'^(.+?)\s+(\+\d+)\s+\(([^)]+)\)', atk.strip())
            if m:
                atk_name = m.group(1).strip().title()
                raw_dmg = m.group(3)
                dmg_clean = re.sub(r'^(\d*d\d+(?:[+\-]\d+)?)\s+\w.*$', r'\1', raw_dmg)
                damage = dmg_clean if re.match(r'\d*d\d+', dmg_clean) else raw_dmg
                atk_obj = {
                    'name': atk_name,
                    'bonus': m.group(2),
                    'damage': damage,
                    'type': 'à distância',
                    'separator': '',
                }
                if ranged_weapons:
                    atk_obj['range'] = ranged_weapons.get(atk_name.lower(), '')
                attacks.append(atk_obj)

    return attacks

def parse_skills(text):
    """Retorna dict {nome: bônus} e dict {nome: contexto condicional}."""
    skills = {}
    skills_context = {}
    m = re.search(r'Perícias\s+(.+?)(?:\n|Equipamento|Tesouro)', text, re.IGNORECASE | re.DOTALL)
    if m:
        for sm in re.finditer(
            r'([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇ][a-záéíóúâêîôûãõàç]+(?:\s[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇ][a-záéíóúâêîôûãõàç]+)*)'
            r'\s+([+\-]\d+)'
            r'(\s+\([^)]+\))?',
            m.group(1)
        ):
            name = sm.group(1)
            bonus = sm.group(2)
            context = sm.group(3).strip() if sm.group(3) else ''
            skills[name] = bonus
            if context:
                skills_context[name] = f'{bonus} {context}'
    return skills, skills_context

def extract_abilities_block(text):
    """Extrai apenas o bloco de texto entre os ataques e os atributos."""
    # Fim do último ataque
    last_attack = None
    for m in re.finditer(r'(?:Corpo a Corpo|À Distância)\s+.+?\.', text, re.IGNORECASE):
        last_attack = m
    start = last_attack.end() if last_attack else 0

    # Início dos atributos
    attr_m = re.search(r'For\s+[—\u2014\u2013\-\d]', text[start:], re.IGNORECASE)
    end = start + attr_m.start() if attr_m else len(text)

    return text[start:end].strip()


ABILITY_SKIP_STARTS = {
    'Morto', 'Monstro', 'Humanoide', 'Construto', 'Animal', 'Espírito',
    'Corpo', 'Distância', 'Perícias', 'Equipamento', 'Tesouro', 'Magias',
    'Pontos', 'Deslocamento', 'Defesa', 'Iniciativa', 'Para', 'Uma',
    'Quando', 'No', 'O', 'A', 'Se', 'Contra', 'Em', 'Ele', 'Ela',
    'Cada', 'Todas', 'Todo', 'Este', 'Esta', 'Seu', 'Sua',
}


def parse_abilities(text):
    """Usa nomes de habilidades como delimitadores para capturar descrições completas."""
    abilities = []
    pattern = re.compile(
        r'([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇ][a-záéíóúâêîôûãõàç]+(?:\s+[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇ][a-záéíóúâêîôûãõàç\-]+)*)'
        r'(?:\s+\(([^)]+)\))?\s+'
        r'(?=[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇ])'
    )
    matches = list(pattern.finditer(text))
    valid = []
    for m in matches:
        name = m.group(1).strip()
        if name.split()[0] in ABILITY_SKIP_STARTS:
            continue
        if not (3 <= len(name) <= 60):
            continue
        valid.append((m.start(), m.end(), name, m.group(2) or ''))
    for i, (start, end, name, action) in enumerate(valid):
        next_start = valid[i + 1][0] if i + 1 < len(valid) else len(text)
        desc = re.sub(r'\s+', ' ', text[end:next_start]).strip()
        if len(desc) < 10:
            continue
        abilities.append({
            'name': name,
            'action': action,
            'is_magical': False,
            'description': desc,
        })
    return abilities

def parse_monster_text(name, text, ranged_weapons=None):
    """Parseia o texto bruto de um monstro."""
    nd = parse_nd(text)
    mtype, subtype, size = parse_type_size(text)

    initiative = parse_stat_line(text, 'initiative', r'Iniciativa\s+([+\-]\d+)')
    perception = parse_stat_line(text, 'perception', r'Percepção\s+([+\-]\d+)')
    defense = parse_stat_line(text, 'defense', r'Defesa\s+(\d+)')
    fort = parse_stat_line(text, 'fort', r'Fort\s+([+\-]\d+)')
    ref = parse_stat_line(text, 'ref', r'Ref\s+([+\-]\d+)')
    von = parse_stat_line(text, 'von', r'Von\s+([+\-]\d+)')
    hp_m = re.search(r'Pontos de Vida\s+(\d+)', text, re.IGNORECASE)
    hp = int(hp_m.group(1)) if hp_m else 0
    pm_m = re.search(r'Pontos de Mana\s+(\d+)', text, re.IGNORECASE)
    pm = int(pm_m.group(1)) if pm_m else 0
    movement_m = re.search(r'Deslocamento\s+(.+?)(?:\n|Corpo)', text, re.IGNORECASE)
    movement = movement_m.group(1).strip() if movement_m else ''
    treasure_m = re.search(r'Tesouro\s+(.+?)(?:\n|\Z)', text, re.IGNORECASE)
    treasure = treasure_m.group(1).strip() if treasure_m else ''
    equipment_m = re.search(r'Equipamento\s+(.+?)(?:\n|\Z)', text, re.IGNORECASE)
    equipment = [e.strip() for e in equipment_m.group(1).split(',')] if equipment_m else []

    # Percepções extras
    other_perception = []
    perc_line_m = re.search(r'Percepção\s+[+\-]\d+,?\s*(.+?)(?:\n|Defesa)', text, re.IGNORECASE)
    if perc_line_m:
        extras = perc_line_m.group(1).strip().rstrip(',')
        if extras:
            other_perception = [e.strip() for e in extras.split(',') if e.strip()]

    # Imunidades, RD, Vulnerabilidades, Resistências
    immunities = []
    damage_reduction = {}
    vulnerabilities = []
    resistances = []
    defesa_line_m = re.search(r'Defesa\s+\d+,\s*Fort.+?(?=Pontos de Vida|\n|$)', text, re.IGNORECASE)
    other_defenses = []
    if defesa_line_m:
        dl = defesa_line_m.group(0)
        imm_m = re.search(r'imunidade\s+a\s+([^,\n]+)', dl, re.IGNORECASE)
        if imm_m:
            immunities = [i.strip() for i in imm_m.group(1).split(' e ')]
        rd_m = re.search(r'redução de dano\s+(\d+)(?:/(\w+))?', dl, re.IGNORECASE)
        if rd_m:
            key = rd_m.group(2) if rd_m.group(2) else 'normal'
            damage_reduction[key] = int(rd_m.group(1))
        res_m = re.search(r'resistência\s+a\s+(\w+)\s+([+\-]?\d+)', dl, re.IGNORECASE)
        if res_m:
            resistances.append({'to': res_m.group(1), 'bonus': res_m.group(2)})
        # Propriedades especiais após Von (ex: incorpóreo, maior que a morte, cura acelerada)
        special_m = re.search(r'Von\s+[+\-]\d+,?\s*(.+)', dl, re.IGNORECASE)
        if special_m:
            special_str = special_m.group(1).strip().rstrip('.')
            # Filtrar o que já foi capturado
            special_str = re.sub(r'imunidade a [^,]+', '', special_str, flags=re.IGNORECASE)
            special_str = re.sub(r'redução de dano \d+(?:/\w+)?', '', special_str, flags=re.IGNORECASE)
            special_str = re.sub(r'resistência a \w+ [+\-]?\d+', '', special_str, flags=re.IGNORECASE)
            special_str = re.sub(r',\s*,', ',', special_str).strip().strip(',').strip()
            if special_str:
                other_defenses = [s.strip() for s in special_str.split(',') if s.strip()]

    attrs = parse_attributes(text)
    attacks = parse_attacks(text, ranged_weapons)
    skills, skills_context = parse_skills(text)
    abilities = parse_abilities(extract_abilities_block(text))

    return {
        'name': name,
        'nd': nd,
        'type': mtype,
        'subtype': subtype,
        'size': size,
        'role': '',
        'initiative': f'+{initiative}' if initiative and not initiative.startswith(('+', '-')) else initiative,
        'perception': f'+{perception}' if perception and not perception.startswith(('+', '-')) else perception,
        'other_perception': other_perception,
        'other_defenses': other_defenses,
        'defense': defense,
        'fort': fort,
        'ref': ref,
        'von': von,
        'immunities': immunities,
        'damage_reduction': damage_reduction,
        'resistances': resistances,
        'vulnerabilities': vulnerabilities,
        'hp': hp,
        'pm': pm,
        'movement': movement,
        'attacks': attacks,
        'spell_description': '',
        'spells': [],
        'abilities': abilities,
        'attributes': attrs,
        'skills': skills,
        'skills_context': skills_context,
        'equipment': equipment,
        'treasure': treasure,
        'description': '',
    }

# ---------------------------------------------------------------------------
# Construção da estrutura de pastas
# ---------------------------------------------------------------------------
def build_description(monster):
    """Gera o texto de descrição do monstro para o grimório."""
    parts = []
    subtype = f' ({monster["subtype"]})' if monster.get('subtype') else ''
    parts.append(f'{monster["type"]}{subtype} {monster["size"]}')
    parts.append(f'ND: {monster["nd"]}')
    if monster.get('initiative'):
        init_line = f'Iniciativa {monster["initiative"]}, Percepção {monster["perception"]}'
        if monster.get('other_perception'):
            init_line += ', ' + ', '.join(monster['other_perception'])
        parts.append(init_line)
    if monster.get('defense'):
        line = f'Defesa {monster["defense"]}'
        if monster.get('fort'): line += f', Fort {monster["fort"]}'
        if monster.get('ref'):  line += f', Ref {monster["ref"]}'
        if monster.get('von'):  line += f', Von {monster["von"]}'
        if monster.get('other_defenses'):
            line += ', ' + ', '.join(monster['other_defenses'])
        parts.append(line)
    if monster.get('immunities'):
        parts.append(f'Imunidades: {", ".join(monster["immunities"])}')
    if monster.get('damage_reduction'):
        rd = ', '.join(str(v) if k == 'normal' else f'{v} a {k}' for k, v in monster['damage_reduction'].items())
        parts.append(f'RD: {rd}')
    if monster.get('vulnerabilities'):
        parts.append(f'Vulnerabilidades: {", ".join(monster["vulnerabilities"])}')
    if monster.get('hp'):
        parts.append(f'Pontos de Vida {monster["hp"]}')
    if monster.get('movement'):
        parts.append(f'Deslocamento: {monster["movement"]}')
    if monster.get('pm'):
        parts.append(f'PM: {monster["pm"]}')
    if monster.get('attacks'):
        for atk in monster['attacks']:
            label = 'Corpo a Corpo' if atk['type'] == 'corpo a corpo' else 'À Distância'
            parts.append(f'{label}: {atk["name"]} {atk["bonus"]} ({atk["damage"]}).')
    if monster.get('abilities'):
        for ab in monster['abilities']:
            action_str = f' ({ab["action"]})' if ab.get('action') else ''
            parts.append(f'{ab["name"]}{action_str} {ab["description"]}')
    if monster.get('spell_description'):
        parts.append(f'Magia: {monster["spell_description"]}')
    if monster.get('spells'):
        for sp in monster['spells']:
            cost = f' ({sp["cost"]})' if sp.get('cost') else ''
            parts.append(f'• {sp["name"]}{cost}: {sp["description"]}')
    attrs = monster.get('attributes', {})
    attr_map = {'str': 'For', 'dex': 'Des', 'con': 'Con', 'int': 'Int', 'wis': 'Sab', 'cha': 'Car'}
    attr_parts = []
    for k, label in attr_map.items():
        v = attrs.get(k)
        attr_parts.append(f'{label} {v if v is not None else "—"}')
    parts.append(' | '.join(attr_parts))
    if monster.get('skills'):
        ctx = monster.get('skills_context', {})
        skills_str = ', '.join(
            ctx.get(k, f'{k} {v}') if k in ctx else f'{k} {v}'
            for k, v in monster['skills'].items()
        )
        parts.append(f'Perícias {skills_str}')
    if monster.get('equipment'):
        equip = [e['name'] if isinstance(e, dict) else e for e in monster['equipment']]
        parts.append(f'Equipamento: {", ".join(equip)}')
    if monster.get('treasure'):
        parts.append(f'Tesouro: {monster["treasure"]}')
    return '\n\n'.join(parts)


def build_item(name, text, ranged_weapons, importable=True):
    monster = parse_monster_text(name, text, ranged_weapons)
    description = build_description(monster)
    return {
        'type': 'item',
        'name': name,
        'description': description,
        'spellType': None,
        '_monster': monster if importable else None,
    }

def nd_sort_key(nd):
    nd = str(nd)
    if nd in ('S', 'S+'): return 999
    if '/' in nd:
        a, b = nd.split('/')
        return int(a) / int(b)
    try:
        return float(nd)
    except ValueError:
        return 998

def build_bestiary(doc, toc, ranged_weapons):
    """Constrói a estrutura de pastas do bestiário."""
    total_pages = doc.page_count

    # Filtrar apenas Capítulo 1
    cap1_start = None
    cap1_end = None
    for i, (level, title, page) in enumerate(toc):
        if level == 1 and 'Capítulo 1' in title:
            cap1_start = i
        elif level == 1 and cap1_start is not None:
            cap1_end = i
            break

    if cap1_start is None:
        print('ERRO: Capítulo 1 não encontrado no sumário')
        return []

    relevant_toc = toc[cap1_start + 1: cap1_end] if cap1_end else toc[cap1_start + 1:]

    # Calcular página final de cada item
    items_with_end = []
    for i, (level, title, page) in enumerate(relevant_toc):
        # Próxima página é o início do próximo item do mesmo nível ou superior
        next_page = total_pages
        for j in range(i + 1, len(relevant_toc)):
            nl, nt, np = relevant_toc[j]
            if nl <= level:
                next_page = np
                break
        items_with_end.append((level, title, page, next_page))

    # Montar estrutura hierárquica
    result_folders = []  # pastas de nível 2 (seções)
    current_section = None  # pasta nível 2
    current_subsection = None  # pasta nível 3 (ex: Lefeu)

    for level, title, page, next_page in items_with_end:
        # Limpar título
        clean_title = re.sub(r'\s+', ' ', title).strip()

        if level == 2:
            # Nova seção principal
            if clean_title in IGNORE_SECTIONS:
                current_section = None
                current_subsection = None
                continue
            current_section = {'type': 'folder', 'name': clean_title, 'items': []}
            current_subsection = None
            result_folders.append(current_section)

        elif level == 3:
            if current_section is None:
                continue
            if clean_title in IGNORE_SECTIONS:
                continue

            # Extrair texto das páginas
            end_p = min(next_page, total_pages)
            text = extract_pages_text(doc, page, end_p)

            # É uma subseção (tem filhos de nível 4)?
            has_children = any(
                l == 4 and p >= page and p < next_page
                for l, t, p, ep in items_with_end
            )

            if has_children:
                # Criar subpasta
                current_subsection = {'type': 'folder', 'name': clean_title, 'items': []}
                current_section['items'].append(current_subsection)
            else:
                current_subsection = None
                # Criar item de monstro
                item = build_item(clean_title, text, ranged_weapons)
                current_section['items'].append(item)

        elif level == 4:
            if current_section is None:
                continue
            if clean_title in IGNORE_SECTIONS:
                continue

            end_p = min(next_page, total_pages)
            text = extract_pages_text(doc, page, end_p)

            item = build_item(clean_title, text, ranged_weapons)
            target = current_subsection if current_subsection else current_section
            target['items'].append(item)

    return result_folders

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if len(sys.argv) < 3:
        print('Uso: python generate_ameacas.py <pdf_path> <output_json> [armas_json]')
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_path = sys.argv[2]
    armas_path = sys.argv[3] if len(sys.argv) > 3 else None

    print(f'Abrindo PDF: {pdf_path}')
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    print(f'Sumário: {len(toc)} entradas')

    ranged_weapons = load_ranged_weapons(armas_path)
    if ranged_weapons:
        print(f'{len(ranged_weapons)} armas à distância carregadas')

    folders = build_bestiary(doc, toc, ranged_weapons)

    result = {
        'type': 'folder',
        'name': 'Ameaças de Arton',
        'items': folders,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f'\nJSON salvo em: {output_path}')
    total = sum(
        len(folder.get('items', [])) for folder in folders
    )
    for folder in folders:
        n = len(folder.get('items', []))
        print(f'  {folder["name"]}: {n} item(s)')

if __name__ == '__main__':
    main()