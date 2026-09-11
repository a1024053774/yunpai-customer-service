"""Isolated live-model acceptance server; never uses existing product data."""
import json,os,sys,tempfile,threading,time,socket,uuid,hashlib
from pathlib import Path
from dataclasses import replace
from datetime import datetime,timezone
import uvicorn
run=json.loads(Path('/tmp/yunpai-current-test-run.json').read_text())
sys.path.insert(0,str(Path(run['candidate_root'])/'src'))
evidence=Path(run['evidence_root'])/'lead'; evidence.mkdir(exist_ok=True)
from yunpai_customer_service.config import Settings
from yunpai_customer_service.demo.app import create_app
from yunpai_customer_service.api import create_api_app
from yunpai_customer_service.llm import ModelGateway
import yunpai_customer_service.graph as graphmod
lock=threading.Lock()
def record(name,item):
    with lock:
        with (evidence/name).open('a') as h:h.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),**item},ensure_ascii=False,default=str)+'\n')
original_build=graphmod.build_graph
def observed_build(**kwargs):
    builder=original_build(**kwargs)
    for name in list(builder.nodes):
        runnable=builder.nodes.pop(name).runnable
        def wrap(state,config,node=name,original=runnable):
            start=time.monotonic()
            try:
                result=original.invoke(state,config)
                record('nodes.jsonl',{'node':node,'trace_id':state.get('trace_id'),'session_id':state.get('external_session_id'),'duration_ms':round((time.monotonic()-start)*1000),'result_keys':sorted(result) if isinstance(result,dict) else []})
                return result
            except BaseException as e:
                record('nodes.jsonl',{'node':node,'trace_id':state.get('trace_id'),'error':type(e).__name__})
                raise
        builder.add_node(name,wrap)
    return builder
graphmod.build_graph=observed_build
old_request=ModelGateway._request
call_count=0
def observed_request(self,payload,**kwargs):
    global call_count
    call_count+=1
    if call_count>80: raise RuntimeError('acceptance model call ceiling reached')
    start=time.monotonic()
    summary={'call_number':call_count,'configured_model':payload.get('model'),'stream':payload.get('stream'),'input_sha256':hashlib.sha256(json.dumps(payload.get('messages',[]),ensure_ascii=False).encode()).hexdigest()}
    # Only synthetic test data and public built-in prompts; omit any private provider fields.
    record('model-inputs.jsonl',{**summary,'messages':payload.get('messages')})
    try:
        result=old_request(self,payload,**kwargs)
        record('models.jsonl',{**summary,'actual_model':result.get('model'),'usage':result.get('usage'),'duration_ms':round((time.monotonic()-start)*1000),'request_id':result.get('id')})
        return result
    except Exception as e:
        record('models.jsonl',{**summary,'duration_ms':round((time.monotonic()-start)*1000),'error':type(e).__name__})
        raise
ModelGateway._request=observed_request
private=Path(tempfile.mkdtemp(prefix='yunpai-live-acceptance-'))
settings=replace(Settings.from_env(),data_dir=private/'data',auth_required=True,admin_auth_required=True,
    bootstrap_tenant_id='acceptance-tenant',bootstrap_client_id='acceptance-client',bootstrap_client_key=uuid.uuid4().hex+uuid.uuid4().hex,
    bootstrap_admin_id='acceptance-admin',admin_api_key=uuid.uuid4().hex+uuid.uuid4().hex,subject_hash_key=uuid.uuid4().hex+uuid.uuid4().hex,
    model_enabled=True,model_mock_mode=False,model_streaming=False,model_retry_attempts=0,model_max_output_tokens=800,
    kg_import_enabled=False,kg_dream_worker_enabled=False,vision_enabled=True)
app=create_app(settings)
def serve(app):
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128)
    port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='warning',lifespan='on'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    deadline=time.monotonic()+120
    while not server.started and thread.is_alive() and time.monotonic()<deadline:time.sleep(.1)
    if not server.started:raise RuntimeError('server startup failed')
    return port,server,thread
demo_port,demo_server,demo_thread=serve(app)
core=app.state.runtime.core
fact='澄羽验收陶杯 QAZEPH 的颜色为湖蓝，容量640ml，材质为陶瓷，测试售价73元。不能用于微波炉。没有记录库存、销量或送达日期。此为合成验收资料。'
docid=core.knowledge.add_document(category='验收商品',intent='product',question='澄羽验收陶杯 QAZEPH 的规格和使用限制',answer=fact,keywords='澄羽 陶杯 QAZEPH 颜色 容量 微波炉',risk_level='low',source='acceptance://synthetic-product-v1',tenant_id=settings.bootstrap_tenant_id,knowledge_key='acceptance-product-qazeph',review_status='approved',approved_by='acceptance-fixture')
api=create_api_app(core)
api_port,api_server,api_thread=serve(api)
public={'demo_url':f'http://127.0.0.1:{demo_port}','api_url':f'http://127.0.0.1:{api_port}','data_dir':str(settings.data_dir),'source_file':str(Path(graphmod.__file__)),'candidate_sha256':run['candidate_sha256'],'model':settings.model_name,'embedding':settings.rag_embedding_provider,'embedding_model':settings.rag_embedding_model,'synthetic_fact':fact,'synthetic_document_id':docid,'pid':os.getpid(),'model_call_limit':80}
(evidence/'runtime.json').write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n')
private_state={**public,'headers':{'X-Client-Id':settings.bootstrap_client_id,'X-Client-Key':settings.bootstrap_client_key,'X-Subject-Id':'acceptance-buyer'},'private_dir':str(private)}
state=private/'client.json';state.write_text(json.dumps(private_state));state.chmod(0o600)
Path('/tmp/yunpai-live-acceptance-state-path').write_text(str(state))
print(json.dumps({'ready':True,**public},ensure_ascii=False),flush=True)
try:
    while True: time.sleep(1)
except KeyboardInterrupt:pass
finally:
    api_server.should_exit=True;demo_server.should_exit=True
    api_thread.join(10);demo_thread.join(10)
    state.unlink(missing_ok=True)
    print('SERVERS_STOPPED',flush=True)
