class OutputPreview {
    constructor() {
        this.apiBase = 'http://localhost:5001/api';  // 改用5001端口
        this.currentDate = null;
        this.currentType = null;
        this.availableTypes = [];
        this.init();
    }

    async init() {
        this.setupEventListeners();
        await this.loadDates();
    }

    setupEventListeners() {
        // 日期选择事件
        document.getElementById('date-selector').addEventListener('change', (e) => {
            this.selectDate(e.target.value);
        });

        // Tab切换事件
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.type);
            });
        });
    }

    async loadDates() {
        try {
            const response = await fetch(`${this.apiBase}/dates`);
            const result = await response.json();

            if (!result.success || !result.dates || result.dates.length === 0) {
                throw new Error('未找到任何数据目录');
            }

            this.populateDateSelector(result.dates);
            this.currentDate = result.dates[0];
            
            // 加载第一个日期的可用文件类型
            await this.loadAvailableTypes(this.currentDate);
            
            this.showStatus('success', `找到 ${result.dates.length} 个日期目录`);

        } catch (error) {
            console.error('加载日期列表失败:', error);
            this.showStatus('error', `加载失败: ${error.message}`);
            this.showError('无法连接到服务器', '请确保已启动预览服务器：python src/msgskill/preview_server.py');
        }
    }

    populateDateSelector(dates) {
        const selector = document.getElementById('date-selector');
        selector.innerHTML = dates.map(date => 
            `<option value="${date}">${date}</option>`
        ).join('');
    }

    async loadAvailableTypes(date) {
        try {
            const response = await fetch(`${this.apiBase}/files/${date}`);
            const result = await response.json();

            if (result.success && result.types) {
                this.availableTypes = result.types;
                this.updateTabStates();
                
                // 自动选择第一个可用的数据类型
                if (this.availableTypes.length > 0) {
                    const firstType = this.availableTypes[0];
                    this.currentType = firstType;
                    this.updateTabState(firstType);
                    await this.loadData(date, firstType);
                }
            }
        } catch (error) {
            console.error('加载文件类型失败:', error);
            this.showStatus('warning', '无法获取可用的数据类型');
        }
    }

    updateTabStates() {
        // 更新所有tab的可用状态
        document.querySelectorAll('.tab-btn').forEach(btn => {
            const type = btn.dataset.type;
            const isAvailable = this.availableTypes.includes(type);
            
            if (isAvailable) {
                btn.classList.remove('opacity-50', 'cursor-not-allowed');
                btn.disabled = false;
            } else {
                btn.classList.add('opacity-50', 'cursor-not-allowed');
                btn.disabled = true;
            }
        });
    }

    async selectDate(date) {
        if (!date) return;

        this.currentDate = date;
        this.showStatus('info', `切换到 ${date}`);
        
        // 重新加载可用类型
        await this.loadAvailableTypes(date);
    }

    updateTabState(type) {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            const isActive = btn.dataset.type === type;
            btn.classList.toggle('tab-active', isActive);
            btn.classList.toggle('bg-blue-100', isActive);
            btn.classList.toggle('text-blue-700', isActive);
        });
    }

    async switchTab(type) {
        if (!this.currentDate) {
            this.showStatus('warning', '请先选择日期');
            return;
        }

        if (!this.availableTypes.includes(type)) {
            this.showStatus('warning', `该日期没有${this.getTypeName(type)}数据`);
            return;
        }

        this.currentType = type;
        this.updateTabState(type);
        await this.loadData(this.currentDate, type);
    }

    async loadData(date, dataType) {
        const contentEl = document.getElementById('content');
        contentEl.classList.add('loading');
        contentEl.innerHTML = `
            <div class="flex items-center justify-center h-64">
                <div class="text-center">
                    <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
                    <p class="text-gray-600">正在加载${this.getTypeName(dataType)}数据...</p>
                </div>
            </div>
        `;

        try {
            const response = await fetch(`${this.apiBase}/data/${date}/${dataType}`);
            const result = await response.json();

            if (!result.success) {
                throw new Error(result.error || '加载失败');
            }

            this.renderData(result.data, dataType, result);
            
            const fileInfo = result.total_files > 1 
                ? `(合并了${result.total_files}个文件，共${result.merged_count}条数据)`
                : ``;
            this.showStatus('success', `${this.getTypeName(dataType)}数据加载成功 ${fileInfo}`);

        } catch (error) {
            console.error('加载数据失败:', error);
            this.showError('数据加载失败', error.message);
            this.showStatus('error', `加载失败: ${error.message}`);
        } finally {
            contentEl.classList.remove('loading');
        }
    }

    showError(title, message) {
        const contentEl = document.getElementById('content');
        contentEl.innerHTML = `
            <div class="flex items-center justify-center h-64">
                <div class="text-center text-red-600">
                    <svg class="w-12 h-12 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
                    </svg>
                    <p class="font-medium text-lg">${title}</p>
                    <p class="text-sm mt-1">${message}</p>
                </div>
            </div>
        `;
    }

    getTypeName(type) {
        const names = {
            'arxiv': 'arXiv论文',
            'hackernews': 'HackerNews',
            'rss': 'RSS源',
            'github': 'GitHub'
        };
        return names[type] || type;
    }

    renderData(data, dataType, metadata = {}) {
        const contentEl = document.getElementById('content');
        
        // 添加文件信息提示
        let fileInfoHtml = '';
        if (metadata.total_files > 1) {
            fileInfoHtml = `
                <div class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <p class="text-sm text-blue-700">
                        📁 已合并<strong>${metadata.total_files}</strong>个${this.getTypeName(dataType)}文件，
                        共<strong>${metadata.merged_count}</strong>条数据 (已去重)
                    </p>
                </div>
            `;
        }
        
        switch(dataType) {
            case 'arxiv':
                this.renderArxivData(data, contentEl, fileInfoHtml);
                break;
            case 'hackernews':
                this.renderHackerNewsData(data, contentEl, fileInfoHtml);
                break;
            case 'rss':
                this.renderRssData(data, contentEl, fileInfoHtml);
                break;
            case 'github':
                this.renderGithubData(data, contentEl, fileInfoHtml);
                break;
            default:
                contentEl.innerHTML = `<div class="text-center text-gray-500">未知数据类型: ${dataType}</div>`;
        }

        contentEl.classList.add('fade-in');
        setTimeout(() => contentEl.classList.remove('fade-in'), 300);
    }

    renderArxivData(data, container, fileInfoHtml = '') {
        const papers = data.papers || [];
        container.innerHTML = `
            ${fileInfoHtml}
            <div class="mb-4">
                <h2 class="text-xl font-semibold text-gray-800">arXiv论文 (${data.count || papers.length}篇)</h2>
                <p class="text-sm text-gray-600">分类: ${data.category_name || 'N/A'} | 抓取时间: ${new Date(data.fetched_at).toLocaleString()}</p>
            </div>
            ${papers.length > 0 ? `
                <div class="space-y-4">
                    ${papers.map(paper => `
                        <div class="border rounded-lg p-4 hover:shadow-md transition-shadow">
                            <h3 class="text-lg font-medium text-blue-600 mb-2">
                                <a href="${paper.pdf_url}" target="_blank" class="hover:underline">${paper.title}</a>
                            </h3>
                            <p class="text-sm text-gray-600 mb-2">
                                作者: ${paper.authors.join(', ')} | 发布时间: ${new Date(paper.published).toLocaleDateString()}
                            </p>
                            <p class="text-gray-700 text-sm leading-relaxed">${paper.summary}</p>
                            <div class="mt-3 flex gap-2">
                                <a href="${paper.pdf_url}" target="_blank" class="text-sm text-blue-600 hover:underline">PDF</a>
                                ${paper.arxiv_url ? `<a href="${paper.arxiv_url}" target="_blank" class="text-sm text-blue-600 hover:underline">arXiv</a>` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : '<div class="text-center text-gray-500 py-8">没有论文数据</div>'}
        `;
    }

    renderHackerNewsData(data, container, fileInfoHtml = '') {
        const items = data.items || [];
        container.innerHTML = `
            ${fileInfoHtml}
            <div class="mb-4">
                <h2 class="text-xl font-semibold text-gray-800">HackerNews (${data.total_count || items.length}条)</h2>
                <p class="text-sm text-gray-600">抓取时间: ${new Date(data.fetched_at).toLocaleString()}</p>
            </div>
            ${items.length > 0 ? `
                <div class="space-y-3">
                    ${items.map(item => `
                        <div class="border rounded-lg p-4 hover:shadow-md transition-shadow">
                            <h3 class="text-lg font-medium mb-2">
                                <a href="${item.source_url}" target="_blank" class="text-blue-600 hover:underline">${item.title}</a>
                            </h3>
                            <p class="text-gray-700 text-sm mb-3">${item.summary || '暂无摘要'}</p>
                            <div class="flex flex-wrap gap-4 text-xs text-gray-500">
                                <span>👍 ${item.score || 0}</span>
                                <span>💬 ${item.comments_count || 0}</span>
                                <span>📅 ${item.published_date}</span>
                                ${item.article_tag ? `<span>🏷️ ${item.article_tag}</span>` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : '<div class="text-center text-gray-500 py-8">没有HackerNews数据</div>'}
        `;
    }

    renderRssData(data, container, fileInfoHtml = '') {
        const feeds = data.feeds || {};
        const feedEntries = Object.entries(feeds).filter(([url, feed]) => !feed.error);
        
        container.innerHTML = `
            ${fileInfoHtml}
            <div class="mb-4">
                <h2 class="text-xl font-semibold text-gray-800">RSS源 (${data.total_items || 0}条)</h2>
                <p class="text-sm text-gray-600">${data.feeds_count || 0}个源 | 抓取时间: ${new Date(data.fetched_at).toLocaleString()}</p>
            </div>
            ${feedEntries.length > 0 ? `
                <div class="space-y-6">
                    ${feedEntries.map(([url, feed]) => `
                        <div>
                            <h3 class="text-lg font-medium text-gray-800 mb-3">
                                <a href="${feed.link}" target="_blank" class="hover:underline">${feed.title}</a>
                            </h3>
                            ${feed.items && feed.items.length > 0 ? `
                                <div class="space-y-3 ml-4">
                                    ${feed.items.map(item => `
                                        <div class="border-l-4 border-blue-200 pl-4 py-2">
                                            <h4 class="font-medium mb-1">
                                                <a href="${item.link}" target="_blank" class="text-blue-600 hover:underline">${item.title}</a>
                                            </h4>
                                            <p class="text-gray-600 text-sm mb-1">${item.published}</p>
                                            <p class="text-gray-700 text-sm">${item.summary}</p>
                                        </div>
                                    `).join('')}
                                </div>
                            ` : '<p class="text-gray-500 text-sm ml-4">该源没有内容</p>'}
                        </div>
                    `).join('')}
                </div>
            ` : '<div class="text-center text-gray-500 py-8">没有RSS数据</div>'}
        `;
    }

    renderGithubData(data, container, fileInfoHtml = '') {
        const items = data.items || [];
        container.innerHTML = `
            ${fileInfoHtml}
            <div class="mb-4">
                <h2 class="text-xl font-semibold text-gray-800">GitHub趋势项目 (${data.total_count || items.length}个)</h2>
                <p class="text-sm text-gray-600">抓取时间: ${new Date(data.fetched_at).toLocaleString()}</p>
            </div>
            ${items.length > 0 ? `
                <div class="space-y-4">
                    ${items.map(item => `
                        <div class="border rounded-lg p-4 hover:shadow-md transition-shadow">
                            <h3 class="text-lg font-medium mb-2">
                                <a href="${item.source_url}" target="_blank" class="text-blue-600 hover:underline">${item.title}</a>
                            </h3>
                            <p class="text-gray-700 text-sm mb-3">${item.summary || '暂无描述'}</p>
                            <div class="flex flex-wrap gap-4 text-xs text-gray-500">
                                ${item.tags && item.tags.length > 0 ? `<span>🏷️ ${item.tags.slice(0, 3).join(', ')}${item.tags.length > 3 ? '...' : ''}</span>` : ''}
                                <span>⭐ ${item.score || 0}</span>
                                <span>🕒 ${new Date(item.published_date).toLocaleDateString()}</span>
                                ${item.author ? `<span>👤 ${item.author}</span>` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : '<div class="text-center text-gray-500 py-8">没有GitHub数据</div>'}
        `;
    }

    showStatus(type, message) {
        const statusEl = document.getElementById('status');
        statusEl.classList.remove('hidden');
        
        const styles = {
            success: 'text-green-600',
            error: 'text-red-600',
            warning: 'text-yellow-600',
            info: 'text-blue-600'
        };
        
        statusEl.className = `mt-4 text-center text-sm ${styles[type]}`;
        statusEl.textContent = message;
        
        // 自动隐藏成功提示
        if (type === 'success') {
            setTimeout(() => {
                statusEl.classList.add('hidden');
            }, 3000);
        }
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    new OutputPreview();
});