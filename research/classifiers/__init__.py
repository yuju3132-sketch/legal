import json
import re
from research.paths import ROOT

def classify(text):
    matches = []
    for topic in json.loads((ROOT / 'config/taxonomy.json').read_text(encoding='utf-8')):
        count = 0
        for keyword in topic['keywords']:
            pattern = r'(?<!\w)' + re.escape(keyword) + r'(?!\w)' if keyword.isascii() else re.escape(keyword)
            count += bool(re.search(pattern, text, re.I))
        if count:
            matches.append((count, topic['name']))
    return [name for _,name in sorted(matches,key=lambda x:-x[0])] or ['Unclassified']
