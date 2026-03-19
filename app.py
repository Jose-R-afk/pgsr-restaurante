"""
PGSR - Restaurante "Donde Siempre"
Universidad Popular del Cesar - Grupo 10
Backend: Flask + MongoDB Atlas
"""
from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
import os, math, random
from datetime import date, datetime, timedelta

app = Flask(__name__)

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://jomireri_db_user:P8tuyr7UHCjvrGMS@pgsr-cluster.8wekyue.mongodb.net/?appName=pgsr-cluster"
)
client = MongoClient(MONGO_URI)
db = client["pgsr_restaurante"]

SMMLV = 1_423_500
AUX_TRANSPORTE = 200_000

def clean(doc):
    if doc: doc["_id"] = str(doc["_id"])
    return doc

def nuevo_id(coleccion, prefijo):
    ultimo = db[coleccion].find_one({"id": {"$regex": f"^{prefijo}-"}}, sort=[("id", -1)])
    num = 0
    if ultimo:
        try: num = int(ultimo["id"].split("-")[1])
        except: pass
    return f"{prefijo}-{num+1:04d}"

def col(n): return db[n]

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/dashboard")
def api_dashboard():
    cerrados = list(col("pedidos").find({"activo": True, "estado": "cerrado"}))
    totales = [p["total"] for p in cerrados]
    def media(v): return sum(v)/len(v) if v else 0
    def mediana(v):
        if not v: return 0
        s=sorted(v); n=len(s)
        return s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2
    def desv(v):
        if len(v)<2: return 0
        m=media(v); return math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1))
    conteo = {}
    for p in cerrados:
        for it in p.get("items",[]):
            conteo[it["plato_id"]] = conteo.get(it["plato_id"],0) + it["cantidad"]
    top = sorted(conteo.items(), key=lambda x:-x[1])[:5]
    top_n = []
    for pid,cnt in top:
        pl = col("platos").find_one({"id":pid})
        top_n.append({"nombre": pl["nombre"] if pl else pid, "cantidad": cnt})
    vd = {}
    for p in cerrados:
        f=str(p.get("fecha",""))[:10]; vd[f]=vd.get(f,0)+p["total"]
    ingresos = sum(c["monto"] for c in col("finanzas").find({"activo":True,"tipo":"ingreso"}))
    egresos  = sum(c["monto"] for c in col("finanzas").find({"activo":True,"tipo":"egreso"}))
    criticos = list(col("productos").find({"activo":True,"$expr":{"$lt":["$stock","$stock_minimo"]}}))
    return jsonify({
        "kpis":{"total_pedidos":col("pedidos").count_documents({"activo":True}),
                "pedidos_cerrados":len(cerrados),"ingresos_totales":ingresos,
                "egresos_totales":egresos,"saldo":ingresos-egresos,
                "empleados_activos":col("empleados").count_documents({"activo":True}),
                "mesas_libres":col("mesas").count_documents({"activo":True,"estado":"libre"}),
                "productos_criticos":len(criticos)},
        "estadisticas":{"media":media(totales),"mediana":mediana(totales),
                        "desv_std":desv(totales),"maximo":max(totales,default=0),
                        "minimo":min(totales,default=0),"suma":sum(totales)},
        "top_platos":top_n,
        "ventas_dia":[{"fecha":f,"total":t} for f,t in sorted(vd.items())[-7:]],
        "criticos":[{"nombre":p["nombre"],"stock":p["stock"],"minimo":p["stock_minimo"]} for p in criticos]
    })

@app.route("/api/productos", methods=["GET","POST"])
def api_productos():
    if request.method=="GET": return jsonify([clean(p) for p in col("productos").find({"activo":True})])
    d=request.json; pid=nuevo_id("productos","PRD")
    col("productos").insert_one({"id":pid,"nombre":d["nombre"],"categoria":d["categoria"],
        "unidad":d["unidad"],"stock":float(d["stock"]),"precio_costo":float(d["precio_costo"]),
        "stock_minimo":float(d["stock_minimo"]),"activo":True,"fecha_creacion":str(date.today())})
    return jsonify({"ok":True,"id":pid})

@app.route("/api/productos/<pid>", methods=["PUT","DELETE"])
def api_producto(pid):
    if request.method=="DELETE":
        col("productos").update_one({"id":pid},{"$set":{"activo":False}}); return jsonify({"ok":True})
    d=request.json; upd={k:d[k] for k in ["nombre","categoria","unidad","stock_minimo","precio_costo"] if k in d}
    if "stock" in d: upd["stock"]=float(d["stock"])
    col("productos").update_one({"id":pid},{"$set":upd}); return jsonify({"ok":True})

@app.route("/api/platos", methods=["GET","POST"])
def api_platos():
    if request.method=="GET": return jsonify([clean(p) for p in col("platos").find({"activo":True})])
    d=request.json; plid=nuevo_id("platos","PLT")
    col("platos").insert_one({"id":plid,"nombre":d["nombre"],"categoria":d["categoria"],
        "precio_venta":float(d["precio_venta"]),"descripcion":d.get("descripcion",""),
        "activo":True,"fecha_creacion":str(date.today())})
    return jsonify({"ok":True,"id":plid})

@app.route("/api/platos/<plid>", methods=["PUT","DELETE"])
def api_plato(plid):
    if request.method=="DELETE":
        col("platos").update_one({"id":plid},{"$set":{"activo":False}}); return jsonify({"ok":True})
    d=request.json; upd={k:d[k] for k in ["nombre","categoria","descripcion"] if k in d}
    if "precio_venta" in d: upd["precio_venta"]=float(d["precio_venta"])
    col("platos").update_one({"id":plid},{"$set":upd}); return jsonify({"ok":True})

@app.route("/api/proveedores", methods=["GET","POST"])
def api_proveedores():
    if request.method=="GET": return jsonify([clean(p) for p in col("proveedores").find({"activo":True})])
    d=request.json; pvid=nuevo_id("proveedores","PV")
    col("proveedores").insert_one({**d,"id":pvid,"activo":True,"fecha_registro":str(date.today())})
    return jsonify({"ok":True,"id":pvid})

@app.route("/api/proveedores/<pvid>", methods=["PUT","DELETE"])
def api_proveedor(pvid):
    if request.method=="DELETE":
        col("proveedores").update_one({"id":pvid},{"$set":{"activo":False}}); return jsonify({"ok":True})
    col("proveedores").update_one({"id":pvid},{"$set":request.json}); return jsonify({"ok":True})

@app.route("/api/pedidos", methods=["GET","POST"])
def api_pedidos():
    if request.method=="GET": return jsonify([clean(p) for p in col("pedidos").find({"activo":True},sort=[("fecha",-1)])])
    d=request.json; pedid=nuevo_id("pedidos","PED")
    items=d.get("items",[]); total=sum(i["cantidad"]*i["precio_unit"] for i in items)
    for i in items: i["subtotal"]=i["cantidad"]*i["precio_unit"]
    doc={"id":pedid,"tipo":d["tipo"],"mesa_id":d.get("mesa_id",""),"mesero_id":d.get("mesero_id",""),
         "cliente_id":d.get("cliente_id",""),"items":items,"total":total,
         "estado":"abierto","fecha":str(datetime.now()),"activo":True}
    col("pedidos").insert_one(doc)
    col("finanzas").insert_one({"id":f"ING-{pedid}","tipo":"ingreso",
        "concepto":f"Pedido {pedid}","monto":total,"fecha":str(date.today()),"activo":True})
    return jsonify({"ok":True,"id":pedid,"total":total})

@app.route("/api/pedidos/<pedid>", methods=["PUT","DELETE"])
def api_pedido(pedid):
    if request.method=="DELETE":
        col("pedidos").update_one({"id":pedid},{"$set":{"activo":False}}); return jsonify({"ok":True})
    col("pedidos").update_one({"id":pedid},{"$set":request.json}); return jsonify({"ok":True})

@app.route("/api/reservas", methods=["GET","POST"])
def api_reservas():
    if request.method=="GET": return jsonify([clean(r) for r in col("reservas").find({"activo":True})])
    d=request.json; rid=nuevo_id("reservas","RSV")
    col("reservas").insert_one({**d,"id":rid,"estado":"confirmada","activo":True})
    return jsonify({"ok":True,"id":rid})

@app.route("/api/reservas/<rid>", methods=["PUT","DELETE"])
def api_reserva(rid):
    if request.method=="DELETE":
        col("reservas").update_one({"id":rid},{"$set":{"activo":False,"estado":"cancelada"}}); return jsonify({"ok":True})
    col("reservas").update_one({"id":rid},{"$set":request.json}); return jsonify({"ok":True})

@app.route("/api/mesas", methods=["GET","POST"])
def api_mesas():
    if request.method=="GET": return jsonify([clean(m) for m in col("mesas").find({"activo":True})])
    d=request.json; mid=nuevo_id("mesas","MSA")
    col("mesas").insert_one({**d,"id":mid,"estado":"libre","activo":True})
    return jsonify({"ok":True,"id":mid})

@app.route("/api/mesas/<mid>", methods=["PUT","DELETE"])
def api_mesa(mid):
    if request.method=="DELETE":
        col("mesas").update_one({"id":mid},{"$set":{"activo":False}}); return jsonify({"ok":True})
    col("mesas").update_one({"id":mid},{"$set":request.json}); return jsonify({"ok":True})

@app.route("/api/empleados", methods=["GET","POST"])
def api_empleados():
    if request.method=="GET": return jsonify([clean(e) for e in col("empleados").find({"activo":True})])
    d=request.json; eid=nuevo_id("empleados","EMP")
    col("empleados").insert_one({**d,"id":eid,"activo":True,
        "salario_base":float(d["salario_base"]),"fecha_ingreso":str(date.today())})
    return jsonify({"ok":True,"id":eid})

@app.route("/api/empleados/<eid>", methods=["PUT","DELETE"])
def api_empleado(eid):
    if request.method=="DELETE":
        col("empleados").update_one({"id":eid},{"$set":{"activo":False}}); return jsonify({"ok":True})
    col("empleados").update_one({"id":eid},{"$set":request.json}); return jsonify({"ok":True})

@app.route("/api/nomina/<eid>")
def api_nomina(eid):
    e=col("empleados").find_one({"id":eid})
    if not e: return jsonify({"error":"No encontrado"}),404
    s=float(e["salario_base"]); aux=AUX_TRANSPORTE if s<=2*SMMLV else 0
    dev=s+aux; ds=s*0.04; dp=s*0.04; ded=ds+dp; neto=dev-ded
    as_=s*0.085; ap=s*0.12; ces=s/12; ic=ces*0.12/12; pri=s/12; vac=s*0.0417
    costo=dev+as_+ap+ces+ic+pri+vac; mes=date.today().strftime("%Y-%m")
    nom_id=f"NOM-{eid}-{mes}"
    doc={"id":nom_id,"empleado_id":eid,"empleado_nombre":e["nombre"],"mes":mes,
         "salario_base":s,"aux_transporte":aux,"devengado":dev,"desc_salud":ds,
         "desc_pension":dp,"deducciones":ded,"neto_pagar":neto,"ap_salud_empr":as_,
         "ap_pension_empr":ap,"cesantias":ces,"int_cesantias":ic,"prima":pri,
         "vacaciones":vac,"costo_empresa":costo,"fecha":str(date.today()),"activo":True}
    col("nominas").update_one({"id":nom_id},{"$set":doc},upsert=True)
    return jsonify(doc)

@app.route("/api/nominas")
def api_nominas(): return jsonify([clean(n) for n in col("nominas").find({"activo":True})])

@app.route("/api/finanzas", methods=["GET","POST"])
def api_finanzas():
    if request.method=="GET": return jsonify([clean(c) for c in col("finanzas").find({"activo":True},sort=[("fecha",-1)])])
    d=request.json; fid=nuevo_id("finanzas","MVF")
    col("finanzas").insert_one({**d,"id":fid,"activo":True,"monto":float(d["monto"]),"fecha":str(date.today())})
    return jsonify({"ok":True,"id":fid})

@app.route("/api/finanzas/<fid>", methods=["DELETE"])
def api_finanza(fid):
    col("finanzas").update_one({"id":fid},{"$set":{"activo":False}}); return jsonify({"ok":True})

@app.route("/api/clientes", methods=["GET","POST"])
def api_clientes():
    if request.method=="GET": return jsonify([clean(c) for c in col("clientes").find({"activo":True})])
    d=request.json; cid=nuevo_id("clientes","CLI")
    col("clientes").insert_one({**d,"id":cid,"puntos":0,"activo":True,"fecha_registro":str(date.today())})
    return jsonify({"ok":True,"id":cid})

@app.route("/api/clientes/<cid>", methods=["PUT","DELETE"])
def api_cliente(cid):
    if request.method=="DELETE":
        col("clientes").update_one({"id":cid},{"$set":{"activo":False}}); return jsonify({"ok":True})
    col("clientes").update_one({"id":cid},{"$set":request.json}); return jsonify({"ok":True})

@app.route("/api/promociones")
def api_promociones():
    promos=[]; hoy=date.today()
    for c in col("clientes").find({"activo":True}):
        compras=sum(p["total"] for p in col("pedidos").find({"cliente_id":c["id"],"activo":True}))
        pts=int(compras/10_000)
        col("clientes").update_one({"id":c["id"]},{"$set":{"puntos":pts}})
        lista=[]
        if pts>=50: lista.append({"tipo":"gold","texto":"50% descuento próxima visita"})
        elif pts>=20: lista.append({"tipo":"silver","texto":"20% descuento próxima visita"})
        elif pts>=10: lista.append({"tipo":"bronze","texto":"Postre gratis"})
        if c.get("cumpleanos")==hoy.strftime("%m-%d"):
            lista.append({"tipo":"birthday","texto":"🎂 ¡Cumpleaños! Almuerzo gratis"})
        if col("pedidos").count_documents({"cliente_id":c["id"]})>=10:
            lista.append({"tipo":"vip","texto":"Cliente VIP - 10% permanente"})
        if lista: promos.append({"cliente":c["nombre"],"telefono":c.get("telefono",""),"puntos":pts,"promos":lista})
    return jsonify(promos)

@app.route("/api/simular", methods=["POST"])
def api_simular():
    dias=int(request.json.get("dias",7))
    if col("platos").count_documents({"activo":True})<3:
        for nm,cat,pv in [("Bandeja Paisa","principal",35000),("Sancocho","principal",25000),
            ("Almuerzo del día","principal",18000),("Jugo natural","bebida",8000),
            ("Postre casero","postre",7000),("Arroz con pollo","principal",22000),("Mojarra frita","principal",30000)]:
            col("platos").insert_one({"id":nuevo_id("platos","PLT"),"nombre":nm,"categoria":cat,
                "precio_venta":pv,"activo":True,"fecha_creacion":str(date.today())})
    if col("empleados").count_documents({"activo":True})<2:
        for nm,cargo in [("Carlos Ruiz","mesero"),("Ana Pérez","cocinero"),("Luis García","cajero"),("María López","mesero")]:
            col("empleados").insert_one({"id":nuevo_id("empleados","EMP"),"nombre":nm,"cedula":"0","cargo":cargo,
                "salario_base":SMMLV+random.randint(0,400000),"telefono":"3001234567",
                "email":f"{nm.split()[0].lower()}@donde.com","activo":True,"fecha_ingreso":str(date.today())})
    if col("mesas").count_documents({"activo":True})<4:
        for i in range(1,9):
            col("mesas").insert_one({"id":nuevo_id("mesas","MSA"),"numero":str(i),
                "capacidad":random.choice([2,4,6]),"zona":random.choice(["interior","exterior"]),
                "estado":"libre","activo":True})
    plids=[p["id"] for p in col("platos").find({"activo":True})]
    eids=[e["id"] for e in col("empleados").find({"activo":True})]
    mids=[m["id"] for m in col("mesas").find({"activo":True})]
    pm={p["id"]:p for p in col("platos").find({"activo":True})}
    hoy=date.today(); tp=0; tv=0; pb=[]; fb=[]
    for d in range(dias):
        fs=hoy-timedelta(days=dias-d-1)
        for _ in range(random.randint(8,30)):
            pedid=nuevo_id("pedidos","PED")
            items=[]; 
            for __ in range(random.randint(1,4)):
                plid=random.choice(plids); pl=pm[plid]; cant=random.randint(1,3); sub=cant*pl["precio_venta"]
                items.append({"plato_id":plid,"nombre":pl["nombre"],"cantidad":cant,"precio_unit":pl["precio_venta"],"subtotal":sub})
            total=sum(i["subtotal"] for i in items)
            hora=f"{random.randint(11,21):02d}:{random.randint(0,59):02d}"
            estado=random.choices(["cerrado","cancelado"],[4,1])[0]
            pb.append({"id":pedid,"tipo":random.choices(["local","domicilio"],[3,1])[0],
                "mesa_id":random.choice(mids),"mesero_id":random.choice(eids),
                "items":items,"total":total,"estado":estado,
                "fecha":f"{fs}T{hora}:00","activo":True,"cliente_id":""})
            fb.append({"id":f"ING-{pedid}","tipo":"ingreso","concepto":f"Pedido {pedid}",
                "monto":total,"fecha":str(fs),"activo":True})
            tp+=1; tv+=total
    if pb: col("pedidos").insert_many(pb)
    if fb: col("finanzas").insert_many(fb)
    for concepto,monto in [("Arriendo",2_500_000),("Servicios",400_000),("Insumos",800_000),("Nómina",5_000_000)]:
        col("finanzas").insert_one({"id":nuevo_id("finanzas","MVF"),"tipo":"egreso",
            "concepto":concepto,"monto":monto,"fecha":str(hoy),"activo":True})
    return jsonify({"ok":True,"pedidos":tp,"ventas":tv,"dias":dias})

@app.route("/api/guardar", methods=["POST"])
def api_guardar(): return jsonify({"ok":True,"msg":"MongoDB guarda automáticamente"})

if __name__ == "__main__":
    port=int(os.environ.get("PORT",5000))
    print(f"\n{'='*50}\n  PGSR - Restaurante 'Donde Siempre'\n  http://localhost:{port}\n{'='*50}\n")
    app.run(host="0.0.0.0", debug=False, port=port)
