"""Beam Designer: offline Tkinter calculator for simply supported/cantilever beams.

Steel shape data source: AISC Shapes Database v15.0 (US units), as referenced
by the original index.html prototype. Educational use only; not for design of record.
"""
import csv
import json
import math
import os
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SHAPES = list(csv.DictReader((ROOT / "01_data" / "steel_w_shapes.csv").open()))
for _s in SHAPES:
    # CSV fields carry units; keep short names inside the calculation/UI code.
    for old, new in (("A_in2","A"),("d_in","d"),("bf_in","bf"),("tw_in","tw"),("tf_in","tf"),("Ix_in4","Ix"),("Sx_in3","Sx"),("Zx_in3","Zx")):
        _s[new] = float(_s.pop(old))
    for _k in _s:
        if _k != "designation": _s[_k] = float(_s[_k])
BY_NAME = {s["designation"]: s for s in SHAPES}
NAVY, BLUE, TEAL, PURPLE, ORANGE = "#1f3a5f", "#2f6fb3", "#178a8a", "#7e57c2", "#e0832a"


def validate_design(data):
    """Validate and normalize a saved design before applying it to the form."""
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("Unsupported or invalid beam design file.")

    def number(value, name):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number.")
        return value

    try:
        support = data["support"]
        shape = data["shape"]
        grade = data["grade"]
        span = number(data["span"], "Span")
        fy = number(data["fy"], "Fy")
        limit = number(data["limit"], "Deflection limit")
        self_weight = data["self_weight"]
        points = data["points"]
        uniforms = data["uniforms"]
        if support not in ("Simply supported", "Cantilever (fixed left)"):
            raise ValueError("Unknown support type.")
        if not isinstance(shape, str) or shape not in BY_NAME:
            raise ValueError("Unknown steel section.")
        if grade not in ("A992", "A36", "Custom Fy"):
            raise ValueError("Unknown steel grade.")
        if not 0 < span <= 500 or fy <= 0 or limit <= 0:
            raise ValueError("Span, Fy, and deflection limit must be positive; span must not exceed 500 ft.")
        if not isinstance(self_weight, bool) or not isinstance(points, list) or not isinstance(uniforms, list):
            raise ValueError("Invalid self-weight or load list.")
        clean_points = []
        for p in points:
            x, magnitude = number(p["x"], "Point position"), number(p["P"], "Point load")
            if p["type"] not in ("Dead", "Live") or not 0 <= x <= span or magnitude < 0:
                raise ValueError("Invalid point load.")
            clean_points.append({"x": x, "P": magnitude, "type": p["type"]})
        clean_uniforms = []
        for u in uniforms:
            a, b, magnitude = number(u["a"], "Uniform start"), number(u["b"], "Uniform end"), number(u["w"], "Uniform load")
            if u["type"] not in ("Dead", "Live") or not 0 <= a < b <= span or magnitude < 0:
                raise ValueError("Invalid uniform load.")
            clean_uniforms.append({"a": a, "b": b, "w": magnitude, "type": u["type"]})
        return {"version": 1, "support": support, "span": span, "shape": shape,
                "grade": grade, "fy": fy, "limit": limit, "self_weight": self_weight,
                "points": clean_points, "uniforms": clean_uniforms}
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError("Beam design file is missing a field or contains an invalid value.") from exc


def analyze(support, L, points, uniforms, E=29000, I=1):
    total = sum(p["P"] for p in points) + sum(u["w"]*(u["b"]-u["a"]) for u in uniforms)
    moment = sum(p["P"]*p["x"] for p in points) + sum(u["w"]*(u["b"]-u["a"])*(u["a"]+u["b"])/2 for u in uniforms)
    rb = moment/L if support == "Simply supported" else 0.0
    ra = total-rb
    m0 = 0.0 if support == "Simply supported" else -moment
    def v(x, side=1):
        value = (ra if (x > 0 if side < 0 else x >= 0) else 0)
        if support == "Simply supported" and (x > L if side < 0 else x >= L): value += rb
        for p in points:
            if x > p["x"] if side < 0 else x >= p["x"]: value -= p["P"]
        for u in uniforms: value -= u["w"]*max(0, min(x,u["b"])-u["a"])
        return value
    def br(x,a): return max(0.0,x-a)
    def m(x): return m0+ra*x-sum(p["P"]*br(x,p["x"]) for p in points)-sum(u["w"]*(br(x,u["a"])**2-br(x,u["b"])**2)/2 for u in uniforms)
    def eiy(x): return m0*x*x/2+ra*x**3/6-sum(p["P"]*br(x,p["x"])**3/6 for p in points)-sum(u["w"]*(br(x,u["a"])**4-br(x,u["b"])**4)/24 for u in uniforms)
    c1 = -eiy(L)/L if support == "Simply supported" else 0
    def d(x, E, I): return -(eiy(x)+c1*x)*1728/(E*I)
    xs = sorted(set([0.0,L]+[p["x"] for p in points]+[q for u in uniforms for q in (u["a"],u["b"])]))
    for a,b in zip(xs,xs[1:]):
        va,vb=v(a,1),v(b,-1)
        if va*vb < 0: xs.append(a+(b-a)*va/(va-vb))
    xs=sorted(set(xs))
    vmax=max(((abs(v(x,s)),x,v(x,s)) for x in xs for s in (-1,1)),default=(0,0,0))
    mmax=max(((abs(m(x)),x,m(x)) for x in xs),default=(0,0,0))
    n=1200; ix=max(range(n+1),key=lambda i:abs(d(L*i/n,E,I)))
    lo=max(0,ix-2)*L/n; hi=min(n,ix+2)*L/n
    for _ in range(45):
        a=lo+(hi-lo)/3; b=hi-(hi-lo)/3
        if abs(d(a,E,I)) < abs(d(b,E,I)): lo=a
        else: hi=b
    dx=(lo+hi)/2
    return {"RA":ra,"RB":rb,"M0":m0,"V":v,"M":m,"d":d,"vmax":vmax,"mmax":mmax,"dmax":(abs(d(dx,E,I)),dx)}


class BeamDesigner(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Beam Designer | ASD")
        self.geometry("1320x920"); self.minsize(1050,720); self.configure(bg="#f3f5f8")
        self.points=[]; self.uniforms=[]; self.point_rows=[]; self.uniform_rows=[]
        self.design_path = None
        menu = tk.Menu(self); file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Open…", command=self.open_design)
        file_menu.add_command(label="Save", command=self.save_design)
        file_menu.add_command(label="Save As…", command=lambda: self.save_design(save_as=True))
        menu.add_cascade(label="File", menu=file_menu); self.config(menu=menu)
        self._style(); self._build(); self.reset()

    def _style(self):
        st=ttk.Style(self); st.theme_use("clam")
        st.configure("TFrame",background="#f3f5f8"); st.configure("Card.TFrame",background="white")
        st.configure("TLabel",background="#f3f5f8",foreground="#1d2733",font=("TkDefaultFont",10))
        st.configure("Title.TLabel",background=NAVY,foreground="white",font=("TkDefaultFont",16,"bold"))
        st.configure("Muted.TLabel",background="white",foreground="#64707d")
        st.configure("Section.TLabel",background="white",foreground="#64707d",font=("TkDefaultFont",10,"bold"))
        st.configure("TButton",padding=6)

    def _build(self):
        header=ttk.Frame(self,padding=(18,12),style="Card.TFrame"); header.pack(fill="x")
        ttk.Label(header,text="BEAM DESIGNER",style="Title.TLabel").pack(side="left")
        self.status=ttk.Label(header,text="Shear · moment · deflection  |  Steel W-shapes · ASD",style="Title.TLabel"); self.status.pack(side="left",padx=20)
        body=ttk.Frame(self,padding=12);body.pack(fill="both",expand=True)
        left=ttk.Frame(body,width=360);left.pack(side="left",fill="y",padx=(0,10));left.pack_propagate(False)
        right=ttk.Frame(body);right.pack(side="left",fill="both",expand=True)
        self.canvas=tk.Canvas(left,bg="white",highlightthickness=0); scroll=ttk.Scrollbar(left,orient="vertical",command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set);scroll.pack(side="right",fill="y");self.canvas.pack(side="left",fill="both",expand=True)
        self.form=ttk.Frame(self.canvas,padding=14,style="Card.TFrame");self.form_win=self.canvas.create_window((0,0),window=self.form,anchor="nw")
        self.form.bind("<Configure>",lambda e:self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",lambda e:self.canvas.itemconfigure(self.form_win,width=e.width))
        self._inputs()
        self.chart=tk.Canvas(right,bg="white",height=490,highlightthickness=0);self.chart.pack(fill="x",expand=False)
        self.chart.bind("<Configure>",lambda e:self.draw())
        self.summary=ttk.Frame(right,padding=10,style="Card.TFrame");self.summary.pack(fill="x",pady=10)
        self.summary_text=ttk.Label(self.summary,text="",style="Muted.TLabel",justify="left")
        self.summary_text.pack(anchor="w")
        self.checks=ttk.Frame(right,padding=12,style="Card.TFrame");self.checks.pack(fill="x")
        self.notes=ttk.Label(right,text="",wraplength=850,justify="left",style="Muted.TLabel");self.notes.pack(fill="x",pady=12)

    def field(self,parent,label,var,values=None):
        ttk.Label(parent,text=label,style="Muted.TLabel").pack(anchor="w",pady=(5,2))
        w=ttk.Combobox(parent,textvariable=var,values=values,state="readonly") if values else ttk.Entry(parent,textvariable=var)
        w.pack(fill="x"); w.bind("<<ComboboxSelected>>",lambda e:self.update());w.bind("<KeyRelease>",lambda e:self.update());return w

    def _inputs(self):
        f=self.form
        ttk.Label(f,text="BEAM",style="Section.TLabel").pack(anchor="w")
        self.support=tk.StringVar();self.field(f,"Support",self.support,["Simply supported","Cantilever (fixed left)"])
        self.span=tk.StringVar();self.field(f,"Span (ft)",self.span)
        ttk.Label(f,text="SECTION",style="Section.TLabel").pack(anchor="w",pady=(12,0))
        self.shape=tk.StringVar();self.field(f,"Steel W-shape",self.shape,list(BY_NAME))
        self.grade=tk.StringVar();self.field(f,"Steel grade",self.grade,["A992","A36","Custom Fy"])
        self.fy=tk.StringVar();self.field(f,"Fy (ksi)",self.fy)
        self.props=ttk.Label(f,text="",style="Muted.TLabel",justify="left");self.props.pack(anchor="w",pady=7)
        self.section_canvas=tk.Canvas(f,height=190,bg="#f6f8fb",highlightthickness=1,highlightbackground="#dfe4ea")
        self.section_canvas.pack(fill="x",pady=(0,8))
        ttk.Label(f,text="POINT LOADS",style="Section.TLabel").pack(anchor="w",pady=(12,0))
        self.pl=ttk.Frame(f,style="Card.TFrame");self.pl.pack(fill="x");ttk.Button(f,text="+ Add point load",command=self.add_point).pack(fill="x")
        ttk.Label(f,text="UNIFORM LOADS",style="Section.TLabel").pack(anchor="w",pady=(12,0))
        self.ul=ttk.Frame(f,style="Card.TFrame");self.ul.pack(fill="x");ttk.Button(f,text="+ Add uniform load",command=self.add_uniform).pack(fill="x")
        self.selfw=tk.BooleanVar();ttk.Checkbutton(f,text="Include beam self-weight (dead)",variable=self.selfw,command=self.update).pack(anchor="w",pady=8)
        self.limit=tk.StringVar();self.field(f,"Live-load deflection limit L /",self.limit)
        ttk.Button(f,text="Reset to example",command=self.reset).pack(fill="x",pady=12)

    def reset(self):
        self.design_path = None
        self.support.set("Simply supported");self.span.set("20");self.shape.set("W12X26");self.grade.set("A992");self.fy.set("50");self.limit.set("360");self.selfw.set(False)
        self.points=[];self.uniforms=[{"a":0.,"b":20.,"w":1.,"type":"Live"}];self.rows();self.update()

    def current_design(self):
        # Read the widgets themselves so the file contains the latest edits.
        try:
            def loads(rows, numeric_fields):
                return [{key: (float(var.get()) if key in numeric_fields else var.get())
                         for key, var in row.items()} for row in rows]
            return validate_design({"version": 1, "support": self.support.get(),
                "span": float(self.span.get()), "shape": self.shape.get(),
                "grade": self.grade.get(), "fy": float(self.fy.get()),
                "limit": float(self.limit.get()), "self_weight": self.selfw.get(),
                "points": loads(self.point_rows, ("x", "P")),
                "uniforms": loads(self.uniform_rows, ("a", "b", "w"))})
        except ValueError as exc:
            raise ValueError(f"Check the beam inputs before saving: {exc}") from exc

    def save_design(self, save_as=False):
        try:
            design = self.current_design()
        except ValueError as exc:
            messagebox.showerror("Cannot save design", str(exc), parent=self)
            return
        path = self.design_path if not save_as else None
        if path is None:
            path = filedialog.asksaveasfilename(parent=self, title="Save beam design",
                defaultextension=".json", filetypes=[("Beam design", "*.json"), ("All files", "*")])
            if not path: return
        temp_path = None
        try:
            # Write beside the destination so a failed save does not truncate it.
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=Path(path).resolve().parent,
                                             prefix=".beam-", suffix=".tmp", delete=False) as f:
                temp_path = f.name
                json.dump(design, f, indent=2, allow_nan=False)
                f.write("\n")
            os.replace(temp_path, path)
            temp_path = None
            self.design_path = path
        except (OSError, ValueError) as exc:
            messagebox.showerror("Cannot save design", str(exc), parent=self)
        finally:
            if temp_path:
                try: os.unlink(temp_path)
                except OSError: pass

    def open_design(self):
        path = filedialog.askopenfilename(parent=self, title="Open beam design",
            filetypes=[("Beam design", "*.json"), ("All files", "*")])
        if not path: return
        try:
            with open(path, encoding="utf-8") as f:
                design = validate_design(json.load(f))
        except (OSError, UnicodeError, ValueError) as exc:
            messagebox.showerror("Cannot open design", str(exc), parent=self)
            return
        self.support.set(design["support"]); self.span.set(str(design["span"]))
        self.shape.set(design["shape"]); self.grade.set(design["grade"])
        self.fy.set(str(design["fy"])); self.limit.set(str(design["limit"]))
        self.selfw.set(design["self_weight"])
        self.points = design["points"]; self.uniforms = design["uniforms"]
        self.rows(); self.update(); self.design_path = path

    def add_point(self):
        try:L=float(self.span.get())
        except ValueError:L=20
        self.points.append({"x":L/2,"P":5.,"type":"Live"});self.rows();self.update()
    def add_uniform(self):
        try:L=float(self.span.get())
        except ValueError:L=20
        self.uniforms.append({"a":0.,"b":L,"w":.5,"type":"Dead"});self.rows();self.update()
    def rows(self):
        for w in self.pl.winfo_children()+self.ul.winfo_children():w.destroy()
        self.point_rows=[];self.uniform_rows=[]
        for parent,items,fields,storage in [(self.pl,self.points,["x","P","type"],self.point_rows),(self.ul,self.uniforms,["a","b","w","type"],self.uniform_rows)]:
            for i,item in enumerate(items):
                row=ttk.Frame(parent,style="Card.TFrame");row.pack(fill="x",pady=2);vars={}
                for key in fields:
                    var=tk.StringVar(value=str(item[key]));vars[key]=var
                    widget=ttk.Combobox(row,textvariable=var,values=["Dead","Live"],state="readonly",width=6) if key=="type" else ttk.Entry(row,textvariable=var,width=7)
                    widget.pack(side="left",padx=2);widget.bind("<KeyRelease>",lambda e:self.read_rows());widget.bind("<<ComboboxSelected>>",lambda e:self.read_rows())
                ttk.Button(row,text="×",width=2,command=lambda j=i,arr=items:self.delete_load(arr,j)).pack(side="right");storage.append(vars)
    def delete_load(self,arr,i):arr.pop(i);self.rows();self.update()
    def read_rows(self):
        for items,rows,nums in [(self.points,self.point_rows,["x","P"]),(self.uniforms,self.uniform_rows,["a","b","w"])]:
            for it,row in zip(items,rows):
                for k,v in row.items():
                    if k=="type":it[k]=v.get()
                    else:
                        try:it[k]=float(v.get())
                        except ValueError:it[k]=float("nan")
        self.update()

    def update(self,*_):
        if not hasattr(self,"chart"):return
        try:
            L=float(self.span.get());fy=float(self.fy.get()) if self.grade.get()=="Custom Fy" else {"A992":50,"A36":36}.get(self.grade.get(),50);den=float(self.limit.get());s=BY_NAME[self.shape.get()]
            if self.grade.get()!="Custom Fy":self.fy.set(str(fy))
            if not math.isfinite(L) or L<=0 or L>500 or fy<=0 or den<=0:raise ValueError("Use a positive span (up to 500 ft), Fy, and limit denominator.")
            if any(not math.isfinite(p[k]) for p in self.points for k in ("x","P")) or any(not math.isfinite(u[k]) for u in self.uniforms for k in ("a","b","w")):raise ValueError("Enter numbers for every load.")
            if any(p["P"]<0 or not 0<=p["x"]<=L for p in self.points):raise ValueError("Point loads must be nonnegative and within the span.")
            if any(u["w"]<0 or not 0<=u["a"]<u["b"]<=L for u in self.uniforms):raise ValueError("Uniform loads must be nonnegative and within the span, with end after start.")
            self.props.configure(text=f"{s['designation']}  |  d {s['d']} in · bf {s['bf']} in · tw {s['tw']} in · tf {s['tf']} in\nA {s['A']} in² · Ix {s['Ix']} in⁴ · Sx {s['Sx']} in³ · E 29,000 ksi")
            self.draw_section(s)
            pts=self.points; uni=[dict(u) for u in self.uniforms]
            if self.selfw.get():uni.append({"a":0,"b":L,"w":s["weight_plf"]/1000,"type":"Dead"})
            self.result=analyze(self.support.get(),L,pts,uni,29000,s["Ix"])
            live=analyze(self.support.get(),L,[p for p in pts if p["type"]=="Live"],[u for u in self.uniforms if u["type"]=="Live"],29000,s["Ix"])
            self.live=live;self.section=s;self.fyval=fy;self.den=den;self.error=None;self.draw();self.render_results()
        except (ValueError,KeyError,ZeroDivisionError) as e:
            self.error=str(e);self.chart.delete("all");self.chart.create_text(20,30,anchor="nw",text=self.error,fill="#a32924",width=700)
            self.summary_text.configure(text="")
            for w in self.checks.winfo_children(): w.destroy()

    def draw_section(self,s):
        c=self.section_canvas;c.delete("all")
        w=max(c.winfo_width(),280);h=190
        # Scale the complete cross-section to the available drawing area.
        scale=min((w-112)/s["bf"],(h-42)/s["d"])
        bw=s["bf"]*scale;bh=s["d"]*scale;tf=s["tf"]*scale;tw=s["tw"]*scale
        cx=w/2;top=24+(h-42-bh)/2;bottom=top+bh;left=cx-bw/2;right=cx+bw/2
        poly=[(left,top),(right,top),(right,top+tf),(cx+tw/2,top+tf),
              (cx+tw/2,bottom-tf),(right,bottom-tf),(right,bottom),
              (left,bottom),(left,bottom-tf),(cx-tw/2,bottom-tf),
              (cx-tw/2,top+tf),(left,top+tf)]
        pts=[v for xy in poly for v in xy]
        c.create_polygon(*pts,fill="#dbe5f1",outline=NAVY,width=2)
        mid=(top+bottom)/2
        c.create_line(left-8,mid,right+8,mid,fill="#d6453d",dash=(5,3))
        c.create_text(right+12,mid,text="x–x",anchor="w",fill="#d6453d",font=("TkDefaultFont",8))
        # Dimension lines for overall depth, flange width, and flange/web thickness.
        xd=left-26;c.create_line(xd,top,xd,bottom,fill="#64707d",arrow="both")
        c.create_text(xd-4,mid,text=f"d = {s['d']:g} in",angle=90,fill="#465363",font=("TkDefaultFont",8))
        yd=min(h-12,bottom+13);c.create_line(left,yd,right,yd,fill="#64707d",arrow="both")
        c.create_text(cx,yd+2,text=f"bf = {s['bf']:g} in",anchor="n",fill="#465363",font=("TkDefaultFont",8))
        c.create_text(right+12,top+tf/2,text=f"tf {s['tf']:g}",anchor="w",fill="#465363",font=("TkDefaultFont",8))
        c.create_line(cx+tw/2,mid+18,right+8,mid+18,fill="#64707d")
        c.create_text(right+12,mid+20,text=f"tw {s['tw']:g}",anchor="w",fill="#465363",font=("TkDefaultFont",8))

    def render_results(self):
        r=self.result;live=self.live;s=self.section;L=float(self.span.get());simple=self.support.get()=="Simply supported"
        mabs,vabs=r["mmax"][0],r["vmax"][0]; fb=mabs*12/s["Sx"];Fb=.66*self.fyval;fv=vabs/(s["d"]*s["tw"]);Fv=.4*self.fyval
        limit=(L if simple else 2*L)*12/self.den;dl=live["dmax"][0];dt=r["dmax"][0]
        checks=[("Bending",fb,Fb,"ksi"),("Shear",fv,Fv,"ksi"),("Deflection (live load)",dl,limit,"in")]
        passed=all(demand/allow<=1+1e-9 for _,demand,allow,_ in checks)
        reaction=f"Reactions: {r['RA']:.2f} / {r['RB']:.2f} kip (left / right)" if simple else f"Fixed end: {r['RA']:.2f} kip, moment {abs(r['M0']):.2f} kip-ft"
        self.summary_text.configure(text=f"{'PASS' if passed else 'FAIL'}  |  {reaction}\nMax shear {vabs:.2f} kip at {r['vmax'][1]:.2f} ft   ·   Max moment {mabs:.2f} kip-ft at {r['mmax'][1]:.2f} ft\nMax total deflection {dt:.3f} in at {r['dmax'][1]:.2f} ft")
        for w in self.checks.winfo_children():w.destroy()
        ttk.Label(self.checks,text="DESIGN CHECKS",style="Section.TLabel").grid(row=0,column=0,columnspan=5,sticky="w",pady=(0,6))
        for c,t in enumerate(("Check","Demand","Allowable","Ratio","Result")):ttk.Label(self.checks,text=t,style="Muted.TLabel").grid(row=1,column=c,sticky="w",padx=8)
        for i,(name,demand,allow,unit) in enumerate(checks,2):
            ratio=demand/allow;ok=ratio<=1+1e-9
            ttk.Label(self.checks,text=name).grid(row=i,column=0,sticky="w",padx=8,pady=4)
            ttk.Label(self.checks,text=f"{demand:.3f} {unit}").grid(row=i,column=1,sticky="w",padx=8)
            ttk.Label(self.checks,text=f"{allow:.3f} {unit}").grid(row=i,column=2,sticky="w",padx=8)
            ttk.Label(self.checks,text=f"{ratio:.2f}").grid(row=i,column=3,sticky="w",padx=8)
            ttk.Label(self.checks,text="PASS" if ok else "FAIL",foreground="#238348" if ok else "#b02b25").grid(row=i,column=4,sticky="w",padx=8)
        self.notes.configure(text="Basis: ASD; stresses use total dead + live load and deflection uses live load only. Beam assumed fully laterally braced; steel section assumed compact. Buckling is not checked. Fb = 0.66 Fy; Fv = 0.4 Fy. Sign convention: positive shear upward on the left face, positive moment sagging, deflection downward. Educational tool, not for design of record.")

    def draw(self):
        if not hasattr(self,"result") or getattr(self,"error",None):return
        c=self.chart;c.delete("all");w=max(480,c.winfo_width());L=float(self.span.get());r=self.result
        left,right=62,w-28;pw=right-left
        def X(x):return left+x/L*pw
        c.create_text(12,14,anchor="nw",text=f"Beam and diagrams  ·  {self.section['designation']}  ·  hover for V, M and δ",fill=NAVY,font=("TkDefaultFont",11,"bold"))
        # Beam/load sketch
        ybeam=85;c.create_line(left,ybeam,right,ybeam,width=8,fill=NAVY)
        for p in self.points:
            x=X(p["x"]);col=ORANGE if p["type"]=="Live" else "#5b6b82";c.create_line(x,38,x,ybeam-5,arrow="last",fill=col,width=2);c.create_text(x,32,text=f"{p['P']:g} kip",fill=col)
        for u in self.uniforms:
            xa,xb=X(u["a"]),X(u["b"]);col=ORANGE if u["type"]=="Live" else "#5b6b82";c.create_line(xa,48,xb,48,fill=col,width=2)
            for j in range(7):
                x=xa+(xb-xa)*j/6;c.create_line(x,48,x,ybeam-5,arrow="last",fill=col)
            c.create_text((xa+xb)/2,38,text=f"{u['w']:g} kip/ft",fill=col)
        for x in (left,right):c.create_polygon(x,ybeam+4,x-9,ybeam+19,x+9,ybeam+19,fill="white",outline=NAVY,width=2)
        chart_specs=[("Shear V (kip)",r["V"],TEAL,150), ("Moment M (kip-ft)",r["M"],BLUE,265),("Deflection δ (in)",lambda x:r["d"](x,29000,self.section["Ix"]),PURPLE,380)]
        for title,fn,col,base in chart_specs:
            vals=[fn(L*i/240) for i in range(241)];vmin=min(0,min(vals));vmax=max(0,max(vals));rng=max(vmax-vmin,1e-9);scale=54/rng
            c.create_text(12,base-36,anchor="nw",text=title,fill=col,font=("TkDefaultFont",10,"bold"));c.create_line(left,base,right,base,fill="#8994a1")
            coords=[]
            for i,val in enumerate(vals):coords.extend((left+pw*i/240,base-val*scale))
            c.create_line(*coords,fill=col,width=2,smooth=False)
        self.tooltip=c.create_text(left,470,anchor="w",text="Move pointer over diagrams to inspect values.",fill="#465363")
        def hover(e):
            x=max(left,min(right,e.x));xx=(x-left)/pw*L
            self.chart.itemconfigure(self.tooltip,text=f"x = {xx:.2f} ft   ·   V = {r['V'](xx):.2f} kip   ·   M = {r['M'](xx):.2f} kip-ft   ·   δ = {r['d'](xx,29000,self.section['Ix']):.3f} in")
        c.bind("<Motion>",hover)


if __name__ == "__main__":
    BeamDesigner().mainloop()
