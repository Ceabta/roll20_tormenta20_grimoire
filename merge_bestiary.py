import json

with open('data/generator/bestiary.json', 'r', encoding='utf-8') as f:
    bestiary = json.load(f)

with open('data/generator/ameacas.json', 'r', encoding='utf-8') as f:
    ameacas = json.load(f)

# Substituir a pasta 'Ameaças de Arton' vazia pelo JSON completo
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