"""Panel de importación (HTML + JS en un solo archivo, sin dependencias).

Diseñado como PANEL MODULAR: hoy gestiona la importación de clientes/direcciones
desde el DBF, pero la grilla de "módulos de importación" está pensada para ir
sumando más conjuntos de datos (productos, histórico de pedidos, etc.) como
nuevas tarjetas, reutilizando el mismo origen DBF y la misma mecánica.
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
  .two{display:grid;grid-template-columns:1fr 1fr;gap:10px}
  .three{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
  button{background:var(--acc);color:#1a1206;border:0;border-radius:8px;
         padding:10px 16px;font-size:14px;font-weight:650;cursor:pointer}
  button.sec{background:var(--chip);color:var(--txt);border:1px solid var(--line)}
  button.ghost{background:transparent;color:var(--acc);border:1px solid var(--acc)}
  button:disabled{opacity:.5;cursor:default}
  .chip{display:inline-block;background:var(--chip);border:1px solid var(--line);
        border-radius:20px;padding:2px 10px;font-size:12px;color:var(--muted)}
  .chip.ok{color:var(--ok);border-color:var(--ok)}
  .chip.bad{color:var(--bad);border-color:var(--bad)}
  .chip.warn{color:var(--warn);border-color:var(--warn)}
  table{width:100%;border-collapse:collapse;font-size:13.5px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
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
</style>
</head>
<body>
<header>
  <h1>import-agent</h1><span class="badge">Ruta80</span>
  <span id="hstate" class="chip" style="margin-left:auto">cargando…</span>
</header>
<main>
  <div class="tabs">
    <button data-tab="resumen" class="active">Resumen</button>
    <button data-tab="importar">Importaciones</button>
    <button data-tab="buscar">Buscar (prueba)</button>
    <button data-tab="sync">Sincronizar con el bot</button>
    <button data-tab="config">Configuración</button>
  </div>

  <!-- RESUMEN -->
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

  <!-- IMPORTACIONES -->
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
        <p>Próximamente. Se sumará como nuevo módulo reutilizando el mismo origen DBF.</p>
        <button class="sec" disabled>Pendiente</button>
      </div>
      <div class="modulo soon">
        <h3>🧾 Histórico de pedidos</h3>
        <p>Próximamente. Para análisis y migración de datos del sistema antiguo.</p>
        <button class="sec" disabled>Pendiente</button>
      </div>
    </div>
  </section>

  <!-- BUSCAR -->
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

  <!-- SYNC -->
  <section id="t-sync" class="hide">
    <div class="card">
      <p class="muted">Compara el índice (DBF) contra los clientes que ya existen en el bot,
        cruzando por celular. Útil para detectar nombres mal escritos en el bot
        (“un cuarto de pollo”) que en el DBF están correctos.</p>
      <div class="row">
        <button onclick="diff()" id="btn-diff">Comparar diferencias</button>
        <span id="diff-state" class="chip">—</span>
      </div>
      <div id="diff-summary" class="grid" style="margin-top:14px"></div>
    </div>
    <div id="diff-tables"></div>
  </section>

  <!-- CONFIG -->
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
      <p class="muted" style="font-size:13px">Solo se usa para el panel de sincronización. La búsqueda en runtime no lo necesita.</p>
      <label>Token para que el bot consulte (opcional)</label>
      <input id="lookup_token" type="password" placeholder="(sin cambios)">
      <label>Codificación del DBF</label>
      <input id="dbf_encoding" placeholder="cp1252">
      <div class="row" style="margin-top:12px"><button class="sec" onclick="saveGlobals()">Guardar</button></div>
    </div>
    <div class="card">
      <h3 style="margin:0 0 8px">Integración del bot (referencia)</h3>
      <pre id="snippet"></pre>
    </div>
  </section>
</main>
<div id="toast"></div>

<script>
const $=id=>document.getElementById(id);
let S=null, pgOff=0, lastDiff=null;
function toast(m){const t=$('toast');t.textContent=m;t.classList.add('show');
  clearTimeout(t._t);t._t=setTimeout(()=>t.classList.remove('show'),3200);}
async function api(path,opts){const r=await fetch(path,opts);
  if(!r.ok){let d='';try{d=(await r.json()).detail}catch(e){}
    throw new Error(d||('HTTP '+r.status));} return r.json();}

// tabs
function goTab(name){
  document.querySelectorAll('.tabs button').forEach(x=>
    x.classList.toggle('active',x.dataset.tab===name));
  ['resumen','importar','buscar','sync','config'].forEach(t=>
    $('t-'+t).classList.toggle('hide',t!==name));
}
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>goTab(b.dataset.tab));

function toggleSrc(){const v=$('src_type').value;
  $('src_smb').classList.toggle('hide',v!=='smb');
  $('src_local').classList.toggle('hide',v!=='local');}

function fillSettings(){
  const s=S.source||{};
  $('src_type').value=s.source_type||'smb'; toggleSrc();
  $('smb_host').value=s.smb_host||''; $('smb_share').value=s.smb_share||'';
  $('smb_path').value=s.smb_path||''; $('smb_user').value=s.smb_user||'';
  $('smb_domain').value=s.smb_domain||'WORKGROUP'; $('local_dir').value=s.local_dir||'';
  $('clientes_file').value=s.clientes_file||''; $('direcciones_file').value=s.direcciones_file||'';
  $('imp-src-label').textContent = (s.source_type==='local')
    ? ('local · '+(s.local_dir||'—'))
    : ('//'+(s.smb_host||'—')+'/'+(s.smb_share||'')+(s.smb_path?'/'+s.smb_path:''));
  $('bot_db_path').value=S.bot_db_path||''; $('dbf_encoding').value=S.dbf_encoding||'cp1252';
  $('m-digits').textContent=S.phone_digits;
  // resumen
  $('s-cli').textContent=S.index.clientes; $('s-dir').textContent=S.index.direcciones;
  $('s-bot').textContent=S.bot_db_disponible?'conectada':'no conectada';
  $('hstate').textContent=S.index.clientes+' clientes';
  const u=S.index.ultima_importacion;
  $('s-ultima').innerHTML=u?('Fecha: <b>'+u.fecha+'</b> · '+u.clientes+' clientes · '
     +u.direcciones+' direcciones'+(u.direcciones_huerfanas_omitidas?
     ' · '+u.direcciones_huerfanas_omitidas+' direcciones huérfanas omitidas':'')):'—';
  $('snippet').textContent=BOT_SNIPPET;
}
async function load(){S=await api('/api/settings');fillSettings();listar();}

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
    await saveSource(true);                       // prueba lo que está en el formulario
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
  if($('lookup_token').value)p.lookup_token=$('lookup_token').value;
  S=await api('/api/globals',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
  fillSettings();toast('Configuración guardada');}

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

async function buscar(){
  const cel=$('q-cel').value.trim();if(!cel)return;
  try{const r=await api('/clientes/buscar?celular='+encodeURIComponent(cel));
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
      +'<button class="ghost" onclick="aplicarNombres(true)">Corregir solo los sospechosos →</button></div>'
      +'<div class="scroll" style="margin-top:10px"><table><thead><tr>'
      +'<th><input type=checkbox onclick="toggleAll(this)"></th><th>Celular</th>'
      +'<th>Nombre en el BOT</th><th>Nombre en el DBF</th></tr></thead><tbody>';
    r.nombre_distinto.forEach((x,i)=>{
      h+='<tr><td><input type=checkbox class="cbn" data-i="'+i+'"'+(x.bot_sospechoso?' checked':'')+'></td>'
        +'<td>'+x.celular+'</td><td class="'+(x.bot_sospechoso?'susp':'')+'">'+esc(x.nombre_bot)
        +(x.bot_sospechoso?' ⚠':'')+'</td><td>'+esc(x.nombre_dbf)+'</td></tr>';});
    h+='</tbody></table></div></div>';
  }
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
    h+='</tbody></table></div></div>';
  }
  $('diff-tables').innerHTML=h||'<p class="muted">Sin diferencias.</p>';
}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function toggleAll(c){document.querySelectorAll('.cbn').forEach(x=>x.checked=c.checked);}
function toggleAllD(c){document.querySelectorAll('.cbd').forEach(x=>x.checked=c.checked);}

async function aplicarNombres(onlySusp){
  const acciones=[];
  document.querySelectorAll('.cbn').forEach(cb=>{
    if(cb.checked){const x=lastDiff.nombre_distinto[+cb.dataset.i];
      if(!onlySusp||x.bot_sospechoso)acciones.push({celular:x.celular,lid:x.lid,tipo:'nombre'});}});
  await aplicar(acciones,'nombres');
}
async function aplicarDir(){
  const acciones=[];
  document.querySelectorAll('.cbd').forEach(cb=>{
    if(cb.checked){const x=lastDiff.falta_direccion[+cb.dataset.i];
      acciones.push({celular:x.celular,lid:x.lid,tipo:'direccion'});}});
  await aplicar(acciones,'direcciones');
}
async function aplicar(acciones,label){
  if(!acciones.length){toast('Nada marcado');return;}
  if(!confirm('Se actualizarán '+acciones.length+' '+label+' en la BD del bot. ¿Continuar?'))return;
  try{const r=await api('/api/sync/aplicar',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({acciones})});
    toast('Aplicado: '+(r.nombre+' nombres, '+r.direccion+' direcciones'
      +(r.errores.length?', '+r.errores.length+' errores':'')));
    diff();
  }catch(e){toast('Error: '+e.message);}
}

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
// Si devuelve datos -> crear el cliente con ese nombre/dirección
// (ya tienes el LID de la conversación) y NO preguntar el nombre.`;

load();
</script>
</body>
</html>
"""
