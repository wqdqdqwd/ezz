// Ezyago Frontend JavaScript

class EzyagoApp {
    constructor() {
        this.apiUrl = window.location.origin;
        this.token = localStorage.getItem('ezyago_token');
        this.user = null;
        this.currentPage = 'overview';
        
        this.init();
    }

    async init() {
        // Hide loading screen after a short delay
        setTimeout(() => {
            document.getElementById('loading-screen').style.display = 'none';
        }, 1000);

        // Check if user is logged in
        if (this.token) {
            await this.loadUserProfile();
            this.showDashboard();
        } else {
            this.showLandingPage();
        }

        this.setupEventListeners();
        this.setupFAQ();
        this.startDemoChart();
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

        // Forms
        document.getElementById('login-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleLogin();
        });

        document.getElementById('register-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleRegister();
        });

        document.getElementById('forgot-password-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleForgotPassword();
        });

        // Modal close on backdrop click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal(modal.id);
                }
            });
        });

        // Auto-refresh dashboard data
        if (this.token) {
            setInterval(() => {
                if (this.currentPage === 'overview') {
                    this.loadDashboardData();
                }
            }, 120000); // Refresh every 10 seconds
        }
    }

    setupFAQ() {
        document.querySelectorAll('.faq-question').forEach(question => {
            question.addEventListener('click', () => {
                const faqItem = question.parentElement;
                const isActive = faqItem.classList.contains('active');
                
                // Close all FAQ items
                document.querySelectorAll('.faq-item').forEach(item => {
                    item.classList.remove('active');
                });
                
                // Open clicked item if it wasn't active
                if (!isActive) {
                    faqItem.classList.add('active');
                }
            });
        });
    }

    startDemoChart() {
        const canvas = document.getElementById('demo-chart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        // Generate demo chart data
        const points = [];
        for (let i = 0; i < 50; i++) {
            points.push({
                x: (i / 49) * width,
                y: height/2 + Math.sin(i * 0.3) * 30 + Math.random() * 20 - 10
            });
        }

        // Draw chart
        ctx.clearRect(0, 0, width, height);
        ctx.strokeStyle = '#6366f1';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        points.forEach((point, index) => {
            if (index === 0) {
                ctx.moveTo(point.x, point.y);
            } else {
                ctx.lineTo(point.x, point.y);
            }
        });
        
        ctx.stroke();

        // Add gradient fill
        ctx.globalAlpha = 0.1;
        ctx.fillStyle = '#6366f1';
        ctx.lineTo(width, height);
        ctx.lineTo(0, height);
        ctx.closePath();
        ctx.fill();
    }

    // Authentication Methods
    async handleLogin() {
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;

        // Client-side validation
        if (!email || !password) {
            this.showNotification('E-posta ve şifre gereklidir.', 'error');
            return;
        }
        
        console.log('🔄 Attempting login for:', email);
        
        try {
            const response = await this.apiCall('/api/auth/login', 'POST', {
                email,
                password
            });

            if (response.access_token) {
                this.token = response.access_token;
                localStorage.setItem('ezyago_token', this.token);
                this.user = response.user;
                
                console.log('✅ Login successful, user role:', this.user.role);
                
                // Check if admin
                if (this.user.role === 'admin') {
                    console.log('👑 Admin user detected, redirecting to admin panel');
                    window.location.href = '/admin';
                    return;
                }
                
                this.closeModal('login-modal');
                this.showDashboard();
                this.showNotification('Başarıyla giriş yaptınız!', 'success');
            }
        } catch (error) {
            console.error('❌ Login error:', error);
            let errorMessage = 'Giriş yapılırken hata oluştu';
            
            if (error.message.includes('Invalid email or password')) {
                errorMessage = 'E-posta veya şifre hatalı.';
            } else if (error.message.includes('blocked')) {
                errorMessage = 'Hesabınız engellenmiş. Lütfen destek ile iletişime geçin.';
            }
            
            this.showNotification(errorMessage, 'error');
        }
    }

    async handleRegister() {
        const fullName = document.getElementById('register-name').value;
        const email = document.getElementById('register-email').value;
        const password = document.getElementById('register-password').value;

        // Client-side validation
        if (!fullName || !email || !password) {
            this.showNotification('Lütfen tüm alanları doldurun.', 'error');
            return;
        }

        if (password.length < 6) {
            this.showNotification('Şifre en az 6 karakter olmalıdır.', 'error');
            return;
        }

        if (!email.includes('@')) {
            this.showNotification('Geçerli bir e-posta adresi girin.', 'error');
            return;
        }
        
        console.log('🔄 Starting registration process...');
        
        try {
            const response = await this.apiCall('/api/auth/register', 'POST', {
                full_name: fullName,
                email,
                password,
                language: 'tr'
            });

            if (response.access_token) {
                this.token = response.access_token;
                localStorage.setItem('ezyago_token', this.token);
                this.user = response.user;
                
                this.closeModal('register-modal');
                this.showDashboard();
                this.showNotification('Hesabınız başarıyla oluşturuldu! 7 günlük deneme süreniz başladı.', 'success');
                console.log('✅ Registration successful');
            }
        } catch (error) {
            console.error('❌ Registration error:', error);
            let errorMessage = 'Kayıt olurken hata oluştu';
            
            if (error.message.includes('already exists')) {
                errorMessage = 'Bu e-posta adresi zaten kullanılıyor.';
            } else if (error.message.includes('password')) {
                errorMessage = 'Şifre çok zayıf. En az 6 karakter kullanın.';
            } else if (error.message.includes('email')) {
                errorMessage = 'Geçersiz e-posta adresi.';
            } else if (error.message.includes('Failed to create')) {
                errorMessage = 'Hesap oluşturulamadı. Lütfen bilgilerinizi kontrol edin.';
            } else {
                errorMessage = `Kayıt hatası: ${error.message}`;
            }
            
            this.showNotification(errorMessage, 'error');
        }
    }

    async handleForgotPassword() {
        const email = document.getElementById('forgot-email').value;

        try {
            await this.apiCall('/api/auth/forgot-password', 'POST', { email });
            this.closeModal('forgot-password-modal');
            this.showNotification('Şifre sıfırlama bağlantısı e-posta adresinize gönderildi.', 'success');
        } catch (error) {
            this.showNotification(error.message || 'Şifre sıfırlama isteği gönderilirken hata oluştu', 'error');
        }
    }

    async loadUserProfile() {
        try {
            const response = await this.apiCall('/api/user/profile', 'GET');
            this.user = response;
            this.updateUserInfo();
        } catch (error) {
            console.error('Failed to load user profile:', error);
            this.logout();
        }
    }

    logout() {
        this.token = null;
        this.user = null;
        localStorage.removeItem('ezyago_token');
        this.showLandingPage();
        this.showNotification('Başarıyla çıkış yaptınız.', 'info');
    }

    // Dashboard Methods
    async loadDashboardData() {
        try {
            // Get bot status (which now includes updated user stats)
            const botStatus = await this.apiCall('/api/bot/status', 'GET');

            this.updateBotStatus(botStatus);
            
            // Update user stats from bot status response
            const userStats = {
                total_trades: botStatus.total_trades,
                winning_trades: botStatus.winning_trades,
                losing_trades: botStatus.losing_trades,
                total_pnl: botStatus.total_pnl
            };
            this.updateUserStats(userStats);
            
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
        }
    }

    updateBotStatus(status) {
        // Update status indicator
        const statusIndicator = document.getElementById('status-indicator');
        const statusText = statusIndicator?.querySelector('.status-text');
        
        if (status.status === 'running') {
            statusIndicator?.classList.add('running');
            if (statusText) statusText.textContent = 'Çalışıyor';
        } else {
            statusIndicator?.classList.remove('running');
            if (statusText) statusText.textContent = 'Durduruldu';
        }

        // Update bot info
        const botStatusEl = document.getElementById('bot-status');
        const currentSymbolEl = document.getElementById('current-symbol');
        const currentPositionEl = document.getElementById('current-position');
        const lastSignalEl = document.getElementById('last-signal');
        const uptimeEl = document.getElementById('uptime');
        
        if (botStatusEl) botStatusEl.textContent = status.status === 'running' ? 'Çalışıyor' : 'Durduruldu';
        if (currentSymbolEl) currentSymbolEl.textContent = status.symbol || '-';
        if (currentPositionEl) currentPositionEl.textContent = status.position_side || '-';
        if (lastSignalEl) lastSignalEl.textContent = status.last_signal || '-';
        if (uptimeEl) uptimeEl.textContent = this.formatUptime(status.uptime || 0);

        // Update control buttons
        const startBtn = document.getElementById('start-bot-btn');
        const stopBtn = document.getElementById('stop-bot-btn');
        
        if (startBtn && stopBtn) {
            if (status.status === 'running') {
                startBtn.disabled = true;
                stopBtn.disabled = false;
            } else {
                startBtn.disabled = false;
                stopBtn.disabled = true;
            }
        }
    }

    updateUserStats(user) {
        const winRate = user.total_trades > 0 ? ((user.winning_trades / user.total_trades) * 100).toFixed(1) : 0;
        
        document.getElementById('total-trades').textContent = user.total_trades || 0;
        document.getElementById('win-rate').textContent = `${winRate}%`;
        
        const totalPnl = user.total_pnl || 0;
        const pnlElement = document.getElementById('total-pnl');
        pnlElement.textContent = `$${totalPnl.toFixed(2)}`;
        
        // Color code the PnL
        if (totalPnl > 0) {
            pnlElement.style.color = 'var(--secondary-color)';
        } else if (totalPnl < 0) {
            pnlElement.style.color = 'var(--danger-color)';
        } else {
            pnlElement.style.color = 'var(--text-primary)';
        }
        
        // Update detailed stats
        document.getElementById('stats-total').textContent = user.total_trades || 0;
        document.getElementById('stats-winning').textContent = user.winning_trades || 0;
        document.getElementById('stats-losing').textContent = user.losing_trades || 0;
        
        const totalProfit = Math.max(0, user.total_pnl || 0);
        const totalLoss = Math.min(0, user.total_pnl || 0);
        
        document.getElementById('stats-profit').textContent = `$${totalProfit.toFixed(2)}`;
        document.getElementById('stats-loss').textContent = `$${Math.abs(totalLoss).toFixed(2)}`;
    }

    updateUserInfo() {
        if (!this.user) return;
        
        document.getElementById('user-name').textContent = this.user.full_name;
        document.getElementById('user-email').textContent = this.user.email;
        
        // Update subscription info
        document.getElementById('subscription-status').textContent = 
            this.user.subscription_status === 'trial' ? 'Deneme Süresi' : 'Premium';
        
        const endDate = this.user.subscription_status === 'trial' 
            ? this.user.trial_end_date 
            : this.user.subscription_end_date;
            
        if (endDate) {
            const remaining = this.calculateRemainingTime(endDate);
            document.getElementById('remaining-time').textContent = remaining;
            document.getElementById('end-date').textContent = new Date(endDate).toLocaleDateString('tr-TR');
        }
    }

    // Bot Control Methods
    async loadBotSettings() {
        try {
            const settings = await this.apiCall('/api/bot/settings', 'GET');
            
            document.getElementById('order-size').value = settings.order_size_usdt;
            document.getElementById('leverage').value = settings.leverage;
            document.getElementById('stop-loss').value = settings.stop_loss_percent;
            document.getElementById('take-profit').value = settings.take_profit_percent;
            document.getElementById('timeframe').value = settings.timeframe;
            
        } catch (error) {
            console.error('Failed to load bot settings:', error);
        }
    }

    async saveBotSettings() {
        const orderSize = parseFloat(document.getElementById('order-size').value);
        const leverage = parseInt(document.getElementById('leverage').value);
        const stopLoss = parseFloat(document.getElementById('stop-loss').value);
        const takeProfit = parseFloat(document.getElementById('take-profit').value);
        const timeframe = document.getElementById('timeframe').value;

        try {
            await this.apiCall('/api/bot/settings', 'POST', {
                order_size_usdt: orderSize,
                leverage: leverage,
                stop_loss_percent: stopLoss,
                take_profit_percent: takeProfit,
                timeframe: timeframe
            });
            
            this.showNotification('Bot ayarları başarıyla kaydedildi!', 'success');
        } catch (error) {
            this.showNotification(error.message || 'Bot ayarları kaydedilirken hata oluştu', 'error');
        }
    }

    resetBotSettings() {
        document.getElementById('order-size').value = 25;
        document.getElementById('leverage').value = 10;
        document.getElementById('stop-loss').value = 4;
        document.getElementById('take-profit').value = 8;
        document.getElementById('timeframe').value = '15m';
    }

    async startBot() {
        const symbol = document.getElementById('symbol-input').value.trim().toUpperCase();
        
        if (!symbol) {
            this.showNotification('Lütfen bir trading sembolü girin.', 'error');
            return;
        }

        try {
            console.log(`🔄 Starting bot for symbol: ${symbol}`);
            const response = await this.apiCall('/api/bot/start', 'POST', { symbol });
            
            // Extract message from response
            let message = 'Bot başlatıldı!';
            if (response) {
                if (typeof response === 'string') {
                    message = response;
                } else if (response.message) {
                    message = response.message;
                } else if (response.detail) {
                    message = response.detail;
                } else if (response.status_message) {
                    message = response.status_message;
                } else {
                    message = `Bot ${symbol} için başarıyla başlatıldı!`;
                }
            }
            
            console.log(`✅ Bot start success: ${message}`);
            this.showNotification(message, 'success');
            
            this.loadDashboardData();
        } catch (error) {
            console.error('Bot start error:', error);
            let errorMessage = 'Bot başlatılırken hata oluştu.';
            
            // Extract error message properly
            if (error && typeof error === 'object') {
                if (error.message) {
                    errorMessage = error.message;
                } else if (error.detail) {
                    errorMessage = error.detail;
                } else if (error.error) {
                    errorMessage = error.error;
                } else {
                    errorMessage = JSON.stringify(error);
                }
            } else if (typeof error === 'string') {
                errorMessage = error;
            }
            
            console.error(`❌ Bot start failed: ${errorMessage}`);
            this.showNotification(errorMessage, 'error');
        }
    }

    async stopBot() {
        try {
            console.log('🔄 Stopping bot...');
            const response = await this.apiCall('/api/bot/stop', 'POST');
            
            // Extract message from response
            let message = 'Bot durduruldu.';
            if (response) {
                if (typeof response === 'string') {
                    message = response;
                } else if (response.message) {
                    message = response.message;
                } else if (response.detail) {
                    message = response.detail;
                } else if (response.status_message) {
                    message = response.status_message;
                }
            }
            
            console.log(`✅ Bot stop success: ${message}`);
            this.showNotification(message, 'info');
            
            this.loadDashboardData();
        } catch (error) {
            console.error('Bot stop error:', error);
            let errorMessage = 'Bot durdurulurken hata oluştu.';
            
            // Extract error message properly
            if (error && typeof error === 'object') {
                if (error.message) {
                    errorMessage = error.message;
                } else if (error.detail) {
                    errorMessage = error.detail;
                } else if (error.error) {
                    errorMessage = error.error;
                } else {
                    errorMessage = JSON.stringify(error);
                }
            } else if (typeof error === 'string') {
                errorMessage = error;
            }
            
            console.error(`❌ Bot stop failed: ${errorMessage}`);
            this.showNotification(errorMessage, 'error');
        }
    }

    // API Keys Methods
    async saveApiKeys() {
        const apiKey = document.getElementById('api-key').value.trim();
        const apiSecret = document.getElementById('api-secret').value.trim();
        const isTestnet = document.getElementById('is-testnet').checked;

        if (!apiKey || !apiSecret) {
            this.showNotification('Lütfen API Key ve Secret alanlarını doldurun.', 'error');
            return;
        }

        try {
            await this.apiCall('/api/user/api-keys', 'POST', {
                api_key: apiKey,
                api_secret: apiSecret,
                is_testnet: isTestnet
            });
            
            this.showNotification('API anahtarları başarıyla kaydedildi.', 'success');
            
            // Clear form
            document.getElementById('api-key').value = '';
            document.getElementById('api-secret').value = '';
        } catch (error) {
            this.showNotification(error.message || 'API anahtarları kaydedilirken hata oluştu', 'error');
        }
    }

    async deleteApiKeys() {
        if (!confirm('API anahtarlarınızı silmek istediğinizden emin misiniz?')) {
            return;
        }

        try {
            await this.apiCall('/api/user/api-keys', 'DELETE');
            this.showNotification('API anahtarları silindi.', 'info');
        } catch (error) {
            this.showNotification(error.message || 'API anahtarları silinirken hata oluştu', 'error');
        }
    }

    // Payment Methods
    async loadPaymentInfo() {
        try {
            const response = await this.apiCall('/api/payment/wallet', 'GET');
            document.getElementById('wallet-address').value = response.wallet_address;
        } catch (error) {
            console.error('Failed to load payment info:', error);
        }
    }

    copyWalletAddress() {
        const walletInput = document.getElementById('wallet-address');
        walletInput.select();
        document.execCommand('copy');
        this.showNotification('Cüzdan adresi kopyalandı!', 'success');
    }

    async requestPayment() {
        try {
            await this.apiCall('/api/payment/request', 'POST', {
                amount: 10,
                message: 'Aylık abonelik ödemesi'
            });
            
            this.showNotification('Ödeme bildirimi gönderildi. 24 saat içinde onaylanacaktır.', 'success');
        } catch (error) {
            this.showNotification(error.message || 'Ödeme bildirimi gönderilirken hata oluştu', 'error');
        }
    }

    // Settings Methods
    async updateProfile() {
        const fullName = document.getElementById('full-name').value.trim();
        const language = document.getElementById('language').value;

        try {
            await this.apiCall('/api/user/profile', 'PUT', {
                full_name: fullName,
                language: language
            });
            
            this.showNotification('Profil başarıyla güncellendi.', 'success');
            await this.loadUserProfile();
        } catch (error) {
            this.showNotification(error.message || 'Profil güncellenirken hata oluştu', 'error');
        }
    }

    async deleteAccount() {
        const confirmation = prompt('Hesabınızı silmek için "SİL" yazın:');
        
        if (confirmation !== 'SİL') {
            return;
        }

        try {
            await this.apiCall('/api/user/account', 'DELETE');
            this.showNotification('Hesabınız başarıyla silindi.', 'info');
            this.logout();
        } catch (error) {
            this.showNotification(error.message || 'Hesap silinirken hata oluştu', 'error');
        }
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
            overview: 'Genel Bakış',
            bot: 'Bot Kontrolü',
            'api-keys': 'API Anahtarları',
            subscription: 'Abonelik',
            settings: 'Ayarlar'
        };
        
        document.getElementById('page-title').textContent = titles[page] || 'Dashboard';
        this.currentPage = page;

        // Load page-specific data
        if (page === 'overview') {
            this.loadDashboardData();
        } else if (page === 'bot') {
            this.loadBotSettings();
        } else if (page === 'subscription') {
            this.loadPaymentInfo();
        } else if (page === 'settings') {
            this.loadSettingsData();
        } else if (page === 'api-keys') {
            this.loadIPWhitelist();
        }
    }

    async loadSettingsData() {
        if (!this.user) return;
        
        document.getElementById('full-name').value = this.user.full_name || '';
        document.getElementById('email').value = this.user.email || '';
        document.getElementById('language').value = this.user.language || 'tr';
    }

    // UI Methods
    showLandingPage() {
        document.getElementById('landing-page').style.display = 'block';
        document.getElementById('dashboard').style.display = 'none';
    }

    showDashboard() {
        document.getElementById('landing-page').style.display = 'none';
        document.getElementById('dashboard').style.display = 'flex';
        this.loadDashboardData();
        this.navigateToPage('overview');
    }

    showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
        }
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
        }
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
        console.log(`🔄 API Call: ${method} ${endpoint}`, data);
        
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
            console.log(`📡 Response status: ${response.status}`);
            
            let result;
            const contentType = response.headers.get('content-type');
            
            if (contentType && contentType.includes('application/json')) {
                result = await response.json();
                console.log('📦 JSON Response:', result);
            } else {
                const text = await response.text();
                console.log('📄 Text Response:', text);
                result = { message: text };
            }

            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}`;
                
                if (result) {
                    if (result.detail) {
                        errorMessage = result.detail;
                    } else if (result.message) {
                        errorMessage = result.message;
                    } else if (result.error) {
                        errorMessage = result.error;
                    } else if (typeof result === 'string') {
                        errorMessage = result;
                    }
                }
                
                console.error('❌ API Error:', errorMessage);
                throw new Error(errorMessage);
            }

            return result;
            
        } catch (fetchError) {
            console.error('🚨 Fetch Error:', fetchError);
            
            if (fetchError.name === 'TypeError' && fetchError.message.includes('fetch')) {
                throw new Error('Bağlantı hatası. İnternet bağlantınızı kontrol edin.');
            }
            
            throw fetchError;
        }
    }

    formatUptime(seconds) {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
        return `${Math.floor(seconds / 86400)}d`;
    }

    calculateRemainingTime(endDate) {
        const now = new Date();
        const end = new Date(endDate);
        const diff = end - now;

        if (diff <= 0) return 'Süresi doldu';

        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));

        if (days > 0) return `${days} gün`;
        if (hours > 0) return `${hours} saat`;
        return 'Bugün bitiyor';
    }

    scrollToFeatures() {
        document.getElementById('features').scrollIntoView({ behavior: 'smooth' });
    }

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.showNotification(`${text} kopyalandı!`, 'success');
        }).catch(() => {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            this.showNotification(`${text} kopyalandı!`, 'success');
        });
    }
}

// Global functions for HTML onclick handlers
function showLoginModal() {
    app.showModal('login-modal');
}

function showRegisterModal() {
    app.showModal('register-modal');
}

function showForgotPasswordModal() {
    app.closeModal('login-modal');
    app.showModal('forgot-password-modal');
}

function closeModal(modalId) {
    app.closeModal(modalId);
}

function logout() {
    app.logout();
}

function startBot() {
    app.startBot();
}

function stopBot() {
    app.stopBot();
}

function saveApiKeys() {
    app.saveApiKeys();
}

function deleteApiKeys() {
    app.deleteApiKeys();
}

function copyWalletAddress() {
    app.copyWalletAddress();
}

function requestPayment() {
    app.requestPayment();
}

function updateProfile() {
    app.updateProfile();
}

function deleteAccount() {
    app.deleteAccount();
}

function scrollToFeatures() {
    app.scrollToFeatures();
}

function saveBotSettings() {
    app.saveBotSettings();
}

function resetBotSettings() {
    app.resetBotSettings();
}

function copyToClipboard(text) {
    app.copyToClipboard(text);
}

// Initialize app when DOM is loaded
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new EzyagoApp();
    
    // Payment form handler
    document.getElementById('payment-notification-form')?.addEventListener('submit', (e) => {
        e.preventDefault();
        submitPaymentNotification();
    });
});
