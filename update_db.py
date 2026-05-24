import json

with open('static/db.json', 'r', encoding='utf-8') as f:
    db = json.load(f)

with open('data/generator/bestiary.json', 'r', encoding='utf-8') as f:
    bestiary = json.load(f)

# Remover qualquer versão anterior do Bestiário
before = len(db['book'])
db['book'] = [
    item for item in db['book']
    if isinstance(item, dict) and item.get('name') not in ('Bestiário', 'Bestiario', 'Bestiary')
]
print(f'Removidos {before - len(db["book"])} item(s) antigos')

db['book'].append(bestiary)

with open('static/db.json', 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print(f'db.json atualizado! Total: {len(db["book"])} itens')
for item in db['book']:
    if isinstance(item, dict):
        print(f'  {item.get("name")}')