import json
import os

with open('data/generator/bestiary.json', 'r', encoding='utf-8') as f:
    bestiary = json.load(f)

with open('data/generator/ameacas.json', 'r', encoding='utf-8') as f:
    ameacas = json.load(f)

# Aplicar overrides manuais se existirem
manual_path = 'data/generator/ameacas_manual.json'
if os.path.exists(manual_path):
    with open(manual_path, 'r', encoding='utf-8') as f:
        manual = json.load(f)

    overrides = {o['name']: o for o in manual.get('overrides', [])}

    def apply_overrides(items):
        for item in items:
            if item.get('type') == 'folder':
                apply_overrides(item.get('items', []))
            elif item.get('type') == 'item':
                name = item.get('name', '')
                if name in overrides:
                    override = overrides[name]
                    if 'description' in override:
                        item['description'] = override['description']
                    if '_monster' in override:
                        item['_monster'] = override['_monster']
                    print(f'  Override aplicado: {name}')

    apply_overrides(ameacas.get('items', []))

# Substituir a pasta 'Ameaças de Arton' pelo JSON atualizado
bestiary['items'] = [
    item for item in bestiary['items']
    if item.get('name') not in ('Ameaças de Arton', 'Ameacas de Arton')
]
bestiary['items'].append(ameacas)

with open('data/generator/bestiary.json', 'w', encoding='utf-8') as f:
    json.dump(bestiary, f, ensure_ascii=False, indent=2)

print('bestiary.json atualizado!')
for item in bestiary['items']:
    print(f'  {item["name"]}: {len(item.get("items", []))} item(s)')