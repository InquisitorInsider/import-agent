"""Panel de importación (HTML + JS en un solo archivo, sin dependencias).

Tabs disponibles y su permiso requerido:
  resumen   — siempre
  importar  — importar
  buscar    — buscar
  sync      — sync
  factura   — factura
  tokens    — tokens   (administrador de tokens API)
  usuarios  — usuarios (administrador de usuarios del panel)
  config    — config
"""

PAGE = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>import-agent · Ruta80</title>
<style>
  :root{
    --bg:#0f1115; --panel:#181b22; --panel2:#1f232c; --line:#2a2f3a;
    --txt:#e6e9ef; --muted:#9aa3b2; --acc:#ff7a18; --acc2:#36c; --ok:#2faa5e;
    --warn:#e0a106; --bad:#d9534f; --chip:#252a34;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
       font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
  header{display:flex;align-items:center;gap:12px;padding:16px 22px;
         border-bottom:1px solid var(--line);background:var(--panel)}
  header h1{font-size:18px;margin:0;font-weight:650}
  header .badge{background:var(--acc);color:#1a1206;border-radius:6px;
       padding:2px 8px;font-size:12px;font-weight:700}
  main{max-width:1080px;margin:0 auto;padding:22px}
  h2{font-size:15px;text-transform:uppercase;letter-spacing:.04em;
     color:var(--muted);margin:26px 0 12px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
        padding:18px;margin-bottom:14px}
  .grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
  .stat{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:14px}
  .stat .n{font-size:26px;font-weight:700}
  .stat .l{color:var(--muted);font-size:13px}
  .modulos{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
  .modulo{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px;
          display:flex;flex-direction:column;gap:10px}
  .modulo.soon{opacity:.55;border-style:dashed}
  .modulo h3{margin:0;font-size:16px;display:flex;align-items:center;gap:8px}
  .modulo p{margin:0;color:var(--muted);font-size:13px}
  .row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
  label{display:block;font-size:13px;color:var(--muted);margin:8px 0 4px}
  input,select{background:var(--panel2);border:1px solid var(--line);color:var(--txt);
       border-radius:8px;padding:9px 10px;font-size:14px;width:100%}
  input[type=checkbox]{width:auto;margin:0}
  .two{display:grid;grid-template-columns:1fr 1fr;gap:10px}
  .three{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
  button{background:var(--acc);color:#1a1206;border:0;border-radius:8px;
         padding:10px 16px;font-size:14px;font-weight:650;cursor:pointer}
  button.sec{background:var(--chip);color:var(--txt);border:1px solid var(--line)}
  button.ghost{background:transparent;color:var(--acc);border:1px solid var(--acc)}
  button.danger{background:transparent;color:var(--bad);border:1px solid var(--bad)}
  button.sm{padding:6px 10px;font-size:12px}
  button:disabled{opacity:.5;cursor:default}
  .chip{display:inline-block;background:var(--chip);border:1px solid var(--line);
        border-radius:20px;padding:2px 10px;font-size:12px;color:var(--muted)}
  .chip.ok{color:var(--ok);border-color:var(--ok)}
  .chip.bad{color:var(--bad);border-color:var(--bad)}
  .chip.warn{color:var(--warn);border-color:var(--warn)}
  table{width:100%;border-collapse:collapse;font-size:13.5px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:middle}
  th{color:var(--muted);font-weight:600;position:sticky;top:0;background:var(--panel)}
  .scroll{max-height:360px;overflow:auto;border:1px solid var(--line);border-radius:10px}
  .muted{color:var(--muted)}
  .susp{color:var(--warn);font-weight:600}
  .tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px}
  .tabs button{background:var(--chip);color:var(--muted);border:1px solid var(--line);font-weight:600}
  .tabs button.active{background:var(--acc);color:#1a1206;border-color:var(--acc)}
  .hide{display:none}
  pre{background:#0b0d11;border:1px solid var(--line);border-radius:8px;padding:12px;
      overflow:auto;font-size:12.5px;color:#cdd6e6}
  #toast{position:fixed;right:18px;bottom:18px;background:var(--panel2);
         border:1px solid var(--line);border-left:4px solid var(--acc);
         border-radius:8px;padding:12px 16px;max-width:360px;opacity:0;
         transform:translateY(8px);transition:.2s}
  #toast.show{opacity:1;transform:none}
  a{color:var(--acc2)}
  /* permisos */
  .perm-grid{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0}
  .perm-cb{display:flex;align-items:center;gap:6px;
            background:var(--panel2);border:1px solid var(--line);border-radius:8px;
            padding:7px 12px;cursor:pointer;color:var(--txt);font-size:13px;
            user-select:none;transition:border-color .15s}
  .perm-cb:has(input:checked){border-color:var(--acc);color:var(--acc)}
  .perm-cb input{accent-color:var(--acc)}
  /* reveal box token */
  .token-reveal{background:#0b0d11;border:1px solid var(--ok);border-radius:10px;
                padding:14px;margin-top:12px}
  .token-reveal label{color:var(--ok);margin-bottom:6px}
  .token-reveal input{font-family:monospace;font-size:13px;background:#0b0d11;
                       border-color:var(--ok)}
  /* acciones inline */
  .acts{display:flex;gap:6px;flex-wrap:wrap}
</style>
</head>
<body>
<header>
  <h1>import-agent</h1><span class="badge">Ruta80</span>
  <span id="hstate" class="chip" style="margin-left:auto">cargando…</span>
  <span id="current-user" class="muted" style="font-size:13px"></span>
</header>
<main>
  <div class="tabs">
    <button data-tab="resumen" class="active">Resumen</button>
    <button data-tab="importar" data-require="importar">Importaciones</button>
    <button data-tab="buscar"   data-require="buscar">Buscar (prueba)</button>
    <button data-tab="sync"     data-require="sync">Sincronizar con el bot</button>
    <button data-tab="factura"  data-require="factura">Facturación</button>
    <button data-tab="tokens"   data-require="tokens">Tokens API</button>
    <button data-tab="usuarios" data-require="usuarios">Usuarios</button>
    <button data-tab="config"   data-require="config">Configuración</button>
  </div>

  <!-- ── RESUMEN ─────────────────────────────────────────────────────────── -->
  <section id="t-resumen">
    <div class="grid">
      <div class="stat"><div class="n" id="s-cli">–</div><div class="l">Clientes en el índice</div></div>
      <div class="stat"><div class="n" id="s-dir">–</div><div class="l">Direcciones en el índice</div></div>
      <div class="stat"><div class="n" id="s-bot">–</div><div class="l">BD del bot</div></div>
    </div>
    <div class="card" style="margin-top:14px">
      <h3 style="margin:0 0 8px">Última importación</h3>
      <div id="s-ultima" class="muted">—</div>
    </div>
    <p class="muted">El bot consulta <code>GET /clientes/buscar?celular=…</code> en tiempo real
      contra este índice. La importación masiva refresca el índice desde el DBF.</p>
  </section>

  <!-- ── IMPORTACIONES ───────────────────────────────────────────────────── -->
  <section id="t-importar" class="hide">
    <div class="card">
      <div class="row" style="justify-content:space-between">
        <span class="muted">Origen de datos: <b id="imp-src-label">—</b></span>
        <span id="imp-src-chip" class="chip">sin probar</span>
      </div>
      <p class="muted" style="font-size:13px;margin:10px 0 0">
        El origen DBF se define y se prueba en la pestaña
        <a href="#" onclick="goTab('config');return false">Configuración</a>.
        Conviene probar la conexión antes de importar.</p>
    </div>
    <h2>Módulos de importación</h2>
    <div class="modulos">
      <div class="modulo">
        <h3>👤 Clientes &amp; direcciones</h3>
        <p>Importa nombre, celular y dirección desde <code>clientesdomicilio.dbf</code> y
           <code>direccionesdomicilio.dbf</code>. Solo celulares de
           <b id="m-digits">9</b> dígitos numéricos.</p>
        <div class="row">
          <button onclick="importar()" id="btn-imp">Importación masiva</button>
          <span id="imp-state" class="chip">—</span>
        </div>
        <div id="imp-result"></div>
      </div>
      <div class="modulo soon">
        <h3>🍗 Productos / catálogo</h3>
        <p>Próximamente.</p>
        <button class="sec" disabled>Pendiente</button>
      </div>
      <div class="modulo soon">
        <h3>🧾 Histórico de pedidos</h3>
        <p>Próximamente.</p>
        <button class="sec" disabled>Pendiente</button>
      </div>
    </div>
  </section>

  <!-- ── BUSCAR ──────────────────────────────────────────────────────────── -->
  <section id="t-buscar" class="hide">
    <div class="card">
      <p class="muted">Simula la consulta que hará el bot cuando no encuentre al cliente.</p>
      <div class="row">
        <input id="q-cel" placeholder="51999888777 / 999888777 / ...@s.whatsapp.net" style="max-width:420px">
        <button onclick="buscar()">Buscar</button>
      </div>
      <div id="b-result" style="margin-top:14px"></div>
    </div>
    <div class="card">
      <div class="row" style="justify-content:space-between">
        <h3 style="margin:0">Listado del índice</h3>
        <input id="q-list" placeholder="filtrar nombre/celular" oninput="listar()" style="max-width:280px">
      </div>
      <div class="scroll" style="margin-top:10px">
        <table><thead><tr><th>Celular</th><th>Nombre</th><th>Tel.</th></tr></thead>
        <tbody id="list-body"></tbody></table>
      </div>
      <div class="row" style="margin-top:10px">
        <button class="sec" onclick="pg(-1)">◀</button>
        <span id="pg-info" class="muted">—</span>
        <button class="sec" onclick="pg(1)">▶</button>
      </div>
    </div>
  </section>

  <!-- ── SYNC ────────────────────────────────────────────────────────────── -->
  <section id="t-sync" class="hide">
    <div class="card">
      <p class="muted">Compara el índice (DBF) contra los clientes que ya existen en el bot,
        cruzando por celular.</p>
      <div class="row">
        <button onclick="diff()" id="btn-diff">Comparar diferencias</button>
        <span id="diff-state" class="chip">—</span>
      </div>
      <div id="diff-summary" class="grid" style="margin-top:14px"></div>
    </div>
    <div id="diff-tables"></div>
  </section>

  <!-- ── TOKENS API ──────────────────────────────────────────────────────── -->
  <section id="t-tokens" class="hide">
    <p class="muted">Cada aplicación que se conecte (bot, facturador, otro sistema) debe
      tener su propio token. Si revocas uno, solo esa aplicación pierde acceso.</p>

    <h2>Crear nuevo token</h2>
    <div class="card">
      <label>Nombre de la aplicación</label>
      <input id="tk-name" placeholder="Ej: Bot WhatsApp, Facturador OSE, Panel Ventas" style="max-width:480px">
      <label style="margin-top:12px">Permisos de acceso</label>
      <div class="perm-grid">
        <label class="perm-cb"><input type="checkbox" id="tk-p-clientes" checked> Clientes <span class="muted">(GET /clientes/buscar)</span></label>
        <label class="perm-cb"><input type="checkbox" id="tk-p-facturacion" checked> Facturación <span class="muted">(GET|POST /facturacion/*)</span></label>
      </div>
      <div class="row" style="margin-top:12px">
        <button onclick="crearToken()">Crear token</button>
      </div>
      <div id="tk-reveal" class="hide token-reveal">
        <label>Token creado — cópialo ahora, no se volverá a mostrar completo:</label>
        <div class="row">
          <input id="tk-reveal-val" readonly onclick="this.select()" style="font-family:monospace">
          <button class="sec" onclick="copiarTokenReveal()">Copiar</button>
        </div>
        <p class="muted" style="font-size:12.5px;margin:6px 0 0">
          Configura esta cadena en la aplicación como
          <code>Authorization: Bearer &lt;TOKEN&gt;</code></p>
      </div>
    </div>

    <h2>Tokens existentes</h2>
    <div class="card">
      <div id="tk-lista">
        <p class="muted">Cargando…</p>
      </div>
    </div>
  </section>

  <!-- ── USUARIOS ────────────────────────────────────────────────────────── -->
  <section id="t-usuarios" class="hide">
    <p class="muted">Cada usuario del panel tiene su propia contraseña y solo puede acceder
      a las secciones para las que tiene permiso.</p>

    <h2>Crear nuevo usuario</h2>
    <div class="card">
      <div class="two">
        <div><label>Usuario</label><input id="usr-name" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="juan.perez"></div>
        <div><label>Contraseña</label><input id="usr-pass" type="password" autocomplete="new-password" placeholder="Mínimo 6 caracteres"></div>
      </div>
      <label style="margin-top:12px">Permisos (secciones del panel)</label>
      <div class="perm-grid" id="usr-perms-new">
        <label class="perm-cb"><input type="checkbox" value="importar"> Importaciones</label>
        <label class="perm-cb"><input type="checkbox" value="buscar"> Buscar (prueba)</label>
        <label class="perm-cb"><input type="checkbox" value="sync"> Sincronizar</label>
        <label class="perm-cb"><input type="checkbox" value="factura"> Facturación</label>
        <label class="perm-cb"><input type="checkbox" value="config"> Configuración</label>
        <label class="perm-cb"><input type="checkbox" value="tokens"> Tokens API</label>
        <label class="perm-cb"><input type="checkbox" value="usuarios"> Usuarios</label>
        <label class="perm-cb"><input type="checkbox" value="*"> Acceso total (*)</label>
      </div>
      <div class="row" style="margin-top:12px">
        <button onclick="crearUsuario()">Crear usuario</button>
      </div>
    </div>

    <h2>Usuarios existentes</h2>
    <div class="card">
      <div id="usr-lista">
        <p class="muted">Cargando…</p>
      </div>
    </div>

    <!-- formulario de edición inline -->
    <div id="usr-edit-card" class="card hide">
      <div class="row" style="justify-content:space-between;margin-bottom:12px">
        <h3 style="margin:0">Editando: <span id="usr-edit-name" style="color:var(--acc)"></span></h3>
        <button class="sec sm" onclick="cerrarEditUser()">✕ Cancelar</button>
      </div>
      <label>Nueva contraseña (dejar vacío para no cambiarla)</label>
      <input id="usr-edit-pass" type="password" autocomplete="new-password" placeholder="Nueva contraseña" style="max-width:360px">
      <label style="margin-top:12px">Permisos</label>
      <div class="perm-grid" id="usr-perms-edit">
        <label class="perm-cb"><input type="checkbox" value="importar"> Importaciones</label>
        <label class="perm-cb"><input type="checkbox" value="buscar"> Buscar (prueba)</label>
        <label class="perm-cb"><input type="checkbox" value="sync"> Sincronizar</label>
        <label class="perm-cb"><input type="checkbox" value="factura"> Facturación</label>
        <label class="perm-cb"><input type="checkbox" value="config"> Configuración</label>
        <label class="perm-cb"><input type="checkbox" value="tokens"> Tokens API</label>
        <label class="perm-cb"><input type="checkbox" value="usuarios"> Usuarios</label>
        <label class="perm-cb"><input type="checkbox" value="*"> Acceso total (*)</label>
      </div>
      <div class="row" style="margin-top:12px">
        <button onclick="guardarUsuario()">Guardar cambios</button>
      </div>
    </div>
  </section>

  <!-- ── CONFIG ──────────────────────────────────────────────────────────── -->
  <section id="t-config" class="hide">
    <h2>Origen de los datos (DBF)</h2>
    <div class="card">
      <label>Tipo de origen</label>
      <select id="src_type" onchange="toggleSrc()">
        <option value="smb">Carpeta compartida en red (SMB)</option>
        <option value="local">Carpeta local / volumen montado</option>
      </select>
      <div id="src_smb">
        <div class="three">
          <div><label>Host / IP (SMB)</label><input id="smb_host" placeholder="192.168.1.X"></div>
          <div><label>Recurso compartido</label><input id="smb_share" placeholder="DATOS"></div>
          <div><label>Subcarpeta (opcional)</label><input id="smb_path" placeholder="domicilio"></div>
        </div>
        <div class="three">
          <div><label>Usuario (vacío = abierto)</label><input id="smb_user" autocomplete="off" autocapitalize="off" spellcheck="false"></div>
          <div><label>Clave</label><input id="smb_pass" type="password" autocomplete="new-password" placeholder="(sin cambios)"></div>
          <div><label>Dominio</label><input id="smb_domain" placeholder="WORKGROUP"></div>
        </div>
      </div>
      <div id="src_local" class="hide">
        <label>Carpeta dentro del contenedor</label>
        <input id="local_dir" placeholder="/dbf">
      </div>
      <div class="two">
        <div><label>Archivo de clientes</label><input id="clientes_file" placeholder="clientesdomicilio.dbf"></div>
        <div><label>Archivo de direcciones</label><input id="direcciones_file" placeholder="direccionesdomicilio.dbf"></div>
      </div>
      <div class="row" style="margin-top:12px">
        <button class="sec" onclick="saveSource()">Guardar origen</button>
        <button class="ghost" id="btn-probar" onclick="probarConexion()">Probar conexión</button>
        <span id="probar-state" class="chip">—</span>
        <span class="muted">Solo lectura: el agente nunca escribe en el DBF.</span>
      </div>
      <div id="probar-result"></div>
    </div>

    <div class="card">
      <h3 style="margin:0 0 8px">Conexión con el bot</h3>
      <label>Ruta del SQLite del bot (montado en el contenedor)</label>
      <input id="bot_db_path" placeholder="/bot/pedidos.db">
      <p class="muted" style="font-size:13px">Solo se usa para el panel de sincronización.</p>
      <label>Codificación del DBF</label>
      <input id="dbf_encoding" placeholder="cp1252">
      <div class="row" style="margin-top:12px"><button class="sec" onclick="saveGlobals()">Guardar</button></div>
      <p class="muted" style="font-size:13px;margin-top:10px">
        Los tokens de acceso para el bot y el facturador se gestionan en la pestaña
        <a href="#" onclick="goTab('tokens');return false">Tokens API</a>.</p>
    </div>

    <div class="card">
      <h3 style="margin:0 0 8px">Integración del bot (referencia)</h3>
      <pre id="snippet"></pre>
    </div>
  </section>

  <!-- ── FACTURACION ─────────────────────────────────────────────────────── -->
  <section id="t-factura" class="hide">
    <p class="muted">Todo esto es editable: si SUNAT cambia tasas, series o códigos, lo ajustas aquí
      sin tocar el código.</p>

    <h2>Datos del emisor</h2>
    <div class="card">
      <div class="two">
        <div><label>RUC</label><input id="fc_ruc" placeholder="20XXXXXXXXX"></div>
        <div><label>Razón social</label><input id="fc_razon_social"></div>
      </div>
      <div class="two">
        <div><label>Nombre comercial</label><input id="fc_nombre_comercial"></div>
        <div><label>Domicilio fiscal</label><input id="fc_domicilio_fiscal"></div>
      </div>
      <div class="three">
        <div><label>Ubigeo</label><input id="fc_ubigeo" placeholder="150101"></div>
        <div><label>Distrito</label><input id="fc_distrito"></div>
        <div><label>Provincia</label><input id="fc_provincia"></div>
      </div>
      <div class="three">
        <div><label>Departamento</label><input id="fc_departamento"></div>
        <div><label>Serie boleta</label><input id="fc_serie_boleta" placeholder="B001"></div>
        <div><label>Serie factura</label><input id="fc_serie_factura" placeholder="F001"></div>
      </div>
      <div class="three">
        <div><label>Moneda</label><input id="fc_moneda" placeholder="PEN"></div>
      </div>
    </div>

    <h2>IGV por rango de fechas (cálculo inverso)</h2>
    <div class="card">
      <p class="muted" style="font-size:13px;margin-top:0">El total = IGV + IPM. La base se calcula
        <code>base = TOTAL ÷ (1 + (IGV+IPM)/100)</code> según la fecha de la venta.</p>
      <div class="scroll" style="max-height:none">
        <table><thead><tr><th>Desde (YYYY-MM-DD)</th><th>Hasta</th><th>IGV %</th><th>IPM %</th>
          <th>Total %</th><th></th></tr></thead>
          <tbody id="fc-reglas"></tbody></table>
      </div>
      <div class="row" style="margin-top:10px"><button class="sec" onclick="addRegla()">+ Agregar regla</button></div>
    </div>

    <h2>Formas de pago (control interno)</h2>
    <div class="card">
      <div class="scroll" style="max-height:none">
        <table><thead><tr><th>Código POS</th><th>Nombre</th><th></th></tr></thead>
          <tbody id="fc-pagos"></tbody></table>
      </div>
      <div class="row" style="margin-top:10px"><button class="sec" onclick="addPago()">+ Agregar forma de pago</button></div>
    </div>

    <h2>Catálogos SUNAT</h2>
    <div class="card">
      <div class="three">
        <div><label>Tipo boleta</label><input id="fc_tipo_boleta" placeholder="03"></div>
        <div><label>Tipo factura</label><input id="fc_tipo_factura" placeholder="01"></div>
        <div><label>Afectación IGV</label><input id="fc_afectacion_igv" placeholder="10"></div>
      </div>
      <div class="three">
        <div><label>Unidad de medida</label><input id="fc_unidad_medida" placeholder="NIU"></div>
        <div><label>Doc. DNI</label><input id="fc_doc_dni" placeholder="1"></div>
        <div><label>Doc. RUC</label><input id="fc_doc_ruc" placeholder="6"></div>
      </div>
      <div class="three">
        <div><label>Doc. sin documento</label><input id="fc_doc_sin" placeholder="0"></div>
        <div><label>Forma de pago SUNAT</label><input id="fc_forma_pago_sunat" placeholder="Contado"></div>
        <div><label>Umbral DNI en boleta (S/)</label><input id="fc_umbral_dni_boleta" placeholder="700"></div>
      </div>
      <div class="row" style="margin-top:12px">
        <button onclick="saveFactura()">Guardar configuración</button>
        <span id="fc-state" class="chip">—</span>
      </div>
    </div>

    <h2>Probar con datos reales</h2>
    <div class="card">
      <div class="row">
        <input id="fc-folio" placeholder="N° de folio, ej. 65271" style="max-width:240px">
        <button onclick="probarFolio()">Ver comprobante</button>
        <input type="date" id="fc-fecha" style="max-width:200px">
        <button class="sec" onclick="probarFecha()">Ver ventas del día</button>
      </div>
      <div id="fc-prueba-info" class="muted" style="margin-top:10px"></div>
      <pre id="fc-prueba"></pre>
    </div>

    <h2>Contrato de salida</h2>
    <div class="card">
      <pre id="fc-contrato"></pre>
    </div>
  </section>
</main>
<div id="toast"></div>

<script>
const $=id=>document.getElementById(id);
let S=null, pgOff=0, lastDiff=null;

// ── Utilidades ─────────────────────────────────────────────────────────────────
function toast(m){const t=$('toast');t.textContent=m;t.classList.add('show');
  clearTimeout(t._t);t._t=setTimeout(()=>t.classList.remove('show'),3200);}
async function api(path,opts){const r=await fetch(path,opts);
  if(!r.ok){let d='';try{d=(await r.json()).detail}catch(e){}
    throw new Error(d||('HTTP '+r.status));} return r.json();}
function esc(s){return(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function esc2(s){return String(s==null?'':s).replace(/"/g,'&quot;');}

// ── Tabs ───────────────────────────────────────────────────────────────────────
const ALL_TABS=['resumen','importar','buscar','sync','factura','tokens','usuarios','config'];
function goTab(name){
  document.querySelectorAll('.tabs button').forEach(x=>
    x.classList.toggle('active',x.dataset.tab===name));
  ALL_TABS.forEach(t=>$('t-'+t).classList.toggle('hide',t!==name));
  if(name==='tokens')loadTokens();
  if(name==='usuarios')loadUsuarios();
}
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>goTab(b.dataset.tab));

// ── Permisos del usuario actual ────────────────────────────────────────────────
function hasPerm(perms,p){return perms.includes('*')||perms.includes(p);}
function applyPerms(perms){
  document.querySelectorAll('.tabs button[data-tab]').forEach(btn=>{
    const req=btn.dataset.require;
    btn.style.display=(!req||hasPerm(perms,req))?'':'none';
  });
}

// ── Carga inicial ──────────────────────────────────────────────────────────────
async function load(){
  try{
    const me=await api('/api/me');
    applyPerms(me.permisos);
    $('current-user').textContent='usuario: '+me.username;
  }catch(e){}
  S=await api('/api/settings');fillSettings();listar();
  loadFactura().catch(()=>{});
}

// ── Settings ───────────────────────────────────────────────────────────────────
function fillSettings(){
  const s=S.source||{};
  $('src_type').value=s.source_type||'smb'; toggleSrc();
  $('smb_host').value=s.smb_host||''; $('smb_share').value=s.smb_share||'';
  $('smb_path').value=s.smb_path||''; $('smb_user').value=s.smb_user||'';
  $('smb_domain').value=s.smb_domain||'WORKGROUP'; $('local_dir').value=s.local_dir||'';
  $('clientes_file').value=s.clientes_file||''; $('direcciones_file').value=s.direcciones_file||'';
  $('imp-src-label').textContent=(s.source_type==='local')
    ?('local · '+(s.local_dir||'—'))
    :('//'+(s.smb_host||'—')+'/'+(s.smb_share||'')+(s.smb_path?'/'+s.smb_path:''));
  $('bot_db_path').value=S.bot_db_path||''; $('dbf_encoding').value=S.dbf_encoding||'cp1252';
  $('m-digits').textContent=S.phone_digits;
  $('s-cli').textContent=S.index.clientes; $('s-dir').textContent=S.index.direcciones;
  $('s-bot').textContent=S.bot_db_disponible?'conectada':'no conectada';
  $('hstate').textContent=S.index.clientes+' clientes';
  const u=S.index.ultima_importacion;
  $('s-ultima').innerHTML=u?('Fecha: <b>'+u.fecha+'</b> · '+u.clientes+' clientes · '
     +u.direcciones+' direcciones'+(u.direcciones_huerfanas_omitidas?
     ' · '+u.direcciones_huerfanas_omitidas+' direcciones huérfanas omitidas':'')):'—';
  $('snippet').textContent=BOT_SNIPPET;
}
function toggleSrc(){const v=$('src_type').value;
  $('src_smb').classList.toggle('hide',v!=='smb');
  $('src_local').classList.toggle('hide',v!=='local');}
async function saveSource(quiet){
  const p={source_type:$('src_type').value,smb_host:$('smb_host').value,
    smb_share:$('smb_share').value,smb_path:$('smb_path').value,smb_user:$('smb_user').value,
    smb_pass:$('smb_pass').value,smb_domain:$('smb_domain').value,local_dir:$('local_dir').value,
    clientes_file:$('clientes_file').value,direcciones_file:$('direcciones_file').value};
  S=await api('/api/source',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
  fillSettings();if(!quiet)toast('Origen guardado');}
async function probarConexion(){
  $('btn-probar').disabled=true;
  $('probar-state').textContent='probando…';$('probar-state').className='chip';
  $('probar-result').innerHTML='';
  try{
    await saveSource(true);
    const r=await api('/api/source/probar',{method:'POST'});
    $('probar-state').textContent='conexión OK';$('probar-state').className='chip ok';
    $('imp-src-chip').textContent='conexión OK';$('imp-src-chip').className='chip ok';
    $('probar-result').innerHTML='<div class="grid" style="margin-top:12px">'
      +r.archivos.map(a=>stat(a.existe?(a.tamano_kb.toLocaleString()+' KB'):'no está',a.nombre)).join('')
      +'</div>';
    toast('Conexión correcta');
  }catch(e){
    $('probar-state').textContent='falló';$('probar-state').className='chip bad';
    $('imp-src-chip').textContent='conexión falló';$('imp-src-chip').className='chip bad';
    $('probar-result').innerHTML='<p class="chip bad" style="margin-top:10px">'+e.message+'</p>';
  }
  $('btn-probar').disabled=false;}
async function saveGlobals(){
  const p={bot_db_path:$('bot_db_path').value,dbf_encoding:$('dbf_encoding').value};
  S=await api('/api/globals',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
  fillSettings();toast('Configuración guardada');}

// ── Importar ───────────────────────────────────────────────────────────────────
async function importar(){
  $('btn-imp').disabled=true;$('imp-state').textContent='importando…';
  try{const r=await api('/api/importar',{method:'POST'});
    const c=r.dbf_stats.clientes,d=r.dbf_stats.direcciones;
    $('imp-state').textContent='listo';$('imp-state').className='chip ok';
    $('imp-result').innerHTML=
      '<div class="grid" style="margin-top:12px">'
      +stat(r.resumen.clientes,'Clientes importados')
      +stat(r.resumen.direcciones,'Direcciones importadas')
      +stat(c.omitidos_idcliente_invalido,'Omitidos: celular inválido')
      +stat(c.omitidos_sin_nombre,'Omitidos: sin nombre')
      +stat(c.telefono1_distinto,'TELEFONO1 ≠ idcliente')
      +stat(d.con_referencia,'Direcciones con referencia')
      +'</div>';
    S=await api('/api/settings');fillSettings();toast('Importación completa');
  }catch(e){$('imp-state').textContent='error';$('imp-state').className='chip bad';
    $('imp-result').innerHTML='<p class="chip bad" style="margin-top:10px">'+e.message+'</p>';}
  $('btn-imp').disabled=false;}
function stat(n,l){return '<div class="stat"><div class="n">'+n+'</div><div class="l">'+l+'</div></div>';}

// ── Buscar ─────────────────────────────────────────────────────────────────────
async function buscar(){
  const cel=$('q-cel').value.trim();if(!cel)return;
  try{const r=await api('/api/clientes/buscar?celular='+encodeURIComponent(cel));
    let h='<div class="card" style="background:var(--panel2)"><b>'+r.nombre+'</b> '
      +'<span class="chip ok">'+r.celular+'</span>';
    if(r.direcciones.length){h+='<ul>';r.direcciones.forEach(d=>{h+='<li>'+(d.calle||'')
      +(d.referencia?' <span class="muted">('+d.referencia+')</span>':'')+'</li>';});h+='</ul>';}
    else h+='<p class="muted">sin direcciones</p>';
    $('b-result').innerHTML=h+'</div>';
  }catch(e){$('b-result').innerHTML='<p class="chip bad">'+e.message+'</p>';}}
async function listar(){
  const q=$('q-list').value.trim();
  const r=await api('/api/clientes?limit=20&offset='+pgOff+'&q='+encodeURIComponent(q));
  $('list-body').innerHTML=r.items.map(c=>'<tr><td>'+c.celular+'</td><td>'+c.nombre
    +'</td><td class="muted">'+(c.telefono||'')+'</td></tr>').join('')
    ||'<tr><td colspan=3 class="muted">sin resultados</td></tr>';
  $('pg-info').textContent=(r.total?(pgOff+1)+'–'+Math.min(pgOff+20,r.total):0)+' de '+r.total;}
function pg(d){pgOff=Math.max(0,pgOff+d*20);listar();}

// ── Sync ───────────────────────────────────────────────────────────────────────
async function diff(){
  $('btn-diff').disabled=true;$('diff-state').textContent='comparando…';
  try{const r=await api('/api/sync/diff');lastDiff=r;
    $('diff-state').textContent='listo';$('diff-state').className='chip ok';
    const s=r.resumen;
    $('diff-summary').innerHTML=
      stat(s.nombre_distinto,'Nombres distintos')
      +stat(s.de_esos_bot_sospechoso,'…de esos, bot sospechoso')
      +stat(s.falta_direccion,'Bot sin dirección (DBF sí)')
      +stat(s.solo_en_bot,'Solo en el bot');
    renderDiff(r);
  }catch(e){$('diff-state').textContent='error';$('diff-state').className='chip bad';
    $('diff-tables').innerHTML='<p class="chip bad">'+e.message+'</p>';}
  $('btn-diff').disabled=false;}
function renderDiff(r){
  let h='';
  if(r.nombre_distinto.length){
    h+='<div class="card"><div class="row" style="justify-content:space-between">'
      +'<h3 style="margin:0">Nombres distintos</h3>'
      +'<div class="row" style="gap:8px">'
      +'<button class="sec" onclick="markSusp()">Marcar sospechosos</button>'
      +'<button class="ghost" onclick="aplicarNombres()">Corregir los marcados →</button></div></div>'
      +'<div class="scroll" style="margin-top:10px"><table><thead><tr>'
      +'<th><input type=checkbox onclick="toggleAll(this)"></th><th>Celular</th>'
      +'<th>Nombre en el BOT</th><th>Nombre en el DBF</th></tr></thead><tbody>';
    r.nombre_distinto.forEach((x,i)=>{
      h+='<tr><td><input type=checkbox class="cbn" data-i="'+i+'"'+(x.bot_sospechoso?' checked':'')+'></td>'
        +'<td>'+x.celular+'</td><td class="'+(x.bot_sospechoso?'susp':'')+'">'+esc(x.nombre_bot)
        +(x.bot_sospechoso?' ⚠':'')+'</td><td>'+esc(x.nombre_dbf)+'</td></tr>';});
    h+='</tbody></table></div></div>';}
  if(r.falta_direccion.length){
    h+='<div class="card"><div class="row" style="justify-content:space-between">'
      +'<h3 style="margin:0">Bot sin dirección (el DBF tiene una)</h3>'
      +'<button class="ghost" onclick="aplicarDir()">Agregar las marcadas →</button></div>'
      +'<div class="scroll" style="margin-top:10px"><table><thead><tr>'
      +'<th><input type=checkbox onclick="toggleAllD(this)"></th><th>Celular</th>'
      +'<th>Cliente</th><th>Dirección del DBF</th></tr></thead><tbody>';
    r.falta_direccion.forEach((x,i)=>{
      h+='<tr><td><input type=checkbox class="cbd" data-i="'+i+'" checked></td>'
        +'<td>'+x.celular+'</td><td>'+esc(x.nombre_bot)+'</td><td>'+esc(x.calle_dbf)
        +(x.referencia_dbf?' <span class="muted">('+esc(x.referencia_dbf)+')</span>':'')+'</td></tr>';});
    h+='</tbody></table></div></div>';}
  $('diff-tables').innerHTML=h||'<p class="muted">Sin diferencias.</p>';}
function toggleAll(c){document.querySelectorAll('.cbn').forEach(x=>x.checked=c.checked);}
function toggleAllD(c){document.querySelectorAll('.cbd').forEach(x=>x.checked=c.checked);}
async function aplicarNombres(){
  const acciones=[];
  document.querySelectorAll('.cbn').forEach(cb=>{
    if(cb.checked){const x=lastDiff.nombre_distinto[+cb.dataset.i];
      acciones.push({celular:x.celular,lid:x.lid,tipo:'nombre'});}});
  await aplicar(acciones,'nombres');}
function markSusp(){document.querySelectorAll('.cbn').forEach(cb=>{
  cb.checked=!!lastDiff.nombre_distinto[+cb.dataset.i].bot_sospechoso;});}
async function aplicarDir(){
  const acciones=[];
  document.querySelectorAll('.cbd').forEach(cb=>{
    if(cb.checked){const x=lastDiff.falta_direccion[+cb.dataset.i];
      acciones.push({celular:x.celular,lid:x.lid,tipo:'direccion'});}});
  await aplicar(acciones,'direcciones');}
async function aplicar(acciones,label){
  if(!acciones.length){toast('Nada marcado');return;}
  if(!confirm('Se actualizarán '+acciones.length+' '+label+' en la BD del bot. ¿Continuar?'))return;
  try{const r=await api('/api/sync/aplicar',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({acciones})});
    toast('Aplicado: '+(r.nombre+' nombres, '+r.direccion+' direcciones'
      +(r.errores.length?', '+r.errores.length+' errores':'')));
    diff();
  }catch(e){toast('Error: '+e.message);}}

// ══════════════════════════════════════════════════════════════════════════════
//  Tokens API
// ══════════════════════════════════════════════════════════════════════════════
let _tokensLoaded=false;
async function loadTokens(){
  if(!$('tk-lista'))return;
  try{
    const list=await api('/api/tokens');
    renderTokens(list);_tokensLoaded=true;
  }catch(e){$('tk-lista').innerHTML='<p class="chip bad">'+e.message+'</p>';}
}
function renderTokens(list){
  if(!list.length){
    $('tk-lista').innerHTML='<p class="muted">Aún no hay tokens. Crea el primero arriba.</p>';
    return;}
  let h='<div class="scroll"><table><thead><tr>'
    +'<th>Nombre / Aplicación</th><th>Permisos</th><th>Estado</th>'
    +'<th>Vista previa</th><th>Creado</th><th>Acciones</th></tr></thead><tbody>';
  list.forEach(t=>{
    const perms=(t.permisos||[]).map(p=>'<span class="chip ok" style="font-size:11px">'+esc(p)+'</span>').join(' ');
    const estado=t.activo
      ?'<span class="chip ok">activo</span>'
      :'<span class="chip bad">inactivo</span>';
    const creado=(t.creado||'').replace('T',' ').replace('Z','');
    h+='<tr>'
      +'<td><b>'+esc(t.name)+'</b></td>'
      +'<td>'+perms+'</td>'
      +'<td>'+estado+'</td>'
      +'<td><code style="font-size:12px">'+esc(t.token_preview)+'</code></td>'
      +'<td class="muted" style="font-size:12px">'+esc(creado)+'</td>'
      +'<td><div class="acts">'
      +'<button class="sec sm" onclick="regenerarToken(\''+esc2(t.id)+'\',\''+esc2(t.name)+'\')">Regenerar</button>'
      +(t.activo
        ?'<button class="sec sm" onclick="toggleToken(\''+esc2(t.id)+'\',false)">Desactivar</button>'
        :'<button class="ghost sm" onclick="toggleToken(\''+esc2(t.id)+'\',true)">Activar</button>')
      +'<button class="danger sm" onclick="eliminarToken(\''+esc2(t.id)+'\',\''+esc2(t.name)+'\')">Eliminar</button>'
      +'</div></td></tr>';
  });
  h+='</tbody></table></div>';
  $('tk-lista').innerHTML=h;
}
function mostrarTokenReveal(tokenCompleto){
  $('tk-reveal-val').value=tokenCompleto;
  $('tk-reveal').classList.remove('hide');
  $('tk-reveal-val').select();
}
function copiarTokenReveal(){
  const i=$('tk-reveal-val');i.select();
  if(navigator.clipboard){navigator.clipboard.writeText(i.value)
    .then(()=>toast('Token copiado')).catch(()=>toast('Copia manual: Ctrl+C'));}
  else{try{document.execCommand('copy');toast('Token copiado');}catch(e){toast('Ctrl+C para copiar');}}}
async function crearToken(){
  const name=$('tk-name').value.trim();
  if(!name){toast('Ingresa el nombre de la aplicación');return;}
  const permisos=[];
  if($('tk-p-clientes').checked)permisos.push('clientes');
  if($('tk-p-facturacion').checked)permisos.push('facturacion');
  if(!permisos.length){toast('Selecciona al menos un permiso');return;}
  try{
    const t=await api('/api/tokens',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name,permisos})});
    $('tk-name').value='';
    $('tk-p-clientes').checked=true;$('tk-p-facturacion').checked=true;
    mostrarTokenReveal(t.token);
    toast('Token "'+t.name+'" creado');
    loadTokens();
  }catch(e){toast('Error: '+e.message);}
}
async function regenerarToken(id,name){
  if(!confirm('Se generará un NUEVO valor para el token "'+name+'".\nLa aplicación dejará de conectar hasta que actualices el valor. ¿Continuar?'))return;
  try{
    const t=await api('/api/tokens/'+encodeURIComponent(id)+'/regenerar',{method:'POST'});
    mostrarTokenReveal(t.token);
    toast('Token regenerado — copia el nuevo valor');
    loadTokens();
  }catch(e){toast('Error: '+e.message);}
}
async function toggleToken(id,activo){
  try{
    await api('/api/tokens/'+encodeURIComponent(id),{method:'PATCH',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({activo})});
    toast(activo?'Token activado':'Token desactivado');
    loadTokens();
  }catch(e){toast('Error: '+e.message);}
}
async function eliminarToken(id,name){
  if(!confirm('¿Eliminar el token "'+name+'" de forma permanente?'))return;
  try{
    await api('/api/tokens/'+encodeURIComponent(id),{method:'DELETE'});
    toast('Token eliminado');
    $('tk-reveal').classList.add('hide');
    loadTokens();
  }catch(e){toast('Error: '+e.message);}
}

// ══════════════════════════════════════════════════════════════════════════════
//  Usuarios
// ══════════════════════════════════════════════════════════════════════════════
let _usrEditTarget=null;
const PERM_LABELS={
  importar:'Importaciones',buscar:'Buscar (prueba)',sync:'Sincronizar',
  factura:'Facturación',config:'Configuración',tokens:'Tokens API',
  usuarios:'Usuarios','*':'Acceso total'};
const PERM_ORDEN=['importar','buscar','sync','factura','config','tokens','usuarios','*'];

async function loadUsuarios(){
  if(!$('usr-lista'))return;
  try{
    const list=await api('/api/usuarios');
    renderUsuarios(list);
  }catch(e){$('usr-lista').innerHTML='<p class="chip bad">'+e.message+'</p>';}
}
function permChips(perms){
  if(!perms||!perms.length)return '<span class="muted">sin permisos</span>';
  return perms.map(p=>{
    const label=PERM_LABELS[p]||p;
    const cls=p==='*'?'chip warn':'chip';
    return '<span class="'+cls+'" style="font-size:11px">'+esc(label)+'</span>';
  }).join(' ');}
function renderUsuarios(list){
  if(!list.length){
    $('usr-lista').innerHTML='<p class="muted">Aún no hay usuarios guardados. '
      +'(El usuario del entorno <code>ADMIN_USER</code> siempre funciona como clave maestra.)</p>';
    return;}
  let h='<div class="scroll"><table><thead><tr>'
    +'<th>Usuario</th><th>Permisos</th><th>Estado</th><th>Creado</th><th>Acciones</th>'
    +'</tr></thead><tbody>';
  list.forEach(u=>{
    const estado=u.activo
      ?'<span class="chip ok">activo</span>'
      :'<span class="chip bad">inactivo</span>';
    const creado=(u.creado||'').replace('T',' ').replace('Z','');
    h+='<tr>'
      +'<td><b>'+esc(u.username)+'</b></td>'
      +'<td>'+permChips(u.permisos)+'</td>'
      +'<td>'+estado+'</td>'
      +'<td class="muted" style="font-size:12px">'+esc(creado)+'</td>'
      +'<td><div class="acts">'
      +'<button class="sec sm" onclick="abrirEditUser(\''+esc2(u.username)+'\','+JSON.stringify(u.permisos||[])+')">Editar</button>'
      +(u.activo
        ?'<button class="sec sm" onclick="toggleUsuario(\''+esc2(u.username)+'\',false)">Desactivar</button>'
        :'<button class="ghost sm" onclick="toggleUsuario(\''+esc2(u.username)+'\',true)">Activar</button>')
      +'<button class="danger sm" onclick="eliminarUsuario(\''+esc2(u.username)+'\')">Eliminar</button>'
      +'</div></td></tr>';
  });
  h+='</tbody></table></div>';
  $('usr-lista').innerHTML=h;
}
function _readPerms(containerId){
  const out=[];
  document.querySelectorAll('#'+containerId+' input[type=checkbox]').forEach(cb=>{
    if(cb.checked)out.push(cb.value);});
  return out;}
async function crearUsuario(){
  const username=$('usr-name').value.trim();
  const password=$('usr-pass').value.trim();
  if(!username||!password){toast('Usuario y contraseña son requeridos');return;}
  if(password.length<6){toast('La contraseña debe tener al menos 6 caracteres');return;}
  const permisos=_readPerms('usr-perms-new');
  try{
    const u=await api('/api/usuarios',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({username,password,permisos})});
    $('usr-name').value='';$('usr-pass').value='';
    document.querySelectorAll('#usr-perms-new input').forEach(cb=>cb.checked=false);
    toast('Usuario "'+u.username+'" creado');
    loadUsuarios();
  }catch(e){toast('Error: '+e.message);}
}
function abrirEditUser(username,permisos){
  _usrEditTarget=username;
  $('usr-edit-name').textContent=username;
  $('usr-edit-pass').value='';
  document.querySelectorAll('#usr-perms-edit input').forEach(cb=>{
    cb.checked=permisos.includes(cb.value);});
  $('usr-edit-card').classList.remove('hide');
  $('usr-edit-card').scrollIntoView({behavior:'smooth',block:'nearest'});
}
function cerrarEditUser(){
  $('usr-edit-card').classList.add('hide');
  _usrEditTarget=null;}
async function guardarUsuario(){
  if(!_usrEditTarget)return;
  const patch={permisos:_readPerms('usr-perms-edit')};
  const pass=$('usr-edit-pass').value.trim();
  if(pass){
    if(pass.length<6){toast('La contraseña debe tener al menos 6 caracteres');return;}
    patch.password=pass;}
  try{
    const u=await api('/api/usuarios/'+encodeURIComponent(_usrEditTarget),{method:'PATCH',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)});
    toast('Usuario "'+u.username+'" actualizado');
    cerrarEditUser();loadUsuarios();
  }catch(e){toast('Error: '+e.message);}
}
async function toggleUsuario(username,activo){
  try{
    await api('/api/usuarios/'+encodeURIComponent(username),{method:'PATCH',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({activo})});
    toast(activo?'Usuario activado':'Usuario desactivado');
    loadUsuarios();
  }catch(e){toast('Error: '+e.message);}
}
async function eliminarUsuario(username){
  if(!confirm('¿Eliminar el usuario "'+username+'" de forma permanente?'))return;
  try{
    await api('/api/usuarios/'+encodeURIComponent(username),{method:'DELETE'});
    toast('Usuario eliminado');
    if(_usrEditTarget===username)cerrarEditUser();
    loadUsuarios();
  }catch(e){toast('Error: '+e.message);}
}

// ══════════════════════════════════════════════════════════════════════════════
//  Facturación
// ══════════════════════════════════════════════════════════════════════════════
let FC=null;
const FC_CONTRATO=`{
  "tipo_comprobante": "03",
  "serie": "B001", "correlativo": 1,
  "fecha_emision": "2026-06-15T16:37:00",
  "moneda": "PEN",
  "numcheque_pos": 65271,
  "cliente": { "tipo_doc": "1", "num_doc": "", "nombre": "VARIOS" },
  "items": [
    { "codigo": "0306", "descripcion": "CHURRASCO A LA PARRILLA",
      "cantidad": 1, "unidad": "NIU",
      "valor_unitario": 23.98, "precio_unitario": 26.50,
      "afectacion_igv": "10", "valor_venta": 23.98, "igv": 2.52 }
  ],
  "totales": { "gravadas": 54.66, "igv": 4.37, "ipm": 1.37,
               "importe_total": 60.40, "en_letras": "SESENTA Y 40/100 SOLES" },
  "forma_pago": "Contado",
  "medio_pago_interno": [ { "codigo": "MC", "nombre": "Izipay", "importe": 60.40 } ],
  "anulado": false, "ya_facturado": false
}`;
async function loadFactura(){
  FC=await api('/api/facturacion');
  const e=FC.emisor||{},s=FC.series||{},c=FC.catalogos||{};
  const set=(id,v)=>{if($(id))$(id).value=(v!=null?v:'');};
  set('fc_ruc',e.ruc);set('fc_razon_social',e.razon_social);set('fc_nombre_comercial',e.nombre_comercial);
  set('fc_domicilio_fiscal',e.domicilio_fiscal);set('fc_ubigeo',e.ubigeo);set('fc_distrito',e.distrito);
  set('fc_provincia',e.provincia);set('fc_departamento',e.departamento);
  set('fc_serie_boleta',s.boleta||'B001');set('fc_serie_factura',s.factura||'F001');set('fc_moneda',FC.moneda||'PEN');
  set('fc_tipo_boleta',c.tipo_boleta);set('fc_tipo_factura',c.tipo_factura);set('fc_afectacion_igv',c.afectacion_igv);
  set('fc_unidad_medida',c.unidad_medida);set('fc_doc_dni',c.doc_dni);set('fc_doc_ruc',c.doc_ruc);set('fc_doc_sin',c.doc_sin);
  set('fc_forma_pago_sunat',c.forma_pago_sunat);set('fc_umbral_dni_boleta',c.umbral_dni_boleta);
  renderReglas(FC.igv_reglas||[]);renderPagos(FC.formas_pago||[]);
  $('fc-contrato').textContent=FC_CONTRATO;
  if($('fc-fecha')&&!$('fc-fecha').value)$('fc-fecha').value=hoyLocal();
}
function reglaRow(r){r=r||{};const tot=((+r.igv||0)+(+r.ipm||0)).toFixed(1);return '<tr>'
  +'<td><input class="rg-desde" value="'+esc2(r.desde)+'" placeholder="2026-01-01" style="min-width:120px"></td>'
  +'<td><input class="rg-hasta" value="'+esc2(r.hasta)+'" placeholder="2026-12-31" style="min-width:120px"></td>'
  +'<td><input class="rg-igv" type="number" step="0.1" value="'+esc2(r.igv)+'" style="max-width:80px" oninput="recalcTot(this)"></td>'
  +'<td><input class="rg-ipm" type="number" step="0.1" value="'+esc2(r.ipm)+'" style="max-width:80px" oninput="recalcTot(this)"></td>'
  +'<td class="rg-tot muted">'+tot+'%</td>'
  +'<td><button class="sec" onclick="this.closest(\'tr\').remove()">✕</button></td></tr>';}
function renderReglas(list){$('fc-reglas').innerHTML=(list&&list.length?list:[{}]).map(reglaRow).join('');}
function addRegla(){$('fc-reglas').insertAdjacentHTML('beforeend',reglaRow());}
function recalcTot(inp){const tr=inp.closest('tr');
  const igv=+tr.querySelector('.rg-igv').value||0,ipm=+tr.querySelector('.rg-ipm').value||0;
  tr.querySelector('.rg-tot').textContent=(igv+ipm).toFixed(1)+'%';}
function pagoRow(p){p=p||{};return '<tr>'
  +'<td><input class="pg-cod" value="'+esc2(p.codigo)+'" style="max-width:120px"></td>'
  +'<td><input class="pg-nom" value="'+esc2(p.nombre)+'"></td>'
  +'<td><button class="sec" onclick="this.closest(\'tr\').remove()">✕</button></td></tr>';}
function renderPagos(list){$('fc-pagos').innerHTML=(list&&list.length?list:[{}]).map(pagoRow).join('');}
function addPago(){$('fc-pagos').insertAdjacentHTML('beforeend',pagoRow());}
async function saveFactura(){
  const reglas=[...document.querySelectorAll('#fc-reglas tr')].map(tr=>({
    desde:tr.querySelector('.rg-desde').value.trim(),hasta:tr.querySelector('.rg-hasta').value.trim(),
    igv:+tr.querySelector('.rg-igv').value||0,ipm:+tr.querySelector('.rg-ipm').value||0})).filter(r=>r.desde);
  const pagos=[...document.querySelectorAll('#fc-pagos tr')].map(tr=>({
    codigo:tr.querySelector('.pg-cod').value.trim(),nombre:tr.querySelector('.pg-nom').value.trim()})).filter(p=>p.codigo);
  const v=id=>$(id).value;
  const payload={
    emisor:{ruc:v('fc_ruc'),razon_social:v('fc_razon_social'),nombre_comercial:v('fc_nombre_comercial'),
      domicilio_fiscal:v('fc_domicilio_fiscal'),ubigeo:v('fc_ubigeo'),distrito:v('fc_distrito'),
      provincia:v('fc_provincia'),departamento:v('fc_departamento')},
    series:{boleta:v('fc_serie_boleta'),factura:v('fc_serie_factura')},
    moneda:v('fc_moneda'),igv_reglas:reglas,formas_pago:pagos,
    catalogos:{tipo_boleta:v('fc_tipo_boleta'),tipo_factura:v('fc_tipo_factura'),
      afectacion_igv:v('fc_afectacion_igv'),unidad_medida:v('fc_unidad_medida'),
      doc_dni:v('fc_doc_dni'),doc_ruc:v('fc_doc_ruc'),doc_sin:v('fc_doc_sin'),
      forma_pago_sunat:v('fc_forma_pago_sunat'),umbral_dni_boleta:+v('fc_umbral_dni_boleta')||0}};
  try{FC=await api('/api/facturacion',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    renderReglas(FC.igv_reglas);renderPagos(FC.formas_pago);
    $('fc-state').textContent='guardado';$('fc-state').className='chip ok';toast('Configuración de facturación guardada');
  }catch(e){$('fc-state').textContent='error';$('fc-state').className='chip bad';toast('Error: '+e.message);}
}
function hoyLocal(){const d=new Date();return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');}
async function probarFolio(){
  const n=$('fc-folio').value.trim();if(!n)return;
  $('fc-prueba-info').textContent='consultando…';$('fc-prueba').textContent='';
  try{const c=await api('/api/facturacion/folio/'+encodeURIComponent(n));
    $('fc-prueba-info').innerHTML='Folio <b>'+c.numcheque_pos+'</b> · '
      +(c.tipo_comprobante==='03'?'Boleta':'Factura')+' '+c.serie
      +' · '+(c.origen==='vigente'?'turno vigente':'cerrado')
      +' · total S/ '+c.totales.importe_total
      +(c.anulado?' · <span class="susp">ANULADO</span>':'')
      +(c.ya_facturado?' · <span class="susp">YA FACTURADO</span>':'');
    $('fc-prueba').textContent=JSON.stringify(c,null,2);
  }catch(e){$('fc-prueba-info').innerHTML='<span class="chip bad">'+e.message+'</span>';$('fc-prueba').textContent='';}}
async function probarFecha(){
  const f=$('fc-fecha').value.trim()||'hoy';
  $('fc-prueba-info').textContent='consultando…';$('fc-prueba').textContent='';
  try{const r=await api('/api/facturacion/ventas?fecha='+encodeURIComponent(f));
    $('fc-prueba-info').innerHTML='<b>'+r.total+'</b> venta(s) el '+r.fecha+' — comprobantes completos:';
    $('fc-prueba').textContent=JSON.stringify(r.comprobantes,null,2);
  }catch(e){$('fc-prueba-info').innerHTML='<span class="chip bad">'+e.message+'</span>';$('fc-prueba').textContent='';}}

// ── Snippet ────────────────────────────────────────────────────────────────────
const BOT_SNIPPET=`// Fase 2 — en el WhatsApp bot, cuando el cliente NO existe en su BD,
// consultar el import-agent ANTES de pedir el nombre:
const AGENT='http://import-agent:8000';
async function buscarEnImportador(celular){
  try{
    const r=await fetch(AGENT+'/clientes/buscar?celular='+encodeURIComponent(celular),
      {headers:{Authorization:'Bearer '+process.env.IMPORT_TOKEN}});
    if(r.ok) return await r.json();   // {nombre, direcciones:[...]}
  }catch(e){}
  return null;
}
// Si devuelve datos -> crear el cliente con ese nombre/dirección y NO preguntar el nombre.`;

load();
</script>
</body>
</html>
"""
