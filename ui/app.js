const $ = id => document.getElementById(id);
const names = ['baseline', 'corrupted', 'repaired'];
let data, selected = 'baseline', step = 0, page = 0, visibleRecords = [];
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = (v, digits=3) => typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—';
const flag = v => v === true ? '<span class="good">PASS</span>' : v === false ? '<span class="bad">FAIL</span>' : 'Chưa có dữ liệu';
const stages = [
 ['Raw ingestion','Crossref snapshot','Lưu bản gốc từ Crossref để truy vết nguồn và phục hồi dữ liệu.','data/raw/crossref_records.json'],
 ['Cleaning','Chuẩn hóa schema','Làm sạch văn bản, chuẩn hóa trường dữ liệu và tính age_days, summary_chars.','data/clean/papers_clean*.json'],
 ['Quality gate','GX + Freshness','Kiểm định dữ liệu bằng Great Expectations và đánh giá độ tươi theo SLA. Trong lab, cảnh báo không dừng luồng benchmark.','data/quality/'],
 ['Vector index','MiniLM → ChromaDB','Nhúng văn bản bằng all-MiniLM-L6-v2 và lưu vào collection ứng với từng trạng thái.','data/embeddings/ · data/chroma/'],
 ['RAG evaluation','Hit Rate · F1 · Judge','Đánh giá truy xuất và câu trả lời trên bộ câu hỏi đã lưu. Các chỉ số bên dưới được đọc từ artifacts.','data/results/*_metrics.json'],
 ['Corruption','6 dạng lỗi','Bỏ bản ghi mới, xóa tóm tắt, chèn nhiễu, cắt tiêu đề, làm cũ ngày và nhân bản dòng.','data/results/corruption_log.json'],
 ['Repair','Tái tạo từ raw','Đọc lại raw snapshot, làm sạch, kiểm định và lập chỉ mục lại để đối chiếu khả năng phục hồi.','data/clean/papers_clean_repaired.json']
];
function renderStages(){
 $('stages').innerHTML = stages.map((s,i)=>`<button class="stage ${i===step?'active':''}" data-step="${i}" aria-pressed="${i===step}"><span>0${i+1} ${i===step?'↗':''}</span>${s[0]}<small>${s[1]}</small></button>`).join('');
 $('stage-detail').innerHTML = `<strong>${stages[step][0]}</strong><p>${stages[step][2]}</p><code>${stages[step][3]}</code>`;
}
function render(){
 const state=data.states[selected], m=state.metrics || {}, q=state.quality || {}, f=state.freshness || {};
 document.querySelectorAll('[data-state]').forEach(b=>{b.classList.toggle('active', b.dataset.state===selected);b.setAttribute('aria-pressed', b.dataset.state===selected);});
 $('state-note').textContent = `${selected.toUpperCase()} · ${q.generated_at ? 'Quality report: '+new Date(q.generated_at).toLocaleString('vi-VN') : 'Chưa có báo cáo chất lượng'}`;
 const stats = [['Bản ghi / '+selected,Array.isArray(state.records)?state.records.length:'—',`${data.raw?.length ?? 0} bản ghi trong raw snapshot`],['Retrieval Hit Rate',number(m.retrieval_hit_rate),`${m.samples ?? '—'} câu hỏi đánh giá`],['Data Quality',q.success===true?'PASS':q.success===false?'FAIL':'—',`${q.unsuccessful_expectations ?? '—'} / ${q.evaluated_expectations ?? '—'} kiểm định thất bại`],['Freshness SLA',f.is_fresh===true?'PASS':f.is_fresh===false?'FAIL':'—',`${f.stale_rows ?? '—'} bản ghi quá hạn · ${f.threshold_days ?? 180} ngày`]];
 $('stats').innerHTML = stats.map(s=>`<article class="stat"><label>${esc(s[0])}</label><strong class="${s[1]==='FAIL'?'bad':''}">${esc(s[1])}</strong><small>${esc(s[2])}</small></article>`).join('');
 $('metrics').innerHTML = [['retrieval_hit_rate','Retrieval Hit Rate',1],['mean_token_f1','Token F1',1],['mean_judge_score','LLM Judge Score',5]].map(([key,label,max])=>`<div class="metric"><div class="metric-head"><strong>${label}</strong><span class="metric-values">${names.map(n=>number(data.states[n].metrics?.[key])).join(' / ')}</span></div><div class="bars">${names.map((n,i)=>{const v=data.states[n].metrics?.[key];return `<div class="track" title="${n}: ${number(v)}"><div class="bar c${i}" style="width:${typeof v==='number'?Math.max(0,Math.min(100,v/max*100)):0}%"></div></div>`;}).join('')}</div></div>`).join('');
 $('quality-content').innerHTML = `<div class="quality-row"><span>Great Expectations</span><strong>${flag(q.success)}</strong></div><div class="quality-row"><span>Freshness SLA</span><strong>${flag(f.is_fresh)}</strong></div><div class="quality-row"><span>Tỷ lệ dữ liệu quá hạn</span><strong>${typeof f.stale_ratio==='number'?number(f.stale_ratio*100,1)+'%':'—'}</strong></div><div class="quality-row"><span>Ngày xuất bản mới nhất</span><strong>${esc(f.latest_published ?? '—')}</strong></div>` + (q.expectations?.length ? `<details><summary>${q.expectations.length} kiểm định chất lượng</summary>${q.expectations.map(e=>`<div class="quality-row"><span>${esc(e.expectation)}<br><small>${esc(e.column)}</small></span>${flag(e.success)}</div>`).join('')}</details>` : '<p class="empty">Chạy baseline để tạo báo cáo kiểm định đầu tiên.</p>') + (f.alert ? `<p class="footnote">${esc(f.alert)}</p>` : '');
 const faults = ['Bỏ bản ghi mới nhất','Xóa nội dung tóm tắt','Chèn ký tự nhiễu','Cắt ngắn tiêu đề','Lùi ngày xuất bản','Nhân bản bản ghi'];
 $('corruption-events').innerHTML = faults.map((label,i)=>{const e=data.corruption?.events?.find(e=>e.step===i+1);return `<div class="corruption-item"><strong><span>0${i+1}</span>${label}</strong><p>${e?esc(e.affected_rows)+' bản ghi bị tác động':'Kịch bản đã có · Chưa có log chạy'}</p></div>`;}).join('');
 const job=data.job, running=job.status==='running';
 $('run-baseline').disabled=running;
 $('run-corruption').disabled=running || !data.states.baseline.metrics || !data.states.baseline.records;
 const statuses={idle:'Chưa chạy từ UI',running:'Đang chạy',completed:'Hoàn tất',failed:'Thất bại'};
 $('job-title').textContent=`Nhật ký thực thi · ${statuses[job.status]}${job.phase?' / '+job.phase:''}${job.exit_code!==null?' / exit '+job.exit_code:''}`;
 $('log').textContent=job.log.length?job.log.join('\n'):'Log của lần chạy từ UI sẽ xuất hiện tại đây.';
 renderRecords();
}
function renderRecords(){
 const source=$('dataset').value==='raw'?data.raw:data.states[selected].records;
 const query=$('search').value.trim().toLowerCase();
 const all=Array.isArray(source)?source:[];
 const filtered=all.filter(r=>[r.title,r.paper_id,r.summary].join(' ').toLowerCase().includes(query));
 const pages=Math.max(1,Math.ceil(filtered.length/8));page=Math.max(0,Math.min(page,pages-1));visibleRecords=filtered.slice(page*8,page*8+8);
 $('record-count').textContent=`${filtered.length} / ${all.length} bản ghi`;
 $('records').innerHTML=visibleRecords.length?visibleRecords.map((r,i)=>`<tr><td><button data-paper="${i}">${esc(r.title || '(Thiếu tiêu đề)')}</button><small>${esc(r.paper_id)}</small></td><td>${esc(r.primary_category || (r.categories || []).join(', '))}</td><td>${esc(r.published)}</td><td>${r.summary?String(r.summary).length+' ký tự':'Trống'}</td></tr>`).join(''):`<tr><td colspan="4" class="empty">${source?'Không tìm thấy bài báo phù hợp.':'Chưa có dataset cho trạng thái này. Hãy chạy pipeline hoặc chọn Raw snapshot.'}</td></tr>`;
 $('page').textContent=`Trang ${page+1} / ${pages}`;$('prev').disabled=page===0;$('next').disabled=page>=pages-1;
}
let loading=false, lastSnapshot="";
async function refresh(){
 if(loading)return;loading=true;
 try{const response=await fetch('/api/snapshot');if(!response.ok)throw Error('Không thể đọc dữ liệu: HTTP '+response.status);const incoming=await response.json();const fingerprint=JSON.stringify(incoming);data=incoming;if(fingerprint!==lastSnapshot){render();lastSnapshot=fingerprint;}$('connection').textContent='● Đã kết nối · Local';$('error').hidden=!data.errors.length;$('error').textContent=data.errors.join('\n');}
 catch(e){$('connection').textContent='Mất kết nối';$('error').hidden=false;$('error').textContent=e.message;}
 finally{loading=false;}
}
async function run(phase){
 $('run-baseline').disabled=true;$('run-corruption').disabled=true;
 try{const response=await fetch('/api/run/'+phase,{method:'POST',headers:{'X-UI-Token':data.token}});const result=await response.json();if(!response.ok)throw Error(result.error);$('logs').open=true;await refresh();}
 catch(e){$('error').hidden=false;$('error').textContent=e.message;$('run-baseline').disabled=false;$('run-corruption').disabled=!data.states.baseline.metrics;}
}
$('refresh').onclick=refresh;
$('run-baseline').onclick=()=>run('baseline');$('run-corruption').onclick=()=>run('corruption');
$('stages').onclick=e=>{const b=e.target.closest('[data-step]');if(b){step=Number(b.dataset.step);renderStages();}};
document.querySelectorAll('[data-state]').forEach(b=>b.onclick=()=>{selected=b.dataset.state;page=0;if(data)render();});
$('search').oninput=()=>{page=0;if(data)renderRecords();};$('dataset').onchange=()=>{page=0;if(data)renderRecords();};
$('prev').onclick=()=>{page--;renderRecords();};$('next').onclick=()=>{page++;renderRecords();};
$('records').onclick=e=>{const b=e.target.closest('[data-paper]');if(!b)return;const r=visibleRecords[Number(b.dataset.paper)];$('paper-title').textContent=r.title||'(Thiếu tiêu đề)';$('paper-id').textContent=r.paper_id;$('paper-summary').textContent=r.summary||'Không có tóm tắt.';$('paper-json').textContent=JSON.stringify(r,null,2);$('paper').showModal();};
$('close-paper').onclick=()=>$('paper').close();
$('run-baseline').disabled=true;$('run-corruption').disabled=true;
renderStages();refresh();setInterval(refresh,3000);

