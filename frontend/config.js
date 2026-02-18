// frontend/config.js
// Файл конфигурации для переключения между локальным сервером и Render

// Определяем окружение
const hostname = window.location.hostname;
const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
const isGithubPages = hostname.includes('github.io');
const isRender = hostname.includes('onrender.com');

// Выбираем URL сервера
let SERVER_URL;
if (isLocalhost) {
    SERVER_URL = 'http://localhost:5000';
} else if (isGithubPages) {
    SERVER_URL = 'https://pwa-791i.onrender.com';
} else if (isRender) {
    SERVER_URL = `https://${hostname}`;
} else {
    SERVER_URL = 'https://pwa-791i.onrender.com'; // fallback
}

export { SERVER_URL };

// Подробная диагностика
console.log('📋 Конфигурация PWA:');
console.log('   Хост:', hostname);
console.log('   Окружение:', 
    isLocalhost ? 'Локальное' : 
    isGithubPages ? 'GitHub Pages' : 
    isRender ? 'Render' : 'Неизвестное'
);
console.log('   API сервер:', SERVER_URL);

// Для отладки в консоли
if (isLocalhost) {
    window.DEBUG = { SERVER_URL, hostname, isLocalhost };
}