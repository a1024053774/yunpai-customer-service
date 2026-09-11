# F09 怎么修的

独立审查完成消息 FAIL：并发 approve+reject 8/8 出现 rejected+仍 active；add_document 残余后重试出现第二条 active。落盘审查文件只对双 approve 写了 PASS，不作手册全合同验收。

## 根因

1. `reject()` 在锁外读 status，UPDATE 无 status 谓词，能把已批准覆写成 rejected。
2. `approve()` 先 `add_document` 再 CAS；中断重试会再插一行。

## 修复

`reject` 与 `approve` 同持 `_write_lock`，CAS `WHERE status IN ('pending','evaluated')`。`approve` 若已有同 source 的 active 行则复用，不再插入。

## 同信号

- before：rejected_plus_active=8, leftover duplicate=true
- after：rejected_plus_active=0, both_ok=0, reused_orphan=true, double approve still 1

frozen sha256 `7589cda0afc0fae803812037c00602ed269c101ea7e753a60b456f893338e310`

实现者自测不算验收。
