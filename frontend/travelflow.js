function monthKey(offset) {
  const day = new Date();
  day.setDate(1);
  day.setMonth(day.getMonth() + offset);
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}`;
}

function monthLabel(key) {
  const [year, month] = key.split('-').map(Number);
  return `${year} 年 ${month} 月`;
}

const MONTH_CURRENT = monthKey(0);
const MONTH_NEXT = monthKey(1);

const hotels = [
  { id: 'h-1', name: '海湾假日酒店', city: '上海', price: 699, rating: 4.6, month: MONTH_CURRENT, weekend: true },
  { id: 'h-2', name: '星河商务酒店', city: '上海', price: 859, rating: 4.7, month: MONTH_CURRENT, weekend: true },
  { id: 'h-3', name: '梧桐精品酒店', city: '杭州', price: 628, rating: 4.8, month: MONTH_CURRENT, weekend: true },
  { id: 'h-4', name: '云端轻居酒店', city: '苏州', price: 559, rating: 4.5, month: MONTH_CURRENT, weekend: true },
  { id: 'h-5', name: '城北青年旅舍', city: '南京', price: 399, rating: 4.2, month: MONTH_CURRENT, weekend: true },
  { id: 'h-6', name: '湖畔度假酒店', city: '杭州', price: 788, rating: 4.9, month: MONTH_CURRENT, weekend: true },
  { id: 'h-7', name: '城市漫步酒店', city: '上海', price: 745, rating: 4.4, month: MONTH_CURRENT, weekend: false },
  { id: 'h-8', name: '秋枫花园酒店', city: '苏州', price: 512, rating: 4.6, month: MONTH_CURRENT, weekend: true },
  { id: 'h-9', name: '逐浪海景酒店', city: '青岛', price: 920, rating: 4.8, month: MONTH_NEXT, weekend: true },
  { id: 'h-10', name: '南湾艺术酒店', city: '深圳', price: 680, rating: 4.7, month: MONTH_NEXT, weekend: true }
];

const state = { month: MONTH_CURRENT, weekendOnly: true, maxPrice: 800, minRating: 4.5 };
const list = document.querySelector('#hotels');
const count = document.querySelector('#result-count');
const comparison = document.querySelector('#comparison');
const comparisonContent = document.querySelector('#comparison-content');
const monthFilter = document.querySelector('#month-filter');
monthFilter.innerHTML = `<option value="${MONTH_CURRENT}" selected>${monthLabel(MONTH_CURRENT)}</option><option value="${MONTH_NEXT}">${monthLabel(MONTH_NEXT)}</option>`;

function visibleHotels() {
  return hotels
    .filter((hotel) => hotel.month === state.month)
    .filter((hotel) => !state.weekendOnly || hotel.weekend)
    .filter((hotel) => !state.maxPrice || hotel.price <= state.maxPrice)
    .filter((hotel) => !state.minRating || hotel.rating >= state.minRating)
    .sort((a, b) => b.rating - a.rating || a.price - b.price);
}

function renderComparison(items) {
  if (items.length < 2) {
    comparison.hidden = true;
    return;
  }
  const [first, second] = items;
  const recommended = first.rating > second.rating || (first.rating === second.rating && first.price <= second.price) ? first : second;
  comparison.hidden = false;
  comparisonContent.innerHTML = `
    <p>候选 1：<b>${first.name}</b> · ¥${first.price} · ${first.rating} 分</p>
    <p>候选 2：<b>${second.name}</b> · ¥${second.price} · ${second.rating} 分</p>
    <p data-field="recommendation">推荐：<b>${recommended.name}</b>，综合评分与价格更优。</p>
  `;
}

function render() {
  const items = visibleHotels();
  count.textContent = `找到 ${items.length} 家符合条件的酒店`;
  list.innerHTML = items.map((hotel) => `
    <article class="hotel-card" data-id="${hotel.id}" data-price="${hotel.price}" data-rating="${hotel.rating}" data-weekend="${hotel.weekend}">
      <p class="tag">${hotel.city} · ${hotel.month} 周末可订</p>
      <h2 data-field="name">${hotel.name}</h2>
      <p>评分 <b data-field="rating">${hotel.rating}</b> / 5.0</p>
      <strong data-field="price">¥${hotel.price}</strong>
      <button class="compare-button" data-hotel-id="${hotel.id}">加入比较</button>
    </article>
  `).join('') || '<p class="empty">没有酒店符合当前条件。</p>';
  renderComparison(items.slice(0, 2));
}

function updateFilters() {
  state.month = document.querySelector('#month-filter').value;
  state.weekendOnly = document.querySelector('#weekend-filter').value === 'weekend';
  state.maxPrice = Number(document.querySelector('#price-filter').value) || null;
  state.minRating = Number(document.querySelector('#rating-filter').value) || null;
  render();
}

document.querySelector('#search-button').addEventListener('click', updateFilters);
['#month-filter', '#weekend-filter', '#price-filter', '#rating-filter'].forEach((selector) => {
  document.querySelector(selector).addEventListener('change', updateFilters);
});

render();
