from __future__ import annotations
import base64, hashlib, json, os, re, sqlite3, time
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parent
LIVE=ROOT/'raw'; STATES=ROOT/'states'; TRIALS=ROOT/'trials'
LIVE.mkdir(exist_ok=True); STATES.mkdir(exist_ok=True); TRIALS.mkdir(exist_ok=True)
runtime=json.loads((ROOT/'runtime.json').read_text())
demo=runtime['demo_url']; host='http://'+runtime['host_api']['listen']; data_dir=Path(runtime['data_dir'])
creds=json.loads((data_dir/'.host-api-creds.json').read_text())
headers={'X-Client-Id':creds['client_id'],'X-Client-Key':creds['client_key'],'X-Subject-Id':'direction-buyer-1'}
results=[]

def digest(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def scrub(v):
    if isinstance(v,dict):
        return {k: ('<redacted>' if re.search(r'key|secret|token|password|authorization|credential',str(k),re.I) else scrub(x)) for k,x in v.items()}
    if isinstance(v,list): return [scrub(x) for x in v]
    return v

def req(method,url,**kw):
    try:
        r=httpx.request(method,url,trust_env=False,timeout=180.0,**kw)
        try: body=r.json()
        except Exception: body={'raw':r.text[:4000]}
        return {'status_code':r.status_code,'headers':{k:v for k,v in r.headers.items() if k.lower() in {'content-type','location'}},'body':scrub(body)}
    except Exception as e:
        return {'status_code':None,'error':f'{type(e).__name__}: {e}'}

def add(id,status,**kw):
    item={'id':id,'status':status,**kw}; results.append(item); print(json.dumps({'id':id,'status':status},ensure_ascii=False),flush=True)

def save(): (LIVE/'probe-results.json').write_text(json.dumps({'run_id':runtime['run_id'],'saved_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'trials':results},ensure_ascii=False,indent=2)+'\n')

def db_rows(sql,args=()):
    with sqlite3.connect(data_dir/'agent.sqlite3') as c:
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute(sql,args).fetchall()]

def post_chat(base, payload, hdr=None, idem=None):
    h=dict(hdr or {})
    if idem: h['Idempotency-Key']=idem
    return req('POST',base+'/api/chat' if base==demo else base+'/v1/chat',headers=h,json=payload)

# L3 preflight and UI HTTP slice
h_demo=req('GET',demo+'/api/health'); h_host=req('GET',host+'/v1/health'); ui=req('GET',demo+'/'); admin=req('GET',demo+'/admin')
add('PREFLIGHT','PASS' if h_demo.get('status_code')==200 and h_host.get('status_code')==200 else 'BLOCKED',demo_health=h_demo,host_health=h_host,ui_http=ui,admin_http=admin,ui_markers={k:(needle in str(ui.get('body'))) for k,needle in [('product','云派'),('multiturn','多轮'),('local_rag','本地 RAG')]},admin_markers={k:(needle in str(admin.get('body'))) for k,needle in [('import','导入'),('evolution','候选')]})

# Static path facts: source text only, no product edits.
source_files=['src/yunpai_customer_service/config.py','src/yunpai_customer_service/intent.py','src/yunpai_customer_service/llm.py','src/yunpai_customer_service/rag.py','src/yunpai_customer_service/embeddings.py','src/yunpai_customer_service/knowledge_ingest.py','src/yunpai_customer_service/api.py']
static={}
for rel in source_files:
    s=(Path.cwd()/rel).read_text(encoding='utf-8')
    static[rel]={'sha256':digest(s.encode()),'contains':{x:(x in s) for x in ['generate_json','FastEmbedProvider','BM25','sqlite3','deepseek','intent_method','keyword','Pinecone','Weaviate','Docling','pdfplumber']}}
(LIVE/'static-path-facts.json').write_text(json.dumps(static,ensure_ascii=False,indent=2)+'\n')
add('D01-D02-static','PASS',level='L0',facts=static,notes=['static call/config evidence only; live behavior and cloud cost evaluated separately'])

# Build three synthetic source files; isolated run inputs, no history overwrite.
nonce='DIR-AUDIT-20260911-ALPHA'
txt=LIVE/f'{nonce}.txt'; md=LIVE/f'{nonce}.md'; pdf=LIVE/f'{nonce}.pdf'
txt.write_text(f'{nonce} TXT source\n产品型号：{nonce}-TXT\n颜色：薄荷绿\n容量：7L\n本资料仅用于本次隔离验收。\n',encoding='utf-8')
md.write_text(f'# {nonce} Markdown source\n\n产品型号：{nonce}-MD\n颜色：深灰\n容量：8L\n\n来源版本：md-v1\n',encoding='utf-8')
try:
    from reportlab.pdfgen import canvas
    c=canvas.Canvas(str(pdf)); c.drawString(72,760,nonce+' PDF source'); c.drawString(72,740,'产品型号：'+nonce+'-PDF'); c.drawString(72,720,'颜色：琥珀色；容量：9L'); c.save()
except Exception as e:
    pdf.write_bytes(b'%PDF-1.4\n'+nonce.encode()+b'\n%%EOF\n')
file_meta={p.suffix:{'name':p.name,'sha256':digest(p.read_bytes()),'bytes':p.stat().st_size} for p in (txt,md,pdf)}
(LIVE/'fixture-digests.json').write_text(json.dumps(file_meta,ensure_ascii=False,indent=2)+'\n')

imports=[]
for p,intent in [(txt,'product'),(md,'product'),(pdf,'product')]:
    with p.open('rb') as f:
        r=httpx.post(demo+'/api/knowledge/import',files={'file':(p.name,f,'application/pdf' if p.suffix=='.pdf' else 'text/plain')},data={'intent':'product_inquiry'},trust_env=False,timeout=180)
    try: body=scrub(r.json())
    except Exception: body={'raw':r.text[:2000]}
    imports.append({'file':p.name,'status_code':r.status_code,'body':body})
add('D07-import','PASS' if all(x['status_code']==200 and (x['body'].get('count',0)>0) for x in imports) else 'FAIL',level='L3',imports=imports)
knowledge=req('GET',demo+'/api/knowledge')
kbody=knowledge.get('body',{}) if isinstance(knowledge.get('body'),dict) else {}
items=kbody.get('items',[]) if isinstance(kbody,dict) else []
matched=db_rows("SELECT id,category,intent,source,version,status,tenant_id,layer,embedding_model FROM knowledge WHERE source LIKE ? ORDER BY id",(f'upload://{nonce}%',))
(STATES/'knowledge-after-import.json').write_text(json.dumps({'http':knowledge,'matched':matched,'total_items':len(items)},ensure_ascii=False,indent=2)+'\n')
add('D08-corpus-state','PASS' if len(matched)>=3 else 'INCOMPLETE',level='L3',matched_count=len(matched),matched=matched,notes=['source/version/item state from API; not business corpus or L4 tenant evidence'])

# Chat probes. Keep model calls bounded and record cost as unknown when provider omits fields.
sid='direction-multiturn-20260911'; first=post_chat(demo,{'session_id':sid,'message':f'请查一下 {nonce}-TXT 这款产品的颜色和容量。'})
second=post_chat(demo,{'session_id':sid,'message':'它的颜色是什么？'})
firstb=first.get('body',{}); secondb=second.get('body',{})
add('D03-multiturn','PASS' if first.get('status_code')==200 and second.get('status_code')==200 and secondb.get('message_id') and secondb.get('session_id')==sid else 'INCOMPLETE',level='L3',session_id=sid,first={k:firstb.get(k) for k in ['message_id','answer','intent','customer_intent','intent_method','sources','model_name','model_reported','model_fallback']},second={k:secondb.get(k) for k in ['message_id','answer','intent','customer_intent','intent_method','sources','model_name','model_reported','model_fallback']},notes=['follow-up reference and answer are model output; independent fact correctness remains manually checked'])

# Non-keyword and ambiguity pairs. Record actual model intent rather than judging by keyword presence.
nonkw=post_chat(demo,{'session_id':'direction-nonkeyword-20260911','message':f'装得下多少东西？请按 {nonce}-TXT 的资料回答。'})
amb=post_chat(demo,{'session_id':'direction-ambiguous-20260911','message':'这个可以吗？'})
for id,resp in [('D05-ambiguous',amb),('D06-nonkeyword',nonkw)]:
    b=resp.get('body',{}) if isinstance(resp.get('body'),dict) else {}
    add(id,'PASS' if resp.get('status_code')==200 and b.get('intent_method')=='model' else 'INCOMPLETE',level='L3',response={k:b.get(k) for k in ['answer','intent','customer_intent','intent_method','confidence','requires_human','route_reason','model_name','model_fallback','sources']},notes=['model intent evidence; one or two prompts cannot prove general routing quality'])

# Host API one authenticated call plus idempotent replay, with separate cloud-cost unknown marker.
host_payload={'session_id':'direction-host-20260911','message':f'请告诉我 {nonce}-TXT 的容量。','context':{'store_id':'demo-qingchuan-shop'}}
host1=post_chat(host,host_payload,headers,idem='direction-host-idem-1'); host2=post_chat(host,host_payload,headers,idem='direction-host-idem-1')
add('D01-host-api','PASS' if host1.get('status_code')==200 and host2.get('status_code')==200 and host1.get('body',{}).get('message_id')==host2.get('body',{}).get('message_id') else 'INCOMPLETE',level='L3',first={k:host1.get('body',{}).get(k) for k in ['message_id','answer','intent_method','model_name','model_fallback','sources']},replay_status=host2.get('status_code'),same_message_id=host1.get('body',{}).get('message_id')==host2.get('body',{}).get('message_id'),cost={'amount':None,'currency':'unknown','reason':'provider response did not expose token/cost fields'})

# Image request: use existing local PNG fixture; record only digest and response metadata.
img_path=Path.cwd()/'docs/screenshots/verify-chat-home.png'
if img_path.exists():
    b64=base64.b64encode(img_path.read_bytes()).decode()
    img=post_chat(demo,{'session_id':'direction-image-20260911','message':'请看看这张图片，告诉我需要进一步确认什么。','image':{'mime_type':'image/png','data_base64':b64}})
    ib=img.get('body',{}) if isinstance(img.get('body'),dict) else {}
    add('D04-image','PASS' if img.get('status_code')==200 and ('vision_status' in ib or 'vision_model' in ib) else 'INCOMPLETE',level='L3',image_sha256=digest(img_path.read_bytes()),response={k:ib.get(k) for k in ['answer','vision_status','vision_model','vision_image_count','intent','customer_intent','intent_method','model_name','model_fallback','sources']},notes=['image is a local existing UI fixture; visual business recognition is not proven by this fixture'])
else: add('D04-image','BLOCKED',reason='local image fixture missing')

# Evolution flow and cross-surface state. Use a chat message as the feedback source.
evochat=post_chat(demo,{'session_id':'direction-evolution-20260911','message':f'请查 {nonce}-TXT 的容量。'})
eb=evochat.get('body',{}) if isinstance(evochat.get('body'),dict) else {}; mid=eb.get('message_id')
if mid:
    fb=req('POST',demo+'/api/feedback',json={'message_id':mid,'rating':-1,'corrected_answer':f'{nonce}-TXT 的容量是 7L，颜色是薄荷绿。','note':'isolated direction audit correction','submitted_by':'direction-audit','evidence_source':f'local:{txt.name}'})
    cand=req('GET',demo+'/api/evolution/candidates'); cb=cand.get('body',{}); citems=cb.get('items',[]) if isinstance(cb,dict) else []
    cid=next((x.get('id') for x in citems if x.get('question') and nonce in str(x.get('question'))),None)
    ev=ap=rb=None
    if cid:
        ev=req('POST',demo+f'/api/evolution/candidates/{cid}/evaluate')
        ap=req('POST',demo+f'/api/evolution/candidates/{cid}/approve',json={'operator':'direction-audit','note':'isolated acceptance only'}) if ev.get('status_code')==200 and ev.get('body',{}).get('gate_passed') else None
        # rollback requires resulting knowledge id from DB/response after approval.
        if ap and ap.get('status_code')==200:
            rb=req('POST',demo+f'/api/evolution/candidates/{cid}/rollback')
    after=req('GET',demo+'/api/evolution/candidates')
    dbstate=db_rows('SELECT id,status,gate_passed,resulting_knowledge_id,decided_by FROM evolution_candidates WHERE id=?',(cid,)) if cid else []
    knowstate=db_rows('SELECT id,status,source FROM knowledge WHERE source=?', (f'evolution:{cid}',)) if cid else []
    state={'candidate_id':cid,'feedback':fb,'list_before':cand,'evaluate':ev,'approve':ap,'rollback':rb,'list_after':after,'sqlite_candidate':dbstate,'sqlite_knowledge':knowstate}
    (STATES/'evolution-after.json').write_text(json.dumps(scrub(state),ensure_ascii=False,indent=2)+'\n')
    consistent=bool(cid and after.get('status_code')==200 and dbstate and ((rb and rb.get('status_code')==200) or (ap is None)))
    add('D09-evolution','PASS' if consistent and rb and rb.get('status_code')==200 and dbstate[0].get('status')=='approved' else 'INCOMPLETE',level='L3',candidate_id=cid,feedback_status=fb.get('status_code'),evaluate_status=ev.get('status_code') if ev else None,approve_status=ap.get('status_code') if ap else None,rollback_status=rb.get('status_code') if rb else None,sqlite_candidate=dbstate,sqlite_knowledge=knowstate,notes=['page/API/SQLite compared; candidate status after rollback is checked for consistency, and any mismatch stays INCOMPLETE'])
else: add('D09-evolution','BLOCKED',reason='chat source message unavailable')

# Direct session/database post-state for multiturn and chat records.
msgs=db_rows("SELECT m.id,s.external_session_id,m.role,m.intent,m.route_reason,m.model_fallback FROM messages m JOIN sessions s ON m.session_id=s.id WHERE s.external_session_id IN (?,?,?,?) ORDER BY m.created_at",(sid,'direction-nonkeyword-20260911','direction-ambiguous-20260911','direction-evolution-20260911'))
(STATES/'messages-after.json').write_text(json.dumps({'rows':msgs},ensure_ascii=False,indent=2)+'\n')
add('D03-D06-sqlite-poststate','PASS' if msgs else 'INCOMPLETE',level='L2/L3',message_count=len(msgs),session_ids=sorted({x.get('external_session_id') for x in msgs}))

# No inference to 10.2: list remaining external boundaries explicitly.
remaining=[
 {'item':'L3 local UI/API','status':'slice-only','reason':'loopback service and HTTP page/API evidence; no independent browser automation or production ingress'},
 {'item':'L4 preproduction','status':'unproved','reason':'no real auth gateway/channel/sandbox business ledger'},
 {'item':'L5 production','status':'blocked','reason':'production writes and production traffic explicitly excluded'},
 {'item':'independent site','status':'unproved','reason':'host API is local loopback with ephemeral isolated credentials'},
 {'item':'HR domain','status':'unproved','reason':'business_domain remains ecommerce; no HR source/SOP/eval acceptance'},
 {'item':'real reverse proxy','status':'unproved','reason':'no proxy process or trusted forwarded-header chain'},
 {'item':'real business ledger','status':'unproved','reason':'no order/refund/inventory/payment external ledger readback'},
 {'item':'clean runtime','status':'unproved','reason':'current candidate is dirty; no clean wheel/image install'},
 {'item':'cost gate','status':'unknown','reason':'DeepSeek provider token/cost fields absent; model calls may incur cloud cost'},
 {'item':'long soak/recovery','status':'unproved','reason':'minimal slices only; no 8h soak or crash recovery'},
]
(LIVE/'10.2-remaining.json').write_text(json.dumps(remaining,ensure_ascii=False,indent=2)+'\n')
add('D10-10.2-boundaries','INCOMPLETE',level='L3/L4/L5',remaining=remaining)

a={'model_calls_possible':True,'cost_amount':None,'cost_currency':'unknown','cost_evidence':'provider response fields absent; do not infer amount','provider':'deepseek','configured_model':runtime.get('configured_model_name'),'vision_model':runtime.get('vision_model'),'retrieval':{'runtime_provider':runtime.get('embedding_provider'),'identity':runtime.get('embedding_identity'),'model':runtime.get('embedding_model'),'local_storage':str(data_dir)},'trials_written':len(results)}
(LIVE/'cost-and-boundary.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
save()
print(json.dumps({'completed':len(results),'data_dir':str(data_dir)},ensure_ascii=False))
