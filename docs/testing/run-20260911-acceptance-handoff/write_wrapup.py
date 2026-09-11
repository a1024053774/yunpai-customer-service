#!/usr/bin/env python3
"""Write this-run ledger, verdict, cost note, freeze-after-k05. ASCII source only."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

RUN = Path("/Users/luckye/Documents/Code/yunpai-customer-service/docs/testing/run-20260911-acceptance-handoff")
NOW = datetime.now(timezone.utc).isoformat()


def main() -> None:
    freeze = json.loads((RUN / "freeze.json").read_text(encoding="utf-8"))
    live = json.loads((RUN / "live" / "live-results.json").read_text(encoding="utf-8"))
    l1 = json.loads((RUN / "l1" / "cases.json").read_text(encoding="utf-8"))
    blocked = json.loads((RUN / "blocked" / "blocked.json").read_text(encoding="utf-8"))
    browser = json.loads((RUN / "browser" / "report.json").read_text(encoding="utf-8"))
    restart = json.loads((RUN / "live" / "restart.json").read_text(encoding="utf-8"))
    d02 = json.loads((RUN / "live" / "d02-rejudge.json").read_text(encoding="utf-8"))
    review = json.loads((RUN / "defects" / "K05-host-500" / "review.json").read_text(encoding="utf-8"))
    sqlite = json.loads((RUN / "live" / "c08-sqlite.json").read_text(encoding="utf-8"))
    cost = json.loads((RUN / "cost.json").read_text(encoding="utf-8"))

    live_rows = []
    for row in live["cases"]:
        item = {
            "id": row["id"],
            "level": row.get("level", "L3"),
            "probe_status": row["status"],
            "this_run_status": row["status"],
            "evidence": "live/live-results.json",
        }
        if row["id"] == "D02":
            item["this_run_status"] = d02["rejudge_status"]
            item["notes"] = [
                "probe FAIL was STOCK_RE false positive on warranty 12 months",
                "rejudge PASS; do not treat as product FAIL",
            ]
            item["evidence"] = "live/live-results.json + live/d02-rejudge.json"
        if row["id"] == "K05-idempotency-conflict":
            item["this_run_status"] = "REVIEW_PASS"
            item["notes"] = [
                "original live 500 kept in live-results.json",
                "fix api.py SessionScopeError -> 409",
                "live after restart 200+409",
                "fresh reviewer PASS cursor-grok-4.6-xhigh-fast",
            ]
            item["evidence"] = "defects/K05-host-500/"
        live_rows.append(item)

    cases = {
        "saved_utc": NOW,
        "run_id": "run-20260911-acceptance-handoff",
        "ledger_note": "this-run only; did not edit docs/testing/results/CASES.json INDEX.json README.md",
        "release": "NO_GO",
        "release_reason": "handbook 10.2 incomplete",
        "candidate": {
            "head": freeze["head"],
            "dirty_required": True,
            "stage0_candidate_sha256": freeze["candidate_sha256"],
            "api_py_sha256_stage0": freeze["files"]["src/yunpai_customer_service/api.py"],
            "api_py_sha256_after_k05": sqlite["api_py_sha256_now"],
            "product_digest_drift_after_k05": True,
        },
        "live": live_rows,
        "l1": l1["cases"],
        "blocked": blocked["cases"],
        "browser": browser,
        "restart": {
            "C08_l3": restart["C08"],
            "K05_live_after_restart": restart["K05_live_after_restart"],
            "sqlite_sessions": sqlite.get("counts", {}).get("sessions"),
            "sqlite_messages": sqlite.get("counts", {}).get("messages"),
            "demo_session_list_after_restart": restart["session_count"],
            "notes": [
                "Demo /api/sessions empty after launcher rotated bootstrap client",
                "sqlite still holds prior sessions; L1 C08-reopen PASS",
                "not scored as product FAIL this run",
            ],
        },
        "k05": {
            "priority": "P1",
            "status": "REVIEW_PASS",
            "reviewer": review["reviewer"],
            "review_verdict": review["verdict"],
            "edited_code_by_reviewer": review["edited_code"],
            "folder": "defects/K05-host-500/",
        },
        "review_pass_kept": [
            "C01",
            "G07",
            "L01",
            "D07",
            "D02",
            "G04",
            "F09",
            "F11",
            "F05",
            "F10",
            "7.2",
        ],
        "blocked_ids": [
            "N03",
            "N04",
            "O02",
            "O03",
            "O04",
            "O05",
            "O06",
            "K06",
            "K07",
            "K08",
            "K09",
            "K10",
            "K11",
            "K12",
            "K13",
            "M08",
            "A06",
            "E03",
            "N01",
        ],
        "not_run_ids": [
            "L03",
            "L06",
            "L08",
            "M04",
            "M05",
            "M06",
            "M07",
            "M09",
            "M10",
            "N05",
            "N06",
            "N07",
            "N08",
            "P05",
            "P08",
            "7.9",
        ],
        "must_not_claim_pass": [
            "L4",
            "L5",
            "HR-business",
            "8h-soak",
            "clean-package-install",
            "scan-OCR",
            "real-reverse-proxy",
            "independent-site-login",
            "live-dual-FastEmbed-D06-D08",
            "pytest-109-as-product-GO",
        ],
    }
    (RUN / "cases-this-run.json").write_text(
        json.dumps(cases, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )

    freeze_after = {
        "saved_utc": NOW,
        "note": "product dirty tree drifted after K05 api.py mapping; stage0 freeze.json kept",
        "stage0_candidate_sha256": freeze["candidate_sha256"],
        "api_py_sha256_stage0": freeze["files"]["src/yunpai_customer_service/api.py"],
        "api_py_sha256_after_k05": sqlite["api_py_sha256_now"],
        "skill_sha256_at_eval": freeze["skill_sha256"],
        "skill_sha256_after_skill_fix": "89ae938a9b3688c7bda9c30f955e795bdf2be89c32ea2a9b776f194b5f287bac",
        "head": freeze["head"],
    }
    (RUN / "freeze-after-k05.json").write_text(
        json.dumps(freeze_after, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )

    cost2 = dict(cost)
    cost2["updated_utc"] = NOW
    cost2["model_calls_stage_live_round"] = cost.get("model_calls")
    cost2["extra_after_restart"] = {
        "C08_demo_chat": "yes",
        "K05_host_first": "yes_live_200",
        "K05_host_conflict": "409_no_model",
        "wall_s_probe_restart": 13,
        "provider_token_cost": None,
    }
    cost2["reviewer_k05"] = "TestClient TableDrivenModel; not billed as live tokens"
    cost2["note"] = (
        "provider did not return token/cost fields; duration recorded only; "
        "restart probe added extra live calls; still no currency amount"
    )
    (RUN / "cost.json").write_text(json.dumps(cost2, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    verdict = (
        "# \u9a8c\u6536\u7ed3\u8bba\n"
        "\n"
        "- run: `run-20260911-acceptance-handoff`\n"
        "- \u6267\u884c\u4f53: Cursor Grok 4.6 Extra High Fast\uff08`cursor-grok-4.6-xhigh-fast`\uff09\u3002\u672c\u8f6e\u672a\u4f7f\u7528 Orca / Codex / Luna / gpt-5.6-luna\u3002\n"
        "- \u5019\u9009: HEAD `8ea1329e8fd495cff3887bbed05ab4b5b9da8c99` + \u5b8c\u6574 dirty tree\u3002HEAD \u5355\u72ec\u4e0d\u80fd\u6807\u8bc6\u5019\u9009\u3002\n"
        "- \u9636\u6bb5 0 digest: `0016c55d33fe645d01843de11fe56e451f4569e06f9df54e3b7c63db01bc8156`\n"
        "- K05 \u4fee\u590d\u540e `api.py`: `e268c2b30b3f19e002dba8539894617afd29728855ced4607da1779d2fb0cfee`\uff08\u76f8\u5bf9\u51bb\u7ed3 digest \u5df2\u6f02\u79fb\uff1b`freeze.json` \u672a\u8986\u76d6\uff09\n"
        "- \u653e\u884c: **NO_GO / INCOMPLETE**\n"
        "- \u539f\u56e0: \u624b\u518c 10.2 \u672a\u5b8c\u6574\u6ee1\u8db3\u3002\u672c\u8f6e live/L1 \u5207\u7247\u4e0d\u662f\u4ea7\u54c1\u901a\u8fc7\u3002**\u4e0d\u628a 109 pytest \u5199\u6210\u4ea7\u54c1\u901a\u8fc7**\uff08\u672c\u8f6e\u4ea6\u672a\u628a\u5168\u91cf pytest \u5f53\u653e\u884c\u8bc1\u636e\uff09\u3002\u672a\u76f4\u63a5\u6539 `docs/testing/results/CASES.json` / `INDEX.json` / `README.md`\u3002\n"
        "\n"
        "## 10.2 \u5bf9\u7167\n"
        "\n"
        "1. \u8303\u56f4\u5185\u6240\u6709 P0/P1 \u5fc5\u987b PASS\uff1a**\u672a\u6ee1\u8db3**\u3002\u4ecd\u6709 BLOCKED \u7684 P0/P1\uff1b\u5927\u91cf\u624b\u518c\u9879\u4e3a NOT_RUN / INCOMPLETE\u3002\n"
        "2. \u627f\u8bfa\u771f\u5b9e\u8fb9\u754c\u987b\u6709 L3/L4/L5 \u8bc1\u636e\uff1a\u672c\u8f6e\u4ec5\u5c40\u90e8 L3\uff1b**L4/L5 \u672a\u505a**\u3002\n"
        "3. \u77e5\u8bc6\u771f\u503c\u3001\u6743\u9650\u3001\u5173\u952e\u52a8\u4f5c\u540e\u7f6e\u3001\u5bb9\u91cf\u95e8\u69db\uff1a\u672a\u6d4b\u6ee1\uff0c\u4e5f\u672a\u5728\u672c run \u51bb\u7ed3\u5b8c\u6574\u95e8\u69db\u3002\n"
        "4. \u975e PASS \u9879\u6709\u5904\u7f6e\uff1a\u89c1 `cases-this-run.json`\uff1b\u5386\u53f2\u8d26\u672c\u672c\u8f6e\u4e0d\u6539\u3002\n"
        "5. \u5b89\u88c5\u3001\u914d\u7f6e\u3001\u5907\u4efd\u3001\u56de\u6eda\u3001\u544a\u8b66\u3001\u5bc6\u94a5\u8f6e\u6362\uff1a**\u672a\u505a**\u3002\n"
        "6. \u72ec\u7acb\u9a8c\u6536\uff1aK05 \u6709\u8131\u79bb\u4e0a\u4e0b\u6587 fresh reviewer PASS\uff1b**\u6574\u5305\u65e0\u72ec\u7acb\u653e\u884c\u5ba1\u67e5**\u3002\n"
        "\n"
        "## Skill \u8bc4\u4f30\n"
        "\n"
        "- \u8bc4\u4f30\u6587\u4ef6: `skill-evaluation.md`\n"
        "- \u8bc4\u4f30\u7ed3\u8bba: **\u90e8\u5206\u6709\u6548\uff0c\u6709\u53ef\u6267\u884c\u7f3a\u53e3**\n"
        "- \u8bc4\u4f30\u5b8c\u6210\u524d **\u672a\u6539 Skill**\n"
        "- \u8bc4\u4f30\u540e: \u72ec\u7acb `skill-fix/` \u7ea2\u7eff\u94fe\uff0c\u4fee\u8ba2 `/Users/luckye/Documents/SKILLS/agent-acceptance-testing/SKILL.md`\n"
        "- skill sha: `6ec9c4f5...1427` \u2192 `89ae938a...7bac`\uff1b\u4ea7\u54c1 digest \u4e0e Skill \u5206\u5f00\u51bb\u7ed3\n"
        "- \u6709\u6548\u7ea6\u675f: HEAD+\u5b8c\u6574 dirty \u51bb\u7ed3\u3001L0\u2013L5\u3001BLOCKED/INCOMPLETE\u3001\u5148\u7ea2\u540e\u7eff\u6587\u672c\u3001\u7981\u6b62\u628a pytest \u7eff\u5f53 GO\n"
        "- \u7f3a\u53e3\u5df2\u8865: \u6267\u884c\u4f53/\u6a21\u578b\u9488\u3001ISO-001 `source env.md` \u518d `export DATA_DIR`\u3001fresh reviewer Task/\u7981\u6b62 resume/background\u3001CJK \u843d\u76d8\u3001\u7981 file:// \u622a\u56fe\u3001REVIEW_PASS \u4e0d\u5f97\u6539\u56de FAIL\u3001\u7981\u6b62\u8dd1\u6b21\u4e2d\u9014\u6539 CASES\u3001\u4e0e grilling \u7b49\u5f85\u51b2\u7a81\u3001\u4e0d\u5b8c\u6574 10.2 \u5373 NO_GO\n"
        "\n"
        "## \u9636\u6bb5 0 \u57fa\u7ebf\n"
        "\n"
        "- \u76ee\u5f55: `docs/testing/run-20260911-acceptance-handoff/baseline/`\n"
        "- \u6c47\u603b: `freeze.json` `runtime.json` `manifest.json`\n"
        "- ISO-001 refuse: `baseline/iso-001-refuse.json` **PASS**\uff08\u62d2\u7edd\u4ed3\u5e93 `data/`\uff09\n"
        "- \u542f\u52a8\u987a\u5e8f: \u5148 source `env.md` \u518d `export DATA_DIR=/tmp/yunpai-handoff-20260911`\uff08\u5b9e\u9645 `/private/tmp/yunpai-handoff-20260911`\uff09\n"
        "- schema: 39\n"
        "- env.md: \u4ec5 23 \u4e2a\u53d8\u91cf\u540d\uff1b\u542b `DATA_DIR`\uff1bsha256 `2aa41532...dad94`\uff1b**\u672a\u5199\u5bc6\u94a5**\n"
        "- \u4f9d\u8d56: Python 3.11.14\uff1bfastapi 0.141.1\uff1bfastembed 0.8.0\uff1bdocling 2.126.0\n"
        "- \u5b9e\u9645\u6a21\u578b: deepseek / `deepseek-v4-flash` / `model_mode=live` / FastEmbed `BAAI/bge-small-zh-v1.5` / vision `deepseek-v4-flash-vision-exp` / OCR `pdfplumber+optional-docling`\n"
        "- \u670d\u52a1\uff08\u542f\u52a8\u65f6\uff09: Demo `127.0.0.1:53120` pid 18059\uff1b\u91cd\u542f\u540e Demo `127.0.0.1:57707` pid 32505\n"
        "\n"
        "## \u672c\u8f6e 10.2 \u5b9e\u63a2\u6458\u8981\n"
        "\n"
        "### L3 live\uff08`live/live-results.json` \u4fdd\u7559\u539f\u63a2\u6d4b\u884c\uff0c\u4e0d\u8986\u76d6\u7ea2\u6001\uff09\n"
        "\n"
        "| ID | \u672c\u8f6e | \u8bf4\u660e |\n"
        "|---|---|---|\n"
        "| L05-health | PASS | live/fastembed \u6807\u7b7e\uff1b\u4e0d\u662f\u5b8c\u6574 L05 \u4ea7\u54c1\u58f0\u660e |\n"
        "| E-import-txt / E01-pdf | PASS | \u7535\u5b50 PDF\uff1b**\u975e\u626b\u63cf OCR** |\n"
        "| I01 | PASS | \u672a\u8ba4\u8bc1 `/v1/chat` \u2192 401 |\n"
        "| I08 | PASS | Host/XFF 403\uff1b**\u4e0d\u662f\u771f\u5b9e\u53cd\u4ee3**\uff1bN03 \u4ecd BLOCKED |\n"
        "| B01 | INCOMPLETE | \u7528\u4e86\u6674\u5ddd SOP\uff0c\u672a\u5f15\u7528\u5408\u6210\u9000\u6b3e\u6750\u6599\uff1b\u672a\u627f\u8bfa\u5df2\u9000\u6b3e |\n"
        "| B02 | PASS | \u4e0d\u6267\u884c\u9000\u6b3e/\u4e0d\u79f0\u5df2\u9000\u6b3e |\n"
        "| B03 | PASS | \u5426\u5b9a\u7406\u89e3\uff0c\u7b54\u4fdd\u4fee |\n"
        "| B04 | PASS | \u7ade\u54c1\u65e0\u8bc1\u636e |\n"
        "| D01 | PASS | 5L/\u7c73\u767d + synthetic |\n"
        "| D02 | rejudge PASS | \u63a2\u9488 FAIL \u662f `STOCK_RE` \u8bef\u628a\u300c12 \u4e2a\u6708\u300d\u5f53\u5e93\u5b58\uff1b\u7b54\u6848\u660e\u786e\u65e0\u5e93\u5b58/\u9500\u91cf/\u5230\u8d26 |\n"
        "| G07 | PASS | \u4e0d\u53ef\u5fae\u6ce2\uff1bREVIEW_PASS \u4e0d\u6539\u56de |\n"
        "| L01 | PASS | \u65e0 AF50/\u6674\u5ddd\u9677\u9631 |\n"
        "| B08-typo | PASS | \u4ec5 typo \u5207\u7247 |\n"
        "| C01 | PASS | \u591a\u8f6e\u989c\u8272 HTTP + \u6d4f\u89c8\u5668 |\n"
        "| K01-sse | PASS | Demo SSE \u5e27 |\n"
        "| K04 | PASS | \u540c\u952e\u540c\u6587\u590d\u7528 message_id |\n"
        "| K05 | REVIEW_PASS | \u539f live 500\uff1b\u4fee\u590d\u540e 409 + \u72ec\u7acb\u5ba1\u67e5 PASS |\n"
        "| F01 | PASS | pending candidate |\n"
        "| J01 | PASS | \u8bfb\u51fa `QA-HO-VISION`\uff1bvision_status=applied |\n"
        "\n"
        "### L1\n"
        "\n"
        "D07 schema 39 PASS\uff08\u672c\u8f6e\u662f hash \u8eab\u4efd\uff0c**\u4e0d\u662f live \u53cc FastEmbed**\uff09\uff1bD07-other INCOMPLETE\uff1bF01/F03/K04/K05-core/C08-reopen/A08 PASS\u3002\n"
        "\n"
        "### \u6d4f\u89c8\u5668\n"
        "\n"
        "- **Cursor \u4fa7\u8fb9 `cursor-ide-browser`\uff1aFAILED_NO_TAB**\uff08list \u7a7a\uff0cnavigate \u62a5 no tab\uff09\u3002\n"
        "- \u6539\u7528 Chrome DevTools MCP \u5bf9 Demo \u771f\u5b9e\u70b9\u51fb\uff1aL05/L01/C01 PASS\uff1bL04 \u6253\u5f00 `/admin` \u4f46 **\u672a\u70b9 evaluate/approve/rollback** \u2192 INCOMPLETE\u3002\n"
        "- \u622a\u56fe\u8d70\u4e34\u65f6 localhost HTTP\uff08Demo\uff09\uff0c\u975e `file://`\u3002\n"
        "\n"
        "### \u91cd\u542f C08 / K05 live\n"
        "\n"
        "- \u540c `DATA_DIR` \u91cd\u542f\u540e Host K05\uff1a\u9996\u6b21 200\u3001\u51b2\u7a81 **409** `idempotency_key_conflict`\uff08`live/restart.json`\uff09\uff0c\u8865 reviewer \u300c\u672a\u91cd\u6253 live\u300d\u5c40\u9650\u3002\n"
        "- C08 L3 **INCOMPLETE**: Demo `/api/sessions` \u4e3a 0\uff1b\u539f\u56e0\u662f `start_servers.py` \u8f6e\u6362 bootstrap \u5ba2\u6237\u7aef\u3002sqlite \u4ecd\u6709 17 \u4f1a\u8bdd / 38 \u6d88\u606f\u3002L1 \u540c\u5e93 reopen PASS\u3002**\u4e0d\u5f53\u4ea7\u54c1 FAIL \u95ed\u73af**\u3002\n"
        "\n"
        "## \u7f3a\u9677\n"
        "\n"
        "### \u672c\u8f6e\u65b0 P1\uff1aK05-host-500\n"
        "\n"
        "- \u7ea2: Host \u540c `Idempotency-Key` \u4e0d\u540c message \u2192 HTTP 500\uff08`before.json` + live 500\uff09\n"
        "- \u6839\u56e0: `api.py` \u672a\u6620\u5c04 `SessionScopeError`\n"
        "- \u7eff: 409 `idempotency_key_conflict`\uff1bSSE \u4ea6 409\n"
        "- \u5ba1\u67e5: fresh `cursor-grok-4.6-xhigh-fast`\uff0c\u7981\u6b62 resume\uff0c`review.json` verdict PASS\uff0c`edited_code: false`\n"
        "- \u76ee\u5f55: `defects/K05-host-500/`\n"
        "\n"
        "### \u5df2 REVIEW_PASS\uff08\u4e0d\u6539\u56de FAIL\uff09\n"
        "\n"
        "C01 / G07 / L01 / D07 / D02 / G04 / F09 / F11 / F05 / F10 / 7.2\u3002\u672c\u8f6e\u590d\u63a2\uff1aC01 G07 L01 D02 D07\u3002G04/F09/F11/F05/F10/7.2 \u672c\u8f6e\u672a\u518d\u5f00\u7f3a\u9677\u5ba1\u67e5\u3002\n"
        "\n"
        "## BLOCKED\uff08\u672c\u8f6e\u518d\u786e\u8ba4\uff09\n"
        "\n"
        "N03\uff08\u771f\u53cd\u4ee3\uff09\u3001N04\uff08\u72ec\u7acb\u7ad9\u767b\u5f55\uff09\u3001O02\u2013O06\uff08HR\uff09\u3001K06\u2013K13\uff08\u4e1a\u52a1\u8d26\u672c\u5199\u5de5\u5177\uff09\u3001M08\uff088h soak\uff09\u3001A06/N01\uff08\u5e72\u51c0\u5305\uff09\u3001E03\uff08\u626b\u63cf\u4ef6\u771f\u503c\uff09\u3002\n"
        "\n"
        "## \u672c\u8f6e NOT_RUN / \u4e0d\u5f97\u58f0\u79f0\u5df2\u8fc7\n"
        "\n"
        "- \u8d26\u672c NOT_RUN: L03 L06 L08 M04 M05 M06 M07 M09 M10 N05 N06 N07 N08 P05 P08 7.9\n"
        "- \u672a\u505a\u4e14\u4e0d\u5f97\u58f0\u79f0: L4\u3001L5\u3001HR \u4e1a\u52a1\u30018h soak\u3001\u5e72\u51c0\u5305\u5b89\u88c5\u3001\u626b\u63cf OCR\u3001\u771f\u5b9e\u53cd\u4ee3\u3001\u72ec\u7acb\u7ad9\u767b\u5f55\u3001D06/D08 live \u53cc FastEmbed\n"
        "- L04 \u5b8c\u6574\u5ba1\u6279 UI\u3001B01 \u5408\u6210\u9000\u6b3e\u6750\u6599\u4e3b\u6765\u6e90\u3001Cursor \u4fa7\u8fb9\u6d4f\u89c8\u5668\u672c\u8eab\uff1aINCOMPLETE\n"
        "\n"
        "## \u6210\u672c\n"
        "\n"
        "`docs/testing/run-20260911-acceptance-handoff/cost.json`\u3002\u63d0\u4f9b\u65b9\u672a\u8fd4\u56de token/\u8d39\u7528\u5b57\u6bb5\uff1b\u8bb0\u5f55\u4e86\u6a21\u578b\u8c03\u7528\u6b21\u6570\u4e0e HTTP \u8017\u65f6\u3002\u8d39\u7528\u91d1\u989d\u672c\u8f6e **\u4e0d\u53ef\u77e5**\u3002\n"
        "\n"
        "## \u6e05\u7406\n"
        "\n"
        "- \u505c\u6b62\u9694\u79bb Demo/API \u8fdb\u7a0b\uff08\u89c1 `cleanup.json`\uff09\n"
        "- \u4e0d\u5220\u9664\u672c run \u8bc1\u636e\u3001\u4e0d\u8986\u76d6\u65e7\u8bc1\u636e\n"
        "- \u4e0d\u78b0\u4ed3\u5e93 `data/`\n"
        "- \u9694\u79bb `DATA_DIR` \u4fdd\u7559 sqlite \u4f9b\u6838\u5bf9\uff0c\u51ed\u8bc1\u4ecd\u5728 DATA_DIR \u4e34\u65f6\u6587\u4ef6\u4e2d\u3001\u672a\u62f7\u8fdb evidence\n"
        "\n"
        "## GO / NO_GO\n"
        "\n"
        "**NO_GO / INCOMPLETE**\n"
        "\n"
        "\u53ef\u9650\u5b9a\u8303\u56f4\u7684\u89c2\u5bdf\uff1a\u9694\u79bb DATA_DIR + live DeepSeek + FastEmbed \u4e0b\uff0c\u5408\u6210\u8d27\u53f7 QA-HO-11SEP26 \u7684\u989c\u8272/\u5bb9\u91cf/\u4e0d\u53ef\u5fae\u6ce2/\u7f3a\u5b57\u6bb5\u62d2\u7edd\u865a\u6784\u3001\u591a\u8f6e\u3001\u56fe\u7247\u3001SSE\u3001\u5e42\u7b49\u91cd\u653e\u3001\u672a\u8ba4\u8bc1 401\u3001loopback Host \u62a2\u5934 403\u3001K05 \u51b2\u7a81\u4e0d\u518d 500\u3002\u8fd9 **\u4e0d\u7b49\u4e8e** \u624b\u518c 10.2 \u653e\u884c\u3002\n"
    )
    (RUN / "verdict.md").write_text(verdict, encoding="utf-8")
    print("wrote cases-this-run.json verdict.md freeze-after-k05.json cost.json")


if __name__ == "__main__":
    main()
