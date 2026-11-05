import argparse, html, json, os, re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

parser=argparse.ArgumentParser(description="Regenera os painéis do perfil Arasaka.")
parser.add_argument('--snapshot', type=Path, help='Usa dados locais para conferir o render.')
options=parser.parse_args()
root=Path(__file__).resolve().parents[1]
username='pjz3650'
token=os.environ.get('GH_TOKEN')
def request(url, api=False):
 headers={'User-Agent':'arasaka-profile-readme'}
 if api:
  headers.update({'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
  if token:
   headers['Authorization']='Bearer '+token
 with urlopen(Request(url,headers=headers),timeout=25) as response:
  return response.read().decode(), response.headers.get('Link','')

if options.snapshot:
 user=json.loads((options.snapshot/'user.json').read_text())
 repos=json.loads((options.snapshot/'repos.json').read_text())
 calendar=(options.snapshot/'calendar.html').read_text()
else:
 user=json.loads(request('https://api.github.com/users/'+username,True)[0])
 repos=[]
 next_url='https://api.github.com/users/'+username+'/repos?per_page=100'
 while next_url:
  data,links=request(next_url,True)
  repos.extend(json.loads(data))
  link=re.search(r'<(https://api\.github\.com/[^>]+)>; rel="next"',links)
  next_url=link[1] if link else None
 calendar=request('https://github.com/users/'+username+'/contributions')[0]
dates={cid: date.fromisoformat(d) for d,cid in re.findall(r'data-date="([\d-]+)" id="([^"]+)"',calendar)}
counts={dates[cid]:int(n.replace(',','')) if n!='No' else 0 for cid,n in re.findall(r'<tool-tip[^>]* for="([^"]+)"[^>]*>\s*(No|[\d,]+) contributions? on',calendar) if cid in dates}
assert len(counts)>360
days=sorted(counts.items())
total=sum(counts.values())
expected=int(re.search(r'id="js-contribution-activity-description"[^>]*>\s*([\d,]+)\s+contributions',calendar)[1].replace(',',''))
assert total==expected,(total,expected)
def count_commits(start, end, depth=0):
 query=f'author:{username} committer-date:{start}..{end} is:public'
 url='https://api.github.com/search/commits?'+urlencode({'q':query,'per_page':1})
 result=json.loads(request(url,True)[0])
 if result.get('incomplete_results') is False:
  return result['total_count']
 if start>=end or depth>=2:
  raise ValueError('A busca do GitHub retornou uma contagem de commits incompleta.')
 middle=start+(end-start)//2
 return count_commits(start,middle,depth+1)+count_commits(middle+timedelta(days=1),end,depth+1)

if options.snapshot:
 commit_search=json.loads((options.snapshot/'commits.json').read_text())
 if commit_search.get('incomplete_results') is not False:
  raise ValueError('O snapshot de commits está incompleto.')
 commit_count=commit_search['total_count']
else:
 commit_count=count_commits(days[0][0],days[-1][0])
maxday,maximum=max(days,key=lambda x:x[1])
run=longest=0
for _,count in days:
 run=run+1 if count else 0
 longest=max(longest,run)
recent=next((i for i,(_,c) in enumerate(reversed(days)) if c==0),len(days))
W=960
red='#ff4848'; bright='#e00000'; cream='#f9e8d6'; dim='#c2a3a1'; panel='#000000'; line='#592327'
sections=[]
assets={}
def text(x,y,s,size=16,fill=cream,weight=400):
 return f'<text x="{x}" y="{y}" font-family="DejaVu Sans Mono,monospace" font-size="{size}" fill="{fill}" font-weight="{weight}">{html.escape(str(s))}</text>'
def path(d,fill='none',stroke=line):
 return f'<path d="{d}" fill="{fill}" stroke="{stroke}"/>'
def rect(x,y,w,h,fill,stroke='none'):
 return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}"/>'
MOTION="""<style>
@keyframes cursor{0%,49%{opacity:1}50%,100%{opacity:0}}
.cursor{animation:cursor 1s step-end .85s infinite both}
@media (prefers-reduced-motion:reduce){.typed{clip-path:none!important}.cursor{animation:none}}
</style>"""

def typing_line(attributes, raw, index):
 if raw in {'NEURAL PATCHBAY', '[ LINK ESTABLISHED ]'}:
  return f'<text {attributes}>{html.escape(raw)}</text>'
 size=float(re.search(r'font-size="([^"]+)"',attributes)[1])
 x=float(re.search(r'\bx="([^"]+)"',attributes)[1])
 y=float(re.search(r'\by="([^"]+)"',attributes)[1])
 clip_id=f'typing-line-{index}'
 delay=min(index*.07,.70)
 duration=min(.70,max(.25,len(raw)*.025))
 end=delay+duration
 advance=size*.603
 width=advance*len(raw)+size
 times=[0]
 widths=[0]
 if delay:
  times.append(delay/end)
  widths.append(0)
 for character in range(1,len(raw)+1):
  times.append((delay+duration*character/max(len(raw),1))/end)
  widths.append(advance*character+2)
 # The base width is complete. Removing the animation restores every glyph.
 times[-1]=1
 widths[-1]=width
 values=';'.join(f'{value:.4f}' for value in widths)
 key_times=';'.join(f'{value:.6f}' for value in times)
 clip=(f'<defs><clipPath id="{clip_id}" clipPathUnits="userSpaceOnUse">'
       f'<rect x="{x-2}" y="{y-size*1.3}" width="{width}" height="{size*1.8}">'
       f'<animate attributeName="width" values="{values}" keyTimes="{key_times}" '
       f'dur="{end:.3f}s" begin="0s" calcMode="discrete" fill="remove"/>'
       '</rect></clipPath></defs>')
 return clip+f'<text {attributes} class="typed" clip-path="url(#{clip_id})">{html.escape(raw)}</text>'

def type_text(body):
 line_index=0
 def replace(match):
  nonlocal line_index
  result=typing_line(match[1],html.unescape(match[2]),line_index)
  line_index+=1
  return result
 return re.sub(r'<text ([^>]+)>([^<]*)</text>',replace,body)

def render_screen():
 row_y=0
 for row_index,row in enumerate(sections):
  slot=W//len(row)
  for column,(loc,alt,_,w) in enumerate(row):
   h,body=assets[loc]
   width=W if len(row)==1 else slot
   height=h+16
   first=column==0
   last=column==len(row)-1
   top=row_index==0
   bottom=row_index==len(sections)-1
   left=16 if first else 0
   right=width-16 if last else width
   upper=11 if top else 0
   lower=height-11 if bottom else height
   grid=f'<defs><pattern id="screen-grid" width="32" height="32" patternUnits="userSpaceOnUse" patternTransform="translate({-(column*slot)%32} {-row_y%32})"><path d="M32 0H0V32" fill="none" stroke="#8a2229" stroke-opacity=".14"/></pattern></defs>'
   background=rect(left,upper,right-left,lower-upper,'#000000')+rect(left,upper,right-left,lower-upper,'url(#screen-grid)')
   sides=[]
   if first:
    sides.append(f'M16 {upper}V{lower}')
   if last:
    sides.append(f'M{width-16} {upper}V{lower}')
   if top or bottom:
    y=upper if top else lower
    sides.append(f'M{left} {y}H{right}')
   frame=''.join(sides)
   edges=''
   if frame:
    edges=f'<path d="{frame}" fill="none" stroke="#e00000" stroke-width="7" opacity=".10"/><path d="{frame}" fill="none" stroke="#ef252a" stroke-width="1.4"/>'
   if top:
    edges+=path('M9 32V4H37M923 4H951V32',stroke='#ff4747')
   if bottom:
    edges+=path(f'M9 {height-32}V{height-4}H37M923 {height-4}H951V{height-32}',stroke='#ff4747')
   if len(row)==1:
    # Keep data labels legible from the first frame, including on cached SVGs.
    content=body if loc in {'assets/stats.svg','assets/contribution-analysis.svg'} else type_text(body)
    # The outer frame belongs to the full screen. Full-width sections sit on its background.
    interior=f'<g transform="translate(43 8) scale(.91 1)">{content}</g>'
    if Path(loc).stem in {'canais','projetos','publicacoes'}:
     interior+=path(f'M66 {height-14}H894',stroke='#682126')+path(f'M66 {height-14}H181',stroke='#e00000')
   else:
    inset_left=43 if first else 7
    inset_right=43 if last else 7
    scale=(width-inset_left-inset_right)/w
    card=path(f'M1 1H{w-11}L{w-1} 11V{h-1}H11L1 {h-11}Z','#11090b','#72242a')
    interior=f'<g transform="translate({inset_left} 8) scale({scale} 1)">{card}{type_text(body)}</g>'
   title=html.escape(alt)
   assets[loc]=f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img"><title>{title}</title>{grid}{background}{edges}{MOTION}{interior}</svg>'
  row_y+=height

def save(name,h,body,alt,w=W,link=None,section=True):
 loc='assets/'+name+'.svg'
 assets[loc]=(h,body)
 if section: sections.append([(loc,alt,link,w)])
 return (loc,alt,link,w)

def rail(n,title,code,h=58):
 return text(24,36,n,15,red,700)+text(70,36,title,18,cream,700)+text(776,36,code,13,dim)+path(f'M47 19V41M740 19V41')
def label(n,title,code):
 save(title.lower().replace(' ','-').replace('ç','c').replace('õ','o'),58,rail(n,title,code),title)
from math import atan2, cos, exp, hypot, sin
from random import Random

def crest(x, y):
 return f'''<g transform="translate({x} {y})">
 <circle r="30" fill="none" stroke="#e00000" stroke-width="3"/>
 <path d="M0 22V-10M0 11L-15 -3M0 11L15 -3" fill="none" stroke="#e00000" stroke-width="4"/>
 <circle cy="-12" r="8" fill="#e00000"/><circle cx="-15" cy="-4" r="7" fill="#e00000"/><circle cx="15" cy="-4" r="7" fill="#e00000"/>
 </g>'''

def module(x, y, w, label, mode):
 result=path(f'M{x} {y}h{w-7}l7 7v48h-{w}Z','#170b0d','#9d272e')
 result+=rect(x+1,y+1,w-9,14,'#2d1014')
 result+=text(x+6,y+11,label,9,'#ffd0ba',700)
 result+=path(f'M{x} {y+16}h{w}',stroke='#6f2428')
 rng=Random(mode+16)
 for dx in range(5,w-4,3):
  u=(dx-w/2)/(w/2)
  for dy in range(20,52,3):
   v=(dy-35)/15
   if mode==0:
    radius=hypot(u*1.6,v)
    value=.82*exp(-((radius-.74)*4)**2)*(.55+.45*cos(atan2(v,u)*17)**2)
   elif mode==1:
    value=.85*exp(-abs(v-.45*sin(u*7)-.16*cos(u*29))*5)
   elif mode==2:
    value=exp(-abs(v-.64*sin(u*4))*3)*(.50+.50*cos(u*16+v*8)**2)
   elif mode==3:
    value=.72*exp(-abs(v+.7*u)*3)*(.4+.6*cos(u*12)**2)
   else:
    value=exp(-min(abs(v-abs(u)*1.3+.65),abs(v-abs(u)*1.3+.22))*5)*.72
   if rng.random()<value:
    result+=rect(x+dx,y+dy,1.5,1.5,rng.choice(['#fa503c','#ca2529','#771e22','#f13631']))
 return result

header='''<defs>
<pattern id="crt" width="4" height="4" patternUnits="userSpaceOnUse"><path d="M0 3H4" stroke="#391216" opacity=".65"/></pattern>
<pattern id="matrix" width="14" height="14" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".7" fill="#703033"/></pattern>
</defs>
'''
header+=rect(2,22,4,299,'#e00000')+rect(18,47,924,260,'url(#crt)')+rect(457,65,473,217,'url(#matrix)')
header+=path('M24 47H936M24 303H936M432 67V284')
header+=text(25,31,'ARASAKA',19,red,700)+text(132,31,'/ SECURITY TERMINAL',13,dim)+text(764,31,'ACN002077 / SP-01',14,dim)
header+=crest(61,121)+text(109,103,'SECURITY LOGIN',13,red,700)+text(108,147,'DAVI DIAS',45,cream,700)
header+=path('M29 168H391L402 179V209H29Z','#150a0d','#aa2d32')+text(43,194,'UID',13,red,700)+text(91,195,'@pjz3650',18,cream,700)+f'<g class="cursor">{rect(196,193,9,2,bright)}</g>'
header+=rect(29,227,181,25,'#351015','#7b2229')+text(41,245,'ACCESS GRANTED',15,red,700)+text(29,275,'CURR NETWORK / ARASAKA NET',13,dim)
header+=text(459,68,'NEURAL PATCHBAY',14,red,700)+text(774,68,'05 NODES / PUBLIC',12,dim)
tracks='M402 188H467V133H505 M622 133H643V112H669 M786 112H804V160H819 M554 156V191H516V204 M725 137V187H700V214H739 M878 184V198H861V214 M630 229H655V255H739 M648 112V86H856V131 M471 133V263H496V229'
header+=f'<path d="{tracks}" fill="none" stroke="#bd3034" stroke-width="1.2"/>'
for nx,ny in [(467,188),(467,133),(643,133),(648,112),(725,187),(804,160),(655,229),(861,198),(471,263),(554,191)]:
 header+=rect(nx-2.5,ny-2.5,5,5,'#e00000')
for item in [(505,101,117,'01 / IRIS SCAN',0),(669,83,117,'02 / NET LINK',1),(819,131,111,'03 / CORE',2),(496,204,134,'04 / ARCHIVE',3),(739,214,143,'05 / RELAY',4)]:
 header+=module(*item)
header+=text(27,326,'pjz3650@sp-01:~$ open dossier',13,dim)+text(780,326,'[ LINK ESTABLISHED ]',12,red,700)
save('header',345,header,'Arasaka Security Login. Davi Dias, @pjz3650. Acesso concedido. Cinco módulos conectados no mapa neural.')
label('01','CANAIS','NET / LINKS')
links=[('GITHUB','https://github.com/pjz3650'),('REPOSITÓRIOS','https://github.com/pjz3650?tab=repositories'),('CONTRIBUIÇÕES','https://github.com/pjz3650#js-contribution-activity'),('GITHUBCARD','https://githubcard.com/pjz3650'),('DEV RPG CARD','https://github-rpg-card.github-rpg-card.workers.dev/?username=pjz3650&theme=cyberpunk')]
sections.append([save('channel-'+str(i),58,text(13,34,name,14,cream,700)+text(163,34,'↗',15,red),name,184,url,False) for i,(name,url) in enumerate(links)])

stats=rail('02','TELEMETRIA DO OPERADOR','NET / STATS')
stats+=path('M24 59H936')
metrics=[(commit_count,'COMMITS PÚBLICOS¹'),(total,'CONTRIBUIÇÕES'),(user['public_repos'],'REPOSITÓRIOS PÚBLICOS'),(user['followers'],'SEGUIDORES'),(longest,'RECORDE EM DIAS')]
for i,(v,l) in enumerate(metrics):
 x=25+i*185
 if i: stats+=path(f'M{x-13} 73V148')
 stats+=text(x,112,v,39,cream,700)+text(x,140,l,13,red,700)
languages=Counter(r['language'] for r in repos if r.get('language') and not r['fork'])
stats+=path('M24 165H936')+text(25,190,'CLASSE // NETRUNNER',15,cream,700)
stats+=text(25,215,'FOCO // BACKEND E APIS',14,dim)
stats+=text(370,190,'LINGUAGENS POR REPO PÚBLICO',15,cream,700)
stats+=text(370,215,' · '.join(f'{l} {n}' for l,n in languages.most_common(5)),14,dim)
stats+=text(25,253,f"DESDE {user['created_at'][:10]}  /  ESTRELAS {sum(r['stargazers_count'] for r in repos)}  /  FORKS {sum(r['forks_count'] for r in repos)}  /  SEQUÊNCIA ATUAL {recent} DIAS",14,red)
stats+=text(25,280,'¹ Commits indexados pelo GitHub no período do calendário.',13,dim)
stats+=text(25,301,f'DADOS DO GITHUB · {days[-1][0]:%d/%m/%Y}',13,dim)
save('stats',324,stats,'Telemetria do GitHub: commits públicos indexados, contribuições, repositórios, seguidores e sequências.',link='https://github.com/pjz3650#js-contribution-activity')

analysis=rail('03','ANÁLISE DE CONTRIBUIÇÕES','NET / ACTIVITY')+path('M24 58H936')
analysis+=text(26,88,'ATIVIDADE POR DIA',17,cream,700)
analysis+=text(26,113,'Cada coluna representa um dia ativo. A altura indica o volume.',14,dim)
base=days[0][0]-timedelta(days=days[0][0].weekday())
tiles=[]
for day,n in days:
 week,row=divmod((day-base).days,7)
 tiles.append((week,row,n))

def quad(points,fill,stroke):
 return path('M'+'L'.join(f'{x:.2f} {y:.2f}' for x,y in points)+'Z',fill,stroke)

columns=[]
# Keep every footprint within its own grid cell. Draw the ground first.
for week,row,n in tiles:
 x=116+week*14.4-row*10
 y=176+week*2.35+row*8
 a,b,c,d=(x,y),(x+10,y+1.63),(x+3.5,y+6.83),(x-6.5,y+5.2)
 analysis+=quad((a,b,c,d),'#160d10','#3d1b21')
 if n:
  columns.append((c[1],x,n,(a,b,c,d)))

# Each complete column is painted back to front, including its cap.
for _,_,n,(a,b,c,d) in sorted(columns):
 height=4+76*(n/maximum)**.55
 a_top,b_top,c_top,d_top=((x,y-height) for x,y in (a,b,c,d))
 analysis+=quad((d_top,c_top,c,d),'#851b25','#b32c35')
 analysis+=quad((b_top,c_top,c,b),'#370c13','#a2232c')
 analysis+=quad((a_top,b_top,c_top,d_top),'#f44a4a' if n>=9 else '#b72934','#b92e37')

analysis+=path('M24 364H936')
analysis+=text(26,392,f'{days[0][0]:%d/%m/%Y} → {days[-1][0]:%d/%m/%Y}',14,dim)
peak_label=text(934,392,f'PICO DIÁRIO // {maxday:%d/%m/%Y} · {maximum} CONTRIBUIÇÕES',14,red,700)
analysis+=f'<g text-anchor="end">{peak_label}</g>'
save('contribution-analysis',417,analysis,'Análise de contribuições do GitHub. Colunas 3D representam o volume de atividade por dia.',link='https://github.com/pjz3650#js-contribution-activity')
label('04','PROJETOS','NET / ARCHIVE')
projects=[
 ('pokedex-strategy-hub','POKÉTACTICS','Catálogo, builds e equipes Pokémon.','TYPESCRIPT / WEB'),
 ('codex-mcp-skill-transfer','CODEX MCP SKILL TRANSFER','Sincronização de MCPs e skills.','POWERSHELL / AUTOMAÇÃO'),
 ('analise-reverberacao-sala-sp','ACÚSTICA · SALA SÃO PAULO','Projeto de análise de reverberação.','PYTHON / SIMULAÇÃO'),
 ('strudel-based-studio','LIVE STUDIO','Estúdio de live coding musical.','TYPESCRIPT / ÁUDIO'),
]
for start in (0,2):
 row=[]
 for i,(repo,title,desc,tag) in enumerate(projects[start:start+2],start+1):
  body=text(22,30,f'ARQUIVO / 0{i}',13,red,700)+path('M22 45H440')+text(22,77,title,22,cream,700)+text(22,105,desc,15,dim)+text(22,140,tag,13,red)+text(409,140,'↗',19,cream,700)
  row.append(save('card-'+repo,160,body,f'{title}. {desc} {tag}.',464,'https://github.com/pjz3650/'+repo,False))
 sections.append(row)

stack=rail('05','STACK TÉCNICA','NET / LOADOUT')+path('M24 57H936')
loadout=[('LINGUAGENS','Java · TypeScript · Python · PowerShell'),('BACKEND','Spring Boot · APIs REST'),('DADOS','PostgreSQL · MongoDB · Redis'),('INFRA','AWS · Kubernetes · GitHub Actions')]
for i,(k,v) in enumerate(loadout):
 y=89+32*i
 stack+=text(25,y,f'0{i+1} / {k}',14,red,700)+text(229,y,v,16,cream)
save('stack',208,stack,'Stack: '+'. '.join(v for _,v in loadout))
label('06','PUBLICAÇÕES','NET / FIELD NOTES')
for i,(repo,title,desc,_) in enumerate(projects,1):
 body=text(24,38,f'0{i} / DOC',14,red,700)+text(129,34,title,17,cream,700)+text(129,58,desc,14,dim)+text(900,44,'↗',20,red)
 save('writing-'+repo,76,body,f'Documentação de {title}',link='https://github.com/pjz3650/'+repo+'#readme')
save('all-docs',58,text(24,36,'ABRIR O ARQUIVO DE REPOSITÓRIOS  ↗',16,cream,700), 'Abrir todos os repositórios',link='https://github.com/pjz3650?tab=repositories')
save('footer',59,text(24,36,'ARASAKA NET // SESSÃO ENCERRADA',16,red,700)+text(845,36,'[ EOF ]',15,dim), 'Arasaka Net. Sessão encerrada.')

def img(loc,alt,link,w):
 item=f'<img src="./{loc}" width="{100 if w==W else 50 if w==464 else 20}%" align="top" alt="{html.escape(alt,quote=True)}">'
 return f'<a href="{html.escape(link,quote=True)}">{item}</a>' if link else item

readme='<!-- Perfil temático de fã. -->\n<p align="center">\n'
readme+='\n'.join(''.join(img(*a) for a in row) for row in sections)+'\n'
readme+='</p>\n'
render_screen()
for data in assets.values():
 ET.fromstring(data)
paths=assets.keys() if options.snapshot else ('assets/stats.svg','assets/contribution-analysis.svg')
for name in paths:
 loc=root/name
 loc.parent.mkdir(exist_ok=True)
 loc.write_text(assets[name],encoding='utf-8')
if options.snapshot:
 (root/'README.md').write_text(readme,encoding='utf-8')
print(f'{commit_count} commits públicos indexados, {total} contribuições, {len(days)} dias')
