"""Explicit recovery after process loss; never resubmit pending paid requests."""
import getpass
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from confidence_agents.design import digest
from confidence_agents.local_replay import ARMS, messages, summarize
from confidence_agents.runtime import Calls, save
from confidence_agents.experiment import source_hash


def main():
    root=Path(sys.argv[1])
    read=lambda p:json.loads(p.read_text(encoding="utf-8"))
    manifest=read(root/"manifest.json")
    if manifest["source_hash"]!=source_hash():
        raise ValueError("Source changed since interrupted run")
    if manifest["backend"]!="openrouter":
        raise ValueError("This recovery is for the interrupted live run")
    # Before launching this utility verify the original process has exited.
    marker=root/".recovery-running"
    with marker.open("x"):
        pass
    try:
        work=[]; unknown=[]
        for context in manifest["contexts"]:
            for arm in ARMS:
                for rep in range(manifest["repeats"]):
                    call_id=f"local/luna/{context['task']['id']}/{arm}/{rep}"
                    path=root/"items"/context["task"]["id"]/"calls"/(digest(call_id)+".json")
                    entry={"context":context,"arm":arm,"repeat":rep,"call_id":call_id,"path":path}
                    if not path.exists():
                        work.append(entry)
                    elif read(path)["status"]!="complete":
                        unknown.append(call_id)
        # This run was approved for 480 attempts: 477 records exist, three unstarted calls remain.
        if len(work)>3 or len(unknown)>1:
            raise ValueError("Unexpected recovery scope; inspect before proceeding")
        save(root/"recovery.json",{"reason":"Original terminal process exited during request; original Python process confirmed absent",
             "unobserved_requests_not_retried":unknown,"not_yet_started_calls":[x["call_id"] for x in work],
             "policy":"Retain pending raw record; treat missing response as invalid in analysis; send only never-started requests"})
        if work:
            os.environ["OPENROUTER_API_KEY"]=getpass.getpass("OpenRouter key: ")
        for entry in work:
            folder=root/"items"/entry["context"]["task"]["id"]
            calls=Calls(folder,"openrouter",len(ARMS)*manifest["repeats"],manifest["max_tokens"])
            calls.ask(entry["call_id"],manifest["model"],messages(entry["context"],entry["arm"]))
            print("Recovered never-started call: "+entry["call_id"],flush=True)
        rows=[]; all_calls=[]
        for context in manifest["contexts"]:
            task=context["task"]; item_rows=[]
            for arm in ARMS:
                for rep in range(manifest["repeats"]):
                    call_id=f"local/luna/{task['id']}/{arm}/{rep}"
                    record=read(root/"items"/task["id"]/"calls"/(digest(call_id)+".json"))
                    all_calls.append(record)
                    response=record.get("parsed") if record["status"]=="complete" else None
                    answer=response["answer"] if response else None
                    item_rows.append({"item_id":task["id"],"semantic":context["semantic"],"truth":task["truth"],
                        "own":context["own"],"own_correct":context["own_correct"],"arm":arm,"repeat":rep,
                        "answer":answer,"wrong":answer!=task["truth"] if answer is not None else None})
            save(root/"items"/task["id"]/"results.json",item_rows)
            rows.extend(item_rows)
        rows.sort(key=lambda r:(r["item_id"],r["arm"],r["repeat"]))
        save(root/"results.json",rows)
        result=summarize(rows,manifest["repeats"],"openrouter",manifest["seed"])
        costs=[r.get("response",{}).get("usage",{}).get("cost") for r in all_calls]
        result["usage"]={"requests":len(all_calls),"reported_cost_usd":sum(c for c in costs if c is not None),
                         "requests_without_cost":sum(c is None for c in costs)}
        result["recovery"]={"unobserved_requests":unknown,"missing_response_count":len(unknown)}
        save(root/"summary.json",result)
        save(root/"progress.json",{"items_completed":len(manifest["contexts"]),"items_planned":len(manifest["contexts"]),
                                    "rows":len(rows),"unobserved_requests":len(unknown)})
        (root/".running").unlink(missing_ok=True)
        print(json.dumps({k:v for k,v in result.items() if k not in ("subgroups","item_effects")},indent=2))
    finally:
        marker.unlink(missing_ok=True)


if __name__=="__main__":
    main()
