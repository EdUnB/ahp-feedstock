from pathlib import Path
import shutil,json,hashlib,runpy
root=Path(__file__).resolve().parents[1]
runpy.run_path(str(root/'scripts/check_integrity.py'),run_name='__main__')
out=root/'dist';out.mkdir(exist_ok=True)
# Explicit allowlist only. Never traverse manuscripts or private workspace folders.
for name in ['index.html','styles.css','app.js','sensitivity.js']:
 shutil.copy2(root/'app/static'/name,out/name)
html=(out/'index.html').read_text(encoding='utf-8').replace('<script src="app.js','<script src="browser-adapter.js" defer></script>\n  <script src="app.js')
html=html.replace('/* Interface apenas: nunca recalcula matrizes, pesos, classes ou CR no navegador. */','')
(out/'index.html').write_text(html,encoding='utf-8')
js=(out/'app.js').read_text(encoding='utf-8').replace('Motor local conectado','Motor Python no navegador').replace('Inicie o aplicativo pelo script INICIAR_WINDOWS.bat ou INICIAR_MAC_LINUX.sh. Esta interface não calcula AHP apenas abrindo o HTML.','Verifique a conexão para carregar o ambiente Python e recarregue a página.')
(out/'app.js').write_text(js,encoding='utf-8')
for name in ['logo-lea.png','logo-pcmec.png']:
 target=out/'assets/institutional'/name
 target.parent.mkdir(parents=True,exist_ok=True)
 shutil.copy2(root/'app/static/institutional'/name,target)
files=[]
for folder in ['engine/ahp_feedstock','app']:
 for p in sorted((root/folder).glob('*.py')):
  if folder=='app' and p.name not in ['__init__.py','sensitivity.py','stability.py']:continue
  rel=p.relative_to(root);target=out/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);files.append(rel.as_posix())
config='engine/config/m2_DEMO_SINTETICO.json';(out/config).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/config,out/config);files.append(config)
for name in ['browser-worker.mjs','browser-adapter.js','bridge.py']:shutil.copy2(root/'web'/name,out/name)
files.append('bridge.py');(out/'python-files.json').write_text(json.dumps(files,indent=2),encoding='utf-8');(out/'.nojekyll').write_text('')
print('Static browser prototype built at',out)
