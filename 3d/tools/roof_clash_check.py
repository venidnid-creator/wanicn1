# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ตรวจโครงหลังคาไม่ให้ชิ้นส่วนกินกัน: python3 tools/roof_clash_check.py hip|gable|manila
(SAT on each member mesh; prints the pairs that overlap more than 4 mm — none expected)."""
import sys, math, itertools, collections
sys.path.insert(0,'.')
from core import wanic_building as B, wanic_rc as R
roof = sys.argv[1] if len(sys.argv) > 1 else "hip"
d=B.default_data(); R.apply_grid(d,[4.0,4.0],[4.0,3.0],1); d["settings"]["roof"]=roof
groups,count=B.roof_members(d)
KEEP=("จันทัน","ตะเฆ่สัน","อกไก่","อะเส","ขื่อ","คานรับดั้ง","ดั้ง","ตุ๊กตา","ค้ำยัน","แป","เพลท","ตะเฆ่ราง")
def data(g):
    vs=[(v.position.x(),v.position.y(),v.position.z()) for v in g.mesh.vertices]
    ns=set(); es=set()
    for f in g.mesh.faces:
        pts=[(p.x(),p.y(),p.z()) for p in (getattr(f,"positions",None) or [getattr(v,"position",v) for v in f.vertices])]
        if not pts or len(pts)<3: continue
        a,b,c=pts[0],pts[1],pts[2]
        u=[b[i]-a[i] for i in range(3)]; w=[c[i]-a[i] for i in range(3)]
        n=[u[1]*w[2]-u[2]*w[1],u[2]*w[0]-u[0]*w[2],u[0]*w[1]-u[1]*w[0]]
        L=math.sqrt(sum(x*x for x in n))
        if L<1e-12: continue
        n=tuple(round(x/L,3) for x in n)
        if n[0]<0 or (n[0]==0 and (n[1]<0 or (n[1]==0 and n[2]<0))): n=tuple(-x for x in n)
        ns.add(n)
        for p,q in zip(pts,pts[1:]+pts[:1]):
            e=[q[i]-p[i] for i in range(3)]; L=math.sqrt(sum(x*x for x in e))
            if L<1e-9: continue
            e=tuple(round(x/L,3) for x in e)
            if e[0]<0 or (e[0]==0 and (e[1]<0 or (e[1]==0 and e[2]<0))): e=tuple(-x for x in e)
            es.add(e)
    return vs,ns,es
items=[]
for g in groups:
    k=g.name.split(' ')[0]
    if k in KEEP: items.append((k,g.name,)+data(g))
def proj(vs,ax): 
    ps=[sum(v[i]*ax[i] for i in range(3)) for v in vs]; return min(ps),max(ps)
def clash(A,Bb,tol=0.004):
    va,na,ea=A; vb,nb,eb=Bb
    axes=list(na|nb)
    for e1 in list(ea)[:12]:
        for e2 in list(eb)[:12]:
            c=(e1[1]*e2[2]-e1[2]*e2[1],e1[2]*e2[0]-e1[0]*e2[2],e1[0]*e2[1]-e1[1]*e2[0])
            L=math.sqrt(sum(x*x for x in c))
            if L>1e-6: axes.append(tuple(x/L for x in c))
    depth=1e9; best=None
    for ax in axes:
        a0,a1=proj(va,ax); b0,b1=proj(vb,ax)
        ov=min(a1,b1)-max(a0,b0)
        if ov<=tol: return 0.0
        if ov<depth: depth,best=ov,ax
    global LASTAX; LASTAX=tuple(round(x,2) for x in best)
    return depth
res=collections.Counter(); ex={}
for (ka,na_,*A),(kb,nb_,*Bb) in itertools.combinations(items,2):
    if ka==kb=="แป": continue
    dep=clash(A,Bb)
    if dep>0.004:
        key=tuple(sorted((ka,kb))); res[key]+=1; ex.setdefault(key,(na_,nb_,round(dep,3),LASTAX))
for k,v in res.most_common(): print(k,v,ex[k])
