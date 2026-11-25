from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]
records=json.loads((root/'provenance/original_engine_sha256.json').read_text(encoding='utf-8'))
for name,expected in records.items():
 actual=hashlib.sha256((root/name).read_bytes()).hexdigest()
 if actual!=expected: raise SystemExit('Original source changed: '+name)
print('Original engine and reference configuration preserved:',len(records),'files')
