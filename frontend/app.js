// frontend/app.js
import { SERVER_URL } from './config.js';

console.log('✅ app.js загружен, SERVER_URL =', SERVER_URL);

let swRegistration = null;
let pushSubscription = null;
let subscriptionTypes = []; // Храним типы подписок

// DOM элементы
const permissionDiv = document.getElementById('permissionStatus');
const subscribeBtn = document.getElementById('subscribeBtn');
const unsubscribeBtn = document.getElementById('unsubscribeBtn');
const sendNotificationBtn = document.getElementById('sendNotificationBtn');
const addTypeBtn = document.getElementById('addTypeBtn');
const refreshTypesBtn = document.getElementById('refreshTypesBtn');
const typesContainer = document.getElementById('typesContainer');
const subscriptionTypesRadio = document.getElementById('subscriptionTypesRadio');
const targetTypesRadio = document.getElementById('targetTypesRadio');
const statsContainer = document.getElementById('statsContainer');
const messageTitle = document.getElementById('messageTitle');
const messageBody = document.getElementById('messageBody');

// Модальное окно
const typeModal = document.getElementById('typeModal');
const modalTitle = document.getElementById('modalTitle');
const typeKey = document.getElementById('typeKey');
const typeName = document.getElementById('typeName');
const typeDescription = document.getElementById('typeDescription');
const typeColor = document.getElementById('typeColor');
const editingTypeKey = document.getElementById('editingTypeKey');
const saveTypeBtn = document.getElementById('saveTypeBtn');
const cancelTypeBtn = document.getElementById('cancelTypeBtn');

// ========== Вспомогательные функции ==========

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

// ========== Загрузка типов подписок ==========

async function loadSubscriptionTypes() {
    try {
        const response = await fetch(`${SERVER_URL}/api/types`);
        if (!response.ok) throw new Error('Ошибка загрузки типов');
        const data = await response.json();
        subscriptionTypes = data.types;
        
        // Обновляем все UI элементы с типами
        renderTypesList();
        renderSubscriptionRadios();
        renderTargetRadios();
        
        console.log('✅ Загружены типы подписок:', subscriptionTypes);
    } catch (error) {
        console.error('❌ Ошибка загрузки типов:', error);
    }
}

// Отображение карточек типов в админке
function renderTypesList() {
    if (!typesContainer) return;
    
    if (subscriptionTypes.length === 0) {
        typesContainer.innerHTML = '<p>Нет созданных типов подписок</p>';
        return;
    }
    
    typesContainer.innerHTML = subscriptionTypes.map(type => `
        <div class="type-card" style="border-left: 4px solid ${type.type_color}">
            <div class="type-header">
                <span class="type-name">${type.type_name}</span>
                <div class="type-actions">
                    <button onclick="editType('${type.type_key}')" class="success" style="padding: 2px 6px;">✏️</button>
                    <button onclick="deleteType('${type.type_key}')" class="danger" style="padding: 2px 6px;">🗑️</button>
                </div>
            </div>
            <div class="type-description">${type.type_description || 'Нет описания'}</div>
            <div class="type-stats">
                <span class="type-badge" style="background: ${type.type_color}">${type.type_key}</span>
                <span>Подписчиков: <span id="stat-${type.type_key}">0</span></span>
            </div>
        </div>
    `).join('');
    
    // Обновляем статистику
    loadStats();
}

// Отображение радио-кнопок для выбора типа подписки
function renderSubscriptionRadios() {
    if (!subscriptionTypesRadio) return;
    
    subscriptionTypesRadio.innerHTML = subscriptionTypes.map(type => `
        <label>
            <input type="radio" name="subscriptionType" value="${type.type_key}">
            <span class="type-badge" style="background: ${type.type_color}">${type.type_name}</span>
            <small>${type.type_description || ''}</small>
        </label>
    `).join('');
    
    // Если есть типы, выбираем первый
    if (subscriptionTypes.length > 0) {
        const firstRadio = subscriptionTypesRadio.querySelector('input[type="radio"]');
        if (firstRadio) firstRadio.checked = true;
    }
}

// Отображение радио-кнопок для выбора цели отправки
function renderTargetRadios() {
    if (!targetTypesRadio) return;
    
    targetTypesRadio.innerHTML = `
        <label>
            <input type="radio" name="targetType" value="all" checked>
            <strong>📢 Всем подписчикам</strong>
        </label>
        ${subscriptionTypes.map(type => `
            <label>
                <input type="radio" name="targetType" value="${type.type_key}">
                <span class="type-badge" style="background: ${type.type_color}">${type.type_name}</span>
            </label>
        `).join('')}
    `;
}

// ========== Статистика ==========

async function loadStats() {
    try {
        const response = await fetch(`${SERVER_URL}/api/types/stats`);
        if (!response.ok) throw new Error('Ошибка загрузки статистики');
        const stats = await response.json();
        
        // Обновляем общую статистику
        statsContainer.innerHTML = `
            <p><strong>Всего подписок:</strong> ${stats.total}</p>
            <p><strong>По типам:</strong></p>
            <ul>
                ${stats.types.map(t => `
                    <li>
                        <span class="type-badge" style="background: ${t.type_color}">${t.type_name}</span>
                        : <strong>${t.subscriber_count}</strong> подписчиков
                    </li>
                `).join('')}
            </ul>
        `;
        
        // Обновляем счетчики в карточках типов
        stats.types.forEach(t => {
            const statElement = document.getElementById(`stat-${t.type_key}`);
            if (statElement) statElement.textContent = t.subscriber_count;
        });
        
    } catch (error) {
        console.error('❌ Ошибка загрузки статистики:', error);
        statsContainer.innerHTML = '<p class="error">Ошибка загрузки статистики</p>';
    }
}

// ========== Управление типами ==========

// Открыть модальное окно для добавления
function openAddModal() {
    modalTitle.textContent = '➕ Добавить тип подписки';
    typeKey.value = '';
    typeName.value = '';
    typeDescription.value = '';
    typeColor.value = '#e2e3e5';
    editingTypeKey.value = '';
    typeKey.disabled = false;
    typeModal.style.display = 'block';
}

// Открыть модальное окно для редактирования
window.editType = function(typeKey) {
    const type = subscriptionTypes.find(t => t.type_key === typeKey);
    if (!type) return;
    
    modalTitle.textContent = '✏️ Редактировать тип';
    typeKey.value = type.type_key;
    typeName.value = type.type_name;
    typeDescription.value = type.type_description || '';
    typeColor.value = type.type_color || '#e2e3e5';
    editingTypeKey.value = type.type_key;
    typeKey.disabled = true; // Ключ нельзя менять
    typeModal.style.display = 'block';
};

// Удалить тип
window.deleteType = async function(typeKey) {
    if (!confirm(`Удалить тип "${typeKey}"? Это действие нельзя отменить.`)) return;
    
    try {
        const response = await fetch(`${SERVER_URL}/api/types/${typeKey}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка удаления');
        }
        
        alert('✅ Тип успешно удален');
        loadSubscriptionTypes(); // Перезагружаем список
        
    } catch (error) {
        alert('❌ ' + error.message);
    }
};

// Сохранить тип (добавить или обновить)
async function saveType() {
    const key = typeKey.value.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_');
    const name = typeName.value.trim();
    const description = typeDescription.value.trim();
    const color = typeColor.value;
    
    if (!key || !name) {
        alert('Заполните ключ и название типа');
        return;
    }
    
    const isEditing = !!editingTypeKey.value;
    const url = isEditing 
        ? `${SERVER_URL}/api/types/${editingTypeKey.value}`
        : `${SERVER_URL}/api/types`;
    
    try {
        const response = await fetch(url, {
            method: isEditing ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type_key: key,
                type_name: name,
                type_description: description,
                type_color: color
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка сохранения');
        }
        
        alert(`✅ Тип успешно ${isEditing ? 'обновлен' : 'добавлен'}`);
        typeModal.style.display = 'none';
        loadSubscriptionTypes(); // Перезагружаем список
        
    } catch (error) {
        alert('❌ ' + error.message);
    }
}

// ========== PWA функционал ==========

async function updateUI() {
    const permission = Notification.permission;
    
    if (swRegistration) {
        try {
            pushSubscription = await swRegistration.pushManager.getSubscription();
        } catch (e) {
            console.error('Ошибка получения подписки:', e);
        }
    }
    
    permissionDiv.className = `status ${permission}`;
    permissionDiv.textContent = `Статус разрешений: ${permission === 'granted' ? '✅ Разрешено' : 
                                 permission === 'denied' ? '❌ Запрещено' : '⏳ Не запрошено'}`;
    
    if (permission === 'granted') {
        subscribeBtn.disabled = !!pushSubscription;
        unsubscribeBtn.disabled = !pushSubscription;
        sendNotificationBtn.disabled = false;
    } else if (permission === 'default') {
        subscribeBtn.disabled = false;
        unsubscribeBtn.disabled = true;
        sendNotificationBtn.disabled = true;
    } else {
        subscribeBtn.disabled = true;
        unsubscribeBtn.disabled = true;
        sendNotificationBtn.disabled = true;
    }
    
    console.log('✅ UI обновлен');
}

async function registerServiceWorker() {
    try {
        swRegistration = await navigator.serviceWorker.register('/service-worker.js');
        console.log('✅ Service Worker зарегистрирован');
        await updateUI();
    } catch (error) {
        console.error('❌ Ошибка регистрации Service Worker:', error);
        permissionDiv.textContent = '❌ Ошибка регистрации Service Worker';
    }
}

async function getVapidPublicKey() {
    const response = await fetch(`${SERVER_URL}/api/vapid-public-key`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const data = await response.json();
    return data.publicKey;
}

async function subscribeToPush() {
    try {
        // Запрашиваем разрешение, если его нет
        if (Notification.permission !== 'granted') {
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') {
                throw new Error('Пользователь не дал разрешение');
            }
        }
        
        // Получаем выбранный тип подписки
        const selectedType = document.querySelector('input[name="subscriptionType"]:checked');
        if (!selectedType) {
            alert('Сначала создайте хотя бы один тип подписки');
            return;
        }
        const subscriptionType = selectedType.value;
        
        // Получаем VAPID ключ
        const vapidPublicKey = await getVapidPublicKey();
        const convertedKey = urlBase64ToUint8Array(vapidPublicKey);
        
        // Создаем подписку
        pushSubscription = await swRegistration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: convertedKey
        });
        
        // Преобразуем подписку в правильный формат
        const subscriptionJSON = pushSubscription.toJSON ? pushSubscription.toJSON() : pushSubscription;
        
        // Формируем данные для отправки на сервер
        const subscriptionData = {
            endpoint: subscriptionJSON.endpoint,
            keys: {
                auth: subscriptionJSON.keys?.auth || '',
                p256dh: subscriptionJSON.keys?.p256dh || ''
            },
            type: subscriptionType
        };
        
        console.log('📤 Отправляем данные на сервер:', subscriptionData);
        
        // Отправляем подписку на сервер
        const response = await fetch(`${SERVER_URL}/api/subscribe`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(subscriptionData)
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.error('❌ Ошибка сервера:', errorData);
            throw new Error(`HTTP error! status: ${response.status}, detail: ${errorData.detail || 'Unknown error'}`);
        }
        
        const result = await response.json();
        console.log(`✅ Подписка типа "${subscriptionType}" создана`, result);
        
        await updateUI();
        await loadStats(); // Обновляем статистику
        
    } catch (error) {
        console.error('❌ Ошибка подписки:', error);
        alert('Ошибка подписки: ' + error.message);
    }
}

async function sendNotification() {
    try {
        const selectedTarget = document.querySelector('input[name="targetType"]:checked');
        if (!selectedTarget) return;
        
        const targetType = selectedTarget.value;
        const title = messageTitle.value.trim() || 'Уведомление';
        const body = messageBody.value.trim() || 'Пустое сообщение';
        
        const confirmMessage = `Отправить сообщение?\n\n` +
            `Кому: ${targetType === 'all' ? 'ВСЕМ подписчикам' : 
                subscriptionTypes.find(t => t.type_key === targetType)?.type_name || targetType}\n` +
            `Заголовок: ${title}\n` +
            `Текст: ${body}\n\n` +
            `Продолжить?`;
        
        if (!confirm(confirmMessage)) return;
        
        const response = await fetch(`${SERVER_URL}/api/send-notification`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                targetType: targetType,
                title: title,
                body: body,
                url: '/'
            })
        });
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const result = await response.json();
        
        alert(`✅ Сообщение отправлено\n\n` +
              `📊 Успешно доставлено: ${result.sent}\n` +
              `❌ Ошибок: ${result.failed}\n` +
              `🗑️ Устаревших подписок удалено: ${result.deleted}`);
        
        await loadStats(); // Обновляем статистику
        
    } catch (error) {
        console.error('❌ Ошибка отправки:', error);
        alert('Ошибка отправки: ' + error.message);
    }
}

async function unsubscribeFromPush() {
    try {
        if (!pushSubscription) return;
        await pushSubscription.unsubscribe();
        pushSubscription = null;
        console.log('✅ Отписались от уведомлений');
        await updateUI();
        await loadStats(); // Обновляем статистику
    } catch (error) {
        console.error('❌ Ошибка отписки:', error);
    }
}

// ========== Инициализация ==========

if ('serviceWorker' in navigator && 'PushManager' in window) {
    console.log('✅ Браузер поддерживает PWA уведомления');
    
    // Загружаем типы подписок
    loadSubscriptionTypes();
    
    // Регистрируем Service Worker
    registerServiceWorker();
    
    // Обработчики событий
    subscribeBtn.addEventListener('click', subscribeToPush);
    unsubscribeBtn.addEventListener('click', unsubscribeFromPush);
    sendNotificationBtn.addEventListener('click', sendNotification);
    
    addTypeBtn.addEventListener('click', openAddModal);
    refreshTypesBtn.addEventListener('click', loadSubscriptionTypes);
    
    saveTypeBtn.addEventListener('click', saveType);
    cancelTypeBtn.addEventListener('click', () => {
        typeModal.style.display = 'none';
    });
    
    // Закрытие модального окна при клике вне его
    window.addEventListener('click', (e) => {
        if (e.target === typeModal) {
            typeModal.style.display = 'none';
        }
    });
    
    // Следим за изменениями разрешений
    if (navigator.permissions) {
        navigator.permissions.query({ name: 'notifications' }).then(permissionStatus => {
            permissionStatus.onchange = updateUI;
        });
    }
    
} else {
    permissionDiv.textContent = '❌ Ваш браузер не поддерживает PWA уведомления';
}