const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const API_URL = window.location.origin;
let state = {
  user: null,
  docType: '',
  topic: '',
  extra: ''
};

const DOC_TYPES = [
  { id: 'доклад', emoji: '📄', name: 'Доклад' },
  { id: 'реферат', emoji: '📚', name: 'Реферат' },
  { id: 'презентация', emoji: '📊', name: 'Презентация' },
  { id: 'эссе', emoji: '📝', name: 'Эссе' },
  { id: 'конспект', emoji: '📖', name: 'Конспект' },
  { id: 'статья', emoji: '✍️', name: 'Статья' },
  { id: 'план', emoji: '📋', name: 'План' },
  { id: 'свой', emoji: '🎯', name: 'Свой' }
];

// --- API Helpers ---
async function apiFetch(path, options = {}) {
  const headers = {
    'X-Init-Data': tg.initData,
    ...(options.headers || {})
  };
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Ошибка ${res.status}`);
  }
  return res.json();
}

// --- Init ---
async function init() {
  if (!tg.initData) {
    document.getElementById('loader').innerHTML = '<div style="color:white;padding:20px;text-align:center;">Откройте приложение через Telegram</div>';
    return;
  }

  try {
    state.user = await apiFetch('/api/me');
    renderUser();
    renderQuickGrid();
    loadRecentDocs();
    renderTypes();
    
    const loader = document.getElementById('loader');
    loader.style.opacity = '0';
    setTimeout(() => loader.classList.add('hidden'), 300);
    document.getElementById('app').classList.remove('hidden');
  } catch (e) {
    tg.showAlert('Ошибка инициализации: ' + e.message);
  }
}

// --- Render ---
function renderUser() {
  const u = state.user;
  const avatar = document.getElementById('userAvatar');
  const profAvatar = document.getElementById('profAvatar');
  
  const initials = (u.first_name || 'U').substring(0, 2).toUpperCase();
  avatar.textContent = initials;
  profAvatar.textContent = initials;

  document.getElementById('userName').textContent = u.first_name || 'User';
  document.getElementById('userPlan').textContent = u.is_premium ? '💎 Premium' : 'Free';
  document.getElementById('greeting').textContent = `Привет, ${u.first_name || 'друг'}! 👋`;
  
  document.getElementById('statGens').textContent = u.free_generations_left + u.premium_generations_left;
  document.getElementById('statRefs').textContent = u.referrals_count || 0;
  
  document.getElementById('profName').textContent = u.first_name || 'User';
  document.getElementById('profId').textContent = 'ID: ' + u.telegram_id;
  
  const pp = document.getElementById('profPlan');
  if (u.is_premium) {
    pp.textContent = '💎 Premium';
    pp.className = 'badge gold';
  } else {
    pp.textContent = 'Free';
    pp.className = 'badge';
  }
}

function renderQuickGrid() {
  const html = DOC_TYPES.map(t => 
    `<div class="type-btn" onclick="selectQuick('${t.id}')"><span>${t.emoji}</span>${t.name}</div>`
  ).join('');
  document.getElementById('quickGrid').innerHTML = html;
}

function renderTypes() {
  const html = DOC_TYPES.map(t => 
    `<div class="type-btn" onclick="selectType(this, '${t.id}')"><span>${t.emoji}</span>${t.name}</div>`
  ).join('');
  document.getElementById('typeGrid').innerHTML = html;
}

async function loadRecentDocs() {
  try {
    const docs = await apiFetch('/api/documents');
    document.getElementById('statDocs').textContent = docs.length;
    
    const html = docs.slice(0, 3).map(d => `
      <div class="doc-item">
        <div>
          <div class="doc-title">${d.title}</div>
          <div class="doc-meta">${d.format.toUpperCase()} • ${new Date(d.created_at).toLocaleDateString('ru')}</div>
        </div>
        <button class="btn-dl" onclick="downloadDoc(${d.id})">⬇️</button>
      </div>
    `).join('');
    
    document.getElementById('recentList').innerHTML = html || '<div style="color:#9CA3AF;font-size:14px;">Пока нет документов</div>';
    document.getElementById('docsList').innerHTML = html || '<div style="color:#9CA3AF;text-align:center;margin-top:20px;">Нет файлов</div>';
  } catch (e) {
    console.error(e);
  }
}

// --- Navigation ---
function nav(screenId) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  
  const screen = document.getElementById(`screen-${screenId}`);
  if (screen) screen.classList.add('active');
  
  const navBtn = document.querySelector(`.nav-btn[data-nav="${screenId}"]`);
  if (navBtn) navBtn.classList.add('active');
  
  if (screenId === 'docs') loadRecentDocs();
}

// --- Create Flow ---
function selectQuick(type) {
  state.docType = type;
  nav('create');
  // Автоматически переходим на шаг 2
  toStep(2);
  document.getElementById('inpTopic').focus();
}

function selectType(el, type) {
  document.querySelectorAll('#typeGrid .type-btn').forEach(b => b.classList.remove('selected'));
  el.classList.add('selected');
  state.docType = type;
  document.getElementById('btnStep1').disabled = false;
}

function toStep(n) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
  
  if (n === 1 || n === 2 || n === 3) {
    document.getElementById(`panel-${n}`).classList.add('active');
    document.querySelector(`.step[data-s="${n}"]`).classList.add('active');
  }
}

// Слушатели ввода
document.getElementById('inpTopic')?.addEventListener('input', (e) => {
  state.topic = e.target.value;
  document.getElementById('btnStep2').disabled = e.target.value.length < 2;
});

document.getElementById('rngPages')?.addEventListener('input', (e) => {
  document.getElementById('lblPages').textContent = e.target.value;
});

// --- Generation ---
async function startGenerate() {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById('panel-loading').classList.add('active');
  
  const statusText = document.getElementById('genStatusText');
  const steps = [
    "Подготовка задания...",
    "Нейросеть думает над структурой...",
    "Генерация текста...",
    "Отрисовка файла...",
    "Почти готово..."
  ];
  let idx = 0;
  const interval = setInterval(() => {
    if (idx < steps.length - 1) { idx++; statusText.textContent = steps[idx]; }
  }, 4000);

  const payload = {
    doc_type: state.docType || 'доклад',
    format: document.getElementById('selFormat').value,
    topic: document.getElementById('inpTopic').value,
    extra: document.getElementById('inpExtra').value,
    pages: parseInt(document.getElementById('rngPages').value),
    include_title_page: document.getElementById('optTitle').checked,
    include_toc: document.getElementById('optToc').checked,
    include_conclusion: true,
    include_sources: false
  };

  try {
    const res = await apiFetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    clearInterval(interval);
    statusText.textContent = "Готово!";
    
    tg.showPopup({
      title: '✅ Документ готов',
      message: `Файл ${res.title}.${res.format.toUpperCase()} создан.\n\nНайти его можно в разделе «Мои документы» или в чате с ботом.`,
      buttons: [{ type: 'ok' }]
    }, () => {
      nav('home');
      loadRecentDocs();
    });
    
  } catch (e) {
    clearInterval(interval);
    tg.showAlert('Ошибка: ' + e.message);
    toStep(3);
  }
}

async function downloadDoc(id) {
  try {
    const url = `${API_URL}/api/documents/${id}/download`;
    const res = await fetch(url, { headers: { 'X-Init-Data': tg.initData } });
    if (!res.ok) throw new Error('Не удалось скачать');
    const blob = await res.blob();
    
    // Используем Telegram API для скачивания, если доступно, иначе обычную ссылку
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = `document_${id}`;
    a.click();
    URL.revokeObjectURL(blobUrl);
  } catch(e) {
    tg.showAlert(e.message);
  }
}

function buyPlan(planKey) {
  // В Telegram Mini App нельзя напрямую вызвать инвойс. 
  // Мы отправляем боту сообщение, и он выставляет счёт.
  tg.sendData(JSON.stringify({ action: 'buy', plan: planKey }));
  tg.close();
}

function copyRef() {
  if (!state.user) return;
  const link = `https://t.me/${BOT_USERNAME}?start=ref_${state.user.telegram_id}`;
  navigator.clipboard.writeText(link).then(() => {
    tg.showAlert('Ссылка скопирована!');
  });
}

function openLink(url) {
  tg.openTelegramLink(url);
}

// Запуск
init();
