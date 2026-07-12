<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>스마트폰 신제품 인사이트 대시보드</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --primary: #0f172a;
            --accent: #0284c7;
            --insight-bg: #f0f9ff;
            --insight-border: #bae6fd;
            --text-main: #334155;
            --text-muted: #64748b;
            --border-color: #e2e8f0;
            --tab-bg: #e2e8f0;
        }

        body {
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 30px 20px;
            line-height: 1.7;
        }

        .header {
            text-align: center;
            margin-bottom: 35px;
        }

        .header h1 {
            font-size: 2.4rem;
            color: var(--primary);
            margin: 0 0 10px 0;
            letter-spacing: -1px;
            font-weight: 800;
        }

        .header p {
            color: var(--text-muted);
            font-size: 1.1rem;
            margin: 0;
        }

        .tab-container {
            display: flex;
            justify-content: center;
            margin-bottom: 30px;
            gap: 12px;
        }

        .tab-btn {
            background-color: var(--tab-bg);
            color: var(--text-muted);
            border: none;
            padding: 12px 28px;
            font-size: 1.05rem;
            font-weight: 700;
            border-radius: 30px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .tab-btn:hover { background-color: #cbd5e1; }
        .tab-btn.active {
            background-color: var(--accent);
            color: white;
            box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3);
        }

        .filter-container {
            display: none; 
            justify-content: center;
            flex-wrap: wrap;
            margin-bottom: 35px;
            gap: 10px;
        }

        .filter-btn {
            background-color: white;
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            padding: 8px 18px;
            border-radius: 20px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .filter-btn.active {
            background-color: var(--primary);
            color: white;
            border-color: var(--primary);
        }

        .dashboard-container {
            max-width: 1350px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 28px;
        }

        /* 가로형 와이드 카드 */
        .device-card {
            background: var(--card-bg);
            border-radius: 16px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03);
            border: 1px solid var(--border-color);
            display: flex;
            overflow: hidden;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .device-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 20px -3px rgba(0,0,0,0.08);
        }

        /* 🚀 카드 왼쪽: 레이아웃 전면 수정 (시사점 박스를 타이틀 바로 아래로) */
        .card-left {
            width: 38%;
            padding: 30px;
            background-color: #fafafa;
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            gap: 16px; /* 고정 간격으로 상단에 밀착 배치 */
        }

        .card-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .tier-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 700;
            color: white;
        }
        .tier-flagship { background-color: #ef4444; }
        .tier-midrange { background-color: #10b981; }
        .tier-budget { background-color: #3b82f6; }

        .maker-badge {
            font-size: 0.8rem;
            color: #475569;
            background: #e2e8f0;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 700;
        }

        .date-badge {
            font-size: 0.8rem;
            color: var(--text-muted);
            background: #f1f5f9;
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 600;
        }

        .device-title {
            font-size: 1.6rem;
            font-weight: 800;
            margin: 0;
            color: var(--primary);
            line-height: 1.3;
        }

        .device-title a {
            color: var(--accent);
            font-size: 1.1rem;
            text-decoration: none;
            margin-left: 8px;
        }

        /* 제품명 바로 아래로 수직 상승 배치된 시사점 박스 */
        .insight-box {
            background-color: var(--insight-bg);
            border: 1px solid var(--insight-border);
            padding: 20px;
            border-radius: 12px;
            margin-top: 5px;
        }

        .insight-box strong {
            display: block;
            color: var(--accent);
            font-size: 0.95rem;
            font-weight: 800;
            margin-bottom: 8px;
        }

        .insight-box p {
            margin: 0;
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--primary);
            line-height: 1.6;
        }

        /* 카드 오른쪽: 인포그래픽 리스트 스타일 개편 */
        .card-right {
            width: 62%;
            padding: 30px;
            display: flex;
            flex-direction: column;
            gap: 24px;
            justify-content: center;
        }

        .detail-section {
            background-color: #f8fafc;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #f1f5f9;
        }

        .detail-section strong {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 1.05rem;
            color: var(--primary);
            margin-bottom: 12px;
            font-weight: 800;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 6px;
        }

        .detail-section strong i {
            color: var(--accent);
        }

        /* 🧹 리스트 가독성 최적화 스타일 */
        .detail-content {
            font-size: 0.98rem;
            color: var(--text-main);
            line-height: 1.7;
        }

        /* 소항목(불릿) 디자인 고도화 */
        .detail-item {
            margin-bottom: 10px;
            padding-left: 12px;
            text-indent: -12px;
        }
        
        .detail-item:last-child {
            margin-bottom: 0;
        }

        .loading { text-align: center; font-size: 1.2rem; color: var(--text-muted); padding: 50px; }

        @media (max-width: 950px) {
            .device-card { flex-direction: column; }
            .card-left, .card-right { width: 100%; box-sizing: border-box; }
            .card-left { border-right: none; border-bottom: 1px solid var(--border-color); }
        }
    </style>
</head>
<body>

    <div class="header">
        <h1>📊 스마트폰 전략 상품기획 대시보드</h1>
        <p>최신 동향 동기화 시점: <span id="update-date" style="font-weight: 800; color: var(--accent);">불러오는 중...</span></p>
    </div>

    <div class="tab-container">
        <button class="tab-btn active" id="tab-latest" onclick="switchTab('latest')">🔥 최신 보고서 (당일)</button>
        <button class="tab-btn" id="tab-history" onclick="switchTab('history')">📚 아카이브 (누적 이력)</button>
    </div>

    <div class="filter-container" id="filter-menu">
        <button class="filter-btn active" onclick="applyFilter('all')">전체 등급</button>
        <button class="filter-btn" onclick="applyFilter('flagship')">🌟 플래그십</button>
        <button class="filter-btn" onclick="applyFilter('midrange')">⚖️ 중급형</button>
        <button class="filter-btn" onclick="applyFilter('budget')">📱 보급형</button>
    </div>

    <div class="dashboard-container" id="dashboard">
        <div class="loading"><i class="fas fa-spinner fa-spin"></i> 구글 데이터베이스를 연동하고 있습니다...</div>
    </div>

    <script>
        const SHEET_ID = '1fKrSktMeXJmnqwUGOgk4QLtwfpAlkkFi5SvYJSrbT5o';
        const SHEET_NAME = '스펙_누적_데이터';
        const URL = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:json&sheet=${encodeURIComponent(SHEET_NAME)}`;

        let allProducts = [];
        let latestDate = "";
        let currentTab = 'latest'; 
        let currentFilter = 'all';

        // 🧹 줄글 텍스트를 구조화된 HTML 인포그래픽 리스트로 자동 가공하는 고도화 함수
        function formatDetailContent(rawText) {
            if (!rawText) return "정보 없음";
            
            // 마크다운 기호 제거 및 기본 정제
            let clean = rawText.replace(/\*\*/g, '').replace(/\*/g, '•').trim();
            
            // '• ' 기호를 기준으로 문장들을 쪼개기
            let lines = clean.split('•');
            let htmlResult = "";
            
            lines.forEach(line => {
                let trimmed = line.trim();
                if (!trimmed) return;
                
                // 항목명에 볼드 처리를 하고 다음 내용을 줄바꿈 처리하기 위한 다이나믹 변환
                // 예: "가격대: 150달러" -> "<strong>• 가격대:</strong> <br>150달러"
                if (trimmed.includes(':')) {
                    let parts = trimmed.split(':');
                    let title = parts[0].trim();
                    let content = parts.slice(1).join(':').trim();
                    htmlResult += `<div class="detail-item"><span style="font-weight:800; color:#0f172a;">• ${title}:</span> <span style="display:block; margin-top:3px; padding-left:14px; color:#475569;">${content}</span></div>`;
                } else {
                    htmlResult += `<div class="detail-item" style="color:#475569;">• ${trimmed}</div>`;
                }
            });
            
            return htmlResult;
        }

        function parseStrategy(text) {
            const extract = (startWord, endWord) => {
                let regex = endWord 
                    ? new RegExp(startWord + "\\s*:\\s*([\\s\\S]*?)(?=" + endWord + ":|$)")
                    : new RegExp(startWord + "\\s*:\\s*([\\s\\S]*)");
                const match = text.match(regex);
                return match ? match[1].trim() : "";
            };
            
            return {
                maker: extract("제조사", "모델명").replace(/[•\*]/g, '').trim(), 
                target: formatDetailContent(extract("주요 타겟 고객층", "핵심 셀링 포인트\\(USP\\)")),
                usp: formatDetailContent(extract("핵심 셀링 포인트\\(USP\\)", "가격대 및 포지셔닝")),
                price: formatDetailContent(extract("가격대 및 포지셔닝", "제품 인사이트 요약\\(1줄\\)")),
                insight: extract("제품 인사이트 요약\\(1줄\\)", null).replace(/[•\*]/g, '').trim()
            };
        }

        function getTierInfo(priceText, targetText) {
            const combined = (priceText + " " + targetText).toLowerCase();
            if (combined.includes('보급형') || combined.includes('초가성비') || combined.includes('엔트리') || combined.includes('저가') || combined.includes('budget')) {
                return { id: 'budget', class: 'tier-budget', label: '📱 보급형', rank: 3 };
            }
            if (combined.includes('중급') || combined.includes('메인스트림') || combined.includes('미드') || combined.includes('mid')) {
                return { id: 'midrange', class: 'tier-midrange', label: '⚖️ 중급형', rank: 2 };
            }
            if (combined.includes('플래그십') || combined.includes('프리미엄') || combined.includes('최고급') || combined.includes('flagship') || combined.includes('premium')) {
                return { id: 'flagship', class: 'tier-flagship', label: '🌟 플래그십', rank: 1 };
            }
            return { id: 'budget', class: 'tier-budget', label: '📱 보급형', rank: 3 };
        }

        window.switchTab = function(tabName) {
            currentTab = tabName;
            document.getElementById('tab-latest').classList.remove('active');
            document.getElementById('tab-history').classList.remove('active');
            document.getElementById('tab-' + tabName).classList.add('active');

            const filterMenu = document.getElementById('filter-menu');
            if (tabName === 'history') {
                filterMenu.style.display = 'flex';
                applyFilter('all'); 
            } else {
                filterMenu.style.display = 'none';
                renderCards(); 
            }
        };

        window.applyFilter = function(tierId) {
            currentFilter = tierId;
            const btns = document.querySelectorAll('.filter-btn');
            btns.forEach(btn => btn.classList.remove('active'));
            if(event && event.target.classList.contains('filter-btn')) event.target.classList.add('active');
            renderCards();
        };

        function renderCards() {
            const dashboard = document.getElementById('dashboard');
            dashboard.innerHTML = '';
            
            let displayList = [];

            if (currentTab === 'latest') {
                displayList = allProducts.filter(p => p.date === latestDate);
                displayList.sort((a, b) => a.tier.rank - b.tier.rank);
            } else {
                displayList = currentFilter === 'all' ? [...allProducts] : allProducts.filter(p => p.tier.id === currentFilter);
                displayList.sort((a, b) => b.date.localeCompare(a.date));
            }

            if (displayList.length === 0) {
                dashboard.innerHTML = '<div class="loading">해당 조건에 부합하는 분석 데이터가 없습니다.</div>';
                return;
            }

            displayList.forEach(product => {
                const card = document.createElement('div');
                card.className = 'device-card';
                card.innerHTML = `
                    <div class="card-left">
                        <div class="card-meta">
                            <span class="maker-badge"><i class="fas fa-industry"></i> ${product.maker}</span>
                            <span class="tier-badge ${product.tier.class}">${product.tier.label}</span>
                            <span class="date-badge"><i class="far fa-calendar-alt"></i> ${product.date}</span>
                        </div>
                        <h2 class="device-title">
                            ${product.modelName} 
                            <a href="${product.url}" target="_blank" title="출시 원문 기사 링크"><i class="fas fa-external-link-alt"></i></a>
                        </h2>
                        <div class="insight-box">
                            <strong><i class="fas fa-quote-left"></i> 기획자 시사점</strong>
                            <p>${product.insight}</p>
                        </div>
                    </div>
                    
                    <div class="card-right">
                        <div class="detail-section">
                            <strong><i class="fas fa-bullseye"></i> 주요 타겟 고객층</strong>
                            <div class="detail-content">${product.target}</div>
                        </div>
                        <div class="detail-section">
                            <strong><i class="fas fa-gem"></i> 핵심 셀링 포인트 (USP)</strong>
                            <div class="detail-content">${product.usp}</div>
                        </div>
                        <div class="detail-section">
                            <strong><i class="fas fa-tags"></i> 가격대 및 포지셔닝 전략</strong>
                            <div class="detail-content">${product.price}</div>
                        </div>
                    </div>
                `;
                dashboard.appendChild(card);
            });
        }

        fetch(URL)
            .then(res => res.text())
            .then(text => {
                const jsonStr = text.substring(47).slice(0, -2);
                const json = JSON.parse(jsonStr);
                const rows = json.table.rows;

                rows.forEach(row => {
                    if (!row.c[0] || !row.c[2] || !row.c[3]) return;
                    
                    let dateStr = row.c[0].f ? row.c[0].f : row.c[0].v.toString();

                    if (dateStr.includes('Date')) {
                        const numbers = dateStr.match(/\d+/g);
                        if (numbers && numbers.length >= 3) {
                            dateStr = `${numbers[0]}-${String(Number(numbers[1]) + 1).padStart(2, '0')}-${String(Number(numbers[2])).padStart(2, '0')}`;
                        }
                    }
                    dateStr = dateStr.trim();
                    
                    const modelName = row.c[2].v; 
                    const strategyText = row.c[3].v; 
                    const newsUrl = row.c[4] ? row.c[4].v : '#'; 

                    const details = parseStrategy(strategyText);
                    const tier = getTierInfo(details.price, details.target);

                    if (dateStr > latestDate) latestDate = dateStr;

                    allProducts.push({
                        date: dateStr,
                        modelName: modelName,
                        url: newsUrl,
                        ...details,
                        tier: tier
                    });
                });

                document.getElementById('update-date').innerText = latestDate;
                renderCards();
            })
            .catch(error => {
                console.error("데이터 동기화 실패:", error);
                document.getElementById('dashboard').innerHTML = '<div class="loading" style="color:#ef4444;">시트 데이터 로드에 실패했습니다. 공유 권한 설정을 확인해 주세요.</div>';
            });
    </script>
</body>
</html>
