from dataclasses import replace
from pathlib import Path
import json,secrets,tempfile
from yunpai_customer_service.config import Settings
from yunpai_customer_service.database import Database
from yunpai_customer_service.customer_service import CustomerServiceCore
from yunpai_customer_service.demo.catalog import seed_demo_store, DEMO_CONTEXT
from yunpai_customer_service.auth import AuthenticationService
with tempfile.TemporaryDirectory(prefix='yunpai-terminal-audit-') as directory:
 settings=replace(Settings.from_env(),data_dir=Path(directory),auth_required=True,
     bootstrap_client_id='audit-adapter',bootstrap_tenant_id='audit-tenant',
     bootstrap_client_key=secrets.token_urlsafe(32),subject_hash_key=secrets.token_urlsafe(32),
     model_mock_mode=False,model_enabled=True,kg_import_enabled=False,kg_dream_worker_enabled=False)
 settings.ensure_directories();db=Database(settings.app_db_path);db.initialize();core=CustomerServiceCore.build(db,settings)
 try:
  seed_demo_store(core,tenant_id=settings.bootstrap_tenant_id)
  auth=AuthenticationService(db,settings);principal=auth.authenticate(settings.bootstrap_client_id,settings.bootstrap_client_key,'audit-user')
  original=core.model.generate_json;decisions=[]
  def record(messages,**kwargs):
   result=original(messages,**kwargs)
   if json.loads(messages[-1]['content']).get('task_type')=='agent_decision':decisions.append(result)
   return result
  core.model.generate_json=record
  response=core.chat(principal,'audit-terminal-live','我刚收到的机器不通电，应该怎么处理？',context=DEMO_CONTEXT)
  evidence={'decisions':decisions,'response':response.model_dump()}
  Path(__file__).with_name('live-terminal-probe.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
  print(json.dumps(evidence,ensure_ascii=False))
 finally:core.close()
