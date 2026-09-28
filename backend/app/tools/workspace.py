from ..config import WORKSPACE,ARTIFACTS
def safe(base,rel):
    p=(base/rel).resolve()
    if p!=base and base not in p.parents:raise ValueError("Path escapes allowed area")
    return p
def list_files():return [str(p.relative_to(WORKSPACE)) for p in WORKSPACE.rglob("*") if p.is_file()]
def read_file(path):
    p=safe(WORKSPACE,path)
    if not p.is_file():return {"error":"File not found"}
    if p.stat().st_size>2_000_000:return {"error":"File too large"}
    return {"path":path,"content":p.read_text(encoding="utf-8")}
def write_artifact(filename,content):
    p=safe(ARTIFACTS,filename);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,encoding="utf-8")
    return {"created":str(p.relative_to(ARTIFACTS)),"bytes":len(content.encode())}
