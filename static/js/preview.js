class OutputPreview {
    constructor() {
        this.apiBase = 'http://localhost:5001/api';  // 改用5001端口
        this.currentDate = null;
        this.currentType = null;
        this.availableTypes = [];
        this.init();
    }

    // 时间字符串格式化为东八区时间
    formatToBeijingTime(timeStr) {
        if (!timeStr) return '未知时间';
        
        try {
            let date = new Date(timeStr);
            
            if (isNaN(date.getTime())) return timeStr;
            
            // 后端已经处理了时区转换，直接格式化为本地时间
            return date.toLocaleString('zh-CN', {
                timeZone: 'Asia/Shanghai',
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        } catch (error) {
            console.warn('时间格式化错误:', error);
            return timeStr;
        }
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

        // 同步到 Notion 按钮
        const syncBtn = document.getElementById('sync-notion-btn');
        if (syncBtn) {
            syncBtn.addEventListener('click', () => {
                this.syncToNotion();
            });
        }
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
                // GitHub数据库始终可用，不依赖日期
                this.availableTypes = [...result.types, 'github-db'];
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
        // GitHub数据库不依赖于日期选择
        if (type !== 'github-db' && !this.currentDate) {
            this.showStatus('warning', '请先选择日期');
            return;
        }

        if (!this.availableTypes.includes(type)) {
            this.showStatus('warning', `该日期没有${this.getTypeName(type)}数据`);
            return;
        }

        this.currentType = type;
        this.updateTabState(type);
        
        // GitHub数据库使用时不需要日期参数
        const dateForLoad = type === 'github-db' ? this.currentDate || 'current' : this.currentDate;
        await this.loadData(dateForLoad, type);
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
            // 特殊处理GitHub数据库类型
            let apiUrl;
            if (dataType === 'github-db') {
                apiUrl = `${this.apiBase}/github/database`;
            } else {
                apiUrl = `${this.apiBase}/data/${date}/${dataType}`;
            }

            const response = await fetch(apiUrl);
            const result = await response.json();

            if (!result.success) {
                throw new Error(result.error || '加载失败');
            }

            this.renderData(result.data, dataType, result);
            
            // GitHub数据库显示特殊信息
            let fileInfo = '';
            if (dataType === 'github-db' && result.from_database) {
                const dbInfo = result.data.database_info || {};
                fileInfo = `(数据库: ${dbInfo.total_projects || 0}项目, AI: ${dbInfo.ai_projects || 0}条)`;
            } else if (result.total_files > 1) {
                fileInfo = `(合并了${result.total_files}个文件，共${result.merged_count}条数据)`;
            }
            
            this.showStatus('success', `${this.getTypeName(dataType)}数据加载成功 ${fileInfo}`);

        } catch (error) {
            console.error('加载数据失败:', error);
            this.showError('数据加载失败', error.message);
            this.showStatus('error', `加载失败: ${error.message}`);
        } finally {
            contentEl.classList.remove('loading');
        }
    }

    async syncItemToNotion(type, item) {
        try {
            const payload = { type, item };
            const res = await fetch(`${this.apiBase}/notion/sync`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            const data = await res.json();

            if (!data.success) {
                throw new Error(data.error || '同步失败');
            }

            const typeName = this.getTypeName(type);
            const title = (item && (item.title || item.name || item.source_url)) || '';
            const shortTitle = title ? `「${title.slice(0, 40)}${title.length > 40 ? '...' : ''}」` : '1 条记录';
            this.showStatus('success', data.message || `${typeName} ${shortTitle} 已同步到 Notion`);
        } catch (error) {
            console.error('同步到 Notion 失败:', error);
            const typeName = this.getTypeName(type);
            this.showStatus('error', `${typeName} 同步失败: ${error.message || '未知错误'}`);
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
            'github': 'GitHub(每日)',
            'github-db': 'GitHub数据库'
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
            case 'github-db':
                this.renderGithubDbData(data, contentEl, fileInfoHtml);
                break;
            default:
                contentEl.innerHTML = `<div class="text-center text-gray-500">未知数据类型: ${dataType}</div>`;
        }

        contentEl.classList.add('fade-in');
        setTimeout(() => contentEl.classList.remove('fade-in'), 300);

        // 绑定单条同步按钮
        this.bindItemSyncHandlers(contentEl, dataType, data);
    }

    bindItemSyncHandlers(container, dataType, data) {
        const buttons = container.querySelectorAll('.sync-notion-item');
        if (!buttons.length) return;

        buttons.forEach(btn => {
            btn.addEventListener('click', () => {
                const type = btn.dataset.type;
                let itemData = null;

                if (type === 'arxiv') {
                    const idx = parseInt(btn.dataset.index, 10);
                    itemData = (data.papers || [])[idx];
                } else if (type === 'hackernews' || type === 'github' || type === 'github-db') {
                    const idx = parseInt(btn.dataset.index, 10);
                    itemData = (data.items || [])[idx];
                } else if (type === 'rss') {
                    const feedIndex = parseInt(btn.dataset.feedIndex, 10);
                    const itemIndex = parseInt(btn.dataset.itemIndex, 10);
                    const entries = Object.entries(data.feeds || {});
                    const entry = entries[feedIndex];
                    if (entry && entry[1] && Array.isArray(entry[1].items)) {
                        itemData = entry[1].items[itemIndex];
                    }
                }

                if (!itemData) {
                    this.showStatus('error', '未找到要同步的数据');
                    return;
                }

                this.syncItemToNotion(type, itemData);
            });
        });
    }

    renderArxivData(data, container, fileInfoHtml = '') {
        const papers = data.papers || [];
        container.innerHTML = `
            ${fileInfoHtml}
            <div class="mb-4">
                <h2 class="text-xl font-semibold text-gray-800">arXiv论文 (${data.count || papers.length}篇)</h2>
                <p class="text-sm text-gray-600">分类: ${data.category_name || 'N/A'} | 抓取时间: ${this.formatToBeijingTime(data.fetched_at)}</p>
            </div>
            ${papers.length > 0 ? `
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    ${papers.map((paper, index) => `
                        <div class="border rounded-lg p-4 hover:shadow-md transition-shadow">
                            <h3 class="text-lg font-medium text-blue-600 mb-2">
                                <a href="${paper.pdf_url}" target="_blank" class="hover:underline">${paper.title}</a>
                            </h3>
                            <p class="text-sm text-gray-600 mb-2">
                                作者: ${paper.authors.join(', ')} | 发布时间: ${this.formatToBeijingTime(paper.published)}
                            </p>
                            <p class="text-gray-700 text-sm leading-relaxed">${paper.summary}</p>
                            <div class="mt-3 flex gap-2 items-center">
                                <a href="${paper.pdf_url}" target="_blank" class="text-sm text-blue-600 hover:underline">PDF</a>
                                ${paper.arxiv_url ? `<a href="${paper.arxiv_url}" target="_blank" class="text-sm text-blue-600 hover:underline">arXiv</a>` : ''}
                                <button class="ml-auto text-sm text-emerald-600 hover:underline sync-notion-item"
                                        data-type="arxiv"
                                        data-index="${index}">
                                    同步到 Notion
                                </button>
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
                <p class="text-sm text-gray-600">抓取时间: ${this.formatToBeijingTime(data.fetched_at)}</p>
            </div>
            ${items.length > 0 ? `
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                    ${items.map((item, index) => `
                        <div class="border rounded-lg p-4 hover:shadow-md transition-shadow">
                            <h3 class="text-lg font-medium mb-2">
                                <a href="${item.source_url}" target="_blank" class="text-blue-600 hover:underline">${item.title}</a>
                            </h3>
                            <p class="text-gray-700 text-sm mb-3">${item.summary || '暂无摘要'}</p>
                            <div class="flex flex-wrap gap-4 text-xs text-gray-500">
                                <span>👍 ${item.score || 0}</span>
                                <span>💬 ${item.comments_count || 0}</span>
                                <span>📅 ${this.formatToBeijingTime(item.published_date)}</span>
                                ${item.article_tag ? `<span>🏷️ ${item.article_tag}</span>` : ''}
                            </div>
                            <div class="mt-2 text-right">
                                <button class="text-xs text-emerald-600 hover:underline sync-notion-item"
                                        data-type="hackernews"
                                        data-index="${index}">
                                    同步到 Notion
                                </button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : '<div class="text-center text-gray-500 py-8">没有HackerNews数据</div>'}
        `;
    }

    renderRssData(data, container, fileInfoHtml = '') {
        const feeds = data.feeds || {};
        // 之前简单用 !feed.error 过滤，导致「有 error 但也有 items 的源」被整体隐藏
        // 现在按是否有可展示条目来决定是否展示该源；如果有 error 再在 UI 上标个提示
        const feedEntries = Object.entries(feeds).filter(([url, feed]) => {
            const items = feed && Array.isArray(feed.items) ? feed.items : [];
            return items.length > 0;
        });
        
        container.innerHTML = `
            ${fileInfoHtml}
            <div class="mb-4">
                <h2 class="text-xl font-semibold text-gray-800">RSS源 (${data.total_items || 0}条)</h2>
                <p class="text-sm text-gray-600">${data.feeds_count || 0}个源 | 抓取时间: ${this.formatToBeijingTime(data.fetched_at)}</p>
            </div>
            ${feedEntries.length > 0 ? `
                <div class="space-y-6">
                    ${feedEntries.map(([url, feed]) => `
                        <div>
                            <h3 class="text-lg font-medium text-gray-800 mb-3">
                                <a href="${feed.link}" target="_blank" class="hover:underline">${feed.title}</a>
                                ${feed.error ? `<span class="ml-2 text-xs text-amber-600">(源有部分错误: ${feed.error.slice(0, 40)}...)</span>` : ''}
                            </h3>
                            ${feed.items && feed.items.length > 0 ? `
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-3 ml-4">
                                    ${feed.items.map((item, itemIndex) => `
                                        <div class="border-l-4 border-blue-200 pl-4 py-2">
                                            <h4 class="font-medium mb-1">
                                                <a href="${item.link}" target="_blank" class="text-blue-600 hover:underline">${item.title}</a>
                                            </h4>
                                            <p class="text-gray-600 text-sm mb-1">${this.formatToBeijingTime(item.published)}</p>
                                            <p class="text-gray-700 text-sm">${item.summary}</p>
                                            <div class="mt-1 text-right">
                                                <button class="text-xs text-emerald-600 hover:underline sync-notion-item"
                                                        data-type="rss"
                                                        data-feed-index="${feedEntries.findIndex(([u]) => u === url)}"
                                                        data-item-index="${itemIndex}">
                                                    同步到 Notion
                                                </button>
                                            </div>
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
                <p class="text-sm text-gray-600">抓取时间: ${this.formatToBeijingTime(data.fetched_at)}</p>
            </div>
            ${items.length > 0 ? `
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    ${items.map((item, index) => `
                        <div class="border rounded-lg p-4 hover:shadow-md transition-shadow">
                            <h3 class="text-lg font-medium mb-2">
                                <a href="${item.source_url}" target="_blank" class="text-blue-600 hover:underline">${item.title}</a>
                            </h3>
                            <p class="text-gray-700 text-sm mb-3">${item.summary || '暂无描述'}</p>
                            <div class="flex flex-wrap gap-4 text-xs text-gray-500">
                                ${item.tags && item.tags.length > 0 ? `<span>🏷️ ${item.tags.slice(0, 3).join(', ')}${item.tags.length > 3 ? '...' : ''}</span>` : ''}
                                <span>⭐ ${item.score || 0}</span>
                                <span>🕒 ${this.formatToBeijingTime(item.published_date)}</span>
                                ${item.author ? `<span>👤 ${item.author}</span>` : ''}
                            </div>
                            <div class="mt-2 text-right">
                                <button class="text-xs text-emerald-600 hover:underline sync-notion-item"
                                        data-type="github"
                                        data-index="${index}">
                                    同步到 Notion
                                </button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : '<div class="text-center text-gray-500 py-8">没有GitHub数据</div>'}
        `;
    }

    // GitHub数据库特殊渲染函数
    renderGithubDbData(data, container, fileInfoHtml = '') {
        const items = data.items || [];
        const dbInfo = data.database_info || {};

        // 带上原始索引，方便后续单条同步
        const itemsWithIndex = items.map((item, index) => ({ item, index }));
        const aiItems = itemsWithIndex.filter(entry => entry.item.is_ai_project);
        const nonAiItems = itemsWithIndex.filter(entry => !entry.item.is_ai_project);
        
        container.innerHTML = `
            ${fileInfoHtml}
            <div class="mb-4">
                <h2 class="text-xl font-semibold text-gray-800">GitHub数据库 (${items.length}个项目)</h2>
                <p class="text-sm text-gray-600">
                    总项目数: ${dbInfo.total_projects || 0} | 
                    AI项目: ${dbInfo.ai_projects || 0} | 
                    白名单: ${dbInfo.whitelist_projects || 0} |
                    显示: ${items.length} (含非AI项目，灰底显示) |
                    数据库更新时间: ${this.formatToBeijingTime(data.fetched_at)}
                </p>
            </div>
            ${items.length > 0 ? `
                <div class="space-y-6">
                    ${aiItems.length > 0 ? `
                        <div>
                            <h3 class="text-lg font-semibold text-gray-800 mb-3">AI项目 (${aiItems.length})</h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                ${aiItems.map(({ item, index }) => `
                                    <div class="border rounded-lg p-4 hover:shadow-md transition-shadow bg-white">
                                        <div class="flex justify-between items-start mb-2">
                                            <h4 class="text-lg font-medium flex-1">
                                                <a href="${item.source_url}" target="_blank" class="text-blue-600 hover:underline">${item.title}</a>
                                            </h4>
                                            <div class="text-right text-sm text-gray-500">
                                                <span class="bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-xs">
                                                    AI评分: ${Math.round((item.ai_score || 0) * 100) / 100}
                                                </span>
                                                ${item._from_database ? `<span class="bg-green-100 text-green-800 px-2 py-1 rounded-full text-xs ml-1">数据库</span>` : ''}
                                            </div>
                                        </div>
                                        <p class="text-gray-700 text-sm mb-3">${item.summary || '暂无描述'}</p>
                                        ${item.ai_reason ? `<div class="mb-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-sm text-gray-700"><strong>AI推荐理由:</strong> ${item.ai_reason}</div>` : ''}
                                        <div class="flex flex-wrap gap-4 text-xs text-gray-500">
                                            ${item.language ? `<span>💻 ${item.language}</span>` : ''}
                                            <span>⭐ ${item.score || 0}</span>
                                            ${item.tags && item.tags.length > 0 ? `<span>🏷️ ${item.tags.join(', ')}</span>` : ''}
                                            <span>👤 ${item.author || 'Unknown'}</span>
                                            <span>🕒 ${this.formatToBeijingTime(item.published_date)}</span>
                                        </div>
                                        <div class="mt-2 text-right">
                                            <button class="text-xs text-emerald-600 hover:underline sync-notion-item"
                                                    data-type="github-db"
                                                    data-index="${index}">
                                                同步到 Notion
                                            </button>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${nonAiItems.length > 0 ? `
                        <div class="border-t border-gray-200 pt-4">
                            <h3 class="text-lg font-semibold text-gray-700 mb-1">非AI项目 (${nonAiItems.length})</h3>
                            <p class="text-xs text-gray-500 mb-3">以下为未被AI识别为AI相关的项目，使用灰色背景展示。</p>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                ${nonAiItems.map(({ item, index }) => `
                                    <div class="border rounded-lg p-4 hover:shadow-md transition-shadow bg-gray-50">
                                        <div class="flex justify-between items-start mb-2">
                                            <h4 class="text-lg font-medium flex-1">
                                                <a href="${item.source_url}" target="_blank" class="text-gray-800 hover:underline">${item.title}</a>
                                            </h4>
                                            <div class="text-right text-sm text-gray-500">
                                                <span class="bg-gray-200 text-gray-700 px-2 py-1 rounded-full text-xs">非AI项目</span>
                                                ${item._from_database ? `<span class="bg-green-100 text-green-800 px-2 py-1 rounded-full text-xs ml-1">数据库</span>` : ''}
                                            </div>
                                        </div>
                                        <p class="text-gray-700 text-sm mb-3">${item.summary || '暂无描述'}</p>
                                        <div class="flex flex-wrap gap-4 text-xs text-gray-500">
                                            ${item.language ? `<span>💻 ${item.language}</span>` : ''}
                                            <span>⭐ ${item.score || 0}</span>
                                            ${item.tags && item.tags.length > 0 ? `<span>🏷️ ${item.tags.join(', ')}</span>` : ''}
                                            <span>👤 ${item.author || 'Unknown'}</span>
                                            <span>🕒 ${this.formatToBeijingTime(item.published_date)}</span>
                                        </div>
                                        <div class="mt-2 text-right">
                                            <button class="text-xs text-emerald-600 hover:underline sync-notion-item"
                                                    data-type="github-db"
                                                    data-index="${index}">
                                                同步到 Notion
                                            </button>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            ` : '<div class="text-center text-gray-500 py-8">GitHub数据库中没有项目数据</div>'}
        `;
    }

    showStatus(type, message) {
        // 使用居中的 Toast 提示，而不是底部状态栏
        const existing = document.getElementById('toast-notification');
        if (existing) {
            existing.remove();
        }

        const wrapper = document.createElement('div');
        wrapper.id = 'toast-notification';
        wrapper.className = 'fixed inset-0 flex items-center justify-center z-50 pointer-events-none';

        const colorMap = {
            success: 'border-emerald-500 text-emerald-700',
            error: 'border-red-500 text-red-700',
            warning: 'border-yellow-500 text-yellow-700',
            info: 'border-blue-500 text-blue-700'
        };
        const bgMap = {
            success: 'bg-emerald-50',
            error: 'bg-red-50',
            warning: 'bg-yellow-50',
            info: 'bg-blue-50'
        };

        const colorClass = colorMap[type] || colorMap.info;
        const bgClass = bgMap[type] || bgMap.info;

        wrapper.innerHTML = `
            <div class="pointer-events-auto max-w-md px-4 py-3 rounded-lg shadow-lg border ${bgClass} ${colorClass}">
                <div class="text-sm font-medium mb-1">
                    ${type === 'success' ? '操作成功' : type === 'error' ? '操作失败' : type === 'warning' ? '提示' : '状态'}
                </div>
                <div class="text-xs sm:text-sm leading-snug">${message}</div>
            </div>
        `;

        document.body.appendChild(wrapper);

        const timeout = type === 'error' ? 4000 : 2500;
        setTimeout(() => {
            wrapper.classList.add('opacity-0', 'transition-opacity', 'duration-300');
            setTimeout(() => {
                wrapper.remove();
            }, 300);
        }, timeout);
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    new OutputPreview();
});