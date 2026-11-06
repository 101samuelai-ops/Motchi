"""Read-only project routing and bounded, source-backed discussion context."""
import hashlib
import json
import math
from pathlib import Path
import re

STOP = set('a an the is are was were be been to of on in for with and or my our your me it this that how what which project projects task tasks progress status done doing complete completed work working please can could tell about next remaining still has have do does i you'.split())

SUMMARY_STYLE = (
    "Answer the actual question. Do not turn every conversation into a progress report. "
    "Return text as a natural, plain-language answer: normally 2-3 short sentences, at most 70 English words or 160 Chinese characters. "
    "For progress questions, lead with what works, the important remaining issue and its practical meaning. "
    "For explanations, answer directly using useful examples; for ideas, discuss options and tradeoffs. "
    "For recommendations, make a clear recommendation and explain the practical reason, rather than repeating the activity log. "
    "Use the recent conversation to resolve follow-up words like it, that and next. Ask one focused clarification only when it would materially change the answer. "
    "Use general knowledge for ordinary questions and distinguish it from verified project facts. Do not claim live web access. "
    "For a requested change, discuss the request and explain that the editable work draft needs the user's explicit action named in workDestination; if no target is chosen, ask them to choose the project first. "
    "Answer the actual question; greetings and ordinary chat need no project report. Match the user's language. "
    "For an overview, prioritize the few projects needing attention instead of listing every event. "
    "Put a short supporting explanation in details, one useful suggested next step in nextStep, and a material uncertainty in caveat. "
    "Use empty strings when these fields add nothing. Keep IDs, quotes, history counts and technical implementation out of text. "
    "Do not invent milestones, deadlines, percentages, blockers, successful tests or user acceptance. "
    "A checklist checkmark is recorded completion, not proof of readiness. A suggestion is not an instruction already sent. "
    "Resolve conflicting reports using chronology and scope: a later user-reported failure reopens the affected outcome despite an earlier AI success claim. "
    "Distinguish reported, tested and user-confirmed outcomes without turning the answer into a technical audit. "
    "For work claims, add evidence entries containing the exact supplied projectId, chat, messageId and a verbatim quote from retrieved history. "
    "Use only references supporting this assessment; never fabricate or rewrite quotes. Details may explain the evidence, but must not expose private reasoning. "
    "History coverage is displayed separately. Mention missing/stale data in caveat when it could change the conclusion. "
    "Selected task details may omit other tasks; keep full counts and never call a partial task list exhaustive. "
)


def discussion_only(text):
    return bool(re.search(r"\b(?:don't|do not|never|what if|suppose|imagine|for example|example of|how (?:do|can|would|should))\b|不要|先不|别再|如果|假如|例如|比如|怎么|如何",text,re.I))


def work_request(text):
    """Prepare the user's own instruction; never authorize or execute it.

    Deliberately conservative: ideas, quotes, negatives and how-to questions
    remain discussion. The editable proposal always needs explicit submission.
    """
    text = str(text).strip()
    if not text or len(text)>3000:return None
    # A proposal is inert, but speculative/quoted/rejected ideas should not
    # clutter the conversation with an apparent commitment either.
    if discussion_only(text):return None
    candidate=re.sub(r'"[^"\n]*"|“[^”\n]*”|「[^」\n]*」|‘[^’\n]*’', '', text)
    candidate=re.sub(r'^\s*(?:(?:hey|hi|hello|你好|您好|嘿|嗨)[\s,，!！]*)?(?:motchi|mochi|莫奇|摩奇|莫琪)[\s,，:：!！]+','',candidate,flags=re.I)
    english = (r"(?:^|[.!?;]\s*|\balso\s+|\band\s+)"
        r"(?:(?:please|can you|could you|I want you to|I'd like you to|let's|lets|we need to)\s+)*"
        r"(?:add|implement|fix|change|update|build|create|remove|replace|refactor|prioritize|defer)\s+\S")
    chinese = r"(?:^|[。！？；]|另外|还有|并且)\s*(?:请|帮我|麻烦你|我想让你|现在|先)*(?:添加|新增|增加|实现|修复|修改|更新|创建|删除|替换|调整|优先处理|推迟|把.{1,60}(?:改成|改为|换成))\S"
    return text if re.search(english,candidate,re.I) or re.search(chinese,candidate) else None


def project_inventory(text):
    text = str(text).strip().rstrip('?.!。？！').strip()
    # Do not turn status/work requests into a catalogue query.
    if re.search(r'任务|进度|完成|修复|添加|删除|\b(?:tasks?|progress|finished|add|remove|fix)\b', text, re.I): return False
    return bool(re.fullmatch(
        r'(?:(?:我们|我|目前|现在|当前|手头|的|正在做|正在进行)\s*)*项目(?:还有|都|还|有)*(?:哪些|哪几个|什么)|'
        r'(?:我们|我|目前|现在|当前|手头|的)*(?:有|还|都)*(?:哪些|哪几个)项目|'
        r'(?:列出|看看|查看|显示)(?:我们|我的|我们的|所有|全部|目前|现在|的)*项目|'
        r'(?:what|which) projects (?:do (?:we|i) (?:currently )?have|are (?:we|you) (?:currently )?(?:tracking|working on))|'
        r'(?:list|show|name)(?: me)? (?:all |my |our |the |current )*projects', text, re.I))


def inventory_answer(projects, question):
    chinese = bool(re.search(r'[\u3400-\u9fff]', question))
    names = [str(p['name']) for p in projects]
    if names:
        text = (f'我目前能看到 {len(names)} 个本地项目：' if chinese else f'I can see {len(names)} local projects: ') + ('、' if chinese else ', ').join(names) + ('。' if chinese else '.')
    else:
        text = '我暂时没有发现本地项目。请先在 Codex 中打开一个项目。' if chinese else 'I have not found local projects yet. Open a project in Codex first.'
    return {'scope':'overview','text':text,'details':'','nextStep':'','caveat':'',
            'evidence':[],'sources':[],'answerSource':'localCatalog',
            'projects':[{'id':p['id'],'name':p['name']} for p in projects],
            'routeReason':'Listed the current local project catalog without requiring AI inference.'}


def provider_notice(code, chinese):
    messages = {
        'authentication': ('我的 AI 连接缺少有效的登录凭据，暂时不能生成回答。请检查 Motchi 使用的 Codex 登录或 API 密钥配置。', 'My AI connection is missing valid credentials. Check the Codex sign-in or API key configuration used by Motchi.'),
        'rate_limit': ('我的 AI 服务暂时达到用量限制。请稍后再试；本地项目列表仍可查看。', 'My AI service has reached a usage limit. Try again later; the local project list is still available.'),
        'timeout': ('我的 AI 服务这次没有及时回答。请稍后再试；本地项目列表仍可查看。', 'My AI service did not answer in time. Try again shortly; the local project list is still available.'),
        'connection': ('我暂时连接不上 AI 服务。请检查网络后再试；本地项目列表仍可查看。', 'I cannot reach my AI service right now. Check the connection and try again; the local project list is still available.'),
        'configuration': ('我的 AI 模型配置暂时不可用。请检查 Codex 的模型设置。', 'My configured AI model is unavailable. Check the model settings in Codex.'),
        'unavailable': ('我的 AI 服务暂时无法回答。请稍后再试；本地项目列表仍可查看。', 'My AI service cannot answer right now. Try again shortly; the local project list is still available.'),
        'invalid_response': ('我收到的回答未通过核实，暂时不能可靠地答复你。请换个说法再试。', 'The answer I received could not be verified. Please rephrase and try again.')}
    return messages.get(code, messages['unavailable'])[0 if chinese else 1]


def question_kind(text):
    if work_request(text):return 'work'
    if re.search(r"what can you (?:do|help)|how can you help|your capabilities|你(?:能|可以)(?:做|帮)|你有什么功能",text,re.I):return 'capabilities'
    if re.search(r"\b(progress|status|finished|remaining|blocker|checklist|what.{0,20}(?:done|attention|next)|how.{0,25}(?:doing|going))\b|进度|完成了|剩余|还有什么|下一步|清单",text,re.I):return 'status'
    if re.search(r"\b(explain|what is|what are|how (?:does|do))\b|解释|是什么|什么是|原理",text,re.I):return 'explanation'
    return 'discussion'


def work_proposal(text, project=None, selection=None, model_intent=None):
    instruction=work_request(text)
    if instruction is None and model_intent=='draftWork' and not discussion_only(text):
        # Model intent may offer an editable draft for natural phrasing beyond
        # imperative patterns. It is never an execution/delivery authorization.
        instruction=str(text).strip()
    if instruction is None:return None
    item=next((i for i in project['items'] if i['id']==selection),None) if project else None
    return {'text':instruction,'projectId':project['id'] if project else None,
            'selection':item['id'] if item else None,'requiresSend':True,
            'canSend':bool(item and item.get('managedCodex'))}


def answer_schema():
    fields = {key: {'type': 'string'} for key in ('text', 'details', 'nextStep', 'caveat')}
    fields.update(scope={'type': 'string', 'enum': ['project', 'overview', 'general']},
                  intent={'type':'string','enum':['answer','brainstorm','recommend','draftWork','clarify']},
                  projectId={'type': ['string', 'null']},
                  evidence={'type': 'array', 'items': {'type': 'object',
                      'properties': {key: {'type': 'string'} for key in ('projectId', 'chat', 'messageId', 'quote')},
                      'required': ['projectId', 'chat', 'messageId', 'quote'], 'additionalProperties': False}})
    return {'type': 'object', 'properties': fields, 'required': list(fields), 'additionalProperties': False}


def presentation(raw, context, project_ids, question=''):
    """Validate displayed references against the exact retrieved project snippets.

    This verifies reference integrity, not the model's interpretation. Invalid or
    oversized output falls back to known counts instead of displaying its claims.
    """
    try:
        answer = json.loads(raw)
        if not isinstance(answer, dict): raise ValueError()
        clean = {}
        for field, limit in (('text', 900), ('details', 4000), ('nextStep', 500), ('caveat', 700)):
            value = answer.get(field, '')
            if not isinstance(value, str) or len(value) > limit: raise ValueError()
            clean[field] = value.strip()
        if not clean['text']: raise ValueError()
        evidence = answer.get('evidence', [])
        if not isinstance(evidence, list) or len(evidence) > 8: raise ValueError()
        messages = {(p['id'], m['chat'], m['id']): m
                    for p in context['projects'] if p['id'] in project_ids
                    for m in p['history']['messages']}
        clean['evidence'] = []
        for ref in evidence:
            if not isinstance(ref, dict): raise ValueError()
            key = tuple(ref.get(k) for k in ('projectId', 'chat', 'messageId'))
            quote = ref.get('quote')
            if (not all(isinstance(k, str) for k in key) or key not in messages or
                    not isinstance(quote, str) or not 4 <= len(quote) <= 1000 or quote not in messages[key]['text']):
                raise ValueError()
            clean['evidence'].append({**{k: ref[k] for k in ('projectId', 'chat', 'messageId')},
                                      'quote': quote, 'role': messages[key]['role'], 'at': messages[key]['at']})
        return clean
    except (ValueError, TypeError, KeyError):
        chinese = bool(re.search(r'[\u3400-\u9fff]', question))
        projects = [p for p in context['projects'] if p['id'] in project_ids]
        counts = []
        for p in projects[:3]:
            c = p['checklist']
            counts.append(p['name'] + ('：' if chinese else ': ') + (
                (f"清单已勾选 {c['completed']}/{c['total']} 项" if chinese else f"{c['completed']} of {c['total']} checklist tasks checked")
                if c.get('total') else ('进度未知' if chinese else 'progress unknown')))
        text = ('；' if chinese else '; ').join(counts) if question_kind(question)=='status' or not question else ''
        failure = context.get('providerFailure', 'invalid_response')
        if text and len(projects) > 3: text += (f'；另有 {len(projects)-3} 个项目' if chinese else f'; plus {len(projects)-3} other projects')
        if not text: text = provider_notice(failure, chinese)
        caveat = ('实时总结暂不可用。这些是记录的清单数量，不能确认项目已可交付。' if chinese else
                  'The live summary is unavailable. Recorded checklist counts do not confirm readiness.') if projects and question_kind(question)=='status' else (
                  '回答服务暂不可用，或返回的内容未通过核实。' if chinese else 'The answer service is unavailable or its response could not be verified.')
        return {'text': text, 'details': '', 'nextStep': '', 'evidence': [], 'summaryUnavailable': True, 'providerIssue': failure, 'caveat': caveat}

def terms(text):
    text = str(text).casefold().replace('’', "'")
    words = {w for w in re.findall(r'[a-z0-9][a-z0-9_-]{1,}', text) if w not in STOP}
    for run in re.findall(r'[\u3400-\u9fff]+', text):
        words.update(run[i:i+2] for i in range(len(run)-1))
    return words


def identity(cwd):
    return hashlib.sha256(str(Path(cwd).resolve()).encode()).hexdigest()[:24]


def checklist_context(progress, question, budget=10000):
    """Keep full counts; bound answer context to relevant/recent task details.

    This never changes the actual checklist or its history-review coverage.
    Omitted details remain visible in the project UI and explicitly disclosed.
    """
    compact = {k:v for k,v in progress.items() if k!='tasks'}
    tasks = progress.get('tasks',[])
    query = terms(question)
    def rank(task):
        overlap = len(query & terms(str(task.get('title') or '')+' '+str(task.get('acceptance') or '')))
        evidence = task.get('evidence')
        at = evidence.get('at',task.get('addedAt',0)) if isinstance(evidence,dict) else task.get('addedAt',0)
        return (overlap, not task.get('done'), at if isinstance(at,(int,float)) else 0)
    selected=[];used=0
    for task in sorted(tasks,key=rank,reverse=True):
        row={k:task[k] for k in ('id','title','done','acceptance','manualOverride') if k in task}
        size=len(json.dumps(row,ensure_ascii=False))
        if size>budget-used:continue
        selected.append(row);used+=size
        if len(selected)>=64:break
    compact.update(tasks=selected,omittedTasks=len(tasks)-len(selected),
                   taskDetailScope='Selected relevant, unfinished and recent task details; totals include the complete checklist.')
    return compact


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
    if question_kind(text)=='capabilities':
        return {'scope':'general','projects':[],'reason':'You asked how Motchi can help, not for a status report.'}
    matches = named(text,projects)
    macro = bool(re.search(r'\b(all (?:my |our )?projects|across (?:my |our )?projects|overall|big picture|everything|macro|compare)\b|所有项目|全部项目|整体|全局|总览|比较',text,re.I))
    if macro or (len(matches)>1 and re.search(r'\band\b|和|与',text,re.I)):
        return {'scope':'overview','projects':matches if len(matches)>1 else projects,'reason':'You asked for a view across projects.'}
    if len(matches)>1:return {'scope':'choice','projects':matches,'reason':'The project name matches more than one project.'}
    if len(matches)==1:return {'scope':'project','projects':matches,'reason':'Matched the project named in your question.'}
    if work_request(text):
        current=next((p for p in projects if p['id']==selected),None)
        return {'scope':'project' if current else 'choice','projects':[current] if current else projects,
                'reason':'Prepare an editable work draft for the selected project; nothing is sent yet.'}
    # An open project's progress follow-up stays there. Topic overlap from an
    # ASR misspelling must not replace an explicit UI selection with a choice.
    if selected:
        current=next((p for p in projects if p['id']==selected),None)
        if current and (re.search(r'\b(it|this|that|our|we|architecture|implementation|decision|tradeoffs?|remain(?:s|ing)?|left|progress(?:ing)?|status|finished|attention|next|blocker|task|checklist)\b|进度|剩|任务|完成|这个|下一步|我们|架构|设计方案|为什么选',text,re.I) or
                        re.fullmatch(r'\s*(?:why|tell me more|can you explain|为什么|详细说说|再解释一下)[?？.!。！\s]*',text,re.I)):
            return {'scope':'project','projects':[current],'reason':'Continued the selected project discussion.'}
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
    if re.search(r'\b(progress(?:ing)?|status|attention|finished|remaining|projects|blockers?|checklist)\b|项目|进度|清单|完成|剩余',text,re.I):
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
