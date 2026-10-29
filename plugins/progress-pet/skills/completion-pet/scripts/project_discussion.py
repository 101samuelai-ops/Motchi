"""Read-only project routing and bounded, source-backed discussion context."""
import hashlib
import math
from pathlib import Path
import re

STOP = set('a an the is are was were be been to of on in for with and or my our your me it this that how what which project projects task tasks progress status done doing complete completed work working please can could tell about next remaining still has have do does i you'.split())

def terms(text):
    text = str(text).casefold().replace('’', "'")
    words = {w for w in re.findall(r'[a-z0-9][a-z0-9_-]{1,}', text) if w not in STOP}
    for run in re.findall(r'[\u3400-\u9fff]+', text):
        words.update(run[i:i+2] for i in range(len(run)-1))
    return words


def identity(cwd):
    return hashlib.sha256(str(Path(cwd).resolve()).encode()).hexdigest()[:24]


def grouped(items):
    groups = {}
    for item in items:
        cwd = str(Path(item['cwd']).resolve())
        p = groups.setdefault(cwd, {'id': identity(cwd), 'cwd': cwd, 'name': item.get('progress',{}).get('name') or Path(cwd).name, 'items': []})
        p['items'].append(item)
    for p in groups.values():
        if p['name'] == 'My project': p['name'] = Path(p['cwd']).name
        p['aliases'] = list(dict.fromkeys([p['name'], Path(p['cwd']).name, re.split(r'[—–:]',p['name'])[0].strip()] + [i['title'] for i in p['items']]))
        primary = next((i for i in p['items'] if i.get('status')=='active'),p['items'][0])
        p['selection'] = primary['id']
        p['progress'] = primary.get('progress',{})
        p['topic'] = ' '.join([t['title'] for t in p['progress'].get('tasks',[])] + [n for i in p['items'] for n in i.get('activity',{}).get('notes',[])])
    return list(groups.values())


def named(text, projects):
    query = text.casefold().replace('’', "'")
    matches = []
    for p in projects:
        for alias in [p['name']] + p.get('aliases',[]):
            alias = alias.strip().casefold()
            if len(alias)<3 and not re.search(r'[\u3400-\u9fff]',alias):continue
            pattern = re.escape(alias)
            if re.search(r'[a-z0-9]',alias):pattern = r'(?<![a-z0-9])'+pattern+r"(?:['’]s)?(?![a-z0-9])"
            if re.search(pattern,query):matches.append(p);break
    return matches


def route(text, projects, selected=None):
    # Addressing the companion does not itself name the Motchi software project.
    text=re.sub(r'^\s*(?:(?:hey|hi|hello|你好|您好|嘿|嗨)[\s,，!！]*(?:motchi|mochi|莫奇|摩奇|莫琪|莫起)|(?:motchi|mochi|莫奇|摩奇)[,，:：])\s*[,，!！:：]?\s*','',text,flags=re.I)
    if not text.strip(' .!?。？！'):
        return {'scope':'general','projects':[],'reason':'You greeted Motchi without naming a project question.'}
    matches = named(text,projects)
    macro = bool(re.search(r'\b(all (?:my |our )?projects|across (?:my |our )?projects|overall|big picture|everything|macro|compare)\b|所有项目|全部项目|整体|全局|总览|比较',text,re.I))
    if macro or (len(matches)>1 and re.search(r'\band\b|和|与',text,re.I)):
        return {'scope':'overview','projects':matches if len(matches)>1 else projects,'reason':'You asked for a view across projects.'}
    if len(matches)>1:return {'scope':'choice','projects':matches,'reason':'The project name matches more than one project.'}
    if len(matches)==1:return {'scope':'project','projects':matches,'reason':'Matched the project named in your question.'}
    # Search task topics by distinctive terms; two meaningful terms and a clear
    # margin are required. Similar topics must produce a choice, not a guess.
    query = terms(text)
    documents = [(p,terms(p.get('topic',''))) for p in projects]
    scores=[]
    for p,words in documents:
        overlap=query & words
        score=sum(math.log(1+len(projects)/(1+sum(w in d for _,d in documents))) for w in overlap)
        if len(overlap)>=2:scores.append((score,p))
    scores.sort(key=lambda row:row[0],reverse=True)
    if scores:
        if len(scores)==1 or scores[0][0]>scores[1][0]*1.4:
            return {'scope':'project','projects':[scores[0][1]],'reason':'Matched distinctive checklist topics in your question.'}
        return {'scope':'choice','projects':[p for score,p in scores if score>=scores[0][0]/1.4],'reason':'Several projects cover this topic.'}
    if selected:
        current=next((p for p in projects if p['id']==selected),None)
        # Only project follow-ups retain a selected project. General questions
        # can leave a project without being mislabelled as that project's work.
        if current and re.search(r'\b(it|this|that|remain(?:s|ing)?|left|progress|status|finished|attention|next|blocker|task|checklist)\b|进度|剩|任务|完成|这个|下一步',text,re.I):
            return {'scope':'project','projects':[current],'reason':'Continued the selected project discussion.'}
    if re.search(r'\b(progress|status|attention|finished|remaining|projects|blockers?|checklist)\b|项目|进度|清单|完成|剩余',text,re.I):
        return {'scope':'overview','projects':projects,'reason':'Reviewed all projects because no single project was named.'}
    return {'scope':'general','projects':[],'reason':'General conversation; no project change requested.'}


def context_for(queue, project, question, budget=14000):
    """Retrieve recent updates, relevant older evidence and initial requirements.

    Project identity is part of every SQL query. The total and selection counts
    disclose the boundary; retrieval never claims exhaustive history analysis.
    """
    cwd=str(Path(project['cwd']).resolve())
    with queue.lock:
        total=queue.db.execute('SELECT COUNT(*) FROM messages WHERE project=?',(cwd,)).fetchone()[0]
        rows=queue.db.execute('SELECT seq,chat,id,role,text,at FROM messages WHERE project=? ORDER BY at DESC,seq DESC LIMIT 600',(cwd,)).fetchall()
        initial=queue.db.execute("SELECT seq,chat,id,role,text,at FROM messages WHERE project=? AND role='user' ORDER BY at,seq LIMIT 3",(cwd,)).fetchall()
    query=terms(question)
    relevant=sorted((r for r in rows if query & terms(r[4])),key=lambda r:(len(query & terms(r[4])),r[5],r[0]),reverse=True)[:8] if query else []
    candidates=rows[:3]+relevant+initial+rows[3:8]
    section_budget=max(250,min(2500,budget//max(1,min(len(candidates),14))))
    selected=[];seen=set();used=0
    for seq,chat,key,role,text,at in candidates:
        if key in seen or used>=budget:continue
        seen.add(key);snippet=text[:min(section_budget,budget-used)];used+=len(snippet)
        selected.append({'id':key,'chat':chat,'role':role,'text':snippet,'at':at,'truncated':len(snippet)<len(text),'seq':seq})
    selected.sort(key=lambda r:(r['at'],r['seq']))
    return {'messages':selected,'availableSections':total,'selectedSections':len(selected),
            'searchedRecentSections':len(rows),'complete':len(selected)==total and not any(r['truncated'] for r in selected),
            'scope':'Selected relevant and recent visible history; unavailable logs and omitted sections were not analyzed.'}
