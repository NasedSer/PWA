// Конфигурация
const SERVER_URL = 'https://pwa-791i.onrender.com';
let swRegistration = null;
let pushSubscription = null;

// DOM элементы
const permissionDiv = document.getElementById('permissionStatus');
const subscribeBtn = document.getElementById('subscribeBtn');
const testBtn = document.getElementById('testNotificationBtn');
const unsubscribeBtn = document.getElementById('unsubscribeBtn');
const subscriptionInfo = document.getElementById('subscriptionInfo');
const subscriptionDetails = document.getElementById('subscriptionDetails');

// Вспомогательная функция для преобразования ключа
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

// Обновление UI в зависимости от статуса
async function updateUI() {
    const permission = Notification.permission;
    
    // Получаем актуальную информацию о подписке
    if (swRegistration) {
        try {
            pushSubscription = await swRegistration.pushManager.getSubscription();
        } catch (e) {
            console.error('Ошибка получения подписки:', e);
        }
    }
    
    console.log('🔄 UI обновление:', { 
        permission, 
        hasSubscription: !!pushSubscription,
        swExists: !!swRegistration
    });
    
    // Обновляем класс и текст статуса
    permissionDiv.className = `status ${permission}`;
    permissionDiv.textContent = `Статус разрешений: ${permission === 'granted' ? '✅ Разрешено' : 
                                 permission === 'denied' ? '❌ Запрещено' : '⏳ Не запрошено'}`;
    
    // ИСПРАВЛЕННАЯ ЛОГИКА АКТИВАЦИИ КНОПОК
    if (permission === 'granted') {
        // Если разрешения есть
        subscribeBtn.disabled = !!pushSubscription; // Активна только если НЕТ подписки
        testBtn.disabled = !pushSubscription;       // Активна только если ЕСТЬ подписка
        unsubscribeBtn.disabled = !pushSubscription; // Активна только если ЕСТЬ подписка
    } else if (permission === 'default') {
        // Если разрешения еще не запрашивались
        subscribeBtn.disabled = false;  // Кнопка подписки активна
        testBtn.disabled = true;        // Тест неактивен
        unsubscribeBtn.disabled = true;  // Отписка неактивна
    } else {
        // Если разрешения запрещены
        subscribeBtn.disabled = true;
        testBtn.disabled = true;
        unsubscribeBtn.disabled = true;
    }
    
    // Отображаем информацию о подписке
    if (pushSubscription) {
        subscriptionInfo.style.display = 'block';
        subscriptionDetails.textContent = JSON.stringify(pushSubscription, null, 2);
    } else {
        subscriptionInfo.style.display = 'none';
    }
    
    console.log('✅ UI обновлен:', {
        subscribeBtnActive: !subscribeBtn.disabled,
        testBtnActive: !testBtn.disabled,
        unsubscribeBtnActive: !unsubscribeBtn.disabled
    });
}

// Регистрация Service Worker
async function registerServiceWorker() {
    try {
        swRegistration = await navigator.serviceWorker.register('/service-worker.js');
        console.log('✅ Service Worker зарегистрирован');
        
        // Удаляем неправильный addEventListener
        // Вместо этого просто обновляем UI
        await updateUI();
        
        // Слушаем обновления Service Worker
        swRegistration.addEventListener('updatefound', () => {
            console.log('🔄 Найдено обновление Service Worker');
            const newWorker = swRegistration.installing;
            newWorker.addEventListener('statechange', () => {
                if (newWorker.state === 'activated') {
                    console.log('✅ Новый Service Worker активирован');
                    updateUI();
                }
            });
        });
        
    } catch (error) {
        console.error('❌ Ошибка регистрации Service Worker:', error);
        permissionDiv.textContent = '❌ Ошибка регистрации Service Worker';
    }
}

// Получение VAPID ключа с сервера
async function getVapidPublicKey() {
    try {
        const response = await fetch(`${SERVER_URL}/api/vapid-public-key`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        return data.publicKey;
    } catch (error) {
        console.error('❌ Ошибка получения VAPID ключа:', error);
        throw error;
    }
}

// Подписка на уведомления
async function subscribeToPush() {
    try {
        // Запрашиваем разрешение, если его нет
        if (Notification.permission !== 'granted') {
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') {
                throw new Error('Пользователь не дал разрешение');
            }
        }
        
        // Получаем VAPID ключ
        const vapidPublicKey = await getVapidPublicKey();
        const convertedKey = urlBase64ToUint8Array(vapidPublicKey);
        
        // Создаем подписку
        pushSubscription = await swRegistration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: convertedKey
        });
        
        // Отправляем подписку на сервер
        const response = await fetch(`${SERVER_URL}/api/subscribe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(pushSubscription)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        console.log('✅ Подписка создана и сохранена на сервере');
        await updateUI();
        
    } catch (error) {
        console.error('❌ Ошибка подписки:', error);
        alert('Ошибка подписки: ' + error.message);
    }
}

// Отправка тестового уведомления
async function sendTestNotification() {
    try {
        const response = await fetch(`${SERVER_URL}/api/send-notification`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: 'Тест PWA',
                body: 'Это тестовое уведомление с сервера!',
                url: '/'
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        console.log('✅ Результат отправки:', result);
        alert(`Уведомление отправлено ${result.sent} подписчикам`);
        
    } catch (error) {
        console.error('❌ Ошибка отправки:', error);
        alert('Ошибка отправки уведомления. Проверьте консоль.');
    }
}

// Отписка от уведомлений
async function unsubscribeFromPush() {
    try {
        if (!pushSubscription) {
            console.log('Нет активной подписки');
            return;
        }
        
        await pushSubscription.unsubscribe();
        pushSubscription = null;
        console.log('✅ Отписались от уведомлений');
        
        // Обновляем UI
        await updateUI();
        
    } catch (error) {
        console.error('❌ Ошибка отписки:', error);
    }
}

// Инициализация
if ('serviceWorker' in navigator && 'PushManager' in window) {
    console.log('✅ Браузер поддерживает PWA уведомления');
    
    // Регистрируем Service Worker
    registerServiceWorker();
    
    // Обработчики кнопок
    subscribeBtn.addEventListener('click', subscribeToPush);
    testBtn.addEventListener('click', sendTestNotification);
    unsubscribeBtn.addEventListener('click', unsubscribeFromPush);
    
    // Следим за изменениями разрешений
    if (navigator.permissions && navigator.permissions.query) {
        navigator.permissions.query({ name: 'notifications' }).then(permissionStatus => {
            permissionStatus.onchange = () => {
                console.log('🔄 Изменился статус разрешений');
                updateUI();
            };
        });
    }
    
} else {
    permissionDiv.textContent = '❌ Ваш браузер не поддерживает PWA уведомления';
    console.error('❌ Браузер не поддерживает необходимые API');
}