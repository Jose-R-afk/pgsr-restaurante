"""
================================================================================
 PGSR - Programa de Gestión de Servicios de Restauración
 Restaurante "Donde Siempre"
 Universidad Popular del Cesar - Ingeniería de Sistemas
 Estructura de Datos - Parcial 1 - Grupo 10
 Backend: Flask (Python) + API REST + Frontend HTML/CSS/JS
================================================================================
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import json, os, math, random
from datetime import date, datetime, timedelta

app = Flask(__name__)
ARCHIVO = "datos_restaurante.json"

# ─── CONSTANTES NÓMINA COLOMBIA 2025 ─────────────────────────────────────────
SMMLV           = 1_423_500
AUX_TRANSPORTE  = 200_000
SALUD_EMP       = 0.04
PENSION_EMP     = 0.04
SALUD_EMPR      = 0.085
PENSION_EMPR    = 0.12

# ─── BASE DE DATOS EN MEMORIA ────────────────────────────────────────────────
datos = {}

def cargar():
    global datos
    if os.path.exists(ARCHIVO):
        with open(ARCHIVO, "r", encoding="utf-8") as f:
            datos = json.load(f)
    _init_tablas()

def guardar():
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

def _init_tablas():
    for t in ["productos","platos","proveedores","pedidos_proveedor",
              "pedidos","reservas","mesas","empleados","nominas",
              "finanzas","clientes"]:
        datos.setdefault(t, {})

def nuevo_id(tabla, prefijo):
    ids = [int(k.split("-")[1]) for k in datos.get(tabla,{}).keys()
           if k.startswith(prefijo+"-")]
    return f"{prefijo}-{(max(ids, default=0)+1):04d}"

cargar()

# ═══════════════════════════════════════════════════════════════════════════════
# RUTA PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template("index.html")

# ═══════════════════════════════════════════════════════════════════════════════
# API - DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/dashboard")
def api_dashboard():
    pedidos_cerrados = [p for p in datos["pedidos"].values()
                        if p.get("activo",True) and p.get("estado")=="cerrado"]
    totales = [p["total"] for p in pedidos_cerrados]
    
    def media(v): return sum(v)/len(v) if v else 0
    def mediana(v):
        if not v: return 0
        s=sorted(v); n=len(s)
        return s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2
    def desv(v):
        if len(v)<2: return 0
        m=media(v)
        return math.sqrt(sum((x-m)**2 for x in v)/(len(v)-1))

    # Top platos
    conteo = {}
    for p in pedidos_cerrados:
        for it in p.get("items",[]):
            pid = it["plato_id"]
            conteo[pid] = conteo.get(pid,0) + it["cantidad"]
    top_platos = sorted(conteo.items(), key=lambda x:-x[1])[:5]
    top_platos_nombres = [
        {"nombre": datos["platos"].get(pid,{}).get("nombre","?"), "cantidad": cnt}
        for pid, cnt in top_platos
    ]

    # Ventas por día (últimos 7)
    ventas_dia = {}
    for p in pedidos_cerrados:
        fecha = p.get("fecha","")[:10]
        ventas_dia[fecha] = ventas_dia.get(fecha, 0) + p["total"]
    ventas_sorted = sorted(ventas_dia.items())[-7:]

    # Finanzas
    ingresos = sum(c["monto"] for c in datos["finanzas"].values() if c.get("activo",True) and c["tipo"]=="ingreso")
    egresos  = sum(c["monto"] for c in datos["finanzas"].values() if c.get("activo",True) and c["tipo"]=="egreso")

    # Inventario crítico
    criticos = [p for p in datos["productos"].values()
                if p.get("activo",True) and p["stock"] < p["stock_minimo"]]

    return jsonify({
        "kpis": {
            "total_pedidos": len(datos["pedidos"]),
            "pedidos_cerrados": len(pedidos_cerrados),
            "ingresos_totales": ingresos,
            "egresos_totales": egresos,
            "saldo": ingresos - egresos,
            "empleados_activos": sum(1 for e in datos["empleados"].values() if e.get("activo",True)),
            "mesas_libres": sum(1 for m in datos["mesas"].values() if m.get("activo",True) and m.get("estado")=="libre"),
            "productos_criticos": len(criticos),
        },
        "estadisticas": {
            "media": media(totales),
            "mediana": mediana(totales),
            "desv_std": desv(totales),
            "maximo": max(totales, default=0),
            "minimo": min(totales, default=0),
            "suma": sum(totales),
        },
        "top_platos": top_platos_nombres,
        "ventas_dia": [{"fecha": f, "total": t} for f,t in ventas_sorted],
        "criticos": [{"nombre": p["nombre"], "stock": p["stock"], "minimo": p["stock_minimo"]} for p in criticos],
    })

# ═══════════════════════════════════════════════════════════════════════════════
# API - PRODUCTOS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/productos", methods=["GET","POST"])
def api_productos():
    if request.method == "GET":
        items = [p for p in datos["productos"].values() if p.get("activo",True)]
        return jsonify(items)
    d = request.json
    pid = nuevo_id("productos","PRD")
    datos["productos"][pid] = {
        "id": pid, "nombre": d["nombre"], "categoria": d["categoria"],
        "unidad": d["unidad"], "stock": float(d["stock"]),
        "precio_costo": float(d["precio_costo"]),
        "stock_minimo": float(d["stock_minimo"]),
        "activo": True, "fecha_creacion": str(date.today())
    }
    guardar()
    return jsonify({"ok": True, "id": pid})

@app.route("/api/productos/<pid>", methods=["PUT","DELETE"])
def api_producto(pid):
    if pid not in datos["productos"]:
        return jsonify({"error": "No encontrado"}), 404
    if request.method == "DELETE":
        datos["productos"][pid]["activo"] = False
        guardar()
        return jsonify({"ok": True})
    d = request.json
    p = datos["productos"][pid]
    for k in ["nombre","categoria","unidad","stock_minimo","precio_costo"]:
        if k in d: p[k] = d[k]
    if "stock" in d: p["stock"] = float(d["stock"])
    guardar()
    return jsonify({"ok": True})

# ═══════════════════════════════════════════════════════════════════════════════
# API - PLATOS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/platos", methods=["GET","POST"])
def api_platos():
    if request.method == "GET":
        items = [p for p in datos["platos"].values() if p.get("activo",True)]
        return jsonify(items)
    d = request.json
    plid = nuevo_id("platos","PLT")
    datos["platos"][plid] = {
        "id": plid, "nombre": d["nombre"], "categoria": d["categoria"],
        "precio_venta": float(d["precio_venta"]),
        "descripcion": d.get("descripcion",""),
        "activo": True, "fecha_creacion": str(date.today())
    }
    guardar()
    return jsonify({"ok": True, "id": plid})

@app.route("/api/platos/<plid>", methods=["PUT","DELETE"])
def api_plato(plid):
    if plid not in datos["platos"]:
        return jsonify({"error": "No encontrado"}), 404
    if request.method == "DELETE":
        datos["platos"][plid]["activo"] = False
        guardar()
        return jsonify({"ok": True})
    d = request.json
    pl = datos["platos"][plid]
    for k in ["nombre","categoria","precio_venta","descripcion"]:
        if k in d: pl[k] = d[k]
    guardar()
    return jsonify({"ok": True})

# ═══════════════════════════════════════════════════════════════════════════════
# API - PROVEEDORES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/proveedores", methods=["GET","POST"])
def api_proveedores():
    if request.method == "GET":
        return jsonify([p for p in datos["proveedores"].values() if p.get("activo",True)])
    d = request.json
    pvid = nuevo_id("proveedores","PV")
    datos["proveedores"][pvid] = {**d, "id": pvid, "activo": True, "fecha_registro": str(date.today())}
    guardar()
    return jsonify({"ok": True, "id": pvid})

@app.route("/api/proveedores/<pvid>", methods=["PUT","DELETE"])
def api_proveedor(pvid):
    if pvid not in datos["proveedores"]:
        return jsonify({"error": "No encontrado"}), 404
    if request.method == "DELETE":
        datos["proveedores"][pvid]["activo"] = False
        guardar()
        return jsonify({"ok": True})
    datos["proveedores"][pvid].update(request.json)
    guardar()
    return jsonify({"ok": True})

# ═══════════════════════════════════════════════════════════════════════════════
# API - PEDIDOS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/pedidos", methods=["GET","POST"])
def api_pedidos():
    if request.method == "GET":
        items = [p for p in datos["pedidos"].values() if p.get("activo",True)]
        return jsonify(sorted(items, key=lambda x: x.get("fecha",""), reverse=True))
    d = request.json
    pedid = nuevo_id("pedidos","PED")
    items = d.get("items",[])
    total = sum(it["cantidad"]*it["precio_unit"] for it in items)
    for it in items:
        it["subtotal"] = it["cantidad"]*it["precio_unit"]
    datos["pedidos"][pedid] = {
        "id": pedid, "tipo": d["tipo"],
        "mesa_id": d.get("mesa_id",""), "mesero_id": d.get("mesero_id",""),
        "cliente_id": d.get("cliente_id",""),
        "items": items, "total": total,
        "estado": "abierto", "fecha": str(datetime.now()),
        "activo": True
    }
    if d.get("tipo")=="domicilio":
        datos["pedidos"][pedid]["direccion"] = d.get("direccion","")
    # Registrar ingreso
    iid = f"ING-{pedid}"
    datos["finanzas"][iid] = {"id":iid,"tipo":"ingreso","concepto":f"Pedido {pedid}",
                               "monto":total,"fecha":str(date.today()),"activo":True}
    guardar()
    return jsonify({"ok": True, "id": pedid, "total": total})

@app.route("/api/pedidos/<pedid>", methods=["PUT","DELETE"])
def api_pedido(pedid):
    if pedid not in datos["pedidos"]:
        return jsonify({"error": "No encontrado"}), 404
    if request.method == "DELETE":
        datos["pedidos"][pedid]["activo"] = False
        guardar(); return jsonify({"ok": True})
    datos["pedidos"][pedid].update(request.json)
    guardar(); return jsonify({"ok": True})

# ═══════════════════════════════════════════════════════════════════════════════
# API - RESERVAS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/reservas", methods=["GET","POST"])
def api_reservas():
    if request.method == "GET":
        return jsonify([r for r in datos["reservas"].values() if r.get("activo",True)])
    d = request.json
    rid = nuevo_id("reservas","RSV")
    datos["reservas"][rid] = {**d, "id": rid, "estado": "confirmada", "activo": True}
    guardar()
    return jsonify({"ok": True, "id": rid})

@app.route("/api/reservas/<rid>", methods=["PUT","DELETE"])
def api_reserva(rid):
    if rid not in datos["reservas"]:
        return jsonify({"error": "No encontrado"}), 404
    if request.method == "DELETE":
        datos["reservas"][rid]["activo"] = False
        datos["reservas"][rid]["estado"] = "cancelada"
        guardar(); return jsonify({"ok": True})
    datos["reservas"][rid].update(request.json)
    guardar(); return jsonify({"ok": True})

# ═══════════════════════════════════════════════════════════════════════════════
# API - MESAS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/mesas", methods=["GET","POST"])
def api_mesas():
    if request.method == "GET":
        return jsonify([m for m in datos["mesas"].values() if m.get("activo",True)])
    d = request.json
    mid = nuevo_id("mesas","MSA")
    datos["mesas"][mid] = {**d, "id": mid, "estado": "libre", "activo": True}
    guardar()
    return jsonify({"ok": True, "id": mid})

@app.route("/api/mesas/<mid>", methods=["PUT","DELETE"])
def api_mesa(mid):
    if mid not in datos["mesas"]:
        return jsonify({"error": "No encontrado"}), 404
    if request.method == "DELETE":
        datos["mesas"][mid]["activo"] = False
        guardar(); return jsonify({"ok": True})
    datos["mesas"][mid].update(request.json)
    guardar(); return jsonify({"ok": True})

# ═══════════════════════════════════════════════════════════════════════════════
# API - EMPLEADOS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/empleados", methods=["GET","POST"])
def api_empleados():
    if request.method == "GET":
        return jsonify([e for e in datos["empleados"].values() if e.get("activo",True)])
    d = request.json
    eid = nuevo_id("empleados","EMP")
    datos["empleados"][eid] = {**d, "id": eid, "activo": True,
                                "salario_base": float(d["salario_base"]),
                                "fecha_ingreso": str(date.today())}
    guardar()
    return jsonify({"ok": True, "id": eid})

@app.route("/api/empleados/<eid>", methods=["PUT","DELETE"])
def api_empleado(eid):
    if eid not in datos["empleados"]:
        return jsonify({"error": "No encontrado"}), 404
    if request.method == "DELETE":
        datos["empleados"][eid]["activo"] = False
        guardar(); return jsonify({"ok": True})
    datos["empleados"][eid].update(request.json)
    guardar(); return jsonify({"ok": True})

# ═══════════════════════════════════════════════════════════════════════════════
# API - NÓMINA
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/nomina/<eid>", methods=["GET"])
def api_nomina(eid):
    if eid not in datos["empleados"]:
        return jsonify({"error": "No encontrado"}), 404
    e = datos["empleados"][eid]
    s = float(e["salario_base"])
    aux = AUX_TRANSPORTE if s <= 2*SMMLV else 0
    dev = s + aux
    ds  = s * SALUD_EMP
    dp  = s * PENSION_EMP
    ded = ds + dp
    neto= dev - ded
    as_ = s * SALUD_EMPR
    ap  = s * PENSION_EMPR
    ces = s / 12
    ic  = ces * 0.12 / 12
    pri = s / 12
    vac = s * 0.0417
    costo = dev + as_ + ap + ces + ic + pri + vac

    nom_id = f"NOM-{eid}-{date.today().strftime('%Y-%m')}"
    datos["nominas"][nom_id] = {
        "id": nom_id, "empleado_id": eid, "empleado_nombre": e["nombre"],
        "mes": date.today().strftime("%Y-%m"), "salario_base": s,
        "aux_transporte": aux, "devengado": dev,
        "desc_salud": ds, "desc_pension": dp, "deducciones": ded,
        "neto_pagar": neto, "ap_salud_empr": as_, "ap_pension_empr": ap,
        "cesantias": ces, "int_cesantias": ic, "prima": pri, "vacaciones": vac,
        "costo_empresa": costo, "fecha": str(date.today()), "activo": True
    }
    guardar()
    return jsonify(datos["nominas"][nom_id])

@app.route("/api/nominas", methods=["GET"])
def api_nominas():
    return jsonify(list(datos["nominas"].values()))

# ═══════════════════════════════════════════════════════════════════════════════
# API - FINANZAS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/finanzas", methods=["GET","POST"])
def api_finanzas():
    if request.method == "GET":
        items = [c for c in datos["finanzas"].values() if c.get("activo",True)]
        return jsonify(sorted(items, key=lambda x: x.get("fecha",""), reverse=True))
    d = request.json
    fid = nuevo_id("finanzas","MVF")
    datos["finanzas"][fid] = {**d, "id": fid, "activo": True,
                               "monto": float(d["monto"]),
                               "fecha": str(date.today())}
    guardar()
    return jsonify({"ok": True, "id": fid})

@app.route("/api/finanzas/<fid>", methods=["DELETE"])
def api_finanza(fid):
    if fid not in datos["finanzas"]:
        return jsonify({"error": "No encontrado"}), 404
    datos["finanzas"][fid]["activo"] = False
    guardar(); return jsonify({"ok": True})

# ═══════════════════════════════════════════════════════════════════════════════
# API - CLIENTES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/clientes", methods=["GET","POST"])
def api_clientes():
    if request.method == "GET":
        return jsonify([c for c in datos["clientes"].values() if c.get("activo",True)])
    d = request.json
    cid = nuevo_id("clientes","CLI")
    datos["clientes"][cid] = {**d, "id": cid, "puntos": 0, "activo": True,
                               "fecha_registro": str(date.today())}
    guardar()
    return jsonify({"ok": True, "id": cid})

@app.route("/api/clientes/<cid>", methods=["PUT","DELETE"])
def api_cliente(cid):
    if cid not in datos["clientes"]:
        return jsonify({"error": "No encontrado"}), 404
    if request.method == "DELETE":
        datos["clientes"][cid]["activo"] = False
        guardar(); return jsonify({"ok": True})
    datos["clientes"][cid].update(request.json)
    guardar(); return jsonify({"ok": True})

@app.route("/api/promociones", methods=["GET"])
def api_promociones():
    promos = []
    compras = {}
    for p in datos["pedidos"].values():
        cli = p.get("cliente_id","")
        if cli and cli in datos["clientes"]:
            compras[cli] = compras.get(cli,0) + p.get("total",0)
    for cid, total in compras.items():
        datos["clientes"][cid]["puntos"] = int(total/10_000)
    hoy = date.today()
    for cid, c in datos["clientes"].items():
        if not c.get("activo",True): continue
        pts = c.get("puntos",0)
        lista = []
        if pts >= 50: lista.append({"tipo":"gold","texto":"50% descuento próxima visita"})
        elif pts >= 20: lista.append({"tipo":"silver","texto":"20% descuento próxima visita"})
        elif pts >= 10: lista.append({"tipo":"bronze","texto":"Postre gratis"})
        cumple = c.get("cumpleanos","")
        if cumple and cumple == hoy.strftime("%m-%d"):
            lista.append({"tipo":"birthday","texto":"🎂 ¡Cumpleaños! Almuerzo gratis"})
        visitas = sum(1 for p in datos["pedidos"].values() if p.get("cliente_id")==cid)
        if visitas >= 10: lista.append({"tipo":"vip","texto":"Cliente VIP - 10% permanente"})
        if lista:
            promos.append({"cliente": c["nombre"], "telefono": c.get("telefono",""), "puntos": pts, "promos": lista})
    guardar()
    return jsonify(promos)

# ═══════════════════════════════════════════════════════════════════════════════
# API - SIMULACIÓN
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/simular", methods=["POST"])
def api_simular():
    dias = int(request.json.get("dias", 7))
    
    # Datos base
    if len(datos["platos"]) < 3:
        platosBase = [
            ("Bandeja Paisa","principal",35000),("Sancocho","principal",25000),
            ("Almuerzo del día","principal",18000),("Jugo natural","bebida",8000),
            ("Postre casero","postre",7000),("Arroz con pollo","principal",22000),
            ("Mojarra frita","principal",30000),
        ]
        for nm,cat,pv in platosBase:
            plid = nuevo_id("platos","PLT")
            datos["platos"][plid] = {"id":plid,"nombre":nm,"categoria":cat,
                "precio_venta":pv,"activo":True,"fecha_creacion":str(date.today())}
    if len(datos["empleados"]) < 2:
        for nm,cargo in [("Carlos Ruiz","mesero"),("Ana Pérez","cocinero"),
                         ("Luis García","cajero"),("María López","mesero")]:
            eid = nuevo_id("empleados","EMP")
            datos["empleados"][eid] = {"id":eid,"nombre":nm,"cedula":"0","cargo":cargo,
                "salario_base":SMMLV+random.randint(0,400000),
                "telefono":"3001234567","email":f"{nm.split()[0].lower()}@donde.com",
                "activo":True,"fecha_ingreso":str(date.today())}
    if len(datos["mesas"]) < 4:
        for i in range(1,9):
            mid = nuevo_id("mesas","MSA")
            datos["mesas"][mid] = {"id":mid,"numero":str(i),
                "capacidad":random.choice([2,4,6]),"zona":random.choice(["interior","exterior"]),
                "estado":"libre","activo":True}
    if len(datos["productos"]) < 2:
        for nm,cat,un,stk,pc,stmin in [
            ("Pollo","carne","kg",50,8000,5),("Arroz","grano","kg",30,2500,10),
            ("Papa","vegetal","kg",40,1800,10)]:
            pid = nuevo_id("productos","PRD")
            datos["productos"][pid] = {"id":pid,"nombre":nm,"categoria":cat,"unidad":un,
                "stock":stk,"precio_costo":pc,"stock_minimo":stmin,"activo":True,
                "fecha_creacion":str(date.today())}

    plids = [p["id"] for p in datos["platos"].values() if p.get("activo",True)]
    eids  = [e["id"] for e in datos["empleados"].values() if e.get("activo",True)]
    mids  = [m["id"] for m in datos["mesas"].values() if m.get("activo",True)]
    
    hoy = date.today()
    total_peds = 0; total_ventas = 0
    for d in range(dias):
        fecha_sim = hoy - timedelta(days=dias-d-1)
        n_peds = random.randint(8, 30)
        for _ in range(n_peds):
            pedid = nuevo_id("pedidos","PED")
            n_items = random.randint(1,4)
            items = []
            for __ in range(n_items):
                plid = random.choice(plids)
                pl = datos["platos"][plid]
                cant = random.randint(1,3)
                sub = cant * pl["precio_venta"]
                items.append({"plato_id":plid,"nombre":pl["nombre"],
                               "cantidad":cant,"precio_unit":pl["precio_venta"],"subtotal":sub})
            total = sum(i["subtotal"] for i in items)
            hora = f"{random.randint(11,21):02d}:{random.randint(0,59):02d}"
            estado = random.choices(["cerrado","cancelado"],[4,1])[0]
            datos["pedidos"][pedid] = {
                "id":pedid,"tipo":random.choices(["local","domicilio"],[3,1])[0],
                "mesa_id":random.choice(mids) if mids else "",
                "mesero_id":random.choice(eids) if eids else "",
                "items":items,"total":total,"estado":estado,
                "fecha":f"{fecha_sim}T{hora}:00","activo":True,"cliente_id":""
            }
            iid = f"ING-{pedid}"
            datos["finanzas"][iid] = {"id":iid,"tipo":"ingreso",
                "concepto":f"Pedido {pedid}","monto":total,
                "fecha":str(fecha_sim),"activo":True}
            total_peds += 1; total_ventas += total
    # Gastos
    for concepto, monto in [("Arriendo",2_500_000),("Servicios",400_000),
                             ("Insumos",800_000),("Nómina",5_000_000)]:
        gid = nuevo_id("finanzas","MVF")
        datos["finanzas"][gid] = {"id":gid,"tipo":"egreso","concepto":concepto,
            "monto":monto,"fecha":str(hoy),"activo":True}
    guardar()
    return jsonify({"ok":True,"pedidos":total_peds,"ventas":total_ventas,"dias":dias})

# ═══════════════════════════════════════════════════════════════════════════════
# API - GUARDAR
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/guardar", methods=["POST"])
def api_guardar():
    guardar()
    return jsonify({"ok": True})

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  PGSR - Restaurante 'Donde Siempre'")
    print("  Servidor iniciado en: http://localhost:5000")
    print("  Universidad Popular del Cesar - Grupo 10")
    print("="*60 + "\n")
    app.run(debug=True, port=5000)
