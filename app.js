const PROCUREMENT_DATA = window.PROCUREMENT_DATA || [];
const DATA = PROCUREMENT_DATA;
const META = window.PROCUREMENT_META || {};
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const money = n => n == null || n === '' ? '—' : new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',notation: n>=1e6?'compact':'standard',maximumFractionDigits:n>=1e6?2:0}).format(Number(n));
const val = r => Number(r.awardAmount || r.ceiling || 0);
let sortKey='postedDate', sortDir=-1;

if (META.asOf && $('#dataAsOf')) $('#dataAsOf').textContent = META.asOf;

function uniq(key){return [...new Set(DATA.map(d=>d[key]).filter(Boolean))].sort()}
function addOptions(id,key){const s=$(id);uniq(key).forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;s.appendChild(o)})}
addOptions('#sourceSystem','sourceSystem'); addOptions('#bureau','bureau'); addOptions('#status','status'); addOptions('#relevance','relevance');

function isPendingStatus(s){s=s.toLowerCase();return s.includes('pending')||s.includes('closed')||s.includes('archived')}
function statusClass(s){s=s.toLowerCase();if(s.includes('awarded'))return 'status-awarded';if(isPendingStatus(s))return 'status-pending';return 'status-open'}
function relClass(s){s=s.toLowerCase().replaceAll(' ','-');return 'rel-'+s}
function filterData(){
  const q=$('#search').value.trim().toLowerCase(), sourceSystem=$('#sourceSystem').value, bureau=$('#bureau').value, status=$('#status').value, rel=$('#relevance').value, range=$('#valueRange').value;
  let [lo,hi]=range?range.split('-').map(Number):[0,Infinity];
  return DATA.filter(r=>{
    const hay=[r.sourceSystem,r.bureau,r.status,r.title,r.awardId,r.winner,r.why,r.instrument].join(' ').toLowerCase();
    const amount=val(r);
    return (!q||hay.includes(q))&&(!sourceSystem||r.sourceSystem===sourceSystem)&&(!bureau||r.bureau===bureau)&&(!status||r.status===status)&&(!rel||r.relevance===rel)&&(!range||(amount>=lo&&amount<=hi));
  }).sort((a,b)=>{
    let A=a[sortKey]??'',B=b[sortKey]??'';
    if(sortKey==='ceiling') {A=val(a);B=val(b)}
    return (A>B?1:A<B?-1:0)*sortDir;
  });
}
function renderKpis(rows){
  const procurement=rows.filter(r=>r.sourceSystem==='SAM.gov'||r.sourceSystem==='World Bank');
  const sam=rows.filter(r=>r.sourceSystem==='SAM.gov').length;
  const worldBank=rows.filter(r=>r.sourceSystem==='World Bank').length;
  const cards=[['Tracked records',rows.length,'Current filtered view'],['Open procurement',procurement.length,'SAM.gov + World Bank'],['SAM.gov',sam,'Federal opportunities'],['World Bank',worldBank,'Project opportunities']];
  $('#kpis').innerHTML=cards.map(c=>`<div class="kpi"><div class="label">${esc(c[0])}</div><div class="value">${esc(c[1])}</div><div class="sub">${esc(c[2])}</div></div>`).join('');
}
function renderBars(rows,key,target){
  const m={};rows.forEach(r=>m[r[key]]=(m[r[key]]||0)+1);const entries=Object.entries(m).sort((a,b)=>b[1]-a[1]);const max=Math.max(1,...entries.map(x=>x[1]));
  $(target).innerHTML=entries.map(([k,n])=>`<div class="bar-row"><div>${esc(k)}</div><div class="bar-track"><div class="bar-fill" style="width:${n/max*100}%"></div></div><strong>${n}</strong></div>`).join('') || '<div class="muted">No matching records.</div>';
}
function renderRows(rows){
  $('#resultCount').textContent=`${rows.length} record${rows.length===1?'':'s'}`;
  $('#rows').innerHTML=rows.map(r=>`<tr>
    <td><strong>${esc(r.bureau)}</strong></td>
    <td><span class="source-tag source-${esc(r.sourceSystem).toLowerCase().replaceAll(/[^a-z0-9]+/g,'-')}">${esc(r.sourceSystem)}</span></td>
    <td><span class="badge ${statusClass(r.status)}">${esc(r.status)}</span></td>
    <td class="title">${esc(r.title)}<div class="why">${esc(r.why)}</div></td>
    <td>${esc(r.awardId)}</td>
    <td><strong>${money(val(r)||null)}</strong><div class="muted">${r.awardAmount?'award':'ceiling / funding'}</div></td>
    <td>${esc(r.closeDate||'—')}</td>
    <td><span class="badge ${relClass(r.relevance)}">${esc(r.relevance||'—')}</span></td>
    <td>${r.source?`<a class="source" href="${esc(r.source)}" target="_blank" rel="noopener">Open ↗</a>`:'—'}</td>
  </tr>`).join('');
}
function render(){const rows=filterData();renderKpis(rows);renderBars(rows,'status','#statusBars');renderBars(rows,'sourceSystem','#sourceBars');renderRows(rows)}
['#search','#sourceSystem','#bureau','#status','#relevance','#valueRange'].forEach(id=>$(id).addEventListener(id==='#search'?'input':'change',render));
$('#reset').addEventListener('click',()=>{['#search','#sourceSystem','#bureau','#status','#relevance','#valueRange'].forEach(id=>$(id).value='');render()});
document.querySelectorAll('th[data-sort]').forEach(th=>th.addEventListener('click',()=>{const k=th.dataset.sort;if(sortKey===k)sortDir*=-1;else{sortKey=k;sortDir=1}render()}));
render();
