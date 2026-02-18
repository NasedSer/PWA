self.addEventListener('push', function(event) {
    if (!(self.Notification && self.Notification.permission === 'granted')) {
        return;
    }

    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data = { title: 'Новое уведомление', body: event.data.text() };
        }
    }

    const title = data.title || 'PWA Уведомление';
    const options = {
        body: data.body || '...',
        icon: data.icon || '/icons/icon-192.png',
        badge: data.badge || '/icons/badge.png',
        vibrate: [200, 100, 200],
        data: data.data || { url: '/' },
        actions: [
            { action: 'open', title: 'Открыть' },
            { action: 'close', title: 'Закрыть' }
        ]
    };

    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    
    if (event.action === 'close') {
        return;
    }
    
    const urlToOpen = event.notification.data?.url || '/';
    event.waitUntil(clients.openWindow(urlToOpen));
});