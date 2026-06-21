import yaml

with open(r'D:\noveos\novel-os\book.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

print('Keys in book.yaml:', list(data.keys())[:10])
if 'chapters' in data:
    print(f'Chapters type: {type(data["chapters"])}')
    if isinstance(data['chapters'], dict):
        print(f'Chapters count: {len(data["chapters"])}')
    elif isinstance(data['chapters'], list):
        print(f'Chapters count: {len(data["chapters"])}')
        for i, ch in enumerate(data['chapters'][:5]):
            print(f'  {i}: {ch}')
else:
    print('No "chapters" key found')
    
# Check other possible keys
for key in data.keys():
    val = data[key]
    if isinstance(val, (list, dict)):
        print(f'{key}: {type(val).__name__} with {len(val)} items')
    else:
        print(f'{key}: {type(val).__name__} = {str(val)[:50]}')
