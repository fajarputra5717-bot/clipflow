import json, urllib.request, urllib.error, http.cookiejar, datetime, subprocess
API="http://127.0.0.1:8001"; U=json.load(open("${QA_SCRATCH}/lanec_users.json"))
def sess(u):
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(m,p,b=None):
        r=urllib.request.Request(API+p,data=json.dumps(b).encode() if b is not None else None,method=m,headers={"Content-Type":"application/json"})
        try: x=op.open(r); t=x.read().decode(); return x.status,(json.loads(t) if t else {})
        except urllib.error.HTTPError as e:
            t=e.read().decode()
            try: return e.code,json.loads(t)
            except Exception: return e.code,{"raw":t[:120]}
    assert call("POST","/api/auth/login",{"username":u,"password":U[u]["pw"]})[0]==200
    return call
A,B=sess("lane-c-a"),sess("lane-c-b")
import datetime as dt, time
sql=lambda q: subprocess.run(["docker","exec","clipflow-staging-postgres-1","psql","-U","clipflow","-d","clipflow","-At","-c",q],capture_output=True,text=True).stdout.strip()
res=[]
def chk(name,got,want): ok=(got in want) if isinstance(want,list) else got==want; res.append((ok,name,got)); print(("PASS" if ok else "FAIL"),name,str(got)[:160],flush=True)
J="b0a4ed97-01a1-4c46-a8cf-950a5caf977a"
cid=sql(f"select id from clip_candidates where job_id='{J}' and final_path is null order by start_time limit 1")
base=f"/api/jobs/{J}/candidates/{cid}"
now=dt.datetime.now(dt.timezone.utc)
s,acc=A("GET","/api/accounts"); lst=acc.get("accounts",acc)
fb=[a for a in lst if a["platform"]=="facebook" and a.get("active",True)]
if not fb: s,a=A("POST","/api/accounts",{"platform":"facebook","handle":"@lane_c_fb"}); fbid=a.get("id") or a["account"]["id"]
else: fbid=fb[0]["id"]
s,plan=A("GET",base+"/schedule-plan"); chk("A schedule-plan",s,200)
fbp=[p for p in plan.get("platforms",[]) if p["platform"]=="facebook"]
sug=[x for a in (fbp[0]["accounts"] if fbp else []) if a["id"]==fbid for x in a["suggestions"]]
print("  plan platforms",[p["platform"] for p in plan.get("platforms",[])],"fb times",fbp[0]["times"] if fbp else None,"sugg",sug[:3])
chk("suggestions are future",all(dt.datetime.fromisoformat(x.replace("Z","+00:00"))>now for x in sug) and len(sug)>0,True)
for m,p,b in (("GET",base+"/schedule-plan",None),("POST",base+"/schedule",{"posts":[{"platform":"facebook","account_id":fbid,"scheduled_for":sug[0]}],"dry_run":True})):
    s,_=B(m,p,b); chk(f"B {m} {p.split('/')[-1]} on A's clip",s,404)
s,_=A("POST",base+"/schedule",{"posts":[{"platform":"facebook","account_id":fbid,"scheduled_for":(now-dt.timedelta(hours=1)).isoformat()}]}); chk("past time 400",s,400)
s,_=A("POST",base+"/schedule",{"posts":[{"platform":"facebook","account_id":fbid,"scheduled_for":sug[0]},{"platform":"facebook","account_id":fbid,"scheduled_for":sug[1]}]}); chk("dup platform 400",s,400)
s,_=A("POST",base+"/schedule",{"posts":[{"platform":"tiktok","account_id":fbid,"scheduled_for":sug[0]}]}); chk("account/platform mismatch 4xx",s,[400,404,409])
s,d=A("POST",base+"/schedule",{"posts":[{"platform":"facebook","account_id":fbid,"scheduled_for":"2026-10-30T12:00:00+07:00"}],"dry_run":True}); chk("dry-run 30 Oct ineligible (window)",(s,(d.get("posts") or [{}])[0].get("eligible")),[(200,False)]); print("  ",(d.get("posts") or [{}])[0].get("ineligible_reason"))
s,d=A("POST",base+"/schedule",{"posts":[{"platform":"facebook","account_id":fbid,"scheduled_for":sug[0]}],"approve":True}); chk("approve & schedule",s,200); print("  approved",d.get("approved"),"status now",sql(f"select status from clip_candidates where id='{cid}'"))
pid=d["posts"][0]["id"]; chk("post planned at slot",(d["posts"][0]["status"],d["posts"][0]["scheduled_for"][:16]),[("planned",dt.datetime.fromisoformat(sug[0].replace("Z","+00:00")).astimezone(dt.timezone(dt.timedelta(hours=7))).isoformat()[:16]),("planned",sug[0][:16])])
s,d2=A("POST",base+"/schedule",{"posts":[{"platform":"facebook","account_id":fbid,"scheduled_for":sug[1]}],"approve":True}); chk("re-plan keeps post id",(s,d2["posts"][0]["id"]==pid),[(200,True)])
s,sc=A("GET","/api/schedule"); chk("A /api/schedule lists post",pid in json.dumps(sc),True); print("  telegram_ready",sc.get("telegram_ready"),"posting_times keys",list(sc.get("posting_times",{})))
s,sb=B("GET","/api/schedule"); chk("B /api/schedule excludes A's post",pid in json.dumps(sb),False)
s,_=B("PATCH",f"/api/posts/{pid}",{"status":"dropped"}); chk("B drop A's post 404",s,404)
s,_=A("PATCH",f"/api/posts/{pid}",{"status":"dropped"}); chk("A drop planned post",s,200)
s,sc=A("GET","/api/schedule"); chk("dropped post leaves schedule",pid in json.dumps(sc),False)
# reminder: post due in 2 min (lead 15) → no bot on staging → reminder_status no_chat
s,d3=A("POST",base+"/schedule",{"posts":[{"platform":"facebook","account_id":fbid,"scheduled_for":(now+dt.timedelta(minutes=3)).isoformat()}],"approve":False}); chk("schedule due-soon post",s,200); rid=d3["posts"][0]["id"]
for i in range(12):
    st=sql(f"select coalesce(reminder_status,'-')||'|'||coalesce(reminded_at::text,'-') from clip_posts where id='{rid}'")
    if not st.startswith("-"): break
    time.sleep(10)
chk("reminder pass reached the post (no bot → no_chat)",st.split("|")[0],["no_chat","queued","sent","failed"]); print("  reminder",st)
s,_=A("PATCH",f"/api/posts/{rid}",{"status":"posted","url":"https://www.facebook.com/reel/7400000000000099"}); chk("mark posted from schedule",s,200)
print("SUMMARY",sum(1 for r in res if r[0]),"/",len(res))
