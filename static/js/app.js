// ============ STATE ============
let pinnedTasks = (() => { try { return JSON.parse(localStorage.getItem('pinnedTasks') || '[]'); } catch(e) { return []; } })();
let taskLocations = (() => { try { return JSON.parse(localStorage.getItem('taskLocations') || '{}'); } catch(e) { return {}; } })();
let clientsMap = {};
let savedProfileName = lsGet('profileName', '');
let currentTheme = lsGet('theme', 'dark');

function applyTheme(theme) {
    currentTheme = theme;
    lsSet('theme', theme);
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.bsTheme = theme;

    const nav = document.getElementById('mainNavbar');
    if (theme === 'light') {
        nav.classList.remove('navbar-dark', 'bg-dark');
        nav.classList.add('navbar-light', 'bg-white');
    } else {
        nav.classList.remove('navbar-light', 'bg-white');
        nav.classList.add('navbar-dark', 'bg-dark');
    }

    const toggle = document.getElementById('themeToggle');
    if (toggle) {
        toggle.classList.toggle('active', theme === 'light');
        toggle.setAttribute('aria-checked', theme === 'light');
    }
    const label = document.getElementById('themeLabel');
    if (label) label.textContent = theme === 'light' ? '\u0421\u0432\u0435\u0442\u043B\u0430\u044F' : '\u0422\u0451\u043C\u043D\u0430\u044F';
}

function toggleTheme() {
    applyTheme(currentTheme === 'light' ? 'dark' : 'light');
}

function openSettings() {
    const modal = new bootstrap.Modal(document.getElementById('settingsModal'));
    document.getElementById('themeToggle').classList.toggle('active', currentTheme === 'light');
    document.getElementById('themeToggle').setAttribute('aria-checked', currentTheme === 'light');
    const label = document.getElementById('themeLabel');
    if (label) label.textContent = currentTheme === 'light' ? '\u0421\u0432\u0435\u0442\u043B\u0430\u044F' : '\u0422\u0451\u043C\u043D\u0430\u044F';
    fetch('/api/settings').then(checkAuth).then(r => r.json()).then(data => {
        document.getElementById('yandexToken').value = data.Yandex_token || '';
        document.getElementById('yandexRefreshToken').value = data.Yandex_refresh_token || '';
        document.getElementById('profileNameInput').value = data.App_profile_name || '';
        savedProfileName = data.App_profile_name || '';
        lsSet('profileName', savedProfileName);
        document.getElementById('exportXlsCheck').checked = data.App_export_xls === 'true';
        const sel = document.getElementById('defaultWarehouseSelect');
        if (sel) {
            const saved = data.App_default_warehouse || '';
                fetchDeduped('/api/warehouse/storages', undefined, 60000)
                    .then(r => r instanceof Response ? r.json().catch(() => ({})) : r)
                    .then(storages => {
                        storages = storages.storages || [];
                    sel.innerHTML = '<option value="">Не выбран</option>' +
                        storages.map(s => `<option value="${s.guid}"${s.guid === saved ? ' selected' : ''}>${s.name}</option>`).join('');
                });
        }
    }).catch(() => {});
    modal.show();
}

function saveYandexSettings() {
    const sel = document.getElementById('defaultWarehouseSelect');
    const defaultWarehouse = sel ? sel.value : '';
    const profileName = document.getElementById('profileNameInput').value.trim();
    const exportXls = document.getElementById('exportXlsCheck').checked;
    const body = {
        Yandex_token: document.getElementById('yandexToken').value.trim(),
        Yandex_refresh_token: document.getElementById('yandexRefreshToken').value.trim(),
        App_default_warehouse: defaultWarehouse,
        App_profile_name: profileName,
        App_export_xls: exportXls ? 'true' : 'false',
    };
    if (defaultWarehouse) {
        lsSet('defaultWarehouse', defaultWarehouse);
    } else {
        localStorage.removeItem('defaultWarehouse');
    }
    fetch('/api/settings', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body),
    }).then(checkAuth).then(r => r.json()).then(data => {
        savedProfileName = profileName;
        lsSet('profileName', savedProfileName);
        const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
        if (modal) modal.hide();
        showAlert('\u041D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u044B', 'success');
    }).catch(() => showAlert('\u041E\u0448\u0438\u0431\u043A\u0430 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u0438\u044F', 'danger'));
}

function saveProfile() {
    const theme = document.getElementById('themeToggle').classList.contains('active') ? 'light' : 'dark';
    applyTheme(theme);
    updateGlobalStatus();
}

// ============ SYNC ============
function syncFromYandex() {
    const btn = document.querySelector('[onclick="syncFromYandex()"]');
    if (!btn) return;
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430...';
    fetch('/api/sync/from-yandex', {method: 'POST'})
        .then(checkAuth).then(r => r.json())
        .then(data => {
            const imported = Object.values(data).filter(v => v.status === 'imported').length;
            showAlert(`\u0417\u0430\u0433\u0440\u0443\u0436\u0435\u043D\u043E: ${imported} ${pluralize(imported, '\u0438\u0441\u0442\u043E\u0447\u043D\u0438\u043A', '\u0438\u0441\u0442\u043E\u0447\u043D\u0438\u043A\u0430', '\u0438\u0441\u0442\u043E\u0447\u043D\u0438\u043A\u043E\u0432')}`, imported > 0 ? 'success' : 'info');
            fetchGlobalStatus();
        })
        .catch(() => showAlert('\u041E\u0448\u0438\u0431\u043A\u0430 \u0437\u0430\u0433\u0440\u0443\u0437\u043A\u0438 \u0441 \u042F\u0414\u0438\u0441\u043A\u0430', 'danger'))
        .finally(() => { btn.disabled = false; btn.innerHTML = orig; });
}

function syncToYandex() {
    const btn = document.querySelector('[onclick="syncToYandex()"]');
    if (!btn) return;
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>\u0412\u044B\u0433\u0440\u0443\u0437\u043A\u0430...';
    fetch('/api/sync/to-yandex', {method: 'POST'})
        .then(checkAuth).then(r => r.json())
        .then(data => {
            showAlert(`\u0412\u044B\u0433\u0440\u0443\u0436\u0435\u043D\u043E: ${data.uploaded} ${pluralize(data.uploaded, '\u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0435', '\u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044F', '\u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0439')}`, data.uploaded > 0 ? 'success' : 'info');
            fetchGlobalStatus();
        })
        .catch(() => showAlert('\u041E\u0448\u0438\u0431\u043A\u0430 \u0432\u044B\u0433\u0440\u0443\u0437\u043A\u0438', 'danger'))
        .finally(() => { btn.disabled = false; btn.innerHTML = orig; });
}

function fetchGlobalStatus() {
    fetch('/api/sync/status')
        .then(checkAuth).then(r => r.json())
        .then(data => {
            const bar = document.getElementById('globalStatusBar');
            if (!bar) return;
            bar.innerHTML = `
                <span><i class="bi bi-inboxes me-1"></i>\u0417\u0430\u044F\u0432\u043E\u043A: <strong>${data.tasks_total}</strong> (\u043E\u0442\u043A\u0440\u044B\u0442\u043E: ${data.tasks_open}, \u0437\u0430\u043A\u0440\u044B\u0442\u043E: ${data.tasks_closed})</span>
                <span><i class="bi bi-arrow-up-circle me-1"></i>\u041E\u0436\u0438\u0434\u0430\u044E\u0442 \u0432\u044B\u0433\u0440\u0443\u0437\u043A\u0438: <strong>${data.pending_actions}</strong></span>
                <button class="btn btn-outline-success btn-sm py-0 px-2" onclick="syncFromYandex()"><i class="bi bi-cloud-download me-1"></i>\u0417\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044C \u0434\u0430\u043D\u043D\u044B\u0435</button>
                <button class="btn btn-outline-info btn-sm py-0 px-2" onclick="syncToYandex()"><i class="bi bi-cloud-upload me-1"></i>\u0412\u044B\u0433\u0440\u0443\u0437\u0438\u0442\u044C \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044F</button>
            `;
        })
        .catch(() => {});
}

function pluralize(n, one, few, many) {
    n = Math.abs(n) % 100;
    if (n >= 5 && n <= 20) return many;
    n %= 10;
    if (n === 1) return one;
    if (n >= 2 && n <= 4) return few;
    return many;
}

// ============ STARTUP ============
function runStartup() {
    const ov = document.getElementById('startupOverlay');
    if (!ov) return;
    if (sessionStorage.getItem('startupDone')) {
        ov.style.display = 'none';
        return;
    }
    setTimeout(() => {
        ov.classList.add('hide');
        sessionStorage.setItem('startupDone', '1');
        setTimeout(() => { ov.style.display = 'none'; }, 600);
    }, 800);
}

// ============ ANDROID BACK BUTTON ============
document.addEventListener('shown.bs.modal', () => { history.pushState(null, ''); });
window.addEventListener('popstate', () => {
    const modal = document.querySelector('.modal.show');
    if (modal) bootstrap.Modal.getInstance(modal)?.hide();
});

// ============ PWA INSTALL ============
let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault();
    deferredPrompt = e;
    const section = document.getElementById('installAppSection');
    if (section) section.classList.remove('d-none');
});
window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    const section = document.getElementById('installAppSection');
    if (section) section.classList.add('d-none');
});
function installApp() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(() => {
        deferredPrompt = null;
        const section = document.getElementById('installAppSection');
        if (section) section.classList.add('d-none');
    });
}

// ============ INIT ============
document.addEventListener('DOMContentLoaded', () => {
    runStartup();
    applyTheme(currentTheme);
    fetchGlobalStatus();
    setInterval(fetchGlobalStatus, 60000);
    window.addEventListener('scroll', () => {
        const btn = document.getElementById('scrollTopBtn');
        if (btn) btn.classList.toggle('show', window.scrollY > 400);
    });
});