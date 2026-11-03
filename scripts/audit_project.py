#!/usr/bin/env python3
"""Audit evidence, identity, timing, approval, mix, and QC artifacts.

The audit is split into two layers:

- Evidence layer (per segment): observations resolve to hashed frames, cues cite
  observations, density and coverage hold, and no evidence is recycled to pad
  numbers. Segment files are drafting inputs and are not rewritten by edits.
- Script layer (script/merged-draft.json): the canonical script the user reviews.
  Dialogue restatement, plot summary, temporal displacement, title/credit
  matching, identity labels, and review-file alignment are checked against the
  merged cues. When no merged draft exists yet (pure drafting phase), the
  segment cues stand in for the script layer.

Every merged cue carries `derivation` (`segment`, `cue_id`) so the auditor can
prove the merged script resolves to real segment artifacts.
"""
import argparse, difflib, hashlib, json, re, sys
from pathlib import Path

STAGES=("initialized","preferences_confirmed","media_analyzed","segments_analyzed","script_drafted","awaiting_user_review","script_approved","narration_generated","mixed","quality_checked","complete")
SUMMARY=("任务目标","行动计划","救援行动失败","核心方案","唯一希望","计划启动","行动分成","这意味着","因此","开始行动","陷入危机")
DONE_STATUSES=("analyzed","drafted","reviewed","approved","complete")
def add(a,t,severity="error",**kw): a.append({"severity":severity,"type":t,**kw})
def n(v):
 try:return float(v)
 except (TypeError,ValueError):return None
def norm(v):return "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]",str(v))).lower()
def rows(v,k):return v if isinstance(v,list) else v.get(k,[]) if isinstance(v,dict) and isinstance(v.get(k),list) else []
def bounds(v):
 if not isinstance(v,dict):return None,None
 s=n(v.get("start",v.get("time")));return s,n(v.get("end",s))
def load(p,a,required=False):
 if not p.is_file():
  if required:add(a,"missing_artifact",path=str(p))
  return None
 try:return json.loads(p.read_text(encoding="utf-8-sig"))
 except Exception as e:add(a,"invalid_json",path=str(p),detail=str(e));return None
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ov(a,b,c,d):return max(0,min(b,d)-max(a,c))
def sim(a,b):
 a,b=norm(a),norm(b)
 if not a or not b:return 0
 aa={a[i:i+2] for i in range(max(1,len(a)-1))};bb={b[i:i+2] for i in range(max(1,len(b)-1))}
 return max(len(aa&bb)/len(aa|bb),difflib.SequenceMatcher(None,a,b).ratio())
def at(p,s):
 try:return STAGES.index(p.get("stage"))>=STAGES.index(s)
 except ValueError:return False
def title_on(p):
 v=(p.get("preferences") or {}).get("opening_credits",(p.get("preferences") or {}).get("titles_and_credits"))
 if isinstance(v,dict):v=v.get("scope")
 return v is True or isinstance(v,str) and v.lower() not in ("skip","skip_both","none","off","false")
def frames_ok(fs,s,e,d):
 if not isinstance(fs,list) or not fs:return False
 vv=[n(x) for x in fs]
 return not any(x is None for x in vv) and vv==sorted(vv) and (d is None or all(0<=x<=d for x in vv)) and s is not None and e is not None and all(s-1<=x<=e+1 for x in vv)
def clipped_coverage_gaps(intervals, start, end, threshold=90):
 if start is None or end is None or end <= start:return []
 clipped=[]
 for left,right in intervals:
  left=n(left);right=n(right)
  if left is None or right is None or right <= left:continue
  left=max(start,left);right=min(end,right)
  if right > left:clipped.append((left,right))
 clipped.sort()
 merged=[]
 for left,right in clipped:
  if not merged or left > merged[-1][1]:merged.append([left,right])
  else:merged[-1][1]=max(merged[-1][1],right)
 gaps=[];cursor=start
 for left,right in merged:
  if left-cursor>threshold:gaps.append((cursor,left))
  cursor=max(cursor,right)
 if end-cursor>threshold:gaps.append((cursor,end))
 return gaps

def review_scope(project):
 batch=project.get("current_review_batch") or {}
 start=n(batch.get("start"));end=n(batch.get("end"))
 return (start,end) if start is not None and end is not None and end > start else (None,None)
def parse_srt(path,a):
 try:text=path.read_text(encoding="utf-8-sig").replace("\r\n","\n")
 except Exception as e:add(a,"invalid_review_srt",detail=str(e));return []
 out=[]
 for block in re.split(r"\n{2,}",text.strip()):
  lines=block.splitlines()
  if len(lines)<3 or not lines[0].strip().isdigit() or " --> " not in lines[1]:add(a,"invalid_review_srt_block",block=block[:100]);continue
  def ts(v):
   m=re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})",v.strip())
   return None if not m else int(m[1])*3600+int(m[2])*60+int(m[3])+int(m[4])/1000
  left,right=lines[1].split(" --> ",1);out.append({"index":int(lines[0]),"start":ts(left),"end":ts(right),"text":"\n".join(lines[2:]).strip()})
 return out
def approval_ok(root,ref,script_version,script_hash,review_hash,a,kind):
 q=load(root/ref,a) if ref else None
 if not isinstance(q,dict):add(a,"invalid_approval_reference",approval_kind=kind,path=ref);return False
 missing=[f for f in ("script_version","script_sha256","review_srt_sha256","approved_at","user_message_ref","verbatim_user_approval") if not q.get(f)]
 if missing:add(a,"approval_missing_field",approval_kind=kind,path=ref,fields=missing);return False
 if q.get("script_version")!=script_version or q.get("script_sha256")!=script_hash or q.get("review_srt_sha256")!=review_hash:add(a,"approval_scope_mismatch",approval_kind=kind,path=ref);return False
 return True

def merge_intervals(pairs):
 merged=[]
 for left,right in sorted((x for x in pairs if x[0] is not None and x[1] is not None and x[1]>=x[0])):
  if not merged or left > merged[-1][1]+0.05:merged.append([left,right])
  else:merged[-1][1]=max(merged[-1][1],right)
 return merged

def audit(root, hash_cache=None):
 root=Path(root);a=[];p=load(root/"project.json",a,True) or {};trd=load(root/"timeline/transcript.json",a) or {};tr=rows(trd,"segments")
 audit_start,audit_end=review_scope(p)
 d=n(p.get("media_duration")) or n(p.get("duration")) or n(trd.get("duration"));sc=rows(load(root/"timeline/scenes.json",a,True) or {},"scenes")
 prev=0
 if not sc:add(a,"empty_scene_table")
 for i,x in enumerate(sc):
  s,e=bounds(x)
  if s is None or e is None or e<=s:add(a,"invalid_scene_bounds",scene=x.get("id"));continue
  if i and s<prev-1:add(a,"scene_overlap",scene=x.get("id"))
  if s>prev+2:add(a,"scene_timeline_gap",start=prev,end=s)
  prev=max(prev,e)
 if d is not None and prev<d-5:add(a,"incomplete_scene_coverage",scene_end=prev,media_duration=d)
 scene_durations=[n(x.get("end"))-n(x.get("start")) for x in sc if n(x.get("start")) is not None and n(x.get("end")) is not None]
 if scene_durations and sum(scene_durations)/len(scene_durations)<15:add(a,"scene_table_too_fine","warning",avg_seconds=round(sum(scene_durations)/len(scene_durations),1))
 bible={k:load(root/f"bible/{k}.json",a,True) for k in ("characters","locations","objects","story-state")}
 if all(x in (None,[],{}) for x in bible.values()):add(a,"all_bibles_empty")
 authorized_tools=set();manifest=load(root/"materials/manifest.json",a)
 cache=hash_cache if hash_cache is not None else None
 def digest(path):
  if cache is None:return sha(path)
  try:st=path.stat()
  except OSError:return None
  key=str(path.resolve());entry=cache.get(key)
  if entry and entry.get("mtime")==st.st_mtime_ns and entry.get("size")==st.st_size and entry.get("ctime")==st.st_ctime_ns and entry.get("sha256"):return entry["sha256"]
  value=sha(path);cache[key]={"sha256":value,"mtime":st.st_mtime_ns,"size":st.st_size,"ctime":st.st_ctime_ns};return value
 if not isinstance(manifest,dict):add(a,"missing_materials_manifest")
 else:
  artifacts=rows(manifest,"artifacts")
  if not artifacts:add(a,"empty_materials_manifest")
  if artifacts and not any(x.get("type") in ("source_media","video") for x in artifacts):add(a,"source_media_not_in_materials_manifest")
  for item in artifacts:
   missing=[f for f in ("id","type","path","sha256","provenance","trust_level","intended_use") if item.get(f) in (None,"")]
   if missing:add(a,"material_missing_fields",material=item.get("id"),fields=missing);continue
   target=root/item["path"]
   if not target.is_file():add(a,"material_file_missing",material=item.get("id"))
   elif digest(target)!=item["sha256"]:add(a,"material_hash_mismatch",material=item.get("id"))
   if item.get("type") in ("srt","subtitle") and item.get("replaces_full_asr") is True:
    checks=item.get("validation") or {}
    if not all(checks.get(x) is True for x in ("encoding_checked","duration_checked","sync_sampled","text_sampled")):add(a,"subtitle_not_validated_for_asr_replacement",material=item.get("id"))
   if item.get("type") in ("character_photo","costume_photo") and item.get("label") and not item.get("label_provenance"):add(a,"character_reference_label_without_provenance",material=item.get("id"))
   if item.get("type")=="authorized_project_tool" and item.get("path"):
    authorized_tools.add(str((root/item["path"]).resolve()).lower())
  for skip in rows(manifest,"skipped_steps"):
   if not skip.get("step") or not skip.get("replaced_by_material_ids") or not skip.get("reason"):add(a,"unjustified_skipped_analysis_step")
 visual_index=load(root/"timeline/visual-evidence.json",a);visual_by_id={}
 if not isinstance(visual_index,dict):add(a,"missing_visual_evidence_index")
 else:
  for item in rows(visual_index,"frames"):
   fid=str(item.get("id"));target=root/str(item.get("path",""))
   if any(item.get(f) in (None,"") for f in ("id","timestamp","path","sha256","source_media_id")):add(a,"visual_evidence_missing_fields",evidence=fid)
   elif not target.is_file():add(a,"visual_evidence_file_missing",evidence=fid)
   elif digest(target)!=item.get("sha256"):add(a,"visual_evidence_hash_mismatch",evidence=fid)
   visual_by_id[fid]=item
 characters=rows(bible.get("characters"),"characters")
 for c in characters:
  if not c.get("canonical_name"):continue
  for key,req in (("name_evidence",("type","start","end","source_text","observation_ids","evidence_frames","confidence")),("person_binding",("method","observation_ids","evidence_frames","confidence"))):
   es=c.get(key)
   if not isinstance(es,list) or not es:add(a,"character_identity_chain_incomplete",character=c.get("id"),field=key);continue
   for z in es:
    miss=[f for f in req if z.get(f) in (None,"",[])]
    if miss:add(a,"identity_evidence_missing_fields",character=c.get("id"),field=key,missing=miss)
  allow=n(c.get("narration_allowed_after"));name=n(c.get("first_naming_cue_time"));speech=n(c.get("first_spoken_line_time"))
  if allow is None:add(a,"missing_narration_reveal_time",character=c.get("id"))
  if name is not None and allow is not None and name<allow-.05:add(a,"character_named_before_reveal",character=c.get("id"))
 title_cues={};approval_refs=[]
 if title_on(p):
  inv=load(root/"timeline/title-credit-events.json",a)
  if not isinstance(inv,dict):add(a,"missing_title_credit_inventory")
  else:
   cr=inv.get("checked_ranges") or {};op=cr.get("opening");en=cr.get("ending")
   if not(isinstance(op,list) and len(op)==2 and n(op[0]) is not None):add(a,"opening_range_not_proven")
   if not(isinstance(en,list) and len(en)==2 and n(en[1]) is not None and d is not None and n(en[1])>=d-2):add(a,"ending_not_checked_to_final_frame")
   if not inv.get("inspection_evidence_frames"):add(a,"title_credit_inspection_without_evidence")
   if inv.get("scope") not in ("opening_and_principal_ending","opening_only","all_ending_cast","complete_ending_roll","user_selected","skip"):
    add(a,"invalid_title_credit_scope")
   raw=rows(inv,"raw_detections");evs=rows(inv,"events");ids={str(e.get("id")) for e in evs}
   if not raw and not inv.get("no_matching_events_evidence"):add(a,"unproven_empty_title_detection")
   for q in raw:
    if any(q.get(f) in (None,"",[]) for f in ("id","start","end","evidence_frames")):add(a,"raw_title_detection_missing_evidence",detection=q.get("id"))
    if str(q.get("event_id")) not in ids and not q.get("exclusion_reason"):add(a,"unaccounted_title_detection",detection=q.get("id"))
   for e in evs:
    s,z=bounds(e);miss=[f for f in ("id","type","start","end","visible_text","ocr_confidence","evidence_frames") if e.get(f) in (None,"",[])]
    if miss:add(a,"title_credit_event_missing_field",event=e.get("id"),missing=miss)
    if not frames_ok(e.get("evidence_frames"),s,z,d):add(a,"invalid_title_credit_evidence",event=e.get("id"))
    cs=e.get("cue_ids") or [];om=e.get("omission_approval")
    if not cs and not isinstance(om,dict):add(a,"title_credit_event_not_described",event=e.get("id"))
    if isinstance(om,dict):
     if any(om.get(f) in (None,"") for f in ("approval_record","script_version","reason")):add(a,"invalid_omission_approval",event=e.get("id"))
     else:approval_refs.append(om["approval_record"])
    for cid in cs:title_cues[str(cid)]=e
 dirs=sorted(x for x in (root/"segments").glob("segment-*") if x.is_dir()) if (root/"segments").is_dir() else []
 if not dirs:add(a,"no_segments")
 if (root/"segments").is_dir():
  for entry in (root/"segments").iterdir():
   if entry.is_dir() and not re.fullmatch(r"segment-\d+", entry.name):add(a,"nonstandard_segment_directory",segment=entry.name,hint="audit 与 merge 工具只发现 segment-NNN 目录；请改名（如 segment-001）或迁出该目录，否则其内容会被静默忽略")
 for directory in dirs:
  for path in directory.rglob("*"):
   if path.is_file() and path.suffix.lower() in (".py",".ps1",".sh",".bat",".cmd",".exe") and str(path.resolve()).lower() not in authorized_tools:
    add(a,"ad_hoc_segment_tool",segment=directory.name,path=str(path.relative_to(root)))
 obs={};seg_cues={};seg_cue_ids_by_dir={};done=[];stats=[];sigs={};segment_meta=[]
 for dr in dirs:
  m=load(dr/"manifest.json",a);oo=load(dr/"observations.json",a);cc=load(dr/"draft-cues.json",a)
  if None in (m,oo,cc):
   add(a,"incomplete_segment_directory",segment=dr.name);segment_meta.append({"name":dr.name,"start":None,"end":None,"complete":False,"credit_like":False});continue
  ol=rows(oo,"observations");cl=rows(cc,"cues");ss,se=bounds(m)
  segment_meta.append({"name":dr.name,"start":ss,"end":se,"complete":True,"credit_like":m.get("segment_type")=="title_credit" or (len(cl)>0 and sum(1 for c in cl if c.get("visual_event_type")=="title_credit")*2>=len(cl))})
  if ss is None or se is None or se<=ss:add(a,"invalid_segment_bounds",segment=dr.name);continue
  mins=(se-ss)/60
  if mins>15.5:add(a,"analysis_segment_too_coarse",segment=dr.name)
  if len(ol)<max(3,int(mins+.999)):add(a,"insufficient_observation_density",segment=dr.name)
  scope_start=max(ss,audit_start) if audit_start is not None else ss
  scope_end=min(se,audit_end) if audit_end is not None else se
  if scope_end > scope_start:
   for left,right in clipped_coverage_gaps((bounds(o) for o in ol),scope_start,scope_end):
    add(a,"unexplained_observation_gap",segment=dr.name,start=left,end=right)
  for o in ol:
   oid=str(o.get("id"));s,e=bounds(o);req=("id","start","end","subject","action","location","evidence_frames","evidence_type","sound_sufficient","confidence")
   miss=[f for f in req if o.get(f) in (None,"",[])]
   if miss:add(a,"observation_missing_fields",observation=oid,fields=miss)
   if oid in obs:add(a,"duplicate_observation_id",observation=oid)
   obs[oid]=o
   if not frames_ok(o.get("evidence_frames"),s,e,d):add(a,"invalid_observation_evidence_frames",observation=oid)
   evidence_ids=o.get("evidence_ids")
   if not isinstance(evidence_ids,list) or len(evidence_ids)!=len(o.get("evidence_frames") or []):add(a,"observation_evidence_index_mismatch",observation=oid)
   else:
    for eid,stamp in zip(evidence_ids,o.get("evidence_frames")):
     indexed=visual_by_id.get(str(eid))
     if not indexed or n(indexed.get("timestamp")) is None or abs(n(indexed["timestamp"])-n(stamp))>.05:add(a,"observation_evidence_unresolved",observation=oid,evidence=eid)
   sg=tuple(o.get("evidence_frames") or [])
   if sg in sigs:
    prev_subject,prev_action,prev_oid=sigs[sg]
    if norm(o.get("subject"))==norm(prev_subject) and norm(o.get("action"))!=norm(prev_action):add(a,"recycled_evidence_frames",observations=[prev_oid,oid])
   elif sg:sigs[sg]=(o.get("subject"),o.get("action"),oid)
   if o.get("sound_sufficient") is True:
    for f in ("visible_state","stability_reason","sound_conveys"):
     if not o.get(f):add(a,"insufficient_no_cue_coverage_record",observation=oid,field=f)
    if o.get("crosses_visual_event") is not False:add(a,"unbounded_no_cue_coverage_record",observation=oid)
  for c in cl:
   cid=str(c.get("id"));seg_cues[cid]=c;seg_cue_ids_by_dir.setdefault(dr.name,set()).add(cid);refs=c.get("observation_ids") or []
   if not refs:add(a,"cue_without_observation_reference",cue=cid)
   if any(str(x) not in obs for x in refs):add(a,"cue_references_unknown_observation",cue=cid)
   if any(obs.get(str(x),{}).get("sound_sufficient") is True for x in refs):add(a,"sound_sufficient_observation_generated_cue",cue=cid)
   fs=c.get("evidence_frames");start=n(c.get("start"))
   if not fs or start is None:add(a,"cue_without_evidence_frames",cue=cid)
   cue_eids=c.get("evidence_ids")
   if not isinstance(cue_eids,list) or any(str(x) not in visual_by_id for x in cue_eids):add(a,"cue_evidence_unresolved",cue=cid)
   if refs and cue_eids and not set(cue_eids).intersection(*(set(obs.get(str(x),{}).get("evidence_ids") or []) for x in refs if str(x) in obs)):add(a,"cue_evidence_not_from_observation",cue=cid)
   facts=c.get("atomic_facts")
   if not isinstance(facts,list) or not any(x.get("role")=="subject" and x.get("priority")=="required" for x in facts) or not any(x.get("role") in ("action","state") and x.get("priority")=="required" for x in facts):add(a,"cue_missing_required_atomic_facts",cue=cid)
  if m.get("status") in DONE_STATUSES:done.append((ss,se))
  stats.append({"segment":dr.name,"observations_per_minute":len(ol)/mins,"average_cue_characters":sum(len(norm(c.get("text",""))) for c in cl)/len(cl) if cl else 0,"credit_like":segment_meta[-1]["credit_like"]})
 merged_path=root/"script/merged-draft.json";merged=load(merged_path,a)
 merged_cues=rows(merged,"cues") if isinstance(merged,dict) else []
 script_cues={str(c.get("id")):c for c in merged_cues} if merged_cues else seg_cues
 ordered=sorted(script_cues.values(),key=lambda x:n(x.get("start")) or 0)
 for c in ordered:
  text=str(c.get("text",""));start=n(c.get("start"));near=[str(x.get("text","")) for x in tr if start is not None and n(x.get("start")) is not None and start-30<=n(x["start"])<=start+30]
  score=max((sim(text,x) for x in near),default=0)
  if len(norm(text))>=6 and score>=.72:add(a,"suspected_dialogue_restatement",cue=c.get("id"),score=round(score,3))
  if any(x in text for x in SUMMARY) or len(norm(text))>48:add(a,"possible_plot_summary","warning",cue=c.get("id"))
  event=n(c.get("visual_event_time"));disp=n(c.get("temporal_displacement"))
  if event is None or disp is None or start is None or abs((start-event)-disp)>.15:add(a,"invalid_temporal_displacement",cue=c.get("id"))
  else:
   kind=c.get("visual_event_type","action");limit=15 if kind in ("location_change","title_credit") else 5
   if abs(disp)>limit and not c.get("displacement_justification"):add(a,"cue_too_far_from_visual_event",cue=c.get("id"),seconds=disp)
 for i,c in enumerate(ordered):
  st=n(c.get("start")) or 0;win=[x for x in ordered[i:i+5] if (n(x.get("start")) or 0)-st<=60]
  if len(win)>=2 and sum(any(t in str(x.get("text","")) for t in SUMMARY) for x in win)>=2:add(a,"distributed_plot_summary",cue_ids=[x.get("id") for x in win])
 if stats:
  narrative=[x for x in stats if not x["credit_like"]]
  if len(narrative)>=2:
   baseline=sorted(x["observations_per_minute"] for x in narrative)[len(narrative)//2]
   for x in narrative:
    if x["observations_per_minute"]<baseline*.55:add(a,"possible_summary_drift",segment=x["segment"],baseline=round(baseline,2),rate=round(x["observations_per_minute"],2))
 if audit_start is None or audit_end is None:
  if done:audit_start=min(x[0] for x in done);audit_end=max(x[1] for x in done)
  elif d is not None:audit_start,audit_end=0,d
 coverage_scenes=[x for x in sc if audit_start is not None and audit_end is not None and bounds(x)[0] is not None and bounds(x)[1] is not None and bounds(x)[0]<audit_end and bounds(x)[1]>audit_start]
 scoped_observations=[o for o in obs.values() if audit_start is not None and audit_end is not None and bounds(o)[0] is not None and bounds(o)[1] is not None and bounds(o)[0]<audit_end and bounds(o)[1]>audit_start]
 for x in coverage_scenes:
  s,e=bounds(x)
  clipped_start=max(s,audit_start);clipped_end=min(e,audit_end)
  if not any(bounds(o)[0]<clipped_end and bounds(o)[1]>clipped_start for o in scoped_observations):add(a,"scene_without_observation_coverage",scene=x.get("id"),audit_start=clipped_start,audit_end=clipped_end)
 no_cue=[o for o in obs.values() if o.get("sound_sufficient") is True]
 boilerplate={norm(o.get("visible_state"))+"|"+norm(o.get("stability_reason"))+"|"+norm(o.get("sound_conveys")) for o in no_cue}
 if len(no_cue)>=3 and len(boilerplate)<=max(1,len(no_cue)//3):add(a,"boilerplate_no_cue_coverage",records=len(no_cue),unique=len(boilerplate))
 for cid,e in title_cues.items():
  c=script_cues.get(cid)
  if not c:add(a,"title_credit_cue_missing",cue=cid);continue
  cs=n(c.get("start"));ce=cs+(n(c.get("duration")) or n(c.get("review_duration")) or .1) if cs is not None else None;es,ee=bounds(e)
  if cs is None or (not ov(cs,ce,es,ee) and abs(cs-es)>5):add(a,"title_credit_cue_time_mismatch",cue=cid)
  if norm(e.get("visible_text")) not in norm(c.get("text")):add(a,"title_credit_cue_text_mismatch",cue=cid)
  if not set(c.get("evidence_frames") or [])&set(e.get("evidence_frames") or []):add(a,"title_credit_cue_evidence_mismatch",cue=cid)
 if done and not isinstance(merged,dict):add(a,"missing_merged_draft")
 elif done:
  cv=merged.get("coverage") or {};actual=(n(cv.get("start")),n(cv.get("end")));exp=(min(x[0] for x in done),max(x[1] for x in done))
  if None in actual or actual[0]>exp[0]+1 or actual[1]<exp[1]-1:add(a,"merged_coverage_incomplete",expected=exp,actual=actual)
 review_srt=root/"script/review.srt";review_map=load(root/"script/review-map.json",a)
 if at(p,"awaiting_user_review") or at(p,"script_approved"):
  if merged_cues:
   seg_ids=set(seg_cues)
   seen=set()
   for c in merged_cues:
    cid=str(c.get("id"))
    if cid in seen:add(a,"duplicate_merged_cue_id",cue=cid)
    seen.add(cid)
    derivation=(c.get("derivation") or {})
    src=str(derivation.get("cue_id") or "")
    seg=str(derivation.get("segment") or "")
    if src!=cid or seg not in seg_cue_ids_by_dir or src not in seg_cue_ids_by_dir.get(seg,set()):add(a,"merged_cue_provenance_broken",cue=cid,segment=seg,derivation_cue_id=src,hint="每条 merged cue 的 derivation 必须为 {segment: 所属分段目录, cue_id: 自身 id}，且该 id 能在该分段 draft-cues.json 中找到；分段重跑 finalize 后请重跑 merge_draft.py")
   for cid in seg_ids:
    if cid not in seen:add(a,"merged_missing_segment_cue",cue=cid,hint="分段 cue 未进入合并稿；请重跑 merge_draft.py 或检查该 cue 是否在合并时被误删")
   for x,y in zip(ordered,ordered[1:]):
    xs=n(x.get("start"));xe=xs+(n(x.get("duration")) or n(x.get("review_duration")) or 0) if xs is not None else None;ys=n(y.get("start"))
    if xs is not None and xe is not None and ys is not None and ys<xe-.01:add(a,"merged_cue_overlap",cues=[x.get("id"),y.get("id")],overlap_seconds=round(xe-ys,3))
  if not review_srt.is_file():add(a,"missing_review_srt")
  if not isinstance(review_map,dict):add(a,"missing_review_map")
  if review_srt.is_file() and isinstance(review_map,dict):
   sr=parse_srt(review_srt,a);mp=rows(review_map,"entries")
   if review_map.get("script_version")!=p.get("script_version"):add(a,"review_map_version_mismatch",map_version=review_map.get("script_version"),project_version=p.get("script_version"),hint="review-map.json 的 script_version 必须与 project.json 的 script_version 一致；改稿后重跑 render_review_srt.py")
   if len(sr)!=len(mp) or len(sr)!=len(ordered):add(a,"review_srt_count_mismatch",srt=len(sr),map=len(mp),cues=len(ordered),hint="review.srt、review-map.json 与合并稿 cue 数量必须一致；合并稿改动后重跑 render_review_srt.py")
   for index,(srow,mrow,cue) in enumerate(zip(sr,mp,ordered),1):
    if srow["index"]!=index or mrow.get("srt_index")!=index:add(a,"review_srt_index_mismatch",index=index)
    if str(mrow.get("cue_id"))!=str(cue.get("id")) or srow["text"]!=str(cue.get("text","")).strip() or mrow.get("text")!=srow["text"]:add(a,"review_srt_text_or_id_mismatch",index=index,hint="改合并稿后必须重跑 render_review_srt.py 重新生成 review.srt 与 review-map.json")
    if srow["start"] is None or srow["end"] is None or abs(srow["start"]-(n(cue.get("start")) or 0))>.002 or abs((mrow.get("start") or 0)-srow["start"])>.002 or abs((mrow.get("end") or 0)-srow["end"])>.002:add(a,"review_srt_timing_mismatch",index=index)
  batch=p.get("current_review_batch") or {};batch_start=n(batch.get("start"));batch_end=n(batch.get("end"))
  convergence=load(root/"qc/identity-convergence.json",a)
  if batch_start is None or batch_end is None:add(a,"missing_current_review_range",hint="awaiting_user_review 阶段的 project.json 必须带 current_review_batch.start/end")
  if not isinstance(convergence,dict):add(a,"missing_identity_convergence_report")
  else:
   cr=convergence.get("review_range") or {};blocks=convergence.get("review_ranges")
   conv_ranges=([(n(x.get("start")),n(x.get("end"))) for x in blocks] if isinstance(blocks,list) and blocks else [(n(cr.get("start")),n(cr.get("end")))] if n(cr.get("start")) is not None else [])
   union=merge_intervals(conv_ranges)
   holes=[(a[1],b[0]) for a,b in zip(union,union[1:]) if b[0]-a[1]>.05]
   if batch_start is not None and batch_end is not None and (not union or union[0][0]>batch_start+.05 or union[-1][1]<batch_end-.05 or holes):
    add(a,"identity_convergence_range_mismatch",batch=[batch_start,batch_end],convergence=union,holes=holes,hint="收敛报告的 review_range（或 review_ranges 并集）必须连续且首尾对齐 current_review_batch（容差 0.05 秒），中间不得留空洞")
   covered=set()
   for entry in rows(convergence,"characters"):
    cid=str(entry.get("character_id"));covered.add(cid);status=entry.get("resolution_status")
    if not cid or status not in ("confirmed","not_yet_revealed","unresolved_after_evidence_review"):add(a,"invalid_identity_resolution",character=cid)
    if not entry.get("evidence_sources_checked"):add(a,"identity_resolution_without_evidence_review",character=cid)
    if status=="unresolved_after_evidence_review" and (not entry.get("unresolved_reason") or not entry.get("uncertainty_item_id")):add(a,"unresolved_identity_not_exposed",character=cid)
   for c in characters:
    cid=str(c.get("id") or c.get("provisional_id") or "")
    first=n(c.get("first_visual_appearance"))
    if cid and batch_end is not None and first is not None and batch_start<=first<=batch_end and cid not in covered:add(a,"batch_character_missing_identity_resolution",character=cid)
  keys={};safe_keys={}
  for c in characters:
   cid=str(c.get("id") or c.get("provisional_id") or "")
   if c.get("provisional_id"):add(a,"provisional_character_in_review_bible",character=cid)
   if cid:
    if cid in keys:add(a,"duplicate_character_record",character=cid)
    keys[cid]=c
   safe=norm(c.get("safe_label"))
   if safe:
    if safe in safe_keys and not c.get("distinct_person_evidence"):add(a,"duplicate_character_safe_label",characters=[safe_keys[safe],cid],safe_label=c.get("safe_label"))
    else:safe_keys[safe]=cid
  for cid,c in keys.items():
   canonical=c.get("canonical_name");allowed=n(c.get("narration_allowed_after"));safe=str(c.get("safe_label") or "")
   related=[cue for cue in script_cues.values() if cid in [str(x) for x in cue.get("subject_character_ids",[])]]
   if not related and any(safe and safe in str(cue.get("text","")) or canonical and canonical in str(cue.get("text","")) for cue in script_cues.values()):add(a,"character_cue_missing_canonical_id",character=cid)
   if canonical and allowed is not None and safe:
    for cue in related:
     if n(cue.get("visual_event_time")) is not None and n(cue.get("visual_event_time"))>=allowed and safe in str(cue.get("text","")):add(a,"obsolete_neutral_label_after_identity_reveal",character=cid,cue=cue.get("id"))
   for variant in c.get("label_variants") or []:
    v=norm(variant)
    if not v:continue
    for cue in script_cues.values():
     if v and v in norm(cue.get("text","")) and (not canonical or v not in norm(canonical)):
      if cid in [str(x) for x in cue.get("subject_character_ids",[])]:
       add(a,"cue_contains_label_variant","warning",character=cid,cue=cue.get("id"),variant=variant,hint="该 cue 文本仍含人物变体标签；收敛时应由 converge_identities.py 的掩码替换算法改写")
      else:
       add(a,"cue_contains_label_variant","warning",character=cid,cue=cue.get("id"),variant=variant,hint="该 cue 未引用此人物但文本含其变体；请检查 subject_character_ids 是否漏写，或该变体实际属于其他人物")
  for cue in script_cues.values():
   for x in cue.get("subject_character_ids") or []:
    if str(x) not in keys:add(a,"cue_references_unknown_character",cue=cue.get("id"),character=x,hint="cue 的 subject_character_ids 必须引用收敛后的 canonical id；provisional_id 不能留在审阅稿")
  if p.get("stage")=="awaiting_user_review" and batch_end is not None:
   for item in segment_meta:
    if not item["complete"] or item["start"] is not None and item["start"]>=batch_end-.05:add(a,"future_segment_started_during_review",segment=item["name"])
 appr=load(root/"script/approved.json",a)
 if at(p,"script_approved") or p.get("approved_script_version") is not None or approval_refs:
  if not isinstance(appr,dict):add(a,"missing_approval_record")
  else:
   for f in ("script_version","script_sha256","review_srt_sha256","approved_at","user_message_ref","verbatim_user_approval"):
    if not appr.get(f):add(a,"approval_missing_field",field=f)
   if merged_path.is_file() and appr.get("script_sha256")!=sha(merged_path):add(a,"approved_script_hash_mismatch")
   if review_srt.is_file() and appr.get("review_srt_sha256")!=sha(review_srt):add(a,"approved_review_srt_hash_mismatch")
   if appr.get("script_version")!=p.get("approved_script_version"):add(a,"approval_version_mismatch")
 if p.get("stage")=="awaiting_user_review" and p.get("approved_script_version")==p.get("script_version"):add(a,"approval_state_contradiction")
 merged_hash=sha(merged_path) if merged_path.is_file() else None;review_hash=sha(review_srt) if review_srt.is_file() else None
 for ref in approval_refs:approval_ok(root,ref,p.get("script_version"),merged_hash,review_hash,a,"omission")
 if (p.get("preferences") or {}).get("character_naming")=="first_speech_once":
  cue_refs={}
  for cue in script_cues.values():
   for x in cue.get("subject_character_ids") or []:cue_refs[str(x)]=cue_refs.get(str(x),0)+1
  for c in characters:
   cid=str(c.get("id") or c.get("provisional_id") or "")
   speech=n(c.get("first_spoken_line_time"));allow=n(c.get("narration_allowed_after"));name=n(c.get("first_naming_cue_time"))
   if speech is not None and allow is not None and speech>=allow and (name is None or name>=speech):add(a,"character_not_named_before_first_speech",character=cid)
  if at(p,"awaiting_user_review") or at(p,"script_approved"):
   for c in characters:
    cid=str(c.get("id") or c.get("provisional_id") or "")
    speech=n(c.get("first_spoken_line_time"));name=n(c.get("first_naming_cue_time"))
    principal=c.get("canonical_name") or cue_refs.get(cid,0)>=3 or name is not None
    if principal and speech is None:
     reviewed=c.get("speech_evidence_reviewed")
     if not isinstance(reviewed,dict) or not reviewed.get("evidence_sources_checked"):
      add(a,"character_speech_timing_unestablished",character=cid,hint="first_speech_once 模式下主要人物必须建立 first_spoken_line_time；无法绑定时附 speech_evidence_reviewed 记录（含 evidence_sources_checked）或登记 uncertainty 条目，不得静默省略")
    elif not principal and speech is None and c.get("safe_label"):add(a,"character_speech_omitted_unverified","warning",character=cid)
 dialogue=rows(load(root/"timeline/dialogue-events.json",a) or {},"events");listen=set()
 if at(p,"narration_generated"):
  if not dialogue:add(a,"missing_dialogue_timeline")
  for q in dialogue:
   if any(q.get(f) in (None,"",[]) for f in ("id","start","end","provenance","source_ids")):add(a,"dialogue_event_missing_provenance",dialogue=q.get("id"))
   if q.get("protected") is True and not q.get("protection_reason"):add(a,"protected_dialogue_missing_reason",dialogue=q.get("id"))
  for cid,c in script_cues.items():
   audio=c.get("audio_path");s=n(c.get("audible_start"));e=n(c.get("audible_end"));md=n(c.get("measured_duration"))
   if not audio or not(root/audio).is_file() or s is None or e is None or md is None or e<=s or abs(e-s-md)>.2:add(a,"missing_or_invalid_rendered_cue_timing",cue=cid);continue
   inter=[]
   for q in dialogue:
    ds,de=bounds(q)
    if ds is None or de is None:continue
    amount=ov(s,e,ds,de)
    if amount:inter.append(q.get("id"))
    if amount or min(abs(s-de),abs(e-ds))<=1:listen.add(cid)
    if amount and q.get("protected") is True:
     ref=c.get("protected_overlap_approval")
     if not approval_ok(root,ref,p.get("script_version"),merged_hash,review_hash,a,"protected_overlap"):add(a,"protected_dialogue_overlap",cue=cid,dialogue=q.get("id"))
   if inter and not c.get("computed_dialogue_overlaps"):add(a,"undeclared_computed_dialogue_overlap",cue=cid)
   if inter and not c.get("placement_attempts"):add(a,"overlap_without_prior_placement_attempts",cue=cid)
   mt=re.match(r"\+(\d+(?:\.\d+)?)%",str(c.get("rate","")))
   if mt and float(mt.group(1))>25:listen.add(cid)
   if re.search(r"[0-9一二三四五六七八九十百千万亿]{2,}",str(c.get("text",""))):listen.add(cid)
 if at(p,"mixed"):
  entries=rows(load(root/"qc/duck-envelope.json",a) or {},"entries");by={str(x.get("cue_id")):x for x in entries}
  for cid in script_cues:
   x=by.get(cid)
   if not x:add(a,"missing_duck_envelope_entry",cue=cid);continue
   vv=[n(x.get(f)) for f in ("duck_start","narration_audible_start","narration_audible_end","duck_end","unity_restored_at")]
   if any(v is None for v in vv) or vv!=sorted(vv):add(a,"invalid_duck_envelope_entry",cue=cid)
   elif vv[4]-vv[2]>2:add(a,"duck_release_too_long",cue=cid)
  ee=sorted(entries,key=lambda x:n(x.get("duck_start")) or 0)
  for x,y in zip(ee,ee[1:]):
   if n(x.get("unity_restored_at")) is not None and n(y.get("duck_start")) is not None and n(x["unity_restored_at"])>n(y["duck_start"]) and n(x.get("narration_audible_end"))<n(y.get("narration_audible_start")):add(a,"continuous_ducking_between_cues",cues=[x.get("cue_id"),y.get("cue_id")])
 if at(p,"quality_checked"):
  lr=load(root/"qc/listening-review.json",a) or {};reviewed={str(x.get("cue_id")):x for x in rows(lr,"reviews") if x.get("result")=="pass" and x.get("reviewer") and x.get("interval")}
  for cid in listen:
   if cid not in reviewed:add(a,"required_listening_incomplete",cue=cid)
  if lr.get("reviewer_kind")=="producing_model":add(a,"self_attested_listening_review")
  if lr.get("all_required_items_complete") is not True:add(a,"listening_review_not_closed")
  final=load(root/"qc/final-report.json",a)
  if not isinstance(final,dict):add(a,"missing_final_audio_measurements")
  else:
   required=("source_sha256","output_sha256","method","tolerance_db","non_narration_samples","narration_presence_samples","source_under_narration_samples")
   missing=[f for f in required if final.get(f) in (None,"",[])]
   if missing:add(a,"final_audio_measurements_incomplete",fields=missing)
 errors=[x for x in a if x["severity"]=="error"]
 return {"schema_version":3,"project":str(root),"passed":not errors,"summary":{"errors":len(errors),"warnings":len(a)-len(errors),"segments":len(dirs),"observations":len(obs),"cues":len(script_cues)},"segment_stats":stats,"issues":a}
def main():
 p=argparse.ArgumentParser();p.add_argument("project_dir");p.add_argument("--report");x=p.parse_args();root=Path(x.project_dir).resolve()
 cache_path=root/"qc/hash-cache.json";cache={}
 if cache_path.is_file():
  try:cache=json.loads(cache_path.read_text(encoding="utf-8-sig")).get("entries") or {}
  except Exception:cache={}
 before=json.dumps(cache,sort_keys=True)
 r=audit(root,cache)
 if json.dumps(cache,sort_keys=True)!=before:
  cache_path.parent.mkdir(parents=True,exist_ok=True)
  cache_path.write_text(json.dumps({"schema_version":1,"entries":cache},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 out=json.dumps(r,ensure_ascii=False,indent=2)+"\n"
 if x.report:Path(x.report).write_text(out,encoding="utf-8")
 for stream in (sys.stdout,sys.stderr):
  if hasattr(stream,"reconfigure"):
   try:stream.reconfigure(encoding="utf-8")
   except Exception:pass
 print(out,end="");return 0 if r["passed"] else 1
if __name__=="__main__":sys.exit(main())
