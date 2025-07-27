// Ezyago Admin Panel JavaScript
class EzyagoAdmin {
    constructor() {
        this.apiUrl = window.location.origin;
        this.token = localStorage.getItem('ezyago_admin_token');
        this.currentPage = 'dashboard';
        this.confirmationCallback = null;
        
        this.init();
    }

    async init() {
        // Hide loading screen
        setTimeout(() => {
            document.getElementById('loading-screen').style.display = 'none';
        }, 1000);

        // Check if admin is logged in
        if (this.token) {
            await this.verifyAdminToken();
        } else {
            this.showLogin();
        }

        this.setupEventListeners();
    }

    setupEventListeners() {
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                this.navigateToPage(page);
            });
        });

        // Admin login form
        document.getElementById('admin-login-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleAdminLogin();
        });

        // User search
        document.getElementById('user-search')?.addEventListener('input', (e) => {
            this.filterUsers(e.target.value);
        });

        // Auto-refresh data
        if (this.token) {
            setInterval(() => {
                if (this.currentPage === 'dashboard') {
                    this.loadDashboardStats();
                }
            }, 120000); // Refresh every 2 minutes
        }
    }

    // Authentication Methods
    async handleAdminLogin() {
        const email = document.getElementById('admin-email').value;
        const password = document.getElementById('admin-password').value;
        const errorEl = document.getElementById('login-error');

        try {
            const response = await this.apiCall('/api/auth/login', 'POST', {
                email,
                password
            });

            if (response.access_token && response.user.role === 'admin') {
                this.token = response.access_token;
                localStorage.setItem('ezyago_admin_token', this.token);
                
                this.showDashboard();
                this.showNotification('Admin girişi başarılı!', 'success');
            } else {
                errorEl.textContent = 'Admin yetkisi bulunamadı.';
            }
        } catch (error) {
            errorEl.textContent = error.message || 'Giriş yapılırken hata oluştu';
        }
    }

    async verifyAdminToken() {
        try {
            const response = await this.apiCall('/api/user/profile', 'GET');
            if (response.role === 'admin') {
                this.showDashboard();
            } else {
                this.adminLogout();
            }
        } catch (error) {
            this.adminLogout();
        }
    }

    adminLogout() {
        this.token = null;
        localStorage.removeItem('ezyago_admin_token');
        this.showLogin();
        this.showNotification('Çıkış yapıldı.', 'info');
    }

    // Dashboard Methods
    async loadDashboardStats() {
        try {
            const stats = await this.apiCall('/api/admin/stats', 'GET');
            this.updateDashboardStats(stats);
        } catch (error) {
            console.error('Failed to load dashboard stats:', error);
        }
    }

    updateDashboardStats(stats) {
        document.getElementById('total-users').textContent = stats.total_users || 0;
        document.getElementById('active-subscribers').textContent = stats.active_subscribers || 0;
        document.getElementById('total-revenue').textContent = `$${stats.total_revenue || 0}`;
        document.getElementById('active-bots').textContent = stats.active_bots || 0;
        document.getElementById('pending-payments-badge').textContent = stats.pending_payments || 0;
    }

    // Users Management
    async loadUsers() {
        try {
            const users = await this.apiCall('/api/admin/users', 'GET');
            this.displayUsers(users);
        } catch (error) {
            console.error('Failed to load users:', error);
            this.showNotification('Kullanıcılar yüklenirken hata oluştu', 'error');
        }
    }

    displayUsers(users) {
        const tbody = document.getElementById('users-table-body');
        
        if (users.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="loading-row">
                        <div class="table-loading">
                            <span>Henüz kullanıcı bulunmuyor</span>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = users.map(user => `
            <tr data-user-id="${user.uid}">
                <td>
                    <div class="user-info">
                        <div class="user-avatar">
                            ${user.full_name.charAt(0).toUpperCase()}
                        </div>
                        <div class="user-details">
                            <h4>${user.full_name}</h4>
                            <p>${user.email}</p>
                        </div>
                    </div>
                </td>
                <td>
                    <span class="status-badge ${user.subscription_status}">
                        ${this.getSubscriptionStatusText(user.subscription_status)}
                    </span>
                </td>
                <td>
                    <div class="bot-status">
                        <div class="bot-status-dot ${user.bot_status}"></div>
                        <span>${this.getBotStatusText(user.bot_status)}</span>
                    </div>
                </td>
                <td>${this.formatDate(user.created_at)}</td>
                <td>
                    <div class="user-actions">
                        ${user.is_blocked ? 
                            `<button class="btn btn-sm btn-secondary" onclick="adminApp.unblockUser('${user.uid}')">
                                <i class="fas fa-unlock"></i>
                            </button>` :
                            `<button class="btn btn-sm btn-danger" onclick="adminApp.blockUser('${user.uid}')">
                                <i class="fas fa-ban"></i>
                            </button>`
                        }
                    </div>
                </td>
            </tr>
        `).join('');
    }

    filterUsers(searchTerm) {
        const rows = document.querySelectorAll('#users-table-body tr[data-user-id]');
        
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            const matches = text.includes(searchTerm.toLowerCase());
            row.style.display = matches ? '' : 'none';
        });
    }

    async blockUser(userId) {
        this.showConfirmation(
            'Kullanıcıyı Engelle',
            'Bu kullanıcıyı engellemek istediğinizden emin misiniz? Kullanıcı sisteme giriş yapamayacak.',
            async () => {
                try {
                    await this.apiCall(`/api/admin/users/${userId}/block`, 'POST');
                    this.showNotification('Kullanıcı engellendi', 'success');
                    this.loadUsers();
                } catch (error) {
                    this.showNotification('Kullanıcı engellenirken hata oluştu', 'error');
                }
            }
        );
    }

    async unblockUser(userId) {
        try {
            await this.apiCall(`/api/admin/users/${userId}/unblock`, 'POST');
            this.showNotification('Kullanıcı engeli kaldırıldı', 'success');
            this.loadUsers();
        } catch (error) {
            this.showNotification('Engel kaldırılırken hata oluştu', 'error');
        }
    }

    // Payments Management
    async loadPayments() {
        try {
            const payments = await this.apiCall('/api/admin/payments/pending', 'GET');
            this.displayPayments(payments);
        } catch (error) {
            console.error('Failed to load payments:', error);
            this.showNotification('Ödemeler yüklenirken hata oluştu', 'error');
        }
    }

    displayPayments(payments) {
        const container = document.getElementById('pending-payments-list');
        
        if (payments.length === 0) {
            container.innerHTML = `
                <div class="loading-item">
                    <span>Bekleyen ödeme bulunmuyor</span>
                </div>
            `;
            return;
        }

        container.innerHTML = payments.map(payment => `
            <div class="payment-card">
                <div class="payment-header">
                    <div class="payment-user">
                        <div class="user-avatar">
                            ${payment.user_id.charAt(0).toUpperCase()}
                        </div>
                        <div>
                            <h4>Kullanıcı: ${payment.user_id}</h4>
                            <p>Ödeme ID: ${payment.payment_id}</p>
                        </div>
                    </div>
                    <div class="payment-amount">$${payment.amount}</div>
                </div>
                
                <div class="payment-details">
                    <div class="payment-detail">
                        <span class="label">Tarih:</span>
                        <span class="value">${this.formatDate(payment.created_at)}</span>
                    </div>
                    ${payment.transaction_hash ? `
                        <div class="payment-detail">
                            <span class="label">TX Hash:</span>
                            <span class="value">${payment.transaction_hash.substring(0, 20)}...</span>
                        </div>
                    ` : ''}
                    ${payment.message ? `
                        <div class="payment-detail">
                            <span class="label">Mesaj:</span>
                            <span class="value">${payment.message}</span>
                        </div>
                    ` : ''}
                </div>
                
                <div class="payment-actions">
                    <button class="btn btn-secondary" onclick="adminApp.approvePayment('${payment.payment_id}')">
                        <i class="fas fa-check"></i>
                        Onayla
                    </button>
                    <button class="btn btn-danger" onclick="adminApp.rejectPayment('${payment.payment_id}')">
                        <i class="fas fa-times"></i>
                        Reddet
                    </button>
                </div>
            </div>
        `).join('');
    }

    async approvePayment(paymentId) {
        this.showConfirmation(
            'Ödemeyi Onayla',
            'Bu ödemeyi onaylamak istediğinizden emin misiniz? Kullanıcının aboneliği 30 gün uzatılacak.',
            async () => {
                try {
                    await this.apiCall(`/api/admin/payments/${paymentId}/approve`, 'POST');
                    this.showNotification('Ödeme onaylandı ve abonelik uzatıldı', 'success');
                    this.loadPayments();
                    this.loadDashboardStats();
                } catch (error) {
                    this.showNotification('Ödeme onaylanırken hata oluştu', 'error');
                }
            }
        );
    }

    async rejectPayment(paymentId) {
        this.showConfirmation(
            'Ödemeyi Reddet',
            'Bu ödemeyi reddetmek istediğinizden emin misiniz?',
            async () => {
                // TODO: Implement payment rejection endpoint
                this.showNotification('Ödeme reddedildi', 'info');
                this.loadPayments();
            }
        );
    }

    // Bots Management
    async loadBots() {
        try {
            // TODO: Implement bot status endpoint
            const bots = []; // await this.apiCall('/api/admin/bots', 'GET');
            this.displayBots(bots);
        } catch (error) {
            console.error('Failed to load bots:', error);
        }
    }

    displayBots(bots) {
        const container = document.getElementById('bots-grid');
        
        if (bots.length === 0) {
            container.innerHTML = `
                <div class="loading-item">
                    <span>Aktif bot bulunmuyor</span>
                </div>
            `;
            return;
        }

        container.innerHTML = bots.map(bot => `
            <div class="bot-card">
                <div class="bot-card-header">
                    <div class="bot-user">${bot.user_email}</div>
                    <div class="bot-status">
                        <div class="bot-status-dot ${bot.status}"></div>
                        <span>${this.getBotStatusText(bot.status)}</span>
                    </div>
                </div>
                
                <div class="bot-card-content">
                    <div class="bot-detail">
                        <span class="label">Sembol:</span>
                        <span class="value">${bot.symbol || '-'}</span>
                    </div>
                    <div class="bot-detail">
                        <span class="label">Pozisyon:</span>
                        <span class="value">${bot.position_side || '-'}</span>
                    </div>
                    <div class="bot-detail">
                        <span class="label">Çalışma Süresi:</span>
                        <span class="value">${this.formatUptime(bot.uptime || 0)}</span>
                    </div>
                    <div class="bot-detail">
                        <span class="label">Toplam İşlem:</span>
                        <span class="value">${bot.total_trades || 0}</span>
                    </div>
                </div>
            </div>
        `).join('');
    }

    // Settings Management
    async loadSettings() {
        // Load current settings
        document.getElementById('last-update').textContent = new Date().toLocaleString('tr-TR');
    }

    async saveSettings() {
        const walletAddress = document.getElementById('usdt-wallet').value;
        const subscriptionPrice = document.getElementById('subscription-price').value;

        // TODO: Implement settings save endpoint
        this.showNotification('Ayarlar kaydedildi', 'success');
    }

    // Navigation Methods
    navigateToPage(page) {
        // Update active nav item
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-page="${page}"]`)?.classList.add('active');

        // Show page
        document.querySelectorAll('.page').forEach(p => {
            p.classList.remove('active');
        });
        document.getElementById(`${page}-page`)?.classList.add('active');

        // Update page title
        const titles = {
            dashboard: 'Dashboard',
            users: 'Kullanıcı Yönetimi',
            payments: 'Ödeme Yönetimi',
            bots: 'Bot Durumu',
            settings: 'Sistem Ayarları'
        };
        
        document.getElementById('page-title').textContent = titles[page] || 'Admin Panel';
        this.currentPage = page;

        // Load page-specific data
        switch (page) {
            case 'dashboard':
                this.loadDashboardStats();
                break;
            case 'users':
                this.loadUsers();
                break;
            case 'payments':
                this.loadPayments();
                break;
            case 'bots':
                this.loadBots();
                break;
            case 'settings':
                this.loadSettings();
                break;
        }
    }

    // UI Methods
    showLogin() {
        document.getElementById('admin-login').style.display = 'flex';
        document.getElementById('admin-dashboard').style.display = 'none';
    }

    showDashboard() {
        document.getElementById('admin-login').style.display = 'none';
        document.getElementById('admin-dashboard').style.display = 'flex';
        this.navigateToPage('dashboard');
    }

    showConfirmation(title, message, callback) {
        document.getElementById('modal-title').textContent = title;
        document.getElementById('modal-message').textContent = message;
        this.confirmationCallback = callback;
        
        const modal = document.getElementById('confirmation-modal');
        modal.classList.add('active');
    }

    closeConfirmationModal() {
        const modal = document.getElementById('confirmation-modal');
        modal.classList.remove('active');
        this.confirmationCallback = null;
    }

    confirmAction() {
        if (this.confirmationCallback) {
            this.confirmationCallback();
        }
        this.closeConfirmationModal();
    }

    showNotification(message, type = 'info') {
        const notification = document.getElementById('notification');
        const icon = notification.querySelector('.notification-icon');
        const messageEl = notification.querySelector('.notification-message');

        // Set icon based on type
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            info: 'fas fa-info-circle',
            warning: 'fas fa-exclamation-triangle'
        };

        icon.className = `notification-icon ${icons[type] || icons.info}`;
        messageEl.textContent = message;
        
        notification.className = `notification ${type}`;
        notification.classList.add('show');

        // Auto hide after 5 seconds
        setTimeout(() => {
            notification.classList.remove('show');
        }, 5000);
    }

    // Utility Methods
    async apiCall(endpoint, method = 'GET', data = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            }
        };
    
        if (this.token) {
            options.headers['Authorization'] = `Bearer ${this.token}`;
        }
    
        if (data) {
            options.body = JSON.stringify(data);
        }
    
        try {
            const response = await fetch(`${this.apiUrl}${endpoint}`, options);
            
            const responseText = await response.text();
            let result;
    
            try {
                result = JSON.parse(responseText);
            } catch (e) {
                result = { detail: responseText };
            }
    
            if (!response.ok) {
                const errorMessage = result.detail || result.message || 'API isteği başarısız oldu';
                throw new Error(errorMessage);
            }
    
            return result;
    
        } catch (error) {
            console.error(`API Call Error (${endpoint}):`, error);
            throw error;
        }
    }

    getSubscriptionStatusText(status) {
        const statusTexts = {
            trial: 'Deneme',
            active: 'Aktif',
            expired: 'Süresi Dolmuş',
            cancelled: 'İptal Edilmiş'
        };
        return statusTexts[status] || status;
    }

    getBotStatusText(status) {
        const statusTexts = {
            running: 'Çalışıyor',
            stopped: 'Durduruldu',
            error: 'Hata'
        };
        return statusTexts[status] || status;
    }

    formatDate(dateString) {
        if (!dateString) return '-';
        return new Date(dateString).toLocaleDateString('tr-TR');
    }

    formatUptime(seconds) {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
        return `${Math.floor(seconds / 86400)}d`;
    }

    // Refresh methods
    refreshAllData() {
        this.loadDashboardStats();
        this.showNotification('Veriler yenilendi', 'success');
    }



    refreshUsers() {
        this.loadUsers();
    }

    refreshPayments() {
        this.loadPayments();
    }

    refreshBots() {
        this.loadBots();
    }
}

// Global functions for HTML onclick handlers
function adminLogout() {
    adminApp.adminLogout();
}

function navigateToPage(page) {
    adminApp.navigateToPage(page);
}

function closeConfirmationModal() {
    adminApp.closeConfirmationModal();
}

function confirmAction() {
    adminApp.confirmAction();
}

function refreshAllData() {
    adminApp.refreshAllData();
}

function refreshUsers() {
    adminApp.refreshUsers();
}

function refreshPayments() {
    adminApp.refreshPayments();
}

function refreshBots() {
    adminApp.refreshBots();
}

function saveSettings() {
    adminApp.saveSettings();
}

function showAddIPModal() {
    adminApp.showAddIPModal();
}

function closeAddIPModal() {
    adminApp.closeAddIPModal();
}

function refreshIPWhitelist() {
    adminApp.loadIPWhitelist();
}

// Initialize admin app when DOM is loaded
let adminApp;
document.addEventListener('DOMContentLoaded', () => {
    adminApp = new EzyagoAdmin();
    
    // Add IP form handler
    document.getElementById('add-ip-form')?.addEventListener('submit', (e) => {
        e.preventDefault();
        adminApp.addIP();
    });
});
